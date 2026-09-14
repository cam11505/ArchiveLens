from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from archivelens.archive.capabilities import ArchiveCapabilities
from archivelens.archive.credentials import ArchiveCredentials


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    name: str
    path: str
    extension: str
    compressed_size: int
    uncompressed_size: int
    index: int
    is_image: bool


class ArchiveProvider(ABC):
    """Read-only provider; entries are valid only within their open session."""

    capabilities: ArchiveCapabilities

    @staticmethod
    @abstractmethod
    def supports(path: str | Path) -> bool: ...

    @abstractmethod
    def open(self, path: str | Path, *, credentials: ArchiveCredentials | None = None) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def list_entries(self) -> list[ArchiveEntry]: ...

    @abstractmethod
    def read_entry(self, entry: ArchiveEntry) -> bytes: ...

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
