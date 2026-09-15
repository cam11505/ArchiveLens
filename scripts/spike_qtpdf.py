"""Reproducible Windows QtPdf backend probe for v1.2 issue #27."""

import argparse
import json
import os
import platform
import time
from pathlib import Path

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtPdf import QPdfDocument, QPdfPageRenderer

from archivelens import config
from archivelens.diagnostic_fixtures import password_pdf_fixture, write_pdf_fixture


def load_render(path: Path, expected_pages: int, render_size: QSize) -> dict:
    document = QPdfDocument()
    started = time.perf_counter()
    error = document.load(str(path))
    load_ms = (time.perf_counter() - started) * 1000
    assert error is QPdfDocument.Error.None_
    assert document.pageCount() == expected_pages
    point_size = document.pagePointSize(0)
    assert render_size.width() * render_size.height() <= config.MAX_PDF_RENDER_PIXELS
    started = time.perf_counter()
    image = document.render(0, render_size)
    render_ms = (time.perf_counter() - started) * 1000
    assert not image.isNull() and image.size() == render_size
    result = {
        "pages": document.pageCount(),
        "label": document.pageLabel(0),
        "points": [point_size.width(), point_size.height()],
        "render_pixels": image.width() * image.height(),
        "load_ms": round(load_ms, 3),
        "render_ms": round(render_ms, 3),
    }
    document.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/qtpdf-spike"))
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication([])
    assert app is not None
    args.output.mkdir(parents=True, exist_ok=True)
    paths = {name: args.output / f"{name}.pdf" for name in ("one", "many", "huge", "protected")}
    write_pdf_fixture(paths["one"])
    write_pdf_fixture(paths["many"], 125)
    write_pdf_fixture(paths["huge"], page_mm=(2000, 2000))
    paths["protected"].write_bytes(password_pdf_fixture())
    results = {
        "python": platform.python_version(),
        "pyside": pyside_version,
        "qt_pdf_dll": str(Path(__file__).parents[1] / ".venv/Lib/site-packages/PySide6/Qt6Pdf.dll"),
        "limits": {
            "pages": config.MAX_PDF_PAGES,
            "render_pixels": config.MAX_PDF_RENDER_PIXELS,
            "render_edge": config.MAX_PDF_RENDER_EDGE,
            "pending_per_worker": config.MAX_PDF_PENDING_RENDERS,
        },
        "renderer_modes": [mode.name for mode in QPdfPageRenderer.RenderMode],
        "one": load_render(paths["one"], 1, QSize(512, 724)),
        "many": load_render(paths["many"], 125, QSize(144, 204)),
        "huge": load_render(paths["huge"], 1, QSize(1024, 1024)),
    }
    protected = QPdfDocument()
    no_password = protected.load(str(paths["protected"]))
    protected.setPassword("wrong")
    wrong_password = protected.load(str(paths["protected"]))
    protected.setPassword("reader-secret")
    correct_password = protected.load(str(paths["protected"]))
    assert no_password is wrong_password is QPdfDocument.Error.IncorrectPassword
    assert correct_password is QPdfDocument.Error.None_
    assert not protected.render(0, QSize(256, 256)).isNull()
    protected.close()
    protected.setPassword("")
    results["password"] = {
        "missing": no_password.name,
        "wrong": wrong_password.name,
        "correct": correct_password.name,
        "cleared": protected.password() == "",
    }
    report = args.output / "report.json"
    report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
