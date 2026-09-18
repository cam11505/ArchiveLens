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
| Current RAR/CBR provider | replacement required | replacement required | Windows UnRAR DLL license is recorded in `docs/BACKENDS.md`; no non-Windows binary is currently shipped | Implement a platform-neutral native-library boundary and qualify an arm64 backend in #44. |
| PyInstaller minimal frozen layout | works | works | Build-only diagnostic | Replace with release-quality `.app` packaging in #46. |

## RAR/CBR evidence and decision

The current provider cannot be used on macOS or Linux:

- availability is explicitly restricted to `sys.platform == "win32"`;
- runtime discovery is hard-coded to `native/UnRAR64.dll`;
- the ABI loader is designed around the Windows UnRAR DLL;
- both non-Windows source and frozen diagnostics therefore reported
  `rar.available = false`.

Candidate direction for #44 is the official UnRAR source/library compiled for
each supported architecture behind the existing bounded callback/session
contract. This is a candidate, not an approval: its macOS arm64 binary,
password/solid/RAR4/RAR5 behavior, resource limits, frozen discovery, exact
license text, and redistribution evidence still require dedicated tests.

Decision for the current backend: **No-Go on macOS arm64**. Do not ship the
Windows-only implementation or silently make RAR optional. The v1.3 release
gate remains blocked until #44 produces an approved macOS arm64 backend and a
formal Go decision. This does not block #43's narrow platform seams or #45's
codec qualification.

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
