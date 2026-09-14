# ArchiveLens

Browse images directly inside ZIP / CBZ archives without extracting the entire archive.

[繁體中文](README.zh-TW.md) · Windows 10/11 x64 · Python 3.12+

## Features

- Open ZIP/CBZ from a file dialog, drag and drop, or a command-line argument.
- Browse naturally sorted images with Previous/Next and keyboard navigation.
- Fit images to the window without changing their aspect ratio; respect EXIF orientation.
- Decode individual images in RAM on a background thread. No extracted image files.
- Local, read-only operation: no archive modification, uploads, telemetry or accounts.
- Resource guards and recoverable errors for damaged, encrypted or oversized entries.
- Physical-pixel 100%, zoom, Ctrl+wheel, drag panning, rotation and fullscreen.
- A 256 MiB decoded-image LRU cache and previous/next-two-image background prefetch.

**Version 1.0.0** implements the original ZIP/CBZ viewer MVP. See
[CHANGELOG.md](CHANGELOG.md) and [verification details](docs/DEVELOPMENT.md).

## Installation

**Windows portable:** download `ArchiveLens-1.0.0-windows-x64.zip` from
[GitHub Releases](https://github.com/cam11505/ArchiveLens/releases), extract the
application folder, then run `ArchiveLens.exe`. Keep `_internal` beside the EXE.
Python is included. Extracting this application package is separate from viewing
your photo archives: the viewer never extracts their images to disk.

**From source:** requires Python 3.12+ with pip. From this project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

Dependencies are downloaded during installation. The application itself operates offline.
The portable build is unsigned; code signing and installers are outside v1.0.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-build.txt -e ".[dev,build]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
```

## Run

```powershell
.\.venv\Scripts\python.exe -m archivelens
.\.venv\Scripts\python.exe -m archivelens photos.zip
.\.venv\Scripts\python.exe -m archivelens.cli photos.zip
```

After setting up a source checkout, double-click `Start-ArchiveLens.cmd` to launch.
You may also drop a ZIP/CBZ onto that launcher.
For diagnostic tracebacks, launch from a terminal with `-m archivelens --debug`.

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| Ctrl+O | Open archive |
| Right / PageDown / Space | Next image |
| Left / PageUp / Backspace | Previous image |
| Home / End | First / last image |
| 0 | Fit to window |
| 1 | Actual size: one image pixel per physical screen pixel |
| + / = / - | Zoom in / out |
| R / Shift+R | Rotate right / left |
| F / F11 / Esc | Toggle / exit fullscreen |
| Ctrl+wheel | Zoom at the pointer |
| Mouse wheel / left-button drag | Scroll / pan |
| F1 / Ctrl+Q | Help / quit |

Navigation stops at both ends. Fit mode follows window size. Manual zoom is retained
across pages; rotation resets per image. Opening another archive resets to fit mode.

## Supported Formats

- Archives: ZIP and CBZ only.
- Images: JPG, JPEG, PNG, WebP, BMP, GIF (first frame).
- Unicode filenames follow ZIP UTF-8/CP437 metadata. Legacy Big5/CP932 overrides
  and password input are not available yet.

## Resource Limits

Limits in `src/archivelens/config.py`: 128 MiB uncompressed per entry, a maximum
compression ratio of 1000, 40 million image pixels, and a 256 MiB Qt decoding
allocation limit. These are individual safeguards, not a total process RAM limit.
Highly compressible legitimate images may also be rejected.

Archive opening reads the directory and requested image first. Idle time is used
to prefetch the next two images and previous image. The 256 MiB cache uses actual
decoded allocation sizes and retains at most this four-page window. One active load
and one replaceable pending request prevent an unbounded work queue; current requests
take priority over further prefetch. Closing waits for the active operation to finish.

These guards do not make arbitrary untrusted input a sandbox. Large directories,
slow storage and unusually complex compressed data may still take time. Local
diagnostic logs are bounded to three 1 MiB files under the OS application-data
directory; `--debug` can include local filenames. No image bytes are logged.

## Roadmap

Later versions may add recent files, bookmarks, thumbnails, password entry, RAR/7Z,
animated GIF and comic-reading layouts. None of these are part of v1.0.

## Verification

Tests generate their own tiny archives and images in pytest temporary directories.
They cover lazy reads, unchanged source archives, Unicode, sorting, duplicate names,
resource guards, damaged/encrypted data, Qt decoding and GUI event flows.
GUI tests use Qt's offscreen platform. A native-window smoke check can be run with:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_gui.py
.\.venv\Scripts\python.exe -m archivelens --self-test-report outputs\self-test.json
```

This generates a small synthetic demo CBZ and a screenshot under `outputs/smoke/`.
It is not a substitute for manual Explorer drag-and-drop or multi-monitor/DPI testing.

## Build a Windows Portable Package

```powershell
.\.venv\Scripts\python.exe scripts\prepare_licenses.py
.\.venv\Scripts\python.exe scripts\build_portable.py
.\.venv\Scripts\python.exe scripts\package_release.py
.\.venv\Scripts\python.exe scripts\verify_release.py dist\release\ArchiveLens-1.0.0-windows-x64.zip --run
```

The first command downloads exact-version Qt/PySide source archives and licenses.
The other commands build locally. Build from a clean Git checkout for a release.
The ZIP contains checksums and commit/build information; verification checks every
file and runs the packaged EXE outside the source tree with a sanitized environment.

GitHub Actions runs tests and the packaged self-test on Windows; Linux also runs
the source tests. Only Windows x64 is distributed as a portable binary in v1.0.

## Architecture

- `archive/`: read-only provider registry, capabilities, ephemeral credentials, ZIP/CBZ provider
  and sorted image catalog. See [provider development](docs/PROVIDERS.md).
- `image/`: in-memory Qt image decoding.
- `ui/`: main window and image viewer.
- `utils/`: natural ordering and file extension filtering.
- `config.py`: centralized resource limits.

## License

MIT for ArchiveLens. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for bundled
Python/Qt/PySide licenses and corresponding source archives.
