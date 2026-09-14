from zipfile import ZipFile

import py7zr
import pytest

from archivelens import config
from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.archive.rar_provider import RarArchiveProvider
from archivelens.diagnostic_fixtures import animated_gif
from archivelens.errors import ResourceLimitError
from archivelens.image.worker import ImageWorker, LoadRequest


@pytest.mark.parametrize("suffix", [".zip", ".7z"])
def test_catalog_entry_limit(tmp_path, monkeypatch, suffix):
    path = tmp_path / ("many" + suffix)
    if suffix == ".zip":
        with ZipFile(path, "w") as archive:
            archive.writestr("1.png", b"a")
            archive.writestr("2.png", b"b")
    else:
        with py7zr.SevenZipFile(path, "w") as archive:
            archive.writestr(b"a", "1.png")
            archive.writestr(b"b", "2.png")
    monkeypatch.setattr(config, "MAX_ARCHIVE_ENTRIES", 1)
    with DEFAULT_REGISTRY.create(path) as provider, pytest.raises(ResourceLimitError):
        provider.open(path)


def test_animation_limit(tmp_path, monkeypatch, wait_until):
    import archivelens.image.worker as module

    path = tmp_path / "animation.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("1.gif", animated_gif())
    monkeypatch.setattr(module, "MAX_ANIMATION_BYTES", 1)
    results = []
    worker = ImageWorker()
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, path, 0))
        wait_until(lambda: bool(results))
        assert results[0].error_type is ResourceLimitError
        assert not results[0].pages
    finally:
        worker.stop()
        assert worker.wait(5000)


def test_rar_catalog_limit(monkeypatch):
    from pathlib import Path

    if not RarArchiveProvider.capabilities.available:
        pytest.skip("Windows backend only")
    monkeypatch.setattr(config, "MAX_ARCHIVE_ENTRIES", 1)
    with RarArchiveProvider() as provider, pytest.raises(ResourceLimitError):
        provider.open(Path(__file__).parent / "fixtures/rar/rar5-solid.rar")
