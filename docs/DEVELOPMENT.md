# ArchiveLens 1.1 development

The v1.1 plan remains in V1.1_PLAN.md. Provider ownership/error contracts are in
PROVIDERS.md; dependency and redistribution decisions are in BACKENDS.md.

- Full-image and thumbnail workers have separate providers and single replaceable
  pending requests. Tokens plus archive/credential revisions suppress stale results.
- Thumbnails request at most the visible 24 rows sequentially, using scaled decode.
  Scrolling replaces pending work; hidden sidebars stop requesting. Solid backends
  have no speculative prefetch. No full-resolution catalog scan at open.
- Full-image LRU remains 256 MiB, shared across a spread. GIF bytes are separate,
  capped at 32 MiB per page; QMovie CacheNone avoids retaining every frame.
- Spread pairing is pure logic in image/reading.py; physical arrow mapping is
  separate from logical next/previous. Scene items share zoom and transform.
- Settings use only a fixed allowlist: geometry/state, thumbnails, double_page,
  rtl and cover. Tests and self-test isolate the settings store.
- Plain ZIP keeps Python zipfile; AES members use pyzipper. 7Z uses a bounded
  WriterFactory. UnRAR uses RAR_TEST memory callbacks and UTF-16 password callbacks.
- Entry count/size/ratio/pixels and cache/media limits are centralized in config.py.
  They are not a process sandbox. Parsing metadata or decompressing a solid prefix
  may allocate/work before application-level checks complete.

Run pytest, Ruff check and Ruff format check. Run `python -m archivelens
--self-test-report outputs/self-test.json` for native GUI/backend diagnostics.
The self-test exercises real encrypted ZIP/AES/7Z and bundled RAR4/RAR5, plus
animation, thumbnails and double pages, beyond the original eight v1.0 checks.

On Windows, run prepare_backends.py before tests/build; it verifies SDK and DLL
hashes. Run prepare_licenses.py to fetch exact sources (including LGPL archive
libraries). Build portable, commit all sources, package_release.py, then build the
installer. verify_installer.py checks install, self-test and uninstall in a unique
workspace directory. CI runs source tests on Windows/Linux and packages on Windows.

Do not tag v1.1.0 until the manual items in V1.1_QA.md and exact-commit CI/release
checks are completed or explicitly deferred with rationale. Automated Qt events
are not evidence of physical Explorer interaction or multi-monitor manual QA.
