"""Source-neutral content provider APIs."""

from archivelens.content.archive_provider import ArchiveContentProvider
from archivelens.content.base import (
    ContentCapabilities,
    ContentPage,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    PageMediaKind,
    SourceIdentity,
    SourceType,
)
from archivelens.content.factory import ContentProviderRegistry, create_content_registry

__all__ = [
    "ArchiveContentProvider",
    "ContentCapabilities",
    "ContentPage",
    "ContentProvider",
    "ContentProviderRegistry",
    "PageDescriptor",
    "PageLoadRequest",
    "PageMediaKind",
    "SourceIdentity",
    "SourceType",
    "create_content_registry",
]
