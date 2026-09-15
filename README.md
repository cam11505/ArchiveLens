# ArchiveLens 1.1 — archive image and comic viewer

[繁體中文](README.zh-TW.md)

A local, read-only Windows image viewer for ZIP/CBZ, 7Z and RAR/CBR.
Open images without extracting an archive into a folder. No telemetry or cloud service.

## Features

- JPG/JPEG, PNG, WebP, BMP, TIFF (first frame), AVIF, JPEG 2000 and static/animated
  GIF; EXIF orientation where present.
- Plain and ZipCrypto/AES ZIP (128/192/256), encrypted 7Z, encrypted RAR4/RAR5.
- Masked password dialog with show-password, retry and Cancel; memory-only credentials.
- Natural page ordering, fit, physical-pixel 100%, zoom, rotation, pan and fullscreen.
- Single/double pages, optional first-page cover, LTR/RTL reading.
- Lazy thumbnail sidebar with its own bounded cache; click to jump.
- Non-sensitive viewer preferences saved between runs.
- Windows x64 portable ZIP and per-user installer; bundled UnRAR requires no external setup.

## Run

Download the portable ZIP and run `ArchiveLens.exe`, or run the setup EXE.
The installer registers Open With and a Start Menu shortcut; desktop shortcut is optional.
It does not change default archive associations. Keep `_internal` beside the portable EXE.

From source (Python 3.12+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-build.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe scripts/prepare_backends.py
.\.venv\Scripts\python.exe -m archivelens
```

`prepare_backends.py` downloads and verifies the official UnRAR 7.21 SDK on Windows.
ZIP/7Z source use is cross-platform; RAR requires the bundled Windows DLL.
`python -m archivelens.cli book.cbz` lists images; the CLI does not prompt for passwords.

HEIC/HEIF and JPEG XL (JXL) are not supported in v1.2 because the evaluated
Windows backends did not pass the documented licensing, resource-preflight or
package-size gates. See [image backend decisions](docs/IMAGE_BACKENDS.md).

## Controls

| Control | Action |
| --- | --- |
| Ctrl+O / drag archive | Open |
| Left / Right | Previous/next according to reading direction |
| PageUp / Backspace; PageDown / Space | Logical previous; next page/spread |
| Home / End | First / last spread |
| 0 / 1 | Fit complete spread / physical-pixel 100% |
| + / - / Ctrl+wheel | Zoom |
| R / Shift+R | Rotate right / left |
| F / F11 / Esc | Fullscreen / leave fullscreen |
| T | Thumbnail sidebar |

Use View and Reading menus for single/double page, direction and cover settings.

## Limits and supported cases

Single-volume archives only. No nested archives, editing, deletion, extraction, recent-file
history, or persistent passwords. Unsupported compression/encryption gives a recoverable error.
7Z duplicate member names and RAR links/multipart archives are not supported. Solid archives
use conservative requested-page reads without speculative prefetch; large solid files can be slow.
Wrong-password and corruption can be ambiguous for 7Z and some older encrypted formats.

Limits: 100,000 directory entries, 128 MiB per decoded archive member, 40 million image pixels,
256 MiB image cache, 64 MiB thumbnail cache, 32 MiB per GIF stream, and 1 GiB total 7Z/RAR
uncompressed catalog. These are component limits, not a total-process RAM guarantee or sandbox.
Passwords never enter command lines, logs or settings; Python cannot erase every immutable
backend memory copy. See [provider contract](docs/PROVIDERS.md) and [backend record](docs/BACKENDS.md).

## Development and release

```powershell
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python scripts/prepare_licenses.py
python scripts/build_portable.py
python scripts/package_release.py
python scripts/build_installer.py --iscc outputs/inno/ISCC.exe
python scripts/verify_release.py dist/release/ArchiveLens-1.1.0-windows-x64.zip --run
```

Release packaging requires a clean committed tree; use `--development` only for local diagnostics.
[Development](docs/DEVELOPMENT.md), [release QA](docs/V1.1_QA.md), and [v1.1 plan](docs/V1.1_PLAN.md).

## License

ArchiveLens is MIT. Qt and several archive libraries use LGPL; corresponding sources and
licenses are distributed with releases. See [third-party notices](THIRD_PARTY_NOTICES.md).
