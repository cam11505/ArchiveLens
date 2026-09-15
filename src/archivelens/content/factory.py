from pathlib import Path

from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.content.archive_provider import ArchiveContentProvider
from archivelens.content.base import ContentProvider
from archivelens.errors import UnsupportedArchiveError


class ContentProviderRegistry:
    """Selection boundary for archives now and folder/PDF providers later."""

    def __init__(self, archive_registry: ArchiveProviderRegistry) -> None:
        self.archive_registry = archive_registry

    @property
    def supported_extensions(self) -> frozenset[str]:
        return self.archive_registry.supported_extensions

    def supports(self, path: str | Path) -> bool:
        return self.archive_registry.supports(path)

    def create(self, path: str | Path) -> ContentProvider:
        if Path(path).suffix.casefold() not in self.archive_registry.registered_extensions:
            raise UnsupportedArchiveError()
        return ArchiveContentProvider(self.archive_registry)

    def file_dialog_filter(self) -> str:
        return self.archive_registry.file_dialog_filter()

    def format_label(self) -> str:
        return self.archive_registry.format_label()


def create_content_registry(
    archive_registry: ArchiveProviderRegistry | None = None,
) -> ContentProviderRegistry:
    return ContentProviderRegistry(
        DEFAULT_REGISTRY if archive_registry is None else archive_registry
    )


DEFAULT_CONTENT_REGISTRY = create_content_registry()
