# ArchiveLens v1.3 macOS and Linux backend spike

## Scope and evidence

- Issue: #42
- Immutable baseline: `v1.2.0` / `af0c01b46041f26ce19a978237970d866eaf017c`
- Spike commit: `8500347b15f94d17118f2ab0f60698f92869cce6`
- GitHub Actions run: [35115676855](https://github.com/cam11505/ArchiveLens/actions/runs/35115676855)
- Runner selection: GitHub-hosted `macos-15` Apple Silicon arm64 and
  `ubuntu-latest` x64
- Toolchain: Python 3.12, PySide6/Qt 6.11.2, Pillow 12.3.0, PyInstaller 6.22.3

The spike ran the full source test suite, then generated and executed a minimal
PyInstaller frozen diagnostic. The diagnostic verified the real machine
architecture, Qt Core/Gui/Widgets, QtPdf, Qt plugin discovery, writable runtime
paths, Pillow codec availability, and archive-provider registration. It did not
produce a release-quality application package.

## v1.2.2 delta revalidation

The immutable implementation baseline for #43–#51 is `v1.2.2` /
`bb0197b0291707287517ba8bdfc3a10ce1ad1149`. The original v1.2.0 spike remains
historical evidence; #42 is rerun only for the maintenance delta that affected
QtPdf rendering, zoom-aware PDF requests, unified Open Content and drag/drop,
dependency licensing, SBOMs, and release verification.

The source and frozen diagnostics now exercise the production
`PdfContentProvider` with a generated one-page fixture and require its rendered
page to be opaque with a white background. The full suite remains responsible
for zoom/cache bounds, password PDFs, source routing, drag/drop, licensing, and
release verification. No private reporter PDF is stored or uploaded.

Delta commit: `56b3231fd0a483e65e963910df92714eef93b858`.
GitHub Actions run: [35336602802](https://github.com/cam11505/ArchiveLens/actions/runs/35336602802).

| Environment | Source tests | Source diagnostic | Frozen diagnostic | Executable |
| --- | --- | --- | --- | --- |
| macOS 15 arm64 | 189 passed, 1 skipped | pass | pass | Mach-O 64-bit arm64 |
| Ubuntu x64 | 189 passed, 1 skipped | pass | pass | ELF 64-bit x86-64 |

Both environments reported ArchiveLens 1.2.2, PySide6/Qt 6.11.2, Pillow
12.3.0, the complete shipped decoder extension set, and successful production
QtPdf rendering in source and frozen layouts. Every render was RGB/opaque with
corner RGBA `[255, 255, 255, 255]`. The macOS runner used Python 3.12.10 and
the Ubuntu runner used Python 3.12.14; both satisfy the Python 3.12 contract.

### Delta classification

| Area | Classification | Evidence / follow-up |
| --- | --- | --- |
| #54 QtPdf render policy | changed and revalidated | Full tests plus source/frozen production-render smoke passed on both platforms. |
| #55 zoom/DPI-aware PDF requests | changed and revalidated | Full PDF/provider/GUI tests passed; resource and cache contracts remain covered by the suite. |
| #56 drag/drop event routing | changed and revalidated | Full GUI tests passed on macOS arm64, Linux x64, and the regular Windows lane. |
| #57 unified Open Content | changed and revalidated | Current shared `MainWindow.open_content` flow passed the full cross-platform source suite; #43 still owns the application-level `open_source` seam and Finder events. |
| #58 licensing/SBOM | changed, conclusions still valid | Dependency versions are unchanged; the regular CI license audit passed. Platform packaging must retain the current notices/SBOM policy. |
| #59 release/package state | changed, conclusions still valid | Windows release verification remains separate; the v1.3 spike found no new non-Windows frozen-layout blocker. |
| v1.2.2 white PDF background | changed and revalidated | Synthetic production render passed in all four macOS/Linux source/frozen combinations. |
| RAR/CBR | unchanged; preliminary No-Go remains | RAR remains registered but unavailable on macOS/Linux. #44 must produce and qualify the native backend before release. |

Conclusion: the original #52 compatibility findings remain valid after the
v1.2.2 delta. Issue #43 may proceed after this documentation and its exact
evidence are merged; #44 remains the formal RAR Go/No-Go gate.

## Results

| Environment | Source tests | Source diagnostic | Frozen diagnostic | Executable |
| --- | --- | --- | --- | --- |
| macOS 15 arm64 | 177 passed, 1 skipped | pass | pass | Mach-O 64-bit arm64 |
| Ubuntu x64 | 177 passed, 1 skipped | pass | pass | ELF 64-bit x86-64 |

Both source and frozen diagnostics reported:

- Qt image, widget, and QtPdf smoke checks passed;
- JPEG, PNG, WebP, BMP, GIF, TIFF, AVIF, and JPEG 2000 decoder extensions
  available;
- ZIP/CBZ and 7Z providers available;
- RAR/CBR registered but unavailable outside Windows.

## Backend classification

| Backend | macOS arm64 | Linux x64 | License/redistribution status | Required action |
| --- | --- | --- | --- | --- |
| Qt Core/Gui/Widgets | works | works | LGPL/commercial Qt terms already tracked for v1.2 | Keep deterministic plugin collection in the app bundle. |
| QtPdf | works | works | Qt terms already tracked for v1.2 | Qualify real PDF fixtures in #45. |
| Pillow raster codecs | works | works | Existing dependency notices apply | Qualify real AVIF/JP2/TIFF fixtures in #45. |
| ZIP/CBZ (`zipfile`/`pyzipper`) | works | works | Existing notices apply | No platform replacement indicated. |
| 7Z (`py7zr`) | works | works | Existing notices apply | No platform replacement indicated. |
| RAR/CBR provider | works | works in source/minimal-frozen qualification | Official UnRAR 7.23 source and complete non-FOSS license are pinned; libraries are built in CI | Go for #46 macOS packaging; Linux packaging remains deferred. |
| PyInstaller minimal frozen layout | works | works | Build-only diagnostic | Replace with release-quality `.app` packaging in #46. |

## RAR/CBR evidence and decision

Issue #44 replaces the Windows-only loading path with a platform-neutral boundary:

- Windows loads the pinned official 7.23 `UnRAR64.dll` with the Windows ABI;
- macOS builds `libunrar.dylib` from pinned official 7.23 portable source;
- Linux builds `libunrar.so` from the same source for source/runtime qualification;
- all platforms use deterministic `outputs/backends` and frozen `native` discovery;
- real RAR3/RAR5, solid and encrypted reads run in both source and minimal-frozen modes.

The official source/library is compiled per architecture behind the existing bounded
callback/session contract. Passwords remain memory-only, normal reads stream the requested
member through callbacks, and no command-line or whole-archive extraction path is added.

Decision: **Go** for the v1.3 macOS arm64 RAR backend.

Exact evidence is GitHub Actions RAR backend gate Run #4 at commit
`01d2f0b0438cfded5a0acbd75981e20a8b20bade`:

- Windows x64, macOS arm64 and Linux x64 all passed the complete pytest suite, source
  diagnostic, real RAR3/RAR5 solid/encrypted reads, minimal-frozen build and frozen reads.
- macOS `libunrar.dylib` is a Mach-O arm64 shared library with SHA-256
  `d03c4c020a6c75b830c5dedb24dc4300d0b49e6c85bdc13549e6f66c81b61a7f`.
- Linux `libunrar.so` is an ELF x86-64 shared library with SHA-256
  `dfee3328fa0e1e05d2a2a1223d3dbe39fef125f806d4f853d62e79d96918ca9b`.
- Windows retained the official x64 DLL with SHA-256
  `894b7d2db8d6363eb12f30c7b89f48eab9e71963b8b438675bdd64c12dd59bcc`.
- All three diagnostics produced the identical fixture payload digest
  `9a6803dc21766df867c06462517045a58c0dd8f3ccde4228648fd3f6d1571f53`.
- Source version 7.23, source archive SHA-256, license classification and built-library
  metadata are preserved in each uploaded `UNRAR-BACKEND.json`.

This Go clears #44 as the RAR prerequisite for #46. It does not approve the final app
bundle, signing, notarization or release checks owned by #46 and later issues, and it does
not expand Linux into a packaged release target.

## Proven remediation boundaries

- #43 may introduce platform services and unified source-open routing, but must
  preserve provider, decoder, worker, cache, and reading-state contracts.
- #44 owns the RAR ABI/backend implementation and formal Go/No-Go result.
- #45 owns representative codec and PDF qualification beyond import/smoke
  evidence.
- #46 owns the reproducible `ArchiveLens.app`; the diagnostic bundle is not a
  distributable artifact.
- Linux packaging remains deferred. Passing this spike establishes source and
  minimal-frozen compatibility only.
