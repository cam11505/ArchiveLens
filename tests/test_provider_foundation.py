import logging
import pickle
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.capabilities import ArchiveCapabilities, RandomAccess
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.archive.zip_provider import ZipArchiveProvider
from archivelens.errors import (
    ArchiveLensError,
    BadPasswordError,
    CorruptedArchiveError,
    PasswordRequiredError,
    ProviderUnavailableError,
    ResourceLimitError,
    UnsupportedArchiveError,
    UnsupportedEncryptionError,
)
from archivelens.image.worker import ImageWorker, LoadRequest


class FakeProvider(ArchiveProvider):
    capabilities = ArchiveCapabilities("Test", frozenset({".test"}))

    def __init__(self):
        self.credentials = None

    @staticmethod
    def supports(path):
        return Path(path).suffix.lower() == ".test"

    def open(self, path, *, credentials=None):
        self.credentials = credentials

    def close(self):
        self.credentials = None

    def list_entries(self):
        return [ArchiveEntry(f"{i}.png", f"{i}.png", ".png", 1, 1, i, True) for i in range(4)]

    def read_entry(self, entry):
        raise NotImplementedError


def registry_for(provider):
    registry = ArchiveProviderRegistry()
    registry.register(provider)
    return registry


def test_registry_selection_and_availability():
    for path in ("book.zip", "book.CBZ", "book.ZiP"):
        assert isinstance(DEFAULT_REGISTRY.create(path), ZipArchiveProvider)
    assert DEFAULT_REGISTRY.create("a.zip") is not DEFAULT_REGISTRY.create("a.zip")
    for path in ("book.txt",):
        with pytest.raises(UnsupportedArchiveError):
            DEFAULT_REGISTRY.create(path)
    registry = registry_for(FakeProvider)
    assert registry.supports("book.TEST")
    assert "*.TEST" in registry.file_dialog_filter()
    with pytest.raises(ValueError):
        registry.register(FakeProvider)

    class Unavailable(FakeProvider):
        capabilities = replace(FakeProvider.capabilities, available=False)

    registry = registry_for(Unavailable)
    assert not registry.supports("book.test")
    with pytest.raises(ProviderUnavailableError):
        registry.create("book.test")

    class MissingDependency(FakeProvider):
        def __init__(self):
            raise ImportError("optional backend absent")

    with pytest.raises(ProviderUnavailableError):
        registry_for(MissingDependency).create("book.test")


def test_credentials_redaction_and_clearing():
    credential = ArchiveCredentials(b"secret-password")
    buffer = credential._password
    request = LoadRequest(1, 1, Path("book.test"), 0, credential)
    assert "secret-password" not in repr(request) + repr(credential) + str(credential)
    with pytest.raises(TypeError):
        pickle.dumps(credential)
    credential.clear()
    assert credential.password_bytes() is None
    assert buffer == bytearray(len(b"secret-password"))
    with ArchiveCredentials(b"") as empty:
        assert empty.password_bytes() == b""
    assert empty.password_bytes() is None


@pytest.mark.parametrize(
    "failure",
    [
        PasswordRequiredError,
        BadPasswordError,
        UnsupportedEncryptionError,
        CorruptedArchiveError,
        ResourceLimitError,
        ProviderUnavailableError,
        RuntimeError,
    ],
)
@pytest.mark.parametrize("stage", ["open", "read"])
def test_structured_errors_are_sanitized(failure, stage, wait_until, caplog):
    class Failing(FakeProvider):
        def open(self, path, *, credentials=None):
            if stage == "open":
                raise failure("secret-password") from ValueError("secret-password")

        def read_entry(self, entry):
            raise failure("secret-password") from ValueError("secret-password")

        def close(self):
            raise RuntimeError("secret-password")

    caplog.set_level(logging.INFO, logger="archivelens.image.worker")
    worker = ImageWorker(registry=registry_for(Failing))
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    credential = ArchiveCredentials(b"secret-password")
    try:
        worker.submit(LoadRequest(1, 1, Path("book.test"), 0, credential))
        wait_until(lambda: bool(results))
        expected = ArchiveLensError if failure is RuntimeError else failure
        assert results[0].error_type is expected
        assert results[0].error == expected.default_message
        assert "secret-password" not in repr(results) + caplog.text
        assert all(record.exc_info is None for record in caplog.records)
    finally:
        worker.stop()
        assert worker.wait(5000)
    assert credential.password_bytes() is None


def test_pending_credentials_and_shutdown(qapp):
    worker = ImageWorker()
    first, second = ArchiveCredentials(b"first"), ArchiveCredentials(b"second")
    worker.submit(LoadRequest(1, 1, Path("a.zip"), 0, first))
    worker.submit(LoadRequest(2, 1, Path("a.zip"), 1))
    assert first.password_bytes() == b"first"
    worker.submit(LoadRequest(3, 2, Path("b.zip"), 0, second))
    assert first.password_bytes() is None
    worker.stop()
    assert second.password_bytes() is None
    rejected = ArchiveCredentials(b"rejected")
    worker.submit(LoadRequest(4, 3, Path("c.zip"), 0, rejected))
    assert rejected.password_bytes() is None


def test_active_switch_and_credential_retry(image_bytes, wait_until):
    entered, release = Event(), Event()
    payload = image_bytes()
    opened, reads, instances = [], [], []

    class Reader(FakeProvider):
        def open(self, path, *, credentials=None):
            super().open(path, credentials=credentials)
            instances.append(self)
            opened.append((path, credentials.password_bytes()))

        def read_entry(self, entry):
            reads.append(entry.index)
            if len(reads) == 1:
                entered.set()
                assert release.wait(5)
            return payload

    worker = ImageWorker(registry=registry_for(Reader))
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    first, second, retry = [ArchiveCredentials(p) for p in (b"first", b"second", b"retry")]
    try:
        worker.submit(LoadRequest(1, 1, Path("a.test"), 0, first))
        wait_until(entered.is_set)
        worker.submit(LoadRequest(2, 1, Path("b.test"), 0, second))
        assert first.password_bytes() is None
        release.set()
        wait_until(lambda: bool(results))
        assert [r.token for r in results] == [2]
        worker.submit(LoadRequest(3, 1, Path("b.test"), 0, retry))
        wait_until(lambda: len(results) == 2)
        assert second.password_bytes() is None
        assert opened == [
            (Path("a.test"), b"first"),
            (Path("b.test"), b"second"),
            (Path("b.test"), b"retry"),
        ]
        assert reads == [0, 0, 0]  # Credential replacement must invalidate cached pixels.
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)
    assert retry.password_bytes() is None
    assert all(instance.credentials is None for instance in instances)


@pytest.mark.parametrize(
    "access,solid,expected",
    [
        (RandomAccess.EFFICIENT, False, [0, 1, 2]),
        (RandomAccess.EFFICIENT, True, [0]),
        (RandomAccess.EXPENSIVE, False, [0]),
        (RandomAccess.UNKNOWN, None, [0]),
    ],
)
def test_runtime_capabilities_control_prefetch(
    access, solid, expected, image_bytes, wait_until, monkeypatch
):
    payload, reads, finished = image_bytes(), [], Event()

    class Reader(FakeProvider):
        def open(self, path, *, credentials=None):
            self.capabilities = replace(self.capabilities, random_access=access, solid=solid)

        def read_entry(self, entry):
            reads.append(entry.index)
            return payload

    original = ImageWorker._prefetch

    def prefetch(*args):
        original(*args)
        finished.set()

    monkeypatch.setattr(ImageWorker, "_prefetch", prefetch)
    worker = ImageWorker(registry=registry_for(Reader))
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, Path("a.test"), 0))
        wait_until(finished.is_set)
        assert reads == expected
    finally:
        worker.stop()
        assert worker.wait(5000)


def test_ui_uses_injected_registry(qapp):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent

    from archivelens.ui.main_window import MainWindow

    registry = registry_for(FakeProvider)
    window = MainWindow(registry=registry)
    try:
        assert window.worker.registry is registry
        assert "TEST" in window.message.text()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(Path("book.test").absolute()))])
        event = QDragEnterEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        assert window._drop_path(event.mimeData()).suffix == ".test"
    finally:
        window.close()


def test_cancel_closes_idle_backend_credentials(image_bytes, wait_until):
    payload = image_bytes()
    closed = Event()

    class Reader(FakeProvider):
        def read_entry(self, entry):
            return payload

        def close(self):
            super().close()
            closed.set()

    worker = ImageWorker(registry=registry_for(Reader))
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    credentials = ArchiveCredentials(b"transient")
    try:
        worker.submit(LoadRequest(1, 1, Path("a.test"), 0, credentials))
        wait_until(lambda: bool(results))
        worker.cancel_session()
        wait_until(closed.is_set)
        assert credentials.password_bytes() is None
        worker.submit(LoadRequest(2, 1, Path("a.test"), 0))
        wait_until(lambda: len(results) == 2)
        assert results[-1].error_type is None
    finally:
        worker.stop()
        assert worker.wait(5000)
