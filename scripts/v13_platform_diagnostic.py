"""Collect deterministic v1.3 platform-spike evidence in source or frozen mode."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from PIL import __version__ as pillow_version
from PySide6 import QtPdf
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QLibraryInfo, QStandardPaths, qVersion
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from archivelens import __version__
from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.archive.rar_provider import RarArchiveProvider
from archivelens.image.decoders import DEFAULT_DECODER_REGISTRY


def build_report() -> dict[str, object]:
    """Return JSON-safe runtime and backend evidence for issue #42."""
    app = QApplication.instance() or QApplication(["archivelens-v13-diagnostic"])
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0)
    if image.isNull():
        raise RuntimeError("Qt image allocation failed")
    widget = QWidget()
    widget.setObjectName("archivelens-v13-diagnostic")

    standard_paths = {
        name: QStandardPaths.writableLocation(location)
        for name, location in (
            ("app_data", QStandardPaths.StandardLocation.AppDataLocation),
            ("cache", QStandardPaths.StandardLocation.CacheLocation),
            ("config", QStandardPaths.StandardLocation.AppConfigLocation),
            ("temp", QStandardPaths.StandardLocation.TempLocation),
        )
    }
    return {
        "schema_version": 1,
        "archivelens_version": __version__,
        "runtime": {
            "frozen": bool(getattr(sys, "frozen", False)),
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "executable": str(Path(sys.executable).resolve()),
        },
        "dependencies": {
            "pyside6": pyside_version,
            "qt": qVersion(),
            "pillow": pillow_version,
        },
        "qt": {
            "platform_plugin": app.platformName(),
            "plugins_path": QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath),
            "standard_paths": standard_paths,
            "qimage_smoke": True,
            "qwidget_smoke": widget.objectName() == "archivelens-v13-diagnostic",
            "qtpdf_smoke": hasattr(QtPdf, "QPdfDocument"),
        },
        "backends": {
            "archive_registered": sorted(DEFAULT_REGISTRY.registered_extensions),
            "archive_available": sorted(DEFAULT_REGISTRY.supported_extensions),
            "decoder_registered": sorted(DEFAULT_DECODER_REGISTRY.registered_extensions),
            "decoder_available": sorted(DEFAULT_DECODER_REGISTRY.supported_extensions),
            "rar": {
                "available": RarArchiveProvider.capabilities.available,
                "format_name": RarArchiveProvider.capabilities.format_name,
                "extensions": sorted(RarArchiveProvider.capabilities.extensions),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-machine", choices=("arm64", "x86_64", "AMD64"))
    args = parser.parse_args()

    report = build_report()
    actual_machine = report["runtime"]["machine"]
    success = args.require_machine is None or actual_machine == args.require_machine
    report["success"] = success
    report["required_machine"] = args.require_machine

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
