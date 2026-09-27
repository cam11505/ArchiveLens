"""Issue #48 qualification; synthetic display/input events are not hardware QA."""

import hashlib
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent

from archivelens import config
from archivelens.content.base import (
    ContentOpenOptions,
    PageLoadRequest,
    SourceType,
    source_identity_for_path,
)
from archivelens.content.folder_provider import FolderContentProvider
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.diagnostic_fixtures import write_pdf_fixture
from archivelens.errors import ContentAccessError
from archivelens.image.media import PageMedia
from archivelens.image.worker import ImageWorker, LoadRequest
from archivelens.reading_state import ReaderState, ReadingStateStore
from archivelens.ui.image_viewer import ImageViewer
from archivelens.ui.main_window import MainWindow


@pytest.fixture
def viewer(qapp):
    widget = ImageViewer()
    widget.resize(640, 480)
    widget.show()
    image = QImage(1200, 800, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    widget.set_image(image)
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


def test_real_qt_scale_actual_size_and_resize(viewer, qapp):
    expected_dpr = os.environ.get("ARCHIVELENS_EXPECTED_DPR")
    if expected_dpr:
        assert viewer.devicePixelRatioF() == pytest.approx(float(expected_dpr))
    viewer.actual_size()
    assert viewer.transform().m11() * viewer.devicePixelRatioF() == pytest.approx(1)
    viewer.resize(440, 320)
    qapp.processEvents()
    assert viewer.view_mode == "actual"
    assert viewer.transform().m11() * viewer.devicePixelRatioF() == pytest.approx(1)


@pytest.mark.parametrize("mode", ["fit_page", "fit_width", "fit_height", "actual", "custom"])
@pytest.mark.parametrize("double", [False, True])
def test_synthetic_display_moves_preserve_mode_rotation_and_spread(
    viewer, qapp, monkeypatch, mode, double
):
    if double:
        image = viewer._item.pixmap().toImage()
        viewer.set_pages((PageMedia(0, image), PageMedia(1, image)), rtl=True)
    viewer.rotate_image(90)
    if mode == "actual":
        viewer.actual_size()
    elif mode == "custom":
        viewer.set_zoom(1.75)
    else:
        getattr(
            viewer,
            {"fit_page": "fit_image", "fit_width": "fit_width", "fit_height": "fit_height"}[mode],
        )()
    bounds = viewer.sceneRect()
    for dpr in (1.0, 2.0, 1.5, 1.0):
        monkeypatch.setattr(viewer, "devicePixelRatioF", lambda dpr=dpr: dpr)
        qapp.sendEvent(viewer, QEvent(QEvent.Type.DevicePixelRatioChange))
        assert viewer.view_mode == mode
        assert viewer.rotation == 90
        assert viewer.sceneRect() == bounds
        physical_scale = viewer.transform().m11() * dpr
        if mode in {"actual", "custom"}:
            assert physical_scale == pytest.approx(1 if mode == "actual" else 1.75)
        else:
            width = (viewer.viewport().width() - 4) / bounds.width()
            height = (viewer.viewport().height() - 4) / bounds.height()
            expected = {"fit_page": min(width, height), "fit_width": width, "fit_height": height}[
                mode
            ]
            assert viewer.transform().m11() == pytest.approx(expected)


def test_trackpad_phases_do_not_double_zoom_or_change_page(viewer, qapp):
    viewer.actual_size()
    signals = []
    viewer.view_mode_changed.connect(lambda *args: signals.append(args))
    for phase, pixel, angle in (
        (Qt.ScrollPhase.ScrollBegin, 0, 0),
        (Qt.ScrollPhase.ScrollUpdate, 12, 120),
        (Qt.ScrollPhase.ScrollEnd, 0, 0),
    ):
        event = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, pixel),
            QPoint(0, angle),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.ControlModifier,
            phase,
            True,
        )
        qapp.sendEvent(viewer.viewport(), event)
        assert event.isAccepted()
    assert len(signals) == 1
    assert viewer.zoom_factor == pytest.approx(config.ZOOM_STEP)
    factor = viewer.zoom_factor
    for modifiers in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier):
        event = QWheelEvent(
            QPointF(100, 100),
            QPointF(100, 100),
            QPoint(0, -24),
            QPoint(),
            Qt.MouseButton.NoButton,
            modifiers,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        qapp.sendEvent(viewer.viewport(), event)
        if modifiers == Qt.KeyboardModifier.NoModifier:
            assert viewer.zoom_factor == factor
        else:
            assert viewer.zoom_factor == pytest.approx(factor * config.ZOOM_STEP ** (-24 / 120))


def test_pdf_cache_render_scale_round_trip_and_thumbnails(tmp_path, qapp, wait_until, monkeypatch):
    source = tmp_path / "Retina 文件.pdf"
    write_pdf_fixture(source, pages=2)
    before = hashlib.sha256(source.read_bytes()).digest()
    worker = ImageWorker()
    results = []
    renders = []
    original = PdfContentProvider.load_page

    def tracked(provider, page, request):
        renders.append(request.render_size)
        return original(provider, page, request)

    monkeypatch.setattr(PdfContentProvider, "load_page", tracked)
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        for token, size in enumerate(((400, 300), (800, 600), (400, 300)), 1):
            worker.submit(LoadRequest(token, 1, source, 0, render_size=size))
            wait_until(lambda token=token: len(results) == token)
            result = results[-1]
            assert not result.error
            image = result.image
            assert image.width() <= size[0] and image.height() <= size[1]
            assert image.width() * image.height() <= config.MAX_PDF_RENDER_PIXELS
            assert not image.hasAlphaChannel()
            assert image.pixelColor(0, 0) == QColor("white")
        assert renders == [(400, 300), (800, 600), (400, 300)]
        provider = PdfContentProvider()
        provider.open(source)
        try:
            thumbnail = provider.load_page(
                provider.list_pages()[0], PageLoadRequest(thumbnail_size=144)
            ).image
            assert max(thumbnail.width(), thumbnail.height()) <= config.THUMBNAIL_SIZE
        finally:
            provider.close()
        assert hashlib.sha256(source.read_bytes()).digest() == before
    finally:
        worker.stop()
        assert worker.wait(5000)


def test_unicode_nested_path_alias_resume_and_missing_source(tmp_path, image_bytes):
    root = tmp_path
    for index in range(7):
        root /= f"章節{index}-長路徑"
    root.mkdir(parents=True)
    source = root / "漫畫-é.PNG"
    source.write_bytes(image_bytes())
    provider = FolderContentProvider()
    provider.open(root)
    page = provider.list_pages()[0]
    assert page.name == source.name
    assert provider.load_page(page, PageLoadRequest()).encoded == image_bytes()
    first = source_identity_for_path(root, SourceType.FOLDER)
    alias = root / ".." / root.name
    assert source_identity_for_path(alias, SourceType.FOLDER) == first
    store = ReadingStateStore(tmp_path / "history.json")
    store.update(first, root.name, ReaderState(page_count=1, fit_mode="actual"))
    assert store.get(source_identity_for_path(alias, SourceType.FOLDER)).state.fit_mode == "actual"
    source.unlink()
    with pytest.raises(ContentAccessError):
        provider.load_page(page, PageLoadRequest())
    with pytest.raises(ContentAccessError):
        provider.open(tmp_path / "unmounted-volume")


def test_symlink_loop_identity_fails_with_domain_error(tmp_path):
    loop = tmp_path / "loop.cbz"
    try:
        loop.symlink_to(loop.name)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(ContentAccessError):
        source_identity_for_path(loop, SourceType.ARCHIVE)


def test_recursive_symlink_loop_is_not_followed(tmp_path, image_bytes):
    root = tmp_path / "folder"
    root.mkdir()
    (root / "1.png").write_bytes(image_bytes())
    try:
        (root / "loop").symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    provider = FolderContentProvider()
    provider.open(root, options=ContentOpenOptions(recursive=True))
    assert [page.name for page in provider.list_pages()] == ["1.png"]


def test_identity_failure_preserves_current_reader(tmp_path, qapp, monkeypatch):
    window = MainWindow()
    errors = []
    monkeypatch.setattr(window, "_show_error", errors.append)
    monkeypatch.setattr(
        "archivelens.ui.main_window.source_identity_for_path",
        lambda *args: (_ for _ in ()).throw(ContentAccessError()),
    )
    try:
        generation = window._generation
        window.open_content(tmp_path / "loop.cbz")
        assert errors
        assert window._generation == generation
        assert window.source_path is None
        window.open_content(tmp_path / "unmounted-folder")
        assert len(errors) == 2
    finally:
        window.close()


def test_pdf_display_scale_rerenders_without_losing_reader_state(
    tmp_path, qapp, wait_until, monkeypatch
):
    source = tmp_path / "display-move.pdf"
    write_pdf_fixture(source, pages=3)
    window = MainWindow()
    window.show()
    try:
        window.open_content(source)
        wait_until(lambda: not window.loading)
        window.go_to(1)
        wait_until(lambda: not window.loading)
        window.viewer.actual_size()
        window.page_rotation = 90
        window.viewer.rotate_image(90)
        window._pdf_resize_timer.stop()
        token = window._token
        monkeypatch.setattr(window.viewer, "devicePixelRatioF", lambda: 2.0)
        qapp.sendEvent(window.viewer, QEvent(QEvent.Type.DevicePixelRatioChange))
        wait_until(lambda: window._token > token and not window.loading)
        assert window.current_index == 1
        assert window.view_mode == "actual"
        assert window.viewer.view_mode == "actual"
        assert window.page_rotation == window.viewer.rotation == 90
        assert (
            window.viewer.image_size.width() * window.viewer.image_size.height()
            <= config.MAX_PDF_RENDER_PIXELS
        )
        assert window.worker.isRunning()
    finally:
        window.close()


def test_actual_mounted_volume_case_and_identity(image_bytes):
    volume = os.environ.get("ARCHIVELENS_TEST_VOLUME")
    if not volume:
        pytest.skip("requires the dedicated mounted-volume qualification lane")
    root = Path(volume)
    upper = root / "Case.PNG"
    lower = root / "case.PNG"
    upper.write_bytes(image_bytes("red"))
    case_sensitive = os.environ["ARCHIVELENS_CASE_SENSITIVE"] == "1"
    assert lower.exists() is not case_sensitive
    first = source_identity_for_path(upper, SourceType.ARCHIVE)
    if case_sensitive:
        lower.write_bytes(image_bytes("blue"))
        assert source_identity_for_path(lower, SourceType.ARCHIVE).storage_key != first.storage_key
    provider = FolderContentProvider()
    provider.open(root)
    assert len(provider.list_pages()) == (2 if case_sensitive else 1)
