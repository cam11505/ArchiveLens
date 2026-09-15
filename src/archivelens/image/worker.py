import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Condition

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.config import MAX_ANIMATION_BYTES, PREFETCH_OFFSETS, THUMBNAIL_SIZE
from archivelens.content.base import (
    ContentOpenOptions,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    SourceIdentity,
)
from archivelens.content.factory import ContentProviderRegistry, create_content_registry
from archivelens.errors import ArchiveLensError, EmptyContentError, ResourceLimitError
from archivelens.image.cache import ImageCache
from archivelens.image.loader import decode_image
from archivelens.image.media import PageMedia
from archivelens.image.reading import spread_indices

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadRequest:
    token: int
    generation: int
    path: Path
    index: int
    credentials: ArchiveCredentials | None = field(default=None, repr=False, compare=False)
    double_page: bool = False
    cover: bool = True
    thumbnail: bool = False
    recursive: bool = False


@dataclass(frozen=True)
class LoadResult:
    token: int
    entries: tuple[PageDescriptor, ...]
    index: int
    image: QImage | None = None
    error: str = ""
    error_type: type[ArchiveLensError] | None = None
    pages: tuple[PageMedia, ...] = ()
    source_identity: SourceIdentity | None = None


@dataclass(frozen=True, slots=True)
class PageCacheKey:
    source: SourceIdentity
    page: str
    render_size: tuple[int, int] | None = None


class ImageWorker(QThread):
    """Own content access in one thread with a single replaceable pending request."""

    result_ready = Signal(object)

    def __init__(
        self,
        parent=None,
        *,
        registry: ArchiveProviderRegistry | None = None,
        content_registry: ContentProviderRegistry | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry = DEFAULT_REGISTRY if registry is None else registry
        self.content_registry = (
            create_content_registry(self.registry) if content_registry is None else content_registry
        )
        self._condition = Condition()
        self._pending: tuple[LoadRequest, int] | None = None
        self._stopping = False
        self._reset_pending = False
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

    def credential_snapshot(self):
        with self._condition:
            password = self._credentials.password_bytes() if self._credentials else None
            return self._credential_revision, ArchiveCredentials(password)

    def cancel_session(self):
        with self._condition:
            self._pending = None
            self._credential_revision += 1
            self._credential_key = None
            self._reset_pending = True
            self._condition.notify()
            if self._credentials:
                self._credentials.clear()
            self._credentials = None

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
        provider: ContentProvider | None = None
        cache = ImageCache()
        revision = -1
        entries: tuple[PageDescriptor, ...] = ()
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(
                        lambda: self._stopping or self._pending is not None or self._reset_pending
                    )
                    if self._stopping:
                        return
                    pending = self._pending
                    self._pending = None
                    reset = self._reset_pending
                    self._reset_pending = False
                if reset:
                    cache.clear()
                    entries = ()
                    revision = -1
                    if provider is not None:
                        self._close_provider(provider)
                        provider = None
                if pending is None:
                    continue
                assert pending is not None
                request, request_revision = pending
                image = None
                pages = []
                error = ""
                error_type = None
                index = request.index
                source_identity = None
                try:
                    if request_revision != revision:
                        cache.clear()
                        entries = ()
                        revision = -1
                        if provider is not None:
                            self._close_provider(provider)
                        provider = None
                        provider = self.content_registry.create(request.path)
                        provider.open(
                            request.path,
                            credentials=request.credentials,
                            options=ContentOpenOptions(
                                recursive=request.recursive,
                                cancelled=lambda revision=request_revision: self._request_cancelled(
                                    revision
                                ),
                            ),
                        )
                        entries = tuple(provider.list_pages())
                        revision = request_revision
                    assert provider is not None
                    source_identity = provider.source_identity
                    if not entries:
                        raise EmptyContentError()
                    indices = spread_indices(
                        index, len(entries), request.double_page, request.cover
                    )
                    index = indices[0]
                    source_identity = provider.source_identity
                    retained_indices = [
                        *indices,
                        *(index + offset for offset in PREFETCH_OFFSETS),
                    ]
                    cache.retain(
                        PageCacheKey(source_identity, entries[item].cache_id)
                        for item in retained_indices
                        if 0 <= item < len(entries)
                    )
                    for page_index in indices:
                        cache_key = PageCacheKey(source_identity, entries[page_index].cache_id)
                        image = cache.get(cache_key)
                        animation = b""
                        if image is None or entries[page_index].extension == ".gif":
                            page_request = PageLoadRequest(
                                thumbnail_size=THUMBNAIL_SIZE if request.thumbnail else None
                            )
                            content = provider.load_page(entries[page_index], page_request)
                            data = content.encoded or b""
                            if content.image is not None:
                                image = content.image
                            elif not request.thumbnail and data.startswith((b"GIF87a", b"GIF89a")):
                                if len(data) > MAX_ANIMATION_BYTES:
                                    raise ResourceLimitError()
                                animation = data
                            if content.image is None:
                                image = (
                                    decode_image(
                                        data,
                                        page_request.thumbnail_size,
                                        entries[page_index].extension,
                                    )
                                    if request.thumbnail
                                    else decode_image(data, extension=entries[page_index].extension)
                                )
                            if not request.thumbnail:
                                cache.put(cache_key, image)
                        pages.append(PageMedia(page_index, image, animation))
                        data = b""
                        animation = b""
                    image = pages[0].image
                except ArchiveLensError as exc:
                    error_type = type(exc)
                    error = error_type.default_message
                    logger.info("Archive load failed (%s)", error_type.__name__)
                except Exception:
                    error_type = ArchiveLensError
                    error = ArchiveLensError.default_message
                    logger.error("Unexpected image load failure")
                data = b""
                animation = b""
                if error and revision == -1 and provider is not None:
                    self._close_provider(provider)
                    provider = None
                with self._condition:
                    if self._stopping:
                        return
                    stale = (
                        self._pending is not None or request_revision != self._credential_revision
                    )
                if not stale:
                    self.result_ready.emit(
                        LoadResult(
                            request.token,
                            entries,
                            index,
                            image,
                            error,
                            error_type,
                            tuple(pages),
                            source_identity,
                        )
                    )
                image = None
                pages = []
                if not stale and not error and not request.thumbnail:
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
    def _close_provider(provider: ContentProvider) -> None:
        try:
            provider.close()
        except Exception:
            # Backend exceptions may contain credentials, including during cleanup.
            logger.error("Archive provider cleanup failed")

    def _request_cancelled(self, revision: int) -> bool:
        with self._condition:
            return (
                self._stopping
                or self._reset_pending
                or self._pending is not None
                or revision != self._credential_revision
            )

    def _prefetch(
        self,
        provider: ContentProvider,
        entries: tuple[PageDescriptor, ...],
        index: int,
        cache: ImageCache,
    ) -> None:
        if not provider.capabilities.allows_prefetch:
            return
        source_identity = provider.source_identity
        for offset in PREFETCH_OFFSETS:
            with self._condition:
                if self._stopping or self._pending is not None or self._reset_pending:
                    return
            neighbor = index + offset
            if neighbor < 0 or neighbor >= len(entries):
                continue
            cache_key = PageCacheKey(source_identity, entries[neighbor].cache_id)
            if cache.get(cache_key) is not None:
                continue
            try:
                content = provider.load_page(entries[neighbor], PageLoadRequest())
                image = (
                    content.image
                    if content.image is not None
                    else decode_image(content.encoded or b"", extension=entries[neighbor].extension)
                )
                # Prefetch must not evict the requested image to store a speculative neighbor.
                if image.sizeInBytes() <= cache.max_bytes - cache.current_bytes:
                    cache.put(cache_key, image)
                image = None
            except ArchiveLensError:
                logger.debug("Skipped unavailable prefetch")
            except Exception:
                logger.error("Unexpected prefetch failure")
