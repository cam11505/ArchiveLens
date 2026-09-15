# ArchiveLens v1.2 image decoder and backend record

Decision date: **2026-09-15**

Test host: Windows 11 x64 build 22631, Python 3.12.14, PySide6/Qt 6.11.2,
PyInstaller 6.22.3. The probe is reproducible with
`scripts/spike_image_backends.py` after installing the exact candidate packages.

## Decoder boundary

`image.decoders.DecoderRegistry` is the only raster-backend selection boundary.
Workers pass encoded bytes, the source extension and an optional thumbnail bound.
Each decoder advertises its extensions, animation support, memory-buffer support
and runtime availability. UI/content providers do not select codec libraries.

All decoders must apply `MAX_IMAGE_PIXELS` before retaining a decoded image and
must map native/backend failures to sanitized `ArchiveLensError` subclasses.
Archive/folder byte limits still apply before decode. A backend that fully allocates
an attacker-declared image before dimensions can be checked is not approved merely
because it can decode a valid sample.

## Decisions

| Format | v1.2 decision | Backend | Notes |
| --- | --- | --- | --- |
| JPEG/PNG/WebP/BMP/GIF | Keep | Qt `QImageReader` 6.11.2 | Existing behavior; memory decode, orientation and Qt allocation limit retained. |
| TIFF (`.tif`, `.tiff`) | Approve | Qt `qTiff` 6.11.2 | Bundled Qt plugin (`qtiff.dll`, 445,752 bytes on the spike host). First frame only in v1.2. |
| AVIF (`.avif`) | Approve | Pillow 12.3.0 `_avif` | Windows cp312 wheel; static 8-bit display path. |
| JPEG 2000 (`.jp2`, `.j2k`, `.j2c`) | Approve | Pillow 12.3.0/OpenJPEG | Windows cp312 wheel; static 8-bit display path. |
| HEIC/HEIF | Defer | None approved | Qt has no Windows HEIC backend. `pillow-heif` wheel is GPLv2 because it bundles x265. |
| JPEG XL (`.jxl`) | Defer | None approved | `pillow-jxl-plugin` is GPL-3.0-or-later. `imagecodecs` is permissive but fails the size/preflight/package-cost gate. |

User documentation must say HEIC/HEIF and JXL are unavailable in v1.2. They remain
recognized only if a future reviewed backend meets the same packaging, resource and
license requirements. Do not silently substitute either rejected wheel.

## Windows spike evidence

### Qt TIFF

- The installed Qt plugin list exposed `tif` and `tiff`.
- An in-memory 8 x 6 RGBA TIFF decoded with alpha.
- A 25% truncated fixture returned a null image with `Unable to read image data`.
- Qt Image Formats documents bundled libtiff and LGPL/commercial deployment terms.
- `scripts/ArchiveLens.spec` includes `qtiff.dll`; the packaged self-test decoded
  TIFF successfully with Python removed from `PATH`.

### Pillow 12.3.0

The official `pillow-12.3.0-cp312-cp312-win_amd64.whl` is 7,227,137 bytes and
reports `avif`, `jpg_2000` and `libtiff` features enabled. The isolated installed
tree was 16,147,391 bytes.

Memory-only RGBA probes produced:

| Format | Alpha | ICC | EXIF orientation | Truncated input |
| --- | --- | --- | --- | --- |
| AVIF | Preserved | Preserved | Tag 6 transposed from 8 x 6 to 6 x 8 | Rejected |
| JP2 | Preserved | Not preserved by the tested round trip | No orientation tag | Rejected |

The approved v1.2 adapter must inspect Pillow dimensions before `load()`, enforce
`MAX_IMAGE_PIXELS`, apply `ImageOps.exif_transpose`, convert to an owned `QImage`,
and sanitize `OSError`, `SyntaxError`, `ValueError`, `MemoryError` and native errors.
16-bit/HDR fidelity is not claimed: v1.2 converts the approved formats to an
8-bit display image. Multi-frame AVIF/JP2 is not claimed.

The selected Pillow-only PyInstaller one-folder spike ran successfully with a
clean `PATH` containing only Windows System32. Its complete diagnostic directory
was 36,540,534 bytes. Required hidden imports are `PIL.AvifImagePlugin` and
`PIL.Jpeg2KImagePlugin`; the normal PyInstaller Pillow hook collects other image
plugins. Final release packaging must include Pillow's license and exact source.

### Rejected HEIC/HEIF candidate

`pillow-heif 1.7.0` has a Python 3.12 Windows x64 wheel and decoded the in-memory
RGBA/ICC fixture. However, its own `LICENSES_bundled.txt` states that binary wheels
are GPLv2 because they bundle GPLv2 x265 in addition to LGPLv3 libheif/libde265.
The wheel also carried MinGW runtime DLLs. Shipping that binary would change the
project's redistribution obligations, so it is rejected for v1.2. Building and
auditing a decode-only libheif stack without x265 is deferred.

Qt 6.11 Image Formats explicitly lists HEIC as unsupported outside Apple operating
systems, so Qt is not a packaged Windows fallback.

### Rejected JPEG XL candidates

- `pillow-jxl-plugin 1.3.8` decoded RGBA/ICC and rejected malformed input, but its
  wheel metadata declares GPL-3.0-or-later. It is rejected.
- `imagecodecs 2026.8.16` with libjxl 0.12.0 is BSD-3-Clause and decoded an in-memory
  RGBA JXL. It requires NumPy and occupied 105,039,376 installed bytes in the spike.
  More importantly, its public `jpegxl_decode` API exposes no dimension-only probe;
  decoding allocates the output array before ArchiveLens can enforce its pixel
  limit. It is rejected for the v1.2 in-process decoder.

## Packaging and license sources

- Qt image formats: <https://doc.qt.io/qt-6/qtimageformats-index.html>
- Qt `QImageReader`: <https://doc.qt.io/qt-6/qimagereader.html>
- Pillow documentation/source: <https://pillow.readthedocs.io/>
- Pillow source: <https://github.com/python-pillow/Pillow>
- pillow-heif source: <https://github.com/bigcat88/pillow_heif>
- pillow-jxl-plugin source: <https://github.com/Isotr0py/pillow-jpegxl-plugin>
- imagecodecs source: <https://github.com/cgohlke/imagecodecs>

Issue #26 produced a complete development package containing 499 files and
121,263,209 uncompressed bytes; its manifest-backed ZIP was 49,498,060 bytes.
`verify_release.py --run --allow-development` passed with a `PATH` limited to
Windows system directories and decoded AVIF, JP2 and TIFF. The inventory contains
Pillow `_avif`/`_imaging`, Qt `qtiff.dll`, Pillow's license, and the verified
`pillow-12.3.0.tar.gz` source (SHA-256
`3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce`).
Release hardening in #30 will repeat this against the final clean v1.2 commit.
