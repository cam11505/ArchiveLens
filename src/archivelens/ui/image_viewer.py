from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QImage, QMovie, QPixmap, QResizeEvent, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from archivelens.config import MAX_ZOOM, MIN_ZOOM, ZOOM_STEP
from archivelens.image.media import PageMedia


class ImageViewer(QGraphicsView):
    """Fit or physical-pixel zoom, quarter-turn rotation, scrolling and drag panning."""

    zoom_changed = Signal(float)
    view_mode_changed = Signal(str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setStyleSheet("QGraphicsView { background: #171b23; border: 0; }")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._item: QGraphicsPixmapItem | None = None
        self._movies = []
        self._group = None
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
        for movie, buffer in self._movies:
            movie.stop()
            movie.frameChanged.disconnect()
            movie.setDevice(None)
            buffer.close()
            buffer.setData(QByteArray())
            movie.deleteLater()
            buffer.deleteLater()
        self._movies.clear()
        self._group = None
        self.scene().clear()
        self._item = None
        self.rotation = 0
        self.image_size = QSize()
        self.resetTransform()
        self.scene().setSceneRect(0, 0, 0, 0)

    def set_image(self, image: QImage) -> None:
        self.set_pages((PageMedia(0, image),))

    def set_pages(self, pages: tuple[PageMedia, ...], rtl=False) -> None:
        self.clear_image()
        items = []
        x = 0
        for page in reversed(pages) if rtl else pages:
            pixmap = QPixmap.fromImage(page.image)
            pixmap.setDevicePixelRatio(1)
            item = self.scene().addPixmap(pixmap)
            item.setPos(x, 0)
            x += page.image.width() + 12
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            items.append(item)
            if page.animation:
                buffer = QBuffer(self)
                buffer.setData(QByteArray(page.animation))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                movie = QMovie(buffer, QByteArray(b"gif"), self)
                movie.setCacheMode(QMovie.CacheMode.CacheNone)

                frame_size = page.image.size()

                def frame_changed(_, movie=movie, item=item, size=frame_size):
                    frame = movie.currentImage()
                    if frame.size() != size:
                        movie.stop()
                        return
                    item.setPixmap(QPixmap.fromImage(frame))

                movie.frameChanged.connect(frame_changed)
                self._movies.append((movie, buffer))
        if not items:
            return
        self._item = items[0]
        self.image_size = QSize(x - 12, max(page.image.height() for page in pages))
        if len(items) > 1:
            self._group = self.scene().createItemGroup(items)
        root = self._group or self._item
        root.setTransformOriginPoint(root.boundingRect().center())
        self.scene().setSceneRect(root.sceneBoundingRect())
        self._apply_view()
        self.centerOn(self.sceneRect().center())
        for movie, _ in self._movies:
            movie.start()

    def fit_image(self) -> None:
        self.fit_mode = True
        self._apply_view()
        self.view_mode_changed.emit("fit_page", self.zoom_factor)

    def actual_size(self) -> None:
        self._set_zoom(1.0, "actual")

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom_factor * ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom_factor / ZOOM_STEP)

    def set_zoom(self, factor: float) -> None:
        self._set_zoom(factor, "custom")

    def _set_zoom(self, factor: float, mode: str) -> None:
        if self._item is None:
            return
        self.fit_mode = False
        self.zoom_factor = max(MIN_ZOOM, min(factor, MAX_ZOOM))
        self._apply_view()
        self.view_mode_changed.emit(mode, self.zoom_factor)

    def rotate_image(self, degrees: int) -> None:
        if self._item is None:
            return
        self.rotation = (self.rotation + degrees) % 360
        root = self._group or self._item
        root.setRotation(self.rotation)
        self.scene().setSceneRect(root.sceneBoundingRect())
        self._apply_view()
        self.centerOn(self.sceneRect().center())

    def _apply_view(self) -> None:
        if self._item is None or self._updating:
            return
        self._updating = True
        try:
            self._set_scrollbars(not self.fit_mode)
            dpr = self.devicePixelRatioF()
            if self.fit_mode:
                rect = self.sceneRect()
                scale = min(
                    max(1, self.viewport().width() - 4) / rect.width(),
                    max(1, self.viewport().height() - 4) / rect.height(),
                )
                self.zoom_factor = scale * dpr
            self.setTransform(QTransform.fromScale(self.zoom_factor / dpr, self.zoom_factor / dpr))
            if self.fit_mode:
                self.centerOn(self.sceneRect().center())
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
