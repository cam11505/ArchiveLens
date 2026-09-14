import lzma
import zlib
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from archivelens import config
from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.capabilities import ArchiveCapabilities, RandomAccess
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.errors import (
    ArchiveAccessError,
    ArchiveNotOpenError,
    CorruptedArchiveError,
    InvalidArchiveEntryError,
    ResourceLimitError,
    UnsupportedArchiveError,
    UnsupportedCompressionError,
    UnsupportedEncryptionError,
)
from archivelens.utils.file_types import ARCHIVE_EXTENSIONS, is_image


class ZipArchiveProvider(ArchiveProvider):
    """Read individual ZIP/CBZ members into RAM without extracting to disk."""

    capabilities = ArchiveCapabilities(
        "ZIP / CBZ", ARCHIVE_EXTENSIONS, random_access=RandomAccess.EFFICIENT, solid=False
    )

    def __init__(self) -> None:
        self._archive: ZipFile | None = None
        self._members: dict[int, tuple[ArchiveEntry, ZipInfo]] = {}
        self._credentials: ArchiveCredentials | None = None

    @staticmethod
    def supports(path: str | Path) -> bool:
        return Path(path).suffix.casefold() in ARCHIVE_EXTENSIONS

    def open(self, path: str | Path, *, credentials: ArchiveCredentials | None = None) -> None:
        self.close()
        if not self.supports(path):
            raise UnsupportedArchiveError()
        self._credentials = credentials
        try:
            self._archive = ZipFile(path, mode="r")
            for index, info in enumerate(self._archive.infolist()):
                if info.is_dir():
                    continue
                member_path = PurePosixPath(info.filename)
                entry = ArchiveEntry(
                    member_path.name,
                    info.filename,
                    member_path.suffix.casefold(),
                    info.compress_size,
                    info.file_size,
                    index,
                    is_image(info.filename),
                )
                self._members[index] = (entry, info)
        except OSError as exc:
            self.close()
            raise ArchiveAccessError() from exc
        except (BadZipFile, UnicodeError, ValueError) as exc:
            self.close()
            raise CorruptedArchiveError() from exc

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
        self._archive = None
        self._members.clear()
        self._credentials = None

    def list_entries(self) -> list[ArchiveEntry]:
        if self._archive is None:
            raise ArchiveNotOpenError()
        return [entry for entry, _ in self._members.values()]

    def read_entry(self, entry: ArchiveEntry) -> bytes:
        if self._archive is None:
            raise ArchiveNotOpenError()
        member = self._members.get(entry.index)
        if member is None or member[0] is not entry:
            raise InvalidArchiveEntryError()
        info = member[1]
        if info.flag_bits & 1:
            raise UnsupportedEncryptionError()
        limit = config.MAX_ENTRY_UNCOMPRESSED_SIZE
        if (
            info.file_size > limit
            or info.file_size / max(1, info.compress_size) > config.MAX_COMPRESSION_RATIO
        ):
            raise ResourceLimitError()
        try:
            with self._archive.open(info, mode="r") as stream:
                data = stream.read(limit + 1)
            if len(data) > limit or len(data) != info.file_size:
                raise ResourceLimitError()
            return data
        except OSError as exc:
            raise ArchiveAccessError() from exc
        except NotImplementedError as exc:
            raise UnsupportedCompressionError() from exc
        except (BadZipFile, RuntimeError, EOFError, zlib.error, lzma.LZMAError) as exc:
            raise CorruptedArchiveError() from exc
