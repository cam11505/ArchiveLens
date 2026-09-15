"""Probe proposed v1.2 Pillow/native codec backends using memory-only fixtures."""

import importlib.metadata
import io
import json
import sys


def _package_version(name: str, fallback: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return fallback


def main() -> int:
    try:
        import PIL
        from PIL import Image, ImageCms, ImageOps, features
    except (ImportError, OSError) as exc:
        print(json.dumps({"success": False, "error": type(exc).__name__}))
        return 1

    packages = {"Pillow": _package_version("Pillow", PIL.__version__)}
    optional = {"HEIF": False, "JXL": False}
    try:
        import pillow_heif
        from pillow_heif import register_heif_opener

        register_heif_opener(thumbnails=False, decode_threads=1)
        packages["pillow-heif"] = _package_version("pillow-heif", pillow_heif.__version__)
        optional["HEIF"] = True
    except (ImportError, OSError):
        pass
    try:
        import pillow_jxl.JpegXLImagePlugin  # noqa: F401

        packages["pillow-jxl-plugin"] = _package_version("pillow-jxl-plugin", "embedded")
        optional["JXL"] = True
    except (ImportError, OSError):
        pass

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = Image.new("RGBA", (8, 6), (20, 100, 220, 96))
    exif = Image.Exif()
    exif[274] = 6
    cases = {
        "AVIF": {"format": "AVIF", "quality": 100},
        "TIFF": {"format": "TIFF", "compression": "tiff_deflate"},
        "JP2": {"format": "JPEG2000", "irreversible": False},
    }
    if optional["HEIF"]:
        cases["HEIF"] = {"format": "HEIF", "quality": 100}
    if optional["JXL"]:
        cases["JXL"] = {"format": "JXL", "lossless": True}
    results = {}
    for name, options in cases.items():
        buffer = io.BytesIO()
        source.save(buffer, exif=exif, icc_profile=profile, **options)
        encoded = buffer.getvalue()
        with Image.open(io.BytesIO(encoded)) as decoded:
            decoded.load()
            transposed = ImageOps.exif_transpose(decoded)
            results[name] = {
                "bytes": len(encoded),
                "size": list(decoded.size),
                "mode": decoded.mode,
                "alpha": "A" in decoded.getbands(),
                "icc": bool(decoded.info.get("icc_profile")),
                "orientation_tag": decoded.getexif().get(274),
                "orientation_size": list(transposed.size),
                "frames": getattr(decoded, "n_frames", 1),
            }
        try:
            with Image.open(io.BytesIO(encoded[: max(1, len(encoded) // 4)])) as malformed:
                malformed.load()
        except (OSError, RuntimeError, SyntaxError, ValueError):
            results[name]["malformed_rejected"] = True
        else:
            results[name]["malformed_rejected"] = False

    report = {
        # TIFF ships through Qt's qTiff plugin; Pillow TIFF is informational only.
        "success": all(results[name]["malformed_rejected"] for name in results.keys() - {"TIFF"}),
        "python": sys.version.split()[0],
        "packages": packages,
        "optional": optional,
        "features": {
            name: bool(features.check(name)) for name in ("avif", "jpg_2000", "libtiff", "webp")
        },
        "formats": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
