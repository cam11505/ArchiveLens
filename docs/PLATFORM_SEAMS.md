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

UnRAR discovery uses the same source/frozen path seam through a platform-neutral
`RarBackend` boundary. Windows loads `UnRAR64.dll`; macOS and Linux load their bundled
native libraries. Availability still fails closed when the selected library is absent.
