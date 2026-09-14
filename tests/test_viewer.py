import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtTest import QTest

from archivelens.config import MAX_ZOOM, MIN_ZOOM
from archivelens.ui.image_viewer import ImageViewer


@pytest.fixture
def viewer(qapp):
    widget = ImageViewer()
    widget.resize(480, 320)
    image = QImage(1600, 900, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    widget.show()
    widget.set_image(image)
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


def test_fit_resize_rotation_and_aspect_ratio(viewer, qapp):
    assert viewer.fit_mode
    before = viewer.zoom_factor
    viewer.resize(240, 160)
    qapp.processEvents()
    assert viewer.zoom_factor < before
    viewer.rotate_image(90)
    assert viewer.sceneRect().width() == pytest.approx(900)
    assert viewer.sceneRect().height() == pytest.approx(1600)
    assert viewer.transform().m11() == pytest.approx(viewer.transform().m22())
    viewer.rotate_image(-90)
    assert viewer.rotation == 0
    viewer.rotate_image(-90)
    assert viewer.rotation == 270


def test_actual_size_matches_physical_pixels_and_zoom_survives_next_image(viewer):
    viewer.actual_size()
    assert not viewer.fit_mode
    assert viewer.transform().m11() * viewer.devicePixelRatioF() == pytest.approx(1)
    viewer.zoom_in()
    expected = viewer.zoom_factor
    viewer.rotate_image(90)
    image = QImage(500, 250, QImage.Format.Format_RGB32)
    viewer.set_image(image)
    assert viewer.zoom_factor == pytest.approx(expected)
    assert viewer.rotation == 0
    assert not viewer.fit_mode
    viewer.zoom_out()
    assert viewer.zoom_factor == pytest.approx(1)
    viewer.set_zoom(1e8)
    assert viewer.zoom_factor == MAX_ZOOM
    viewer.set_zoom(1e-10)
    assert viewer.zoom_factor == MIN_ZOOM
    viewer.fit_image()
    assert viewer.fit_mode


def test_scroll_and_drag_pan_with_control_wheel_zoom(viewer, qapp):
    viewer.actual_size()
    qapp.processEvents()
    bar = viewer.horizontalScrollBar()
    bar.setValue(bar.maximum() // 2)
    before = bar.value()
    QTest.mousePress(viewer.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(200, 100))
    QTest.mouseMove(viewer.viewport(), QPoint(100, 100))
    QTest.mouseRelease(viewer.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    assert bar.value() > before
    factor = viewer.zoom_factor
    wheel = QWheelEvent(
        QPointF(120, 100),
        QPointF(120, 100),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qapp.sendEvent(viewer.viewport(), wheel)
    assert viewer.zoom_factor > factor
    factor = viewer.zoom_factor
    wheel = QWheelEvent(
        QPointF(120, 100),
        QPointF(120, 100),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qapp.sendEvent(viewer.viewport(), wheel)
    assert viewer.zoom_factor == factor
