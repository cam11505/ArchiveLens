import sys
from dataclasses import replace
from pathlib import Path, PurePosixPath

from archivelens import config
from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.capabilities import ArchiveCapabilities, RandomAccess
from archivelens.archive.unrar import RarSession, dll_path
from archivelens.errors import (
    ArchiveNotOpenError,
    CorruptedArchiveError,
    InvalidArchiveEntryError,
    ResourceLimitError,
)
from archivelens.utils.file_types import is_image


class RarArchiveProvider(ArchiveProvider):
    capabilities = ArchiveCapabilities(
        "RAR / CBR",
        frozenset({".rar", ".cbr"}),
        supports_passwords=True,
        random_access=RandomAccess.EXPENSIVE,
        available=sys.platform == "win32" and dll_path().is_file(),
    )

    def __init__(self):
        self._path = None
        self._credentials = None
        self._entries = []

    @staticmethod
    def supports(path):
        return Path(path).suffix.casefold() in {".rar", ".cbr"}

    def open(self, path, *, credentials=None):
        self.close()
        session = RarSession(path, credentials)
        try:
            self.capabilities = replace(type(self).capabilities, solid=bool(session.flags & 8))
            total = 0
            index = 0
            while (header := session.header()) is not None:
                if index >= config.MAX_ARCHIVE_ENTRIES:
                    raise ResourceLimitError()
                size = header.UnpSize | (header.UnpSizeHigh << 32)
                packed = header.PackSize | (header.PackSizeHigh << 32)
                total += size
                if total > config.MAX_SOLID_UNCOMPRESSED_SIZE:
                    raise ResourceLimitError()
                if not header.Flags & 0x20 and not header.RedirType:
                    name = header.FileNameW.replace("\\", "/")
                    member = PurePosixPath(name)
                    self._entries.append(
                        ArchiveEntry(
                            member.name,
                            name,
                            member.suffix.casefold(),
                            packed,
                            size,
                            index,
                            is_image(name),
                        )
                    )
                session.process()
                index += 1
            self._path = Path(path)
            self._credentials = credentials
        except Exception:
            self.close()
            raise
        finally:
            session.close()

    def close(self):
        self._path = None
        self._entries = []
        self._credentials = None

    def list_entries(self):
        if self._path is None:
            raise ArchiveNotOpenError()
        return self._entries.copy()

    def read_entry(self, entry):
        if self._path is None:
            raise ArchiveNotOpenError()
        if not any(item is entry for item in self._entries):
            raise InvalidArchiveEntryError()
        if (
            entry.uncompressed_size > config.MAX_ENTRY_UNCOMPRESSED_SIZE
            or entry.uncompressed_size / max(1, entry.compressed_size)
            > config.MAX_COMPRESSION_RATIO
        ):
            raise ResourceLimitError()
        session = RarSession(self._path, self._credentials, extract=True)
        try:
            for index in range(entry.index + 1):
                header = session.header()
                if header is None:
                    raise CorruptedArchiveError()
                if index == entry.index:
                    data = session.process(True, entry.uncompressed_size)
                    if len(data) != entry.uncompressed_size:
                        raise CorruptedArchiveError()
                    return data
                session.process()
        finally:
            session.close()
