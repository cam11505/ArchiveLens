"""Qualify the shipped v1.2.2 raster and QtPdf paths on macOS arm64."""

from __future__ import annotations

import argparse
import io
import json
import platform
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageCms
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication

from archivelens import __version__, config
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.content.archive_provider import ArchiveContentProvider
from archivelens.content.base import PageLoadRequest
from archivelens.content.factory import DEFAULT_CONTENT_REGISTRY
from archivelens.content.folder_provider import FolderContentProvider
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.diagnostic_fixtures import password_pdf_fixture, write_pdf_fixture
from archivelens.errors import ArchiveLensError, BadPasswordError, PasswordRequiredError
from archivelens.image.decoders import DEFAULT_DECODER_REGISTRY
from archivelens.platform_paths import is_frozen_runtime

SHIPPED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".avif",
    ".jp2",
    ".j2k",
    ".j2c",
)
DEFERRED_EXTENSIONS = (".heic", ".heif", ".jxl")


def _encode_fixture(fmt: str, *, orientation: int | None = None, icc: bool = False) -> bytes:
    mode = "RGB" if fmt in {"JPEG", "BMP"} else "RGBA"
    image = Image.new(mode, (8, 6), (32, 96, 192) if mode == "RGB" else (32, 96, 192, 127))
    options: dict[str, object] = {}
    if fmt == "WEBP":
        options["lossless"] = True
    elif fmt == "AVIF":
        options["quality"] = 100
    elif fmt == "JPEG2000":
        options["irreversible"] = False
    elif fmt == "TIFF":
        options["compression"] = "tiff_deflate"
    elif fmt == "JPEG":
        options["quality"] = 95
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    if icc:
        options["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    stream = io.BytesIO()
    image.save(stream, fmt, **options)
    return stream.getvalue()


def _fixtures() -> dict[str, bytes]:
    formats = {
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".png": "PNG",
        ".webp": "WEBP",
        ".bmp": "BMP",
        ".gif": "GIF",
        ".tif": "TIFF",
        ".tiff": "TIFF",
        ".avif": "AVIF",
        ".jp2": "JPEG2000",
        ".j2k": "JPEG2000",
        ".j2c": "JPEG2000",
    }
    return {extension: _encode_fixture(fmt) for extension, fmt in formats.items()}


def _decode_matrix(fixtures: dict[str, bytes]) -> dict[str, object]:
    results = {}
    for extension, payload in fixtures.items():
        full = DEFAULT_DECODER_REGISTRY.decode(payload, extension=extension)
        thumbnail = DEFAULT_DECODER_REGISTRY.decode(payload, thumbnail_size=4, extension=extension)
        malformed_rejected = False
        try:
            DEFAULT_DECODER_REGISTRY.decode(b"not valid media", extension=extension)
        except ArchiveLensError:
            malformed_rejected = True
        results[extension] = {
            "full_size": list(full.size().toTuple()),
            "thumbnail_size": list(thumbnail.size().toTuple()),
            "alpha": full.hasAlphaChannel(),
            "malformed_rejected": malformed_rejected,
        }

    avif = _encode_fixture("AVIF", orientation=6, icc=True)
    oriented = DEFAULT_DECODER_REGISTRY.decode(avif, extension=".avif")
    results["avif_metadata"] = {
        "orientation_size": list(oriented.size().toTuple()),
        "icc": oriented.colorSpace().isValid(),
        "alpha": oriented.hasAlphaChannel(),
    }
    old_limit = config.MAX_IMAGE_PIXELS
    try:
        config.MAX_IMAGE_PIXELS = 10
        size_guard = False
        try:
            DEFAULT_DECODER_REGISTRY.decode(fixtures[".avif"], extension=".avif")
        except ArchiveLensError:
            size_guard = True
    finally:
        config.MAX_IMAGE_PIXELS = old_limit
    results["resource_guard"] = size_guard
    return results


def _provider_matrix(root: Path, fixtures: dict[str, bytes]) -> dict[str, object]:
    folder = root / "media"
    folder.mkdir()
    for index, (extension, payload) in enumerate(fixtures.items(), 1):
        (folder / f"{index:02d}{extension}").write_bytes(payload)
    archive = root / "media.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.iterdir()):
            output.write(path, path.name)

    results = {}
    for name, provider in (
        ("folder", FolderContentProvider()),
        ("zip", ArchiveContentProvider(DEFAULT_CONTENT_REGISTRY.archive_registry)),
    ):
        with provider:
            provider.open(folder if name == "folder" else archive)
            pages = provider.list_pages()
            decoded = []
            for page in pages:
                content = provider.load_page(page, PageLoadRequest())
                image = DEFAULT_DECODER_REGISTRY.decode(content.encoded, extension=page.extension)
                thumb = DEFAULT_DECODER_REGISTRY.decode(
                    content.encoded, thumbnail_size=4, extension=page.extension
                )
                decoded.append(not image.isNull() and max(thumb.width(), thumb.height()) <= 4)
            results[name] = {"pages": len(pages), "decoded": all(decoded)}
    return results


def _pdf_matrix(root: Path) -> dict[str, object]:
    ordinary = root / "ordinary.pdf"
    many = root / "many.pdf"
    protected = root / "protected.pdf"
    malformed = root / "malformed.pdf"
    write_pdf_fixture(ordinary)
    write_pdf_fixture(many, pages=125)
    protected.write_bytes(password_pdf_fixture())
    malformed.write_bytes(b"%PDF-1.7\nmalformed")

    with PdfContentProvider() as provider:
        provider.open(ordinary)
        page = provider.list_pages()[0]
        thumbnail = provider.load_page(page, PageLoadRequest(thumbnail_size=144)).image
        high_dpi = provider.load_page(page, PageLoadRequest(render_size=(4096, 4096))).image
        corner = high_dpi.pixelColor(0, 0)
        ordinary_result = {
            "thumbnail_size": list(thumbnail.size().toTuple()),
            "high_dpi_size": list(high_dpi.size().toTuple()),
            "high_dpi_pixels": high_dpi.width() * high_dpi.height(),
            "opaque_white_background": not high_dpi.hasAlphaChannel()
            and corner.getRgb() == (255, 255, 255, 255),
        }

    with PdfContentProvider() as provider:
        provider.open(many)
        many_pages = len(provider.list_pages())

    missing_rejected = wrong_rejected = False
    try:
        PdfContentProvider().open(protected)
    except PasswordRequiredError:
        missing_rejected = True
    try:
        with ArchiveCredentials(b"wrong") as credentials:
            PdfContentProvider().open(protected, credentials=credentials)
    except BadPasswordError:
        wrong_rejected = True
    with ArchiveCredentials(b"reader-secret") as credentials, PdfContentProvider() as provider:
        provider.open(protected, credentials=credentials)
        password_rendered = not provider.load_page(
            provider.list_pages()[0], PageLoadRequest(render_size=(512, 512))
        ).image.isNull()

    malformed_rejected = False
    try:
        PdfContentProvider().open(malformed)
    except ArchiveLensError:
        malformed_rejected = True
    return {
        "ordinary": ordinary_result,
        "many_pages": many_pages,
        "password": {
            "missing_rejected": missing_rejected,
            "wrong_rejected": wrong_rejected,
            "correct_rendered": password_rendered,
        },
        "malformed_rejected": malformed_rejected,
        "limits": {
            "pages": config.MAX_PDF_PAGES,
            "render_pixels": config.MAX_PDF_RENDER_PIXELS,
            "render_edge": config.MAX_PDF_RENDER_EDGE,
            "pending_per_worker": config.MAX_PDF_PENDING_RENDERS,
        },
    }


def build_report() -> dict[str, object]:
    app = QApplication.instance() or QApplication(["archivelens-v13-media"])
    assert app is not None
    fixtures = _fixtures()
    with tempfile.TemporaryDirectory(prefix="archivelens-v13-media-") as directory:
        root = Path(directory)
        raster = _decode_matrix(fixtures)
        providers = _provider_matrix(root, fixtures)
        pdf = _pdf_matrix(root)

    supported = set(DEFAULT_DECODER_REGISTRY.supported_extensions)
    required = set(SHIPPED_EXTENSIONS)
    success = (
        required <= supported
        and not (set(DEFERRED_EXTENSIONS) & supported)
        and all(raster[extension]["malformed_rejected"] for extension in SHIPPED_EXTENSIONS)
        and raster["avif_metadata"]
        == {
            "orientation_size": [6, 8],
            "icc": True,
            "alpha": True,
        }
        and raster["resource_guard"]
        and all(
            item["pages"] == len(SHIPPED_EXTENSIONS) and item["decoded"]
            for item in providers.values()
        )
        and pdf["ordinary"]["opaque_white_background"]
        and pdf["many_pages"] == 125
        and all(pdf["password"].values())
        and pdf["malformed_rejected"]
    )
    return {
        "schema_version": 1,
        "success": success,
        "archivelens_version": __version__,
        "runtime": {
            "frozen": is_frozen_runtime(),
            "python": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
            "executable": str(Path(sys.executable).resolve()),
        },
        "dependencies": {"pyside6": pyside_version, "qt": qVersion(), "pillow": Image.__version__},
        "decoder_extensions": {
            "required": list(SHIPPED_EXTENSIONS),
            "available": sorted(supported),
            "deferred_absent": sorted(set(DEFERRED_EXTENSIONS) - supported),
        },
        "raster": raster,
        "providers": providers,
        "pdf": pdf,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-machine", choices=("arm64", "x86_64", "AMD64"))
    parser.add_argument("--require-version")
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args()
    report = build_report()
    report["success"] = bool(
        report["success"]
        and (args.require_machine is None or report["runtime"]["machine"] == args.require_machine)
        and (args.require_version is None or __version__ == args.require_version)
        and (not args.require_frozen or report["runtime"]["frozen"])
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
