from collections import OrderedDict
from collections.abc import Iterable

from PySide6.QtGui import QImage

from archivelens.config import IMAGE_CACHE_BYTES


class ImageCache:
    """Worker-owned LRU bounded by actual QImage allocation size, not image count."""

    def __init__(self, max_bytes: int = IMAGE_CACHE_BYTES) -> None:
        if max_bytes < 0:
            raise ValueError("Cache budget must not be negative")
        self.max_bytes = max_bytes
        self._images: OrderedDict[int, QImage] = OrderedDict()
        self.current_bytes = 0

    def __len__(self) -> int:
        return len(self._images)

    def get(self, key: int) -> QImage | None:
        image = self._images.get(key)
        if image is None:
            return None
        self._images.move_to_end(key)
        return QImage(image)

    def put(self, key: int, image: QImage) -> bool:
        self._remove(key)
        cost = image.sizeInBytes()
        if image.isNull() or cost > self.max_bytes:
            return False
        while self._images and self.current_bytes + cost > self.max_bytes:
            self._remove(next(iter(self._images)))
        self._images[key] = QImage(image)
        self.current_bytes += cost
        return True

    def retain(self, keys: Iterable[int]) -> None:
        keep = set(keys)
        for key in tuple(self._images):
            if key not in keep:
                self._remove(key)

    def _remove(self, key: int) -> None:
        image = self._images.pop(key, None)
        if image is not None:
            self.current_bytes -= image.sizeInBytes()

    def clear(self) -> None:
        self._images.clear()
        self.current_bytes = 0
