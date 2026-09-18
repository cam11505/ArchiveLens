# Changelog

## 1.2.2 — 2026-09-18

- Fixed PDFs with an implicit transparent page background rendering as black text over
  the dark reader surface by compositing QtPdf output onto an opaque white page.
- Added a synthetic regression test covering transparent QtPdf corners and preserved
  the existing annotation/render-size behavior.
- Reused the identical Qt 6.11.2 corresponding-source asset from the project-controlled
  v1.2.1 release by verified URL and SHA-256 instead of uploading another 580 MB copy.

## 1.2.1 — 2026-09-17

- Enabled explicit QtPdf annotation and LCD-optimized rendering, with a deterministic
  compatibility corpus and documented PDFium limitations.
- Added bounded, render-size-aware PDF rerendering for zoom, resize, rotation and
  display-scale changes without adding a second render queue.
- Fixed supported-source drag/drop over the active reader and thumbnail surfaces while
  rejecting multiple, unsupported and remote URLs before changing the current source.
- Unified the welcome screen, File menu, native choosers, help and documentation around
  one Open Content workflow for supported files and image folders.

- Clarified that ArchiveLens application source is MIT-licensed FOSS while official
  binary distributions are mixed-license bundles whose third-party components retain
  their own terms; UnRAR is explicitly treated as a redistributable non-FOSS component.
- Added `docs/LICENSING.md`, an audited dependency/license policy and SPDX 2.3 release SBOM.
- Added CI/release license gates so unreviewed runtime dependencies cannot ship silently.
- Extended portable/installer release verification to require licensing metadata, SBOM,
  notices, source material and checksums as part of the verified release set.

## 1.2.0 — 2026-09-16

- Added a source-neutral ContentProvider layer for archives, image folders and PDF.
- Added bounded flat/recursive folder reading with reparse-point loop protection.
- Added local resume/history/bookmarks with schema migration and no credential storage.
- Added AVIF and JPEG 2000 through Pillow 12.3, plus Qt TIFF; documented HEIC/HEIF
  and JPEG XL as explicitly deferred after backend/license/resource evaluation.
- Added QtPdf reading, supported password retry, thumbnails, double-page display,
  high-DPI bounded rendering and PDF Open With registration.
- Added Fit Width/Height and conservative display-only automatic/manual border trim.
- Extended package diagnostics, licenses, resource/stale-result tests and Windows RC checks.
- Bounded deeply nested upstream-license paths so the Windows installer remains usable
  from ordinary and custom installation directories while retaining an origin-path index.

## 1.1.0 — 2026-09-15

- Added encrypted ZIP/CBZ (ZipCrypto and AES), 7Z, and bundled Windows RAR/CBR.
- Added memory-only password dialogs, retry and cancellation.
- Added animated GIF playback, lazy thumbnails, double pages, cover and LTR/RTL.
- Persisted non-sensitive viewer preferences; added per-user Windows installer.
- Extended resource guards, backend/GUI tests, license sources and packaged checks.
- Automated source, portable and installer verification passed. Physical Explorer,
  multi-monitor and Windows 10 QA was explicitly deferred for this release.


## 1.0.0 — 2026-09-14

- Read ZIP/CBZ images on demand without modifying or extracting the photo archive.
- Natural folder/filename ordering, Unicode paths and duplicate-member handling.
- JPG/JPEG/PNG/WebP/BMP/GIF-first-frame decoding with EXIF orientation.
- Open dialog, drag/drop, keyboard navigation and image/archive status.
- Fit, physical-pixel 100%, zoom, wheel scrolling, drag panning, rotation and fullscreen.
- Single-worker background loading, latest-request validation, bounded LRU cache and prefetch.
- Entry/image resource guards, recoverable errors and bounded local diagnostic logging.
- Windows x64 portable packaging, built-in end-to-end diagnostics, file manifests,
  SHA-256 verification, third-party licenses and upstream source archives.
- Windows and Linux test automation; Windows packaged-application validation.
