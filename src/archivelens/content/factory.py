from pathlib import Path

from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.content.archive_provider import ArchiveContentProvider
from archivelens.content.base import ContentProvider, SourceType
from archivelens.content.folder_provider import FolderContentProvider
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.errors import UnsupportedArchiveError, UnsupportedContentError


class ContentProviderRegistry:
    """Selection boundary for archives now and folder/PDF providers later."""

    def __init__(self, archive_registry: ArchiveProviderRegistry) -> None:
        self.archive_registry = archive_registry

    @property
    def supported_extensions(self) -> frozenset[str]:
        return self.archive_registry.supported_extensions | {".pdf"}

    def supports(self, path: str | Path) -> bool:
        source = Path(path)
        return (
            source.is_dir()
            or source.suffix.casefold() == ".pdf"
            or self.archive_registry.supports(source)
        )

    def source_type(self, path: str | Path) -> SourceType:
        source = Path(path)
        if source.is_dir():
            return SourceType.FOLDER
        if source.suffix.casefold() == ".pdf":
            return SourceType.PDF
        if source.suffix.casefold() not in self.archive_registry.registered_extensions:
            raise UnsupportedArchiveError()
        return SourceType.ARCHIVE

    def create(self, path: str | Path) -> ContentProvider:
        source = Path(path)
        if source.is_dir():
            return FolderContentProvider()
        if source.suffix.casefold() == ".pdf":
            return PdfContentProvider()
        if source.suffix.casefold() not in self.archive_registry.registered_extensions:
            raise UnsupportedContentError()
        return ArchiveContentProvider(self.archive_registry)

    def file_dialog_filter(self) -> str:
        archives = " ".join(
            f"*{item.upper()}" for item in sorted(self.archive_registry.supported_extensions)
        )
        return (
            f"支援的內容 (*.pdf {archives});;PDF 文件 (*.pdf);;"
            f"{self.archive_registry.file_dialog_filter()}"
        )

    def format_label(self) -> str:
        return f"{self.archive_registry.format_label()}、PDF 或圖片資料夾"


def create_content_registry(
    archive_registry: ArchiveProviderRegistry | None = None,
) -> ContentProviderRegistry:
    return ContentProviderRegistry(
        DEFAULT_REGISTRY if archive_registry is None else archive_registry
    )


DEFAULT_CONTENT_REGISTRY = create_content_registry()
