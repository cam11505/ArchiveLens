from dataclasses import replace
from io import BytesIO
from lzma import LZMAError
from pathlib import Path, PurePosixPath

import py7zr
from py7zr.exceptions import (
    Bad7zFile,
    CrcError,
    PasswordRequired,
    UnsupportedCompressionMethodError,
)
from py7zr.io import Py7zIO, WriterFactory

from archivelens import config
from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.archive.capabilities import ArchiveCapabilities, RandomAccess
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.errors import (
    ArchiveAccessError,
    ArchiveNotOpenError,
    BadPasswordError,
    CorruptedArchiveError,
    InvalidArchiveEntryError,
    PasswordRequiredError,
    ResourceLimitError,
    UnsupportedCompressionError,
)
from archivelens.utils.file_types import is_image


class BoundedBuffer(Py7zIO):
    def __init__(self, limit):
        self.buffer = BytesIO()
        self.limit = limit

    def write(self, data):
        if self.buffer.tell() + len(data) > self.limit:
            raise ResourceLimitError()
        return self.buffer.write(data)

    def read(self, size=None):
        return self.buffer.read(-1 if size is None else size)

    def seek(self, offset, whence=0):
        return self.buffer.seek(offset, whence)

    def flush(self):
        pass

    def size(self):
        return self.buffer.getbuffer().nbytes


class EntryFactory(WriterFactory):
    def __init__(self, name, limit):
        self.name = name
        self.output = BoundedBuffer(limit)
        self.created = False

    def create(self, filename):
        if filename != self.name or self.created:
            raise CorruptedArchiveError()
        self.created = True
        return self.output


class SevenZipArchiveProvider(ArchiveProvider):
    capabilities = ArchiveCapabilities(
        "7Z", frozenset({".7z"}), supports_passwords=True, random_access=RandomAccess.EXPENSIVE
    )

    def __init__(self):
        self._archive = None
        self._entries = []
        self._credentials = None
        self._encrypted = False

    @staticmethod
    def supports(path):
        return Path(path).suffix.casefold() == ".7z"

    def open(self, path, *, credentials: ArchiveCredentials | None = None):
        self.close()
        self._credentials = credentials
        password = credentials.password_bytes() if credentials else None
        try:
            self._archive = py7zr.SevenZipFile(
                path, "r", password=password.decode("utf-8") if password is not None else None
            )
            self._encrypted = self._archive.needs_password()
            files = self._archive.list()
            if len(files) > config.MAX_ARCHIVE_ENTRIES:
                raise ResourceLimitError()
            info = self._archive.archiveinfo()
            self.capabilities = replace(type(self).capabilities, solid=info.solid)
            if (
                info.uncompressed > config.MAX_SOLID_UNCOMPRESSED_SIZE
                or info.uncompressed / max(1, Path(path).stat().st_size)
                > config.MAX_COMPRESSION_RATIO
            ):
                raise ResourceLimitError()
            names = set()
            for i, member in enumerate(files):
                if not member.is_file or member.is_symlink:
                    continue
                if member.filename in names:
                    raise UnsupportedCompressionError()
                names.add(member.filename)
                name = PurePosixPath(member.filename)
                self._entries.append(
                    ArchiveEntry(
                        name.name,
                        member.filename,
                        name.suffix.casefold(),
                        member.compressed or 0,
                        member.uncompressed,
                        i,
                        is_image(member.filename),
                    )
                )
        except PasswordRequired as exc:
            self.close()
            raise PasswordRequiredError() from exc
        except OSError as exc:
            self.close()
            raise ArchiveAccessError() from exc
        except UnsupportedCompressionMethodError as exc:
            self.close()
            raise UnsupportedCompressionError() from exc
        except (Bad7zFile, CrcError, ValueError, TypeError, EOFError, LZMAError) as exc:
            self.close()
            if password is not None:
                raise BadPasswordError() from exc
            raise CorruptedArchiveError() from exc
        except Exception:
            self.close()
            raise

    def close(self):
        if self._archive is not None:
            self._archive.close()
        self._archive = None
        self._entries = []
        self._credentials = None
        self._encrypted = False

    def list_entries(self):
        if self._archive is None:
            raise ArchiveNotOpenError()
        return self._entries.copy()

    def read_entry(self, entry):
        if self._archive is None:
            raise ArchiveNotOpenError()
        if not any(item is entry for item in self._entries):
            raise InvalidArchiveEntryError()
        password = self._credentials.password_bytes() if self._credentials else None
        if self._encrypted and password is None:
            raise PasswordRequiredError()
        if entry.uncompressed_size > config.MAX_ENTRY_UNCOMPRESSED_SIZE:
            raise ResourceLimitError()
        target = EntryFactory(
            entry.path, min(entry.uncompressed_size, config.MAX_ENTRY_UNCOMPRESSED_SIZE)
        )
        try:
            self._archive.reset()
            self._archive.extract(targets=[entry.path], factory=target)
            data = target.output.buffer.getvalue()
            if len(data) != entry.uncompressed_size:
                raise CorruptedArchiveError()
            return data
        except PasswordRequired as exc:
            raise PasswordRequiredError() from exc
        except UnsupportedCompressionMethodError as exc:
            raise UnsupportedCompressionError() from exc
        except (Bad7zFile, CrcError, ValueError, TypeError, EOFError, LZMAError) as exc:
            if self._encrypted:
                raise BadPasswordError() from exc
            raise CorruptedArchiveError() from exc
        finally:
            target.output.buffer.close()
