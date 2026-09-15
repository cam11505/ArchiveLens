from pathlib import Path

from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.catalog import image_entries
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import ArchiveProviderRegistry
from archivelens.content.base import (
    ContentCapabilities,
    ContentOpenOptions,
    ContentPage,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    PageMediaKind,
    SourceIdentity,
    SourceType,
    source_identity_for_path,
)
from archivelens.errors import ArchiveNotOpenError, InvalidPageError


class ArchiveContentProvider(ContentProvider):
    """Adapt existing archive backends to source-neutral reader pages."""

    def __init__(self, registry: ArchiveProviderRegistry) -> None:
        self._registry = registry
        self._provider: ArchiveProvider | None = None
        self._identity: SourceIdentity | None = None
        self._pages: tuple[PageDescriptor, ...] = ()
        self._entries: tuple[ArchiveEntry, ...] = ()

    @property
    def capabilities(self) -> ContentCapabilities:
        archive = self._provider.capabilities if self._provider is not None else None
        return ContentCapabilities(
            SourceType.ARCHIVE,
            supports_credentials=bool(archive and archive.supports_passwords),
            allows_prefetch=bool(archive and archive.allows_prefetch),
        )

    @property
    def source_identity(self) -> SourceIdentity:
        if self._identity is None:
            raise ArchiveNotOpenError()
        return self._identity

    def open(
        self,
        path: str | Path,
        *,
        credentials: ArchiveCredentials | None = None,
        options: ContentOpenOptions | None = None,
    ) -> None:
        del options
        self.close()
        source = Path(path)
        provider = self._registry.create(source)
        try:
            provider.open(source, credentials=credentials)
            entries = tuple(image_entries(provider))
        except Exception:
            try:
                provider.close()
            except Exception:
                pass
            raise
        self._provider = provider
        self._entries = entries
        self._pages = tuple(
            PageDescriptor(
                index=index,
                name=entry.name,
                path=entry.path,
                extension=entry.extension,
                media_kind=PageMediaKind.RASTER,
                cache_id=f"archive-entry:{entry.index}:{entry.path}",
                size_bytes=entry.uncompressed_size,
            )
            for index, entry in enumerate(entries)
        )
        self._identity = source_identity_for_path(source, SourceType.ARCHIVE)

    def close(self) -> None:
        provider, self._provider = self._provider, None
        self._identity = None
        self._pages = ()
        self._entries = ()
        if provider is not None:
            provider.close()

    def list_pages(self) -> list[PageDescriptor]:
        if self._provider is None:
            raise ArchiveNotOpenError()
        return list(self._pages)

    def load_page(self, page: PageDescriptor, request: PageLoadRequest) -> ContentPage:
        del request
        if self._provider is None:
            raise ArchiveNotOpenError()
        if not 0 <= page.index < len(self._pages) or self._pages[page.index] is not page:
            raise InvalidPageError()
        return ContentPage(encoded=self._provider.read_entry(self._entries[page.index]))
