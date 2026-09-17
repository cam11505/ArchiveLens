# ArchiveLens 1.2 — local image, comic, folder and PDF reader

[繁體中文](README.zh-TW.md)

A local, read-only Windows reader for image archives, image folders and PDF files.
No telemetry, cloud service, source modification or whole-book extraction.

## Features

- ZIP/CBZ, 7Z, RAR/CBR, flat/recursive image folders and local PDF documents.
- JPG/JPEG, PNG, WebP, BMP, TIFF (first frame), AVIF, JPEG 2000 and
  static/animated GIF; EXIF orientation where supported.
- Plain and ZipCrypto/AES ZIP, encrypted 7Z/RAR, and supported password PDFs.
  Credentials remain in memory for the current session and are never persisted.
- Resume, bounded recent-reading history and application-level page bookmarks.
- Single/double pages, optional cover, LTR/RTL navigation and lazy thumbnails.
- Fit Page/Spread, Fit Width, Fit Height, physical-pixel 100%, zoom, rotation,
  pan and fullscreen.
- Conservative automatic black/white-border trim and predictable manual
  per-edge percentage trim. All trim/rotation operations are display-only.
- Windows x64 portable ZIP and per-user installer with bundled codecs, UnRAR and
  QtPdf; no external reader, decoder or archive utility is required.

## Run

Download the portable ZIP and run `ArchiveLens.exe`, or run the setup EXE.
Keep `_internal` beside the portable executable. The installer registers ArchiveLens
under Open With for supported archives and PDF without changing default associations.

From source (Python 3.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-build.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe scripts/prepare_backends.py
.\.venv\Scripts\python.exe -m archivelens
```

`prepare_backends.py` downloads and verifies the official UnRAR 7.21 SDK on Windows.
The GUI opens all supported content sources. The compatibility CLI only lists images
inside archive files and does not prompt for passwords.

HEIC/HEIF and JPEG XL (JXL) are not supported in v1.2 because the evaluated Windows
backends did not pass the documented licensing, resource-preflight or package-size
gates. See [image backend decisions](docs/IMAGE_BACKENDS.md).

## Controls

| Control | Action |
| --- | --- |
| Ctrl+O | Open a supported archive or PDF file |
| Ctrl+Shift+O | Open an image folder |
| Drag one supported file or folder | Open or safely switch the current content source |
| Left / Right | Previous/next according to reading direction |
| PageUp / Backspace; PageDown / Space | Logical previous/next page or spread |
| Home / End | First/last spread |
| 0 / 2 / 3 / 1 | Fit Page/Spread / Width / Height / physical-pixel 100% |
| + / - / Ctrl+wheel | Zoom |
| R / Shift+R | Rotate right/left |
| F / F11 / Esc | Fullscreen/leave fullscreen |
| T | Thumbnail sidebar |
| Ctrl+B | Add/remove the current page bookmark |

Use File > Open Content for the native file/folder choices. Use View for page layout, fit and border trim. Use Reading for direction, cover,
recursive-folder mode, bookmarks and recent history.

## Limits and supported cases

Single-volume archives only. No nested archives, editing, PDF annotations/forms/OCR,
decrypted persistent cache or password persistence. Unsupported compression/encryption
returns a recoverable error. 7Z duplicate names and RAR links/multipart archives are
not supported. Solid archives avoid speculative prefetch and can be slower.

- Up to 100,000 archive/folder/PDF entries or pages; recursive folders are limited
  to 32 levels and never follow symlinks, junctions or reparse points.
- 128 MiB per archive member, 1 GiB solid catalog and 40 million decoded image pixels.
- PDF renders are capped at 16 million pixels and 8,192 pixels per edge, with one
  replaceable pending request per worker and no speculative PDF prefetch.
- Image and thumbnail caches are capped at 256 MiB and 64 MiB; GIF streams at 32 MiB.
- Auto trim samples at most a 512-pixel-long preview and conservatively trims only
  low-variance neutral light/dark borders.

These are component limits, not a total-process RAM guarantee or malware sandbox.
Passwords never enter command lines, logs, settings, state files or manifests; Python
and native libraries cannot guarantee erasure of every immutable in-process copy.
See [provider contract](docs/PROVIDERS.md), [display policy](docs/READER_DISPLAY.md),
[archive backends](docs/BACKENDS.md), and [QtPdf backend](docs/QTPDF_BACKEND.md).

## Development and release

```powershell
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python scripts/license_audit.py --check
python scripts/prepare_licenses.py
python scripts/build_portable.py
python -m build --no-isolation --outdir dist/release
python scripts/package_release.py
python scripts/verify_release.py dist/release/ArchiveLens-1.2.0-windows-x64.zip --run
python scripts/build_installer.py --iscc outputs/inno/ISCC.exe
python scripts/verify_installer.py dist/release/ArchiveLens-1.2.0-setup-x64.exe
python scripts/release_checksums.py
```

Release packaging requires a clean committed tree. `--development` is only for local
diagnostics. See [development](docs/DEVELOPMENT.md), [v1.2 QA](docs/V1.2_QA.md), and
[v1.2 plan](docs/V1.2_PLAN.md).

## License

**ArchiveLens application source is MIT-licensed open-source software.** Official
binary distributions are **mixed-license distributions**: Python, Qt/PySide, Pillow,
archive libraries, UnRAR, Microsoft runtime components and other bundled software retain
their own terms. In particular, the bundled UnRAR component is redistributed under its
upstream freeware license and is not classified by ArchiveLens as FOSS.

Release artifacts include exact notices/corresponding sources plus an SPDX SBOM and an
audited dependency policy. See [licensing and distribution policy](docs/LICENSING.md),
[third-party notices](THIRD_PARTY_NOTICES.md), and `license-policy.json`.
