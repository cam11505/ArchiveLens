import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Condition

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.catalog import image_entries
from archivelens.archive.zip_provider import ZipArchiveProvider
from archivelens.config import PREFETCH_OFFSETS
from archivelens.errors import ArchiveLensError
from archivelens.image.cache import ImageCache
from archivelens.image.loader import decode_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadRequest:
    token: int
    generation: int
    path: Path
    index: int


@dataclass(frozen=True)
class LoadResult:
    token: int
    entries: tuple[ArchiveEntry, ...]
    index: int
    image: QImage | None = None
    error: str = ""


class ImageWorker(QThread):
    """Own archive access in one thread with a single replaceable pending request."""

    result_ready = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._condition = Condition()
        self._pending: LoadRequest | None = None
        self._stopping = False

    def submit(self, request: LoadRequest) -> None:
        with self._condition:
            if not self._stopping:
                self._pending = request
                self._condition.notify()

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._pending = None
            self._condition.notify()

    def run(self) -> None:
        provider: ArchiveProvider = ZipArchiveProvider()
        cache = ImageCache()
        generation = -1
        entries: tuple[ArchiveEntry, ...] = ()
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._stopping or self._pending is not None)
                    if self._stopping:
                        return
                    request = self._pending
                    self._pending = None
                assert request is not None
                image = None
                error = ""
                index = request.index
                try:
                    if request.generation != generation:
                        cache.clear()
                        entries = ()
                        generation = -1
                        provider.open(request.path)
                        entries = tuple(image_entries(provider))
                        generation = request.generation
                    if not entries:
                        raise ArchiveLensError("此壓縮檔中沒有找到可顯示的圖片。")
                    index = max(0, min(index, len(entries) - 1))
                    cache.retain([index, *(index + offset for offset in PREFETCH_OFFSETS)])
                    image = cache.get(index)
                    if image is None:
                        image = decode_image(provider.read_entry(entries[index]))
                        cache.put(index, image)
                except ArchiveLensError as exc:
                    error = str(exc)
                    logger.info("Archive load failed: %s", request.path, exc_info=True)
                except Exception:
                    logger.exception("Unexpected image load failure: %s", request.path)
                    error = "載入失敗，請嘗試其他圖片或重新開啟壓縮檔。"
                with self._condition:
                    if self._stopping:
                        return
                    stale = self._pending is not None
                if not stale:
                    self.result_ready.emit(LoadResult(request.token, entries, index, image, error))
                image = None
                if not stale and not error:
                    self._prefetch(provider, entries, index, cache)
        finally:
            cache.clear()
            provider.close()

    def _prefetch(
        self,
        provider: ArchiveProvider,
        entries: tuple[ArchiveEntry, ...],
        index: int,
        cache: ImageCache,
    ) -> None:
        for offset in PREFETCH_OFFSETS:
            with self._condition:
                if self._stopping or self._pending is not None:
                    return
            neighbor = index + offset
            if neighbor < 0 or neighbor >= len(entries) or cache.get(neighbor) is not None:
                continue
            try:
                image = decode_image(provider.read_entry(entries[neighbor]))
                # Prefetch must not evict the requested image to store a speculative neighbor.
                if image.sizeInBytes() <= cache.max_bytes - cache.current_bytes:
                    cache.put(neighbor, image)
                image = None
            except ArchiveLensError:
                logger.debug("Skipped unavailable prefetch: %s", entries[neighbor].path)
            except Exception:
                logger.exception("Unexpected prefetch failure")
