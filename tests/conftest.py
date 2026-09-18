import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QImage, QImageReader  # noqa: E402

from archivelens.application import ArchiveLensApplication  # noqa: E402
from archivelens.config import IMAGE_ALLOCATION_LIMIT_MB  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = ArchiveLensApplication.instance() or ArchiveLensApplication([])
    app.setQuitOnLastWindowClosed(False)
    QImageReader.setAllocationLimit(IMAGE_ALLOCATION_LIMIT_MB)
    yield app


@pytest.fixture
def image_bytes(qapp):
    def create(color="red", fmt="PNG", width=32, height=24):
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert image.save(buffer, fmt)
        return bytes(data)

    return create


@pytest.fixture
def wait_until(qapp):
    def wait(predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while not predicate():
            qapp.processEvents()
            if time.monotonic() > deadline:
                pytest.fail("Timed out waiting for Qt background work")
            time.sleep(0.005)
        qapp.processEvents()

    return wait


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    import archivelens.ui.main_window as main_window
    from archivelens.reading_state import ReadingStateStore

    monkeypatch.setattr(
        main_window,
        "create_settings",
        lambda: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(
        main_window,
        "create_reading_state_store",
        lambda settings=None: ReadingStateStore(
            tmp_path.parent / f"{tmp_path.name}-appdata" / "reading-state.json"
        ),
    )
