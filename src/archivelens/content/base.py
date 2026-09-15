import hashlib
import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Self

from PySide6.QtGui import QImage

from archivelens.archive.credentials import ArchiveCredentials


class SourceType(StrEnum):
    ARCHIVE = "archive"
    FOLDER = "folder"
    PDF = "pdf"


class PageMediaKind(StrEnum):
    RASTER = "raster"
    RENDERED = "rendered"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Cross-provider namespace used by caches and, later, reading state."""

    source_type: SourceType
    canonical_path: str
    size_bytes: int | None = None
    modified_ns: int | None = None
    scan_signature: str = ""

    @property
    def storage_key(self) -> str:
        payload = json.dumps(
            [
                self.source_type,
                self.canonical_path,
                self.size_bytes,
                self.modified_ns,
                self.scan_signature,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_identity_for_path(
    path: str | Path, source_type: SourceType, *, scan_signature: str = ""
) -> SourceIdentity:
    source = Path(path)
    canonical = os.path.normcase(str(source.resolve(strict=False)))
    try:
        stat = source.stat()
    except OSError:
        return SourceIdentity(source_type, canonical, scan_signature=scan_signature)
    size = stat.st_size if source.is_file() else None
    return SourceIdentity(source_type, canonical, size, stat.st_mtime_ns, scan_signature)


@dataclass(frozen=True, slots=True)
class PageDescriptor:
    """Stable reader-facing page metadata without storage-specific fields."""

    index: int
    name: str
    path: str
    extension: str
    media_kind: PageMediaKind
    cache_id: str
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class PageLoadRequest:
    """Provider-neutral page request; render size is reserved for PDF providers."""

    thumbnail_size: int | None = None
    render_size: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class ContentOpenOptions:
    recursive: bool = False
    cancelled: Callable[[], bool] = field(default=lambda: False, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ContentPage:
    """A page is either encoded raster bytes or an already-rendered image."""

    encoded: bytes | None = field(default=None, repr=False)
    image: QImage | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (self.encoded is None) == (self.image is None):
            raise ValueError("ContentPage requires exactly one payload")


@dataclass(frozen=True, slots=True)
class ContentCapabilities:
    source_type: SourceType
    supports_credentials: bool = False
    allows_prefetch: bool = False


class ContentProvider(ABC):
    """Read-only source-neutral provider used by reader workers."""

    @property
    @abstractmethod
    def capabilities(self) -> ContentCapabilities: ...

    @property
    @abstractmethod
    def source_identity(self) -> SourceIdentity: ...

    @abstractmethod
    def open(
        self,
        path: str | Path,
        *,
        credentials: ArchiveCredentials | None = None,
        options: ContentOpenOptions | None = None,
    ) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def list_pages(self) -> list[PageDescriptor]: ...

    @abstractmethod
    def load_page(self, page: PageDescriptor, request: PageLoadRequest) -> ContentPage: ...

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
