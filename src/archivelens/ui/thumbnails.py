from PySide6.QtCore import QAbstractListModel, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QListView

from archivelens.config import THUMBNAIL_CACHE_BYTES, THUMBNAIL_SIZE
from archivelens.image.cache import ImageCache
from archivelens.image.worker import ImageWorker, LoadRequest


class ThumbnailModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = ()
        self.cache = ImageCache(THUMBNAIL_CACHE_BYTES)

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        row = index.row()
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{row + 1}. {self.entries[row].name}"
        if role == Qt.ItemDataRole.DecorationRole:
            image = self.cache.get(row)
            return QPixmap.fromImage(image) if image is not None else None
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(THUMBNAIL_SIZE + 20, THUMBNAIL_SIZE + 30)
        return None

    def reset_entries(self, entries):
        self.beginResetModel()
        self.entries = entries
        self.cache.clear()
        self.endResetModel()


class ThumbnailSidebar(QListView):
    page_selected = Signal(int)

    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.catalog = ThumbnailModel(self)
        self.setModel(self.catalog)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.setMinimumWidth(180)
        self.worker = ImageWorker(self, registry=registry)
        self.worker.result_ready.connect(self._result)
        self.worker.start()
        self.path = None
        self.generation = -1
        self.revision = -1
        self.token = 0
        self._credentials = None
        self._requested = None
        self._failed = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.load_visible)
        self.verticalScrollBar().valueChanged.connect(lambda _: self._timer.start())
        self.clicked.connect(lambda index: self.page_selected.emit(index.row()))

    def reset_session(self):
        self.token += 1
        self.path = None
        self.revision = -1
        self._requested = None
        self._failed.clear()
        self._timer.stop()
        if self._credentials:
            self._credentials.clear()
        self._credentials = None
        self.worker.cancel_session()
        self.catalog.reset_entries(())

    def set_session(self, path, generation, entries, revision, credentials):
        if self.path == path and self.generation == generation and self.revision == revision:
            credentials.clear()
            return
        self.reset_session()
        self.path, self.generation, self.revision = path, generation, revision
        self._credentials = credentials
        self.catalog.reset_entries(entries)
        self._timer.start()

    def visible_rows(self):
        count = len(self.catalog.entries)
        if not count:
            return []
        first = self.indexAt(QPoint(2, 2)).row()
        last = self.indexAt(QPoint(2, self.viewport().height() - 2)).row()
        first = max(0, first)
        if last < first:
            last = min(count - 1, first + max(1, self.viewport().height() // 174))
        return list(range(first, min(last + 1, first + 24, count)))

    def load_visible(self):
        if not self.isVisible() or self.path is None:
            return
        wanted = [
            row
            for row in self.visible_rows()
            if self.catalog.cache.get(row) is None and row not in self._failed
        ]
        if not wanted:
            return
        row = wanted[0]
        if self._requested == row:
            return
        self.token += 1
        self._requested = row
        credentials, self._credentials = self._credentials, None
        self.worker.submit(
            LoadRequest(self.token, self.generation, self.path, row, credentials, thumbnail=True)
        )

    def _result(self, result):
        if result.token != self.token or self.path is None:
            return
        self._requested = None
        if result.error or result.image is None:
            self._failed.add(result.index)
        else:
            self.catalog.cache.put(result.index, result.image)
            index = self.catalog.index(result.index)
            self.catalog.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])
        self._timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._timer.start()

    def shutdown(self):
        self.reset_session()
        self.worker.stop()
