# ArchiveLens platform seams

ArchiveLens keeps the reader, providers, worker, cache, and Qt image pipeline
platform-neutral. OS-specific behavior is limited to these narrow seams.

## Unified source opening

`ArchiveLensApplication.open_source(path)` is the desktop boundary for every
supported source-open entry point:

```text
startup argv / Finder QFileOpenEvent / file dialog / drag and drop / recent item
                                  |
                                  v
               ArchiveLensApplication.open_source(path)
                                  |
                                  v
                     MainWindow.open_content(path)
```

Finder events received before the main window is ready are queued in order and
flushed when the handler is installed. The application accepts local file paths
only; URL/network source support is not introduced. Finder document declarations
remain owned by #47.

## Runtime and writable paths

`archivelens.platform_paths` owns source-versus-frozen runtime roots, native
backend paths, and Qt writable locations. Production backend discovery and the
packaged self-test use the same helpers. A frozen runtime without a bundle root
fails explicitly instead of searching the current directory or `PATH`.

Current Windows UnRAR discovery remains behavior-compatible. #44 will add the
platform-neutral RAR ABI/backend boundary and macOS arm64 implementation; this
seam does not approve or silently enable a non-Windows RAR backend.
