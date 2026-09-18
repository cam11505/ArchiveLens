"""UnRAR 7.21 x64 ABI. Test operations stream bytes via callbacks; never extract."""

import ctypes as c
import sys
from pathlib import Path

from archivelens import config
from archivelens.errors import (
    ArchiveAccessError,
    BadPasswordError,
    CorruptedArchiveError,
    PasswordRequiredError,
    ProviderUnavailableError,
    ResourceLimitError,
    UnsupportedCompressionError,
)
from archivelens.platform_paths import native_backend_path


def dll_path():
    return native_backend_path("UnRAR64.dll")


CALLBACK = getattr(c, "WINFUNCTYPE", c.CFUNCTYPE)(
    c.c_int, c.c_uint, c.c_ssize_t, c.c_ssize_t, c.c_ssize_t
)
U = c.c_uint


class Header(c.Structure):
    _pack_ = 1
    _fields_ = (
        [
            ("ArcName", c.c_char * 1024),
            ("ArcNameW", c.c_wchar * 1024),
            ("FileName", c.c_char * 1024),
            ("FileNameW", c.c_wchar * 1024),
        ]
        + [
            (n, U)
            for n in (
                "Flags",
                "PackSize",
                "PackSizeHigh",
                "UnpSize",
                "UnpSizeHigh",
                "HostOS",
                "FileCRC",
                "FileTime",
                "UnpVer",
                "Method",
                "FileAttr",
            )
        ]
        + [("CmtBuf", c.c_void_p)]
        + [(n, U) for n in ("CmtBufSize", "CmtSize", "CmtState", "DictSize", "HashType")]
        + [("Hash", c.c_char * 32), ("RedirType", U), ("RedirName", c.c_void_p)]
        + [
            (n, U)
            for n in (
                "RedirNameSize",
                "DirTarget",
                "MtimeLow",
                "MtimeHigh",
                "CtimeLow",
                "CtimeHigh",
                "AtimeLow",
                "AtimeHigh",
            )
        ]
        + [
            ("ArcNameEx", c.c_void_p),
            ("ArcNameExSize", U),
            ("FileNameEx", c.c_void_p),
            ("FileNameExSize", U),
            ("Reserved", U * 982),
        ]
    )


class OpenData(c.Structure):
    _pack_ = 1
    _fields_ = [
        ("ArcName", c.c_void_p),
        ("ArcNameW", c.c_wchar_p),
        ("OpenMode", U),
        ("OpenResult", U),
        ("CmtBuf", c.c_void_p),
        ("CmtBufSize", U),
        ("CmtSize", U),
        ("CmtState", U),
        ("Flags", U),
        ("Callback", CALLBACK),
        ("UserData", c.c_ssize_t),
        ("OpFlags", U),
        ("CmtBufW", c.c_void_p),
        ("MarkOfTheWeb", c.c_void_p),
        ("Reserved", U * 23),
    ]


class RarSession:
    def __init__(self, path, credentials, extract=False):
        if sys.platform != "win32" or not dll_path().is_file():
            raise ProviderUnavailableError()
        self.dll = c.WinDLL(str(dll_path()))
        self.dll.RAROpenArchiveEx.argtypes = [c.POINTER(OpenData)]
        self.dll.RAROpenArchiveEx.restype = c.c_void_p
        self.dll.RARReadHeaderEx.argtypes = [c.c_void_p, c.POINTER(Header)]
        self.dll.RARProcessFileW.argtypes = [c.c_void_p, c.c_int, c.c_wchar_p, c.c_wchar_p]
        self.dll.RARCloseArchive.argtypes = [c.c_void_p]
        self.credentials = credentials
        self.output = None
        self.limit = 0
        self.failure = None
        self.password_requests = 0
        self.callback = CALLBACK(self._callback)
        data = OpenData(
            ArcNameW=str(Path(path).absolute()), OpenMode=int(extract), Callback=self.callback
        )
        self.handle = self.dll.RAROpenArchiveEx(c.byref(data))
        self.flags = data.Flags
        try:
            self.check(data.OpenResult)
            if not self.handle:
                raise CorruptedArchiveError()
            if self.flags & 1:  # Multipart archives may trigger external file discovery.
                raise UnsupportedCompressionError()
        except Exception:
            self.close()
            raise

    def _callback(self, msg, user, p1, p2):
        try:
            if msg in (2, 4):
                password = self.credentials.password_bytes() if self.credentials else None
                if password is None:
                    self.failure = PasswordRequiredError
                    return -1
                self.password_requests += 1
                if self.password_requests > 8:
                    self.failure = BadPasswordError
                    return -1
                data = (
                    password.decode("utf-8").encode("utf-16-le") + b"\0\0"
                    if msg == 4
                    else password + b"\0"
                )
                if len(data) > p2 * (2 if msg == 4 else 1):
                    self.failure = BadPasswordError
                    return -1
                c.memmove(p1, data, len(data))
                return 1
            if msg == 1:
                if self.output is not None:
                    if p2 < 0 or len(self.output) + p2 > self.limit:
                        self.failure = ResourceLimitError
                        return -1
                    self.output.extend(c.string_at(p1, p2))
                return 1
            if msg in (0, 3, 5):
                self.failure = ResourceLimitError if msg == 5 else UnsupportedCompressionError
                return -1
            return 0
        except Exception:
            self.failure = CorruptedArchiveError
            return -1

    def check(self, code):
        if self.failure:
            raise self.failure()
        if code:
            error = {
                11: ResourceLimitError,
                14: UnsupportedCompressionError,
                15: ArchiveAccessError,
                18: ArchiveAccessError,
                22: PasswordRequiredError,
                24: BadPasswordError,
                25: ResourceLimitError,
            }.get(code, CorruptedArchiveError)
            raise error()

    def header(self):
        header = Header()
        code = self.dll.RARReadHeaderEx(self.handle, c.byref(header))
        if code == 10:
            return None
        self.check(code)
        if header.DictSize > config.MAX_ENTRY_UNCOMPRESSED_SIZE // 1024:
            raise ResourceLimitError()
        return header

    def process(self, read=False, limit=0):
        self.output = bytearray() if read else None
        self.limit = limit
        try:
            self.check(self.dll.RARProcessFileW(self.handle, 1 if read else 0, None, None))
            return bytes(self.output) if read else None
        finally:
            self.output = None

    def close(self):
        if self.handle:
            self.dll.RARCloseArchive(self.handle)
        self.handle = None
        self.credentials = None
        self.output = None
