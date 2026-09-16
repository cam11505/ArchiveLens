# Changelog

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
