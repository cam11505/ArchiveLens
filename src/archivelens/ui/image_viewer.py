from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QResizeEvent, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from archivelens.config import MAX_ZOOM, MIN_ZOOM, ZOOM_STEP


class ImageViewer(QGraphicsView):
    """Fit or physical-pixel zoom, quarter-turn rotation, scrolling and drag panning."""

    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setStyleSheet("QGraphicsView { background: #171b23; border: 0; }")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._item: QGraphicsPixmapItem | None = None
        self.fit_mode = True
        self.zoom_factor = 1.0
        self.rotation = 0
        self.image_size = QSize()
        self._updating = False
        self._set_scrollbars(False)

    def _set_scrollbars(self, enabled: bool) -> None:
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if enabled
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)

    def reset_view_state(self) -> None:
        self.fit_mode = True
        self.zoom_factor = 1.0
        self.clear_image()

    def clear_image(self) -> None:
        self.scene().clear()
        self._item = None
        self.rotation = 0
        self.image_size = QSize()
        self.resetTransform()
        self.scene().setSceneRect(0, 0, 0, 0)

    def set_image(self, image: QImage) -> None:
        self.clear_image()
        self.image_size = image.size()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(1)
        self._item = self.scene().addPixmap(pixmap)
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._item.setTransformOriginPoint(self._item.boundingRect().center())
        self.scene().setSceneRect(self._item.sceneBoundingRect())
        self._apply_view()
        self.centerOn(self._item)

    def fit_image(self) -> None:
        self.fit_mode = True
        self._apply_view()

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom_factor * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom_factor / ZOOM_STEP)

    def set_zoom(self, factor: float) -> None:
        if self._item is None:
            return
        self.fit_mode = False
        self.zoom_factor = max(MIN_ZOOM, min(factor, MAX_ZOOM))
        self._apply_view()

    def rotate_image(self, degrees: int) -> None:
        if self._item is None:
            return
        self.rotation = (self.rotation + degrees) % 360
        self._item.setRotation(self.rotation)
        self.scene().setSceneRect(self._item.sceneBoundingRect())
        self._apply_view()
        self.centerOn(self._item)

    def _apply_view(self) -> None:
        if self._item is None or self._updating:
            return
        self._updating = True
        try:
            self._set_scrollbars(not self.fit_mode)
            dpr = self.devicePixelRatioF()
            if self.fit_mode:
                rect = self._item.sceneBoundingRect()
                scale = min(
                    max(1, self.viewport().width() - 4) / rect.width(),
                    max(1, self.viewport().height() - 4) / rect.height(),
                )
                self.zoom_factor = scale * dpr
            self.setTransform(QTransform.fromScale(self.zoom_factor / dpr, self.zoom_factor / dpr))
            if self.fit_mode:
                self.centerOn(self._item)
            self.zoom_changed.emit(self.zoom_factor)
        finally:
            self._updating = False

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_view()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta and self._item is not None:
                self.set_zoom(self.zoom_factor * ZOOM_STEP ** max(-8, min(delta / 120, 8)))
            event.accept()
        else:
            super().wheelEvent(event)
