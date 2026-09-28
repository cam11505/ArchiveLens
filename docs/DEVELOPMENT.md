# ArchiveLens development

The normative scope and release order are in `V1.2_PLAN.md`. `PROVIDERS.md`
defines source/provider ownership, while `IMAGE_BACKENDS.md`, `QTPDF_BACKEND.md`
and `BACKENDS.md` record dependency and redistribution decisions.

## Architecture and bounds

- `ContentProviderRegistry` selects archive, folder or PDF providers. Storage-specific
  metadata never leaks into reader page descriptors.
- Main-image and thumbnail workers each own one provider and one replaceable pending
  request. Generation/token/credential checks suppress stale results. PDFs do not prefetch.
- Folder traversal is iterative and bounded by count/depth, ignores inaccessible children,
  never follows symlinks/reparse points, and can be cancelled during source switches.
- Decoder selection is centralized. Byte, compression, pixel, PDF render, cache, history,
  bookmark, folder and auto-trim bounds live in `config.py`.
- Reading state is versioned JSON written atomically under the per-user application-data
  directory. Schema v2 reads v0/v1 records safely. Credentials and decoded/rendered data
  are outside the persistence model.
- Fit, rotation and trim are display state. Auto trim examines a bounded preview and fails
  conservatively; PDF resize/DPI changes replace the pending bounded render.

## Source checks

```powershell
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m archivelens --self-test-report outputs/self-test.json
```

Run `prepare_backends.py` before backend tests/builds. It fetches the verified official
DLL on Windows and compiles the verified official portable source on macOS/Linux. The
self-test exercises
encrypted ZIP/7Z/RAR, AVIF/JP2/TIFF, folder traversal, QtPdf normal/password/resource paths,
fit/trim, animation, thumbnails, reading-state safety and source immutability.

## Reproducible Windows release

Run `prepare_licenses.py` to collect exact installed licenses and corresponding source
archives. Build from a clean committed checkout, then run `build_portable.py`,
`package_release.py`, `build_installer.py`, `verify_release.py --run`,
`verify_installer.py`, and `release_checksums.py`. Build metadata records the exact commit;
portable and installer verification reject a different commit or incomplete manifest.

CI repeats source tests and approved RAR backend preparation on Windows/macOS/Ubuntu,
retains JUnit and source reader self-test reports, and runs full portable/installer
checks on a clean Windows runner. Automated offscreen tests are not evidence of
physical Explorer, multi-monitor or Mac hardware behavior. Historical v1.2.2 QA
documents are release-specific records, not current v1.3 release approval.

## macOS arm64 development app

v1.3 issue #46 adds a native, self-contained development `ArchiveLens.app`. Build and
verification commands, metadata, included runtimes, and the explicit #47/#49 scope
boundaries are documented in `MACOS_PACKAGING.md`. The bundle is unsigned/ad-hoc and
must not be represented as an official macOS release.

`V1.3_PLAN.md` defines current scope. `MACOS_DEVELOPMENT.md` describes CI downloads,
exact tested commit identification and independent development DMG verification.
`ARTIFACT_VERIFICATION.md` describes common versus native/platform checks.
`V1.3_DEVELOPMENT_QA.md` records the authorized #51 development-only regression
subset and official/manual blockers. Version stays 1.2.2 during this work.
Do not run the protected official workflow or create an RC/tag/release while the
formal signing/notarization/staple/Gatekeeper gates remain unresolved.
