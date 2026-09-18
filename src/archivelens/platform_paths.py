"""Narrow source/frozen and writable-location seams used by production code."""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_root(*, frozen: bool | None = None, bundle_root: str | Path | None = None) -> Path:
    """Return the deterministic root used to discover bundled runtime files."""
    is_frozen = is_frozen_runtime() if frozen is None else frozen
    if is_frozen:
        root = bundle_root if bundle_root is not None else getattr(sys, "_MEIPASS", None)
        if root is None:
            raise RuntimeError("Frozen runtime root is unavailable")
        return Path(root).resolve()
    return Path(__file__).resolve().parents[2]


def native_backend_path(
    filename: str, *, frozen: bool | None = None, bundle_root: str | Path | None = None
) -> Path:
    root = runtime_root(frozen=frozen, bundle_root=bundle_root)
    is_frozen = is_frozen_runtime() if frozen is None else frozen
    directory = "native" if is_frozen else "outputs/backends"
    return root / directory / filename


def writable_location(location: QStandardPaths.StandardLocation) -> Path:
    return Path(QStandardPaths.writableLocation(location))
