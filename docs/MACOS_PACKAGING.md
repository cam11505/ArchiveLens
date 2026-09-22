# macOS arm64 application packaging

## Scope

This document records ArchiveLens v1.3 issue #46. The immutable parity baseline is
`v1.2.2` / `bb0197b0291707287517ba8bdfc3a10ce1ad1149`.

Issue #46 produces a self-contained **development** `ArchiveLens.app` on the pinned
GitHub-hosted `macos-15` Apple Silicon runner. It reuses the RAR decision from #44
and the shipped-codec/QtPdf qualification from #45; it does not repeat those spikes.

Explicit exclusions:

- no Finder document declarations or Open With behavior (#47);
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
- `build-info.json` and `compiled-source.json`.

The bundle identifier is `com.cam11505.archivelens`. `argv_emulation` is disabled;
Finder file events and document declarations remain owned by #47.

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

- bundle identity/version and absence of #47 document declarations;
- required metadata, notices, licenses, QtPdf, image plugins, and RAR runtime;
- exclusion of QtWebEngine;
- arm64 architecture for every Mach-O file found in the bundle;
- packaged GUI/backend self-test with Python/venv variables removed.

The workflow archives the verified `.app` with `ditto` only as CI evidence. It is
not the official v1.3 DMG and must not be published as a signed/notarized release.
