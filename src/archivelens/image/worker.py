import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Condition

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.catalog import image_entries
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.config import PREFETCH_OFFSETS
from archivelens.errors import ArchiveLensError, EmptyArchiveError
from archivelens.image.cache import ImageCache
from archivelens.image.loader import decode_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadRequest:
    token: int
    generation: int
    path: Path
    index: int
    credentials: ArchiveCredentials | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class LoadResult:
    token: int
    entries: tuple[ArchiveEntry, ...]
    index: int
    image: QImage | None = None
    error: str = ""
    error_type: type[ArchiveLensError] | None = None


class ImageWorker(QThread):
    """Own archive access in one thread with a single replaceable pending request."""

    result_ready = Signal(object)

    def __init__(self, parent=None, *, registry: ArchiveProviderRegistry | None = None) -> None:
        super().__init__(parent)
        self.registry = DEFAULT_REGISTRY if registry is None else registry
        self._condition = Condition()
        self._pending: tuple[LoadRequest, int] | None = None
        self._stopping = False
        self._credentials: ArchiveCredentials | None = None
        self._credential_key: tuple[int, Path] | None = None
        self._credential_revision = 0

    def submit(self, request: LoadRequest) -> None:
        """Transfer credential ownership to this worker until replacement or stop."""
        with self._condition:
            if self._stopping:
                if request.credentials is not None:
                    request.credentials.clear()
                return
            key = (request.generation, request.path)
            if key != self._credential_key or (
                request.credentials is not None and request.credentials is not self._credentials
            ):
                if self._credentials is not None:
                    self._credentials.clear()
                self._credentials = request.credentials or ArchiveCredentials()
                self._credential_key = key
                self._credential_revision += 1
            self._pending = (
                replace(request, credentials=self._credentials),
                self._credential_revision,
            )
            self._condition.notify()

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._pending = None
            if self._credentials is not None:
                self._credentials.clear()
            self._credentials = None
            self._credential_key = None
            self._condition.notify()

    def run(self) -> None:
        provider: ArchiveProvider | None = None
        cache = ImageCache()
        revision = -1
        entries: tuple[ArchiveEntry, ...] = ()
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._stopping or self._pending is not None)
                    if self._stopping:
                        return
                    pending = self._pending
                    self._pending = None
                assert pending is not None
                request, request_revision = pending
                image = None
                error = ""
                error_type = None
                index = request.index
                try:
                    if request_revision != revision:
                        cache.clear()
                        entries = ()
                        revision = -1
                        if provider is not None:
                            self._close_provider(provider)
                        provider = None
                        provider = self.registry.create(request.path)
                        provider.open(request.path, credentials=request.credentials)
                        entries = tuple(image_entries(provider))
                        revision = request_revision
                    assert provider is not None
                    if not entries:
                        raise EmptyArchiveError()
                    index = max(0, min(index, len(entries) - 1))
                    cache.retain([index, *(index + offset for offset in PREFETCH_OFFSETS)])
                    image = cache.get(index)
                    if image is None:
                        image = decode_image(provider.read_entry(entries[index]))
                        cache.put(index, image)
                except ArchiveLensError as exc:
                    error_type = type(exc)
                    error = error_type.default_message
                    logger.info("Archive load failed (%s)", error_type.__name__)
                except Exception:
                    error_type = ArchiveLensError
                    error = ArchiveLensError.default_message
                    logger.error("Unexpected image load failure")
                if error and revision == -1 and provider is not None:
                    self._close_provider(provider)
                    provider = None
                with self._condition:
                    if self._stopping:
                        return
                    stale = self._pending is not None
                if not stale:
                    self.result_ready.emit(
                        LoadResult(request.token, entries, index, image, error, error_type)
                    )
                image = None
                if not stale and not error:
                    assert provider is not None
                    self._prefetch(provider, entries, index, cache)
        finally:
            cache.clear()
            try:
                if provider is not None:
                    self._close_provider(provider)
            finally:
                self.stop()

    @staticmethod
    def _close_provider(provider: ArchiveProvider) -> None:
        try:
            provider.close()
        except Exception:
            # Backend exceptions may contain credentials, including during cleanup.
            logger.error("Archive provider cleanup failed")

    def _prefetch(
        self,
        provider: ArchiveProvider,
        entries: tuple[ArchiveEntry, ...],
        index: int,
        cache: ImageCache,
    ) -> None:
        if not provider.capabilities.allows_prefetch:
            return
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
                logger.debug("Skipped unavailable prefetch")
            except Exception:
                logger.error("Unexpected prefetch failure")
