# v1.1 backend and redistribution record (#5, #13)

| Format | Backend | License | Native code |
| --- | --- | --- | --- |
| Plain/ZipCrypto ZIP/CBZ | Python 3.12 zipfile | PSF | Python runtime |
| AES ZIP/CBZ | pyzipper 0.4.0 | MIT + inherited Python license | pycryptodomex 3.23.0 (BSD/public domain) |
| 7Z | py7zr 1.1.3 | LGPL-2.1-or-later | BCJ, PPMd, inflate64, Brotli, Zstandard |
| RAR/CBR (Windows x64) | official UnRAR DLL 7.23 | UnRAR freeware license | UnRAR64.dll |
| RAR/CBR (macOS arm64) | official portable UnRAR source 7.23 | UnRAR freeware license | libunrar.dylib |
| RAR/CBR (Linux x64 source/runtime qualification) | official portable UnRAR source 7.23 | UnRAR freeware license | libunrar.so |

Exact transitive versions are pinned in constraints-build.txt and recorded in
licenses/archive-backends.json. py7zr, pybcj, pyppmd, inflate64 and multivolumefile
use LGPL-2.1-or-later; Brotli/texttable MIT, psutil BSD-3-Clause, backports.zstd PSF-2.0
plus bundled Zstandard terms. prepare_licenses.py collects installed license texts
and exact PyPI source distributions, verifies published SHA-256 and includes them
in upstream-sources.json. All source archives accompany the release, including LGPL
libraries. Rebuild against modified dependencies with the provided source/spec;
reverse engineering to debug library modifications is permitted.

## UnRAR spike outcome

Windows SDK: https://www.rarlab.com/rar/unrardll-723.exe (7.23 stable).
SDK SHA-256: 68b064b34691988158c4126d3cf422f4e74a7d1d618c26bafc93b4e502b88b55.
x64 DLL SHA-256: 894b7d2db8d6363eb12f30c7b89f48eab9e71963b8b438675bdd64c12dd59bcc.
Portable source: https://www.rarlab.com/rar/unrarsrc-7.2.3.tar.gz.
Source SHA-256: 3995af0aa32b1505a566da053725551a1f0698dc42b2fdf7ba7d65db0d004e33.
The bundled license permits using and redistributing UnRAR components in software
handling RAR archives, but prohibits recreating the proprietary compression algorithm.
The exact text is shipped as licenses/UNRAR-LICENSE.txt.

The adapter is based on the packed UnRAR ABI and documented callbacks. Platform-specific
library discovery, loader and callback calling convention are isolated behind
`RarBackend`; archive-facing provider, worker and UI semantics do not branch by OS.
RAR_TEST + UCM_PROCESSDATA provides single-member bytes without extraction;
UCM_NEEDPASSWORDW provides an in-process password buffer, never command arguments.
Missing/bad password use DLL error codes. Multipart, link and excessive-dictionary
cases are rejected/skipped. Callback failures are converted after returning to Python.
No dependence on WinRAR, Homebrew, MacPorts, registry discovery or system PATH.

Local real-DLL tests passed for pre-RAR5/RAR4-compatible solid archives, RAR5 solid,
CRC, encrypted data, encrypted headers and Unicode names. Small ISC-licensed rarfile
fixtures are attributed in tests/fixtures/rar. Frozen self-test checks DLL discovery
with Python and third-party binaries removed from PATH. Installed smoke testing is
tracked separately in V1.1_QA.md; source success alone does not prove packaging.

7Z uses bounded WriterFactory memory output, disables prefetch, rejects duplicate
member names, and caps total decompressed catalog at 1 GiB. ZIP AES is tested at
128/192/256 bits. 7Z cannot always distinguish wrong passwords from corruption;
RAR older encryption may also report corruption for invalid data/passwords.
No claim is made for every compression method or multipart archive.
