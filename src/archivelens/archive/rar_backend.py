"""Platform-neutral discovery and loading for the bundled UnRAR library."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from archivelens.platform_paths import native_backend_path


@dataclass(frozen=True)
class RarBackend:
    """Describe one supported in-process UnRAR ABI implementation."""

    platform: str
    filename: str
    loader: Callable[[str], object]
    callback_factory: Callable[..., type]

    def path(self, *, frozen: bool | None = None, bundle_root: str | Path | None = None) -> Path:
        return native_backend_path(self.filename, frozen=frozen, bundle_root=bundle_root)

    @property
    def available(self) -> bool:
        return self.path().is_file()

    def load(self):
        return self.loader(str(self.path()))


def backend_for_platform(platform: str | None = None) -> RarBackend | None:
    """Return the bundled backend contract for a Python platform identifier."""
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        return RarBackend(
            platform="windows-x64",
            filename="UnRAR64.dll",
            loader=getattr(ctypes, "WinDLL", ctypes.CDLL),
            callback_factory=getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE),
        )
    if platform == "darwin":
        return RarBackend(
            platform="macos",
            filename="libunrar.dylib",
            loader=ctypes.CDLL,
            callback_factory=ctypes.CFUNCTYPE,
        )
    if platform.startswith("linux"):
        return RarBackend(
            platform="linux",
            filename="libunrar.so",
            loader=ctypes.CDLL,
            callback_factory=ctypes.CFUNCTYPE,
        )
    return None


def current_backend() -> RarBackend | None:
    return backend_for_platform()


def backend_available() -> bool:
    backend = current_backend()
    return backend is not None and backend.available
