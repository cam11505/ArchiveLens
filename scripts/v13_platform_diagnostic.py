"""Collect deterministic v1.3 platform-spike evidence in source or frozen mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

from PIL import __version__ as pillow_version
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QLibraryInfo, QStandardPaths, qVersion
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from archivelens import __version__
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.archive.rar_backend import current_backend
from archivelens.archive.rar_provider import RarArchiveProvider
from archivelens.content.base import PageLoadRequest
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.diagnostic_fixtures import write_pdf_fixture
from archivelens.image.decoders import DEFAULT_DECODER_REGISTRY
from archivelens.platform_paths import is_frozen_runtime, runtime_root


def _pdf_render_smoke() -> dict[str, object]:
    """Exercise the production QtPdf path, including opaque page compositing."""
    with tempfile.TemporaryDirectory(prefix="archivelens-v13-pdf-") as directory:
        path = Path(directory) / "diagnostic.pdf"
        write_pdf_fixture(path)
        with PdfContentProvider() as provider:
            provider.open(path)
            pages = provider.list_pages()
            page = provider.load_page(pages[0], PageLoadRequest(render_size=(320, 320)))
            image = page.image
            if image is None or image.isNull():
                raise RuntimeError("QtPdf production render failed")
            corner = image.pixelColor(0, 0)
            return {
                "pages": len(pages),
                "width": image.width(),
                "height": image.height(),
                "has_alpha_channel": image.hasAlphaChannel(),
                "corner_rgba": [corner.red(), corner.green(), corner.blue(), corner.alpha()],
                "opaque_white_background": not image.hasAlphaChannel()
                and corner.getRgb() == (255, 255, 255, 255),
            }


def _rar_smoke() -> dict[str, object]:
    """Exercise real RAR3/RAR5, solid and encrypted reads without extraction."""
    if not RarArchiveProvider.capabilities.available:
        return {"success": False, "reason": "backend unavailable"}
    fixture_root = runtime_root() / (
        "self-test-rar" if is_frozen_runtime() else "tests/fixtures/rar"
    )
    cases = {}
    for name in ("rar3-solid.rar", "rar5-solid.rar", "rar5-psw.rar"):
        with ArchiveCredentials(b"password") as credentials, RarArchiveProvider() as provider:
            provider.open(fixture_root / name, credentials=credentials)
            entries = provider.list_entries()
            payloads = [provider.read_entry(entry) for entry in reversed(entries)]
            cases[name] = {
                "entries": len(entries),
                "sha256": hashlib.sha256(b"".join(payloads)).hexdigest(),
            }
    return {"success": True, "cases": cases}


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
    rar_backend = current_backend()
    rar_path = rar_backend.path() if rar_backend is not None else None
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
            "qtpdf_smoke": True,
            "qtpdf_production_render": _pdf_render_smoke(),
        },
        "backends": {
            "archive_registered": sorted(DEFAULT_REGISTRY.registered_extensions),
            "archive_available": sorted(DEFAULT_REGISTRY.supported_extensions),
            "decoder_registered": sorted(DEFAULT_DECODER_REGISTRY.registered_extensions),
            "decoder_available": sorted(DEFAULT_DECODER_REGISTRY.supported_extensions),
            "rar": {
                "available": RarArchiveProvider.capabilities.available,
                "backend_path": str(rar_path) if rar_path is not None else None,
                "backend_platform": rar_backend.platform if rar_backend is not None else None,
                "backend_present": rar_path.is_file() if rar_path is not None else False,
                "format_name": RarArchiveProvider.capabilities.format_name,
                "extensions": sorted(RarArchiveProvider.capabilities.extensions),
                "smoke": _rar_smoke(),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-machine", choices=("arm64", "x86_64", "AMD64"))
    parser.add_argument("--require-version")
    parser.add_argument("--require-rar", action="store_true")
    args = parser.parse_args()

    report = build_report()
    actual_machine = report["runtime"]["machine"]
    machine_matches = args.require_machine is None or actual_machine == args.require_machine
    version_matches = args.require_version is None or __version__ == args.require_version
    pdf_render = report["qt"]["qtpdf_production_render"]
    rar_matches = not args.require_rar or (
        report["backends"]["rar"]["available"] and report["backends"]["rar"]["smoke"]["success"]
    )
    success = (
        machine_matches
        and version_matches
        and rar_matches
        and pdf_render["opaque_white_background"]
    )
    report["success"] = success
    report["required_machine"] = args.require_machine
    report["required_version"] = args.require_version
    report["required_rar"] = args.require_rar

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
