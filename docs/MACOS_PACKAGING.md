# macOS arm64 application packaging

## Scope

This document records ArchiveLens v1.3 issue #46. The immutable parity baseline is
`v1.2.2` / `bb0197b0291707287517ba8bdfc3a10ce1ad1149`.

Issue #46 produces a self-contained **development** `ArchiveLens.app` on the pinned
GitHub-hosted `macos-15` Apple Silicon runner. It reuses the RAR decision from #44
and the shipped-codec/QtPdf qualification from #45; it does not repeat those spikes.

Explicit exclusions:

- no DMG, Developer ID identity, hardened-runtime policy, notarization, or staple (#49);
- no Linux package;
- no HEIC/HEIF or JPEG XL/JXL support.

## Build

The build is native arm64 and uses the pinned v1.2.2 toolchain:

```text
python scripts/license_audit.py --check
python scripts/prepare_backends.py
python scripts/prepare_licenses.py
python scripts/build_macos_app.py --development
```

`scripts/MacOSArchiveLens.spec` creates `dist/ArchiveLens.app` with:

- an arm64 PyInstaller bootloader and bundled Python runtime;
- Qt Widgets, QtPdf, and the required Qt image-format plugins;
- Pillow AVIF/JPEG 2000 native modules;
- the approved arm64 `libunrar.dylib` under the common frozen runtime layout;
- RAR self-test fixtures;
- README/license/notices and audited third-party licenses;
- a generated application icon;
- `build-info.json`, `compiled-source.json`, and exact-source SPDX SBOM.

The bundle identifier is `com.cam11505.archivelens`. `argv_emulation` is disabled;
Issue #47 adds alternate-viewer Finder declarations for CBZ, CBR, ZIP, RAR, 7Z,
and PDF. No direct-image or folder document types are declared and no default
association is set. Folder opening remains available through Open Folder/drag-drop.

## Build metadata

The bundled `build-info.json` schema records:

- version and exact source commit;
- `channel=development` and `development=true`;
- `os=macos`, `architecture=arm64`, `artifact_kind=app`;
- Python, PySide6, Qt, and dependency versions;
- native RAR backend name/version/architecture/hash;
- immutable parity baseline tag/commit.

The #46 verifier requires `--allow-development`. This prevents an unsigned/ad-hoc
bundle from being mistaken for an official release artifact.

## Verification

```text
python scripts/verify_macos_app.py dist/ArchiveLens.app \
  --expected-commit <40-character commit> \
  --allow-development \
  --run
```

Verification checks:

- bundle identity/version and exact six-type Finder declarations with Viewer role
  and Alternate rank;
- required metadata, notices, licenses, QtPdf, image plugins, and RAR runtime;
- exclusion of QtWebEngine;
- arm64 architecture for every Mach-O file found in the bundle;
- copying the app to an isolated directory outside the checkout and launching it
  through macOS LaunchServices (`open -W -n`);
- packaged GUI/backend self-test with Python/venv variables removed.

The workflow archives the verified `.app` with `ditto` only as CI evidence. It is
not the official v1.3 DMG and must not be published as a signed/notarized release.

Issue #49 adds the separated official candidate and development DMG probe described
in [MACOS_SIGNING.md](MACOS_SIGNING.md). The development path remains credential-free.

## Issue #47 native integration

Open, Quit, and fullscreen use Qt standard keys; About, Quit, and macOS Preferences
use explicit menu roles. Existing bookmark/folder keys map to Command on macOS
through Qt. Preferences edits only existing cover and recursive-folder settings.
Logical previous/next retain their meaning in RTL; only arrow actions reverse.

The macOS workflow also runs `scripts/verify_macos_open_events.py` against a copied
packaged app outside the checkout. Real LaunchServices cold CBZ and warm PDF opens
must reach the shared source-open boundary and load a page; JSON evidence is
uploaded with the app. This is hosted-runner evidence, not physical Finder menu QA.

References: [Qt standard keys](https://doc.qt.io/qt-6/qkeysequence.html) and
[Apple document roles/rank](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html).
