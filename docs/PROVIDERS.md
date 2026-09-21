# Provider development

## Content providers (v1.2)

`ContentProviderRegistry` is the only reader-facing source-selection boundary.
It maps local directories to `FolderContentProvider`, `.pdf` to
`PdfContentProvider`, and supported archive extensions to
`ArchiveContentProvider`. The reader consumes stable `PageDescriptor` objects and
either encoded raster bytes or a provider-rendered `QImage`; PDF pages are never
represented as fake archive entries.

Each `ImageWorker` creates, opens, uses and closes its provider inside the worker
thread. A worker has one in-flight operation and one replaceable pending request.
PDF documents are therefore rendered synchronously in their owner thread without
an additional backend queue; PDFs do not prefetch. Cache identity includes source,
page and PDF render size. Main and thumbnail workers have separate provider
instances and byte-bounded caches.

Folders are scanned iteratively. Flat/recursive behavior is explicit, traversal
checks cancellation, count and depth limits, and Windows reparse points/junctions
and symlinks are never followed. Inaccessible non-root children are skipped; an
inaccessible root is a recoverable content error.

QtPdf credentials use the same owned `ArchiveCredentials` transfer as encrypted
archives. A successful load clears the plaintext password from `QPdfDocument`;
wrong/missing/unsupported security paths are typed, recoverable errors. Closing a
PDF explicitly destroys the native document in its owner thread so Windows file
handles are released. No provider writes source data or persists credentials.

## Archive backends

`ArchiveProviderRegistry` is the shared selection boundary for the worker, CLI,
file dialog and drag/drop. The default registry enables ZIP/CBZ and 7Z; RAR/CBR is available when the
bundled platform UnRAR library is present. Backend details are in BACKENDS.md.

## Adding a backend

Implement `ArchiveProvider` with class-level `ArchiveCapabilities` and register
its class. Extensions include a leading dot and are normalized case-insensitively;
duplicate registration is rejected. Each `create(path)` returns a fresh provider.
Optional dependency imports belong inside the backend, not at application import
time. Report unavailable dependencies through `available=False` or
`ProviderUnavailableError`; constructor ImportError/OSError is also translated.
Unavailable formats are omitted from UI discovery. Unknown extensions raise
`UnsupportedArchiveError`.

Capabilities describe format name, extensions, password support, availability,
random access cost and optional solid behavior. A provider can replace its instance
capabilities after opening an archive. Prefetch runs only for explicitly efficient,
non-solid archives; unknown/expensive/solid archives load requested pages only.
ZIP retains the existing bounded next-two/previous-one prefetch and cache policy.

Keep member reads lazy and read-only. Never extract to a temporary directory.
Entries remain valid only in their originating open provider session. Backends
must enforce resource limits and translate failures into the exception classes in
`errors.py`, including password required, bad password, unsupported encryption,
corruption, resource limits and unavailable backend. Control flow uses types,
not localized message matching.

## Credential ownership and errors

`ArchiveCredentials(bytes)` owns an in-memory mutable password buffer. Its repr
is redacted and serialization is rejected. Direct callers clear it explicitly or
use its context manager. Providers borrow the object through
`open(path, credentials=...)` and drop that reference on `close()`; they must not
persist, log or include secrets in error messages.

Submitting `LoadRequest(..., credentials=...)` transfers ownership to ImageWorker.
Navigation in the same generation/path reuses the current credential. Replacing
credentials or changing generation/path clears the old buffer immediately and
invalidates the provider/cache session. `stop()` clears active/pending credentials;
submissions after stop are also cleared. Token checks and the replaceable pending
request continue to suppress stale results.

`password_bytes()` returns a temporary backend copy. Python cannot guarantee
zeroization of immutable copies or backend allocations; clearing overwrites the
owned bytearray and removes its reference, not every process-memory copy. Avoid
retaining copies. Credentials are never stored in settings, files or logs.

Worker results carry a canonical localized message and `error_type` (the exception
class), never the backend exception object/traceback. Load, prefetch and cleanup
logs exclude backend messages and tracebacks. CLI also uses canonical messages.
ZIP supports ZipCrypto/AES using supplied credentials; strong encryption outside
the documented support reports UnsupportedEncryptionError.

## Validation

Run `python -m pytest -q` and `python -m ruff check .`. The provider foundation tests
use injected in-memory backends for error propagation, credential lifecycle,
session replacement, UI discovery and capability-aware prefetch. Existing ZIP,
image, GUI, race and cache tests remain regression coverage.
