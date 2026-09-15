"""Source-neutral content provider APIs."""

from archivelens.content.archive_provider import ArchiveContentProvider
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
from archivelens.content.factory import ContentProviderRegistry, create_content_registry
from archivelens.content.folder_provider import FolderContentProvider

__all__ = [
    "ArchiveContentProvider",
    "ContentCapabilities",
    "ContentOpenOptions",
    "ContentPage",
    "ContentProvider",
    "ContentProviderRegistry",
    "FolderContentProvider",
    "PageDescriptor",
    "PageLoadRequest",
    "PageMediaKind",
    "SourceIdentity",
    "SourceType",
    "create_content_registry",
    "source_identity_for_path",
]
