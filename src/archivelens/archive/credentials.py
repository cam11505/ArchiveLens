from threading import Lock
from typing import Self


class ArchiveCredentials:
    """Ephemeral password owner; borrowed backend byte copies cannot be zeroized by Python."""

    __slots__ = ("_lock", "_password")

    def __init__(self, password: bytes | None = None) -> None:
        self._lock = Lock()
        self._password: bytearray | None = None
        if password is not None:
            if not isinstance(password, bytes):
                raise TypeError("Password must be bytes")
            self._password = bytearray(password)

    def __repr__(self) -> str:
        return "ArchiveCredentials(<redacted>)"

    def __reduce_ex__(self, protocol: int) -> None:
        raise TypeError("Archive credentials cannot be serialized")

    def password_bytes(self) -> bytes | None:
        """Return a short-lived backend copy; never log or persist it."""
        with self._lock:
            return bytes(self._password) if self._password is not None else None

    def clear(self) -> None:
        with self._lock:
            if self._password is not None:
                self._password[:] = b"\0" * len(self._password)
                self._password = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.clear()
