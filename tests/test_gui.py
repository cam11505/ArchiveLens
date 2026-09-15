import hashlib
from threading import Event
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest

from archivelens.diagnostic_fixtures import write_pdf_fixture
from archivelens.image.trim import TrimMargins
from archivelens.image.worker import LoadResult
from archivelens.ui.main_window import MainWindow


@pytest.fixture
def archive(tmp_path, image_bytes):
    path = tmp_path / "旅行照片.cbz"
    with ZipFile(path, "w") as target:
        for name, color in [("10.png", "blue"), ("2.png", "green"), ("1.png", "red")]:
            target.writestr(name, image_bytes(color))
        target.writestr("README.txt", "not an image")
    return path


@pytest.fixture
def window(qapp, wait_until, monkeypatch):
    errors = []
    widget = MainWindow()
    monkeypatch.setattr(widget, "_show_error", errors.append)
    widget.test_errors = errors
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    wait_until(lambda: not widget.worker.isRunning())
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


def test_open_navigate_fit_and_no_extraction(window, archive, wait_until):
    before = hashlib.sha256(archive.read_bytes()).digest()
    files_before = set(archive.parent.iterdir())
    window.open_archive(archive)
    wait_until(lambda: not window.loading)
    assert [entry.name for entry in window.entries] == ["1.png", "2.png", "10.png"]
    assert window.counter.text() == "1 / 3"
    assert window.stack.currentWidget() is window.viewer
    assert window.viewer._item.pixmap().toImage().pixelColor(0, 0).name() == "#ff0000"
    assert not window.previous_action.isEnabled()
    window.next_action.trigger()
    wait_until(lambda: not window.loading)
    assert window.counter.text() == "2 / 3"
    assert "2.png" in window.windowTitle()
    assert window.viewer._item.pixmap().toImage().pixelColor(0, 0).name() == "#008000"
    window.previous_action.trigger()
    wait_until(lambda: not window.loading)
    window.navigate(-1)
    assert window.current_index == 0
    window.go_to(99)
    wait_until(lambda: not window.loading)
    assert window.current_index == 2
    assert not window.next_action.isEnabled()
    transform = window.viewer.transform()
    assert transform.m11() == pytest.approx(transform.m22())
    assert not window.test_errors
    assert hashlib.sha256(archive.read_bytes()).digest() == before
    assert set(archive.parent.iterdir()) == files_before


@pytest.mark.parametrize(
    "key,index",
    [
        (Qt.Key.Key_Right, 1),
        (Qt.Key.Key_PageDown, 1),
        (Qt.Key.Key_Space, 1),
        (Qt.Key.Key_End, 2),
    ],
)
def test_keyboard_navigation(window, archive, wait_until, key, index):
    window.open_archive(archive)
    wait_until(lambda: not window.loading)
    window.activateWindow()
    QTest.keyClick(window, key)
    wait_until(lambda: not window.loading)
    assert window.current_index == index
    QTest.keyClick(window, Qt.Key.Key_Home)
    wait_until(lambda: not window.loading)
    assert window.current_index == 0


def test_drag_drop(window, archive, wait_until, qapp):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(archive))])
    drag = QDragEnterEvent(
        QPoint(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(window, drag)
    assert drag.isAccepted()
    drop = QDropEvent(
        QPointF(20, 20),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(window, drop)
    assert drop.isAccepted()
    wait_until(lambda: not window.loading)
    assert window.counter.text() == "1 / 3"


def test_pdf_reader_navigation_spread_and_resume(window, tmp_path, wait_until):
    source = tmp_path / "manual.pdf"
    write_pdf_fixture(source, pages=5)
    before = hashlib.sha256(source.read_bytes()).digest()
    window.open_content(source)
    wait_until(lambda: not window.loading)
    assert len(window.entries) == 5
    assert window.entries[0].extension == ".pdf"
    assert window.viewer.image_size.width() > 0
    window.go_to(2)
    wait_until(lambda: not window.loading)
    window.set_reading(double=True)
    wait_until(lambda: not window.loading)
    assert window.counter.text() == "2–3 / 5"
    window.open_content(source)
    wait_until(lambda: not window.loading)
    assert window.current_index == 1
    assert window.double_page
    assert hashlib.sha256(source.read_bytes()).digest() == before


def test_pdf_viewport_resize_requests_fresh_bounded_render(window, tmp_path, wait_until, qapp):
    source = tmp_path / "resize.pdf"
    write_pdf_fixture(source)
    window.open_content(source)
    wait_until(lambda: not window.loading)
    window._pdf_resize_timer.stop()
    old_token = window._token
    old_size = window.viewer.image_size
    window.resize(700, 500)
    qapp.processEvents()
    wait_until(lambda: window._token > old_token and not window.loading)
    assert window.viewer.image_size != old_size
    assert window.viewer.image_size.width() * window.viewer.image_size.height() <= 16_000_000


def test_fit_and_manual_trim_actions_are_persisted_without_source_changes(
    window, archive, wait_until
):
    before = hashlib.sha256(archive.read_bytes()).digest()
    window.open_archive(archive)
    wait_until(lambda: not window.loading)
    original = window.viewer.image_size
    window.fit_width_current()
    assert window.view_mode == "fit_width"
    assert window.fit_width_action.isChecked()
    window.set_trim_mode("manual", TrimMargins(10, 0, 20, 0))
    wait_until(lambda: not window.loading)
    assert window.viewer.image_size.width() < original.width()
    record = window.reading_store.get(window.source_identity)
    assert record is not None
    assert record.state.fit_mode == "fit_width"
    assert record.state.trim_mode == "manual"
    assert record.state.trim_margins == (10, 0, 20, 0)
    assert hashlib.sha256(archive.read_bytes()).digest() == before


def test_rapid_navigation_and_stale_result(window, archive, wait_until):
    window.open_archive(archive)
    wait_until(lambda: not window.loading)
    stale_token = window._token
    window.navigate(1)
    window.navigate(1)
    window.navigate(-1)
    window._on_result(LoadResult(stale_token, (), 0, error="stale failure"))
    wait_until(lambda: not window.loading)
    assert window.current_index == 1
    assert window.counter.text() == "2 / 3"
    assert not window.test_errors
    assert window.viewer._item.pixmap().toImage().pixelColor(0, 0).name() == "#008000"


def test_empty_bad_archive_and_corrupt_image_recovery(window, archive, tmp_path, wait_until):
    empty = tmp_path / "empty.zip"
    with ZipFile(empty, "w"):
        pass
    window.open_archive(empty)
    wait_until(lambda: not window.loading)
    assert "沒有找到" in window.test_errors[-1]
    assert window.counter.text() == "0 / 0"
    window.open_archive(tmp_path / "missing.zip")
    wait_until(lambda: not window.loading)
    assert "無法開啟" in window.test_errors[-1]
    broken = tmp_path / "broken.zip"
    with ZipFile(broken, "w") as target, ZipFile(archive) as source:
        target.writestr("1.png", b"broken")
        target.writestr("2.png", source.read("2.png"))
    window.open_archive(broken)
    wait_until(lambda: not window.loading)
    assert window.counter.text() == "1 / 2"
    assert window.next_action.isEnabled()
    window.navigate(1)
    wait_until(lambda: not window.loading)
    assert window.stack.currentWidget() is window.viewer
    assert window.counter.text() == "2 / 2"


def test_switch_archive_during_decode(
    window, archive, tmp_path, image_bytes, wait_until, monkeypatch
):
    import archivelens.image.worker as worker_module

    entered = Event()
    release = Event()
    original = worker_module.decode_image

    def delayed(data, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(data, *args, **kwargs)

    other = tmp_path / "other.zip"
    with ZipFile(other, "w") as target:
        target.writestr("only.png", image_bytes("yellow"))
    monkeypatch.setattr(worker_module, "decode_image", delayed)
    window.open_archive(archive)
    try:
        wait_until(entered.is_set)
        window.open_archive(other)
    finally:
        release.set()
    wait_until(lambda: not window.loading)
    assert window.counter.text() == "1 / 1"
    assert window.entries[0].name == "only.png"
    assert window.viewer._item.pixmap().toImage().pixelColor(0, 0).name() == "#ffff00"


def test_close_while_decode_is_active(window, archive, wait_until, monkeypatch):
    import archivelens.image.worker as worker_module

    entered = Event()
    release = Event()
    original = worker_module.decode_image

    def delayed(data, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(data, *args, **kwargs)

    monkeypatch.setattr(worker_module, "decode_image", delayed)
    window.open_archive(archive)
    try:
        wait_until(entered.is_set)
        window.close()
        assert window._closing
        assert window.worker.isRunning()
    finally:
        release.set()
    wait_until(lambda: not window.worker.isRunning())
    assert not window.isVisible()


def test_viewer_shortcuts_and_fullscreen_restore(window, archive, wait_until, qapp):
    window.open_archive(archive)
    wait_until(lambda: not window.loading)
    window.activateWindow()
    QTest.keyClick(window, Qt.Key.Key_1)
    assert window.viewer.zoom_factor == pytest.approx(1)
    QTest.keyClick(window, Qt.Key.Key_Equal)
    assert window.viewer.zoom_factor > 1
    QTest.keyClick(window, Qt.Key.Key_Minus)
    assert window.viewer.zoom_factor == pytest.approx(1)
    QTest.keyClick(window, Qt.Key.Key_R)
    assert window.viewer.rotation == 90
    QTest.keyClick(window, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier)
    assert window.viewer.rotation == 0
    QTest.keyClick(window, Qt.Key.Key_0)
    assert window.viewer.fit_mode
    QTest.keyClick(window, Qt.Key.Key_F11)
    qapp.processEvents()
    assert window.isFullScreen()
    assert not window.toolbar.isVisible()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not window.isFullScreen()
    assert window.toolbar.isVisible()
    window.showMaximized()
    qapp.processEvents()
    window.toggle_fullscreen()
    qapp.processEvents()
    window.exit_fullscreen()
    qapp.processEvents()
    assert window.isMaximized()
