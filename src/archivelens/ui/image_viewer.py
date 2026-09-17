from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QImage, QMovie, QPixmap, QResizeEvent, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from archivelens.config import MAX_ZOOM, MIN_ZOOM, ZOOM_STEP
from archivelens.image.media import PageMedia
from archivelens.image.trim import TrimMargins, trim_rect


class ImageViewer(QGraphicsView):
    """Fit or physical-pixel zoom, quarter-turn rotation, scrolling and drag panning."""

    zoom_changed = Signal(float)
    view_mode_changed = Signal(str, float)
    viewport_changed = Signal()

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
        self.view_mode = "fit_page"
        self.zoom_factor = 1.0
        self.rotation = 0
        self.image_size = QSize()
        self.render_pixel_ratio = 1.0
        self._updating = False
        self.trim_mode = "off"
        self.trim_margins = TrimMargins()
        self._set_scrollbars(False)

    @property
    def fit_mode(self) -> bool:
        return self.view_mode.startswith("fit_")

    def _set_scrollbars(self, enabled: bool) -> None:
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if enabled
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)

    def reset_view_state(self) -> None:
        self.view_mode = "fit_page"
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
        self.render_pixel_ratio = 1.0
        self.resetTransform()
        self.scene().setSceneRect(0, 0, 0, 0)

    def set_image(self, image: QImage) -> None:
        self.set_pages((PageMedia(0, image),))

    def set_pages(self, pages: tuple[PageMedia, ...], rtl=False) -> None:
        self.clear_image()
        items = []
        x = 0
        displayed_sizes = []
        render_ratios = []
        for page in reversed(pages) if rtl else pages:
            crop = trim_rect(page.image, self.trim_mode, self.trim_margins)
            displayed = page.image.copy(crop) if crop != page.image.rect() else page.image
            pixmap = QPixmap.fromImage(displayed)
            pixmap.setDevicePixelRatio(1)
            item = self.scene().addPixmap(pixmap)
            item.setPos(x, 0)
            x += displayed.width() + 12
            displayed_sizes.append(displayed.size())
            render_ratios.append(max(0.01, page.image.devicePixelRatio()))
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            items.append(item)
            if page.animation:
                buffer = QBuffer(self)
                buffer.setData(QByteArray(page.animation))
                buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                movie = QMovie(buffer, QByteArray(b"gif"), self)
                movie.setCacheMode(QMovie.CacheMode.CacheNone)

                frame_size = page.image.size()

                def frame_changed(_, movie=movie, item=item, size=frame_size, crop=crop):
                    frame = movie.currentImage()
                    if frame.size() != size:
                        movie.stop()
                        return
                    if crop != frame.rect():
                        frame = frame.copy(crop)
                    item.setPixmap(QPixmap.fromImage(frame))

                movie.frameChanged.connect(frame_changed)
                self._movies.append((movie, buffer))
        if not items:
            return
        self._item = items[0]
        self.render_pixel_ratio = min(render_ratios)
        self.image_size = QSize(x - 12, max(size.height() for size in displayed_sizes))
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
        self._set_fit_mode("fit_page")

    def fit_width(self) -> None:
        self._set_fit_mode("fit_width")

    def fit_height(self) -> None:
        self._set_fit_mode("fit_height")

    def _set_fit_mode(self, mode: str) -> None:
        self.view_mode = mode
        self._apply_view()
        self.view_mode_changed.emit(mode, self.zoom_factor)

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
        self.view_mode = mode
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
            if self.view_mode == "fit_page":
                self._set_scrollbars(False)
            elif self.view_mode == "fit_width":
                self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            elif self.view_mode == "fit_height":
                self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            else:
                self._set_scrollbars(True)
            dpr = self.devicePixelRatioF()
            if self.fit_mode:
                rect = self.sceneRect()
                width_scale = max(1, self.viewport().width() - 4) / rect.width()
                height_scale = max(1, self.viewport().height() - 4) / rect.height()
                if self.view_mode == "fit_width":
                    scale = width_scale
                elif self.view_mode == "fit_height":
                    scale = height_scale
                else:
                    scale = min(width_scale, height_scale)
                self.zoom_factor = scale * dpr * self.render_pixel_ratio
            display_scale = self.zoom_factor / (dpr * self.render_pixel_ratio)
            self.setTransform(QTransform.fromScale(display_scale, display_scale))
            if self.fit_mode:
                self.centerOn(self.sceneRect().center())
            self.zoom_changed.emit(self.zoom_factor)
        finally:
            self._updating = False

    def set_trim(self, mode: str, margins: TrimMargins | None = None) -> None:
        self.trim_mode = mode if mode in {"off", "auto", "manual"} else "off"
        self.trim_margins = (margins or TrimMargins()).normalized()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_view()
        self.viewport_changed.emit()

    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self._apply_view()
            self.viewport_changed.emit()
        return result

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta and self._item is not None:
                self.set_zoom(self.zoom_factor * ZOOM_STEP ** max(-8, min(delta / 120, 8)))
            event.accept()
        else:
            super().wheelEvent(event)
