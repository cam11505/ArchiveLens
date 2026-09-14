# v1.1 backend and redistribution record (#5, #13)

| Format | Backend | License | Native code |
| --- | --- | --- | --- |
| Plain/ZipCrypto ZIP/CBZ | Python 3.12 zipfile | PSF | Python runtime |
| AES ZIP/CBZ | pyzipper 0.4.0 | MIT + inherited Python license | pycryptodomex 3.23.0 (BSD/public domain) |
| 7Z | py7zr 1.1.3 | LGPL-2.1-or-later | BCJ, PPMd, inflate64, Brotli, Zstandard |
| RAR/CBR (Windows x64) | official UnRAR DLL 7.21 | UnRAR DLL freeware license | UnRAR64.dll |

Exact transitive versions are pinned in constraints-build.txt and recorded in
licenses/archive-backends.json. py7zr, pybcj, pyppmd, inflate64 and multivolumefile
use LGPL-2.1-or-later; Brotli/texttable MIT, psutil BSD-3-Clause, backports.zstd PSF-2.0
plus bundled Zstandard terms. prepare_licenses.py collects installed license texts
and exact PyPI source distributions, verifies published SHA-256 and includes them
in upstream-sources.json. All source archives accompany the release, including LGPL
libraries. Rebuild against modified dependencies with the provided source/spec;
reverse engineering to debug library modifications is permitted.

## UnRAR spike outcome

Official SDK: https://www.rarlab.com/rar/unrardll-721.exe (7.21 stable).
SDK SHA-256: e1dd2126d13dc75aa7c0c1a3964176fb3c8f728bbccfb0ce129f3a6c02542c1d.
x64 DLL SHA-256: 4b4a5cf24a5d60102f31b9d0c591064085ea9ac2336dd31c4bee483091dcbc9f.
The downloaded SDK had a valid win.rar GmbH Authenticode signature. The bundled
SDK license permits free use of unrar.dll in software handling RAR archives.
The exact text is shipped as licenses/UNRAR-LICENSE.txt.

The adapter is based on the SDK's packed unrar.h ABI and documented callbacks.
RAR_TEST + UCM_PROCESSDATA provides single-member bytes without extraction;
UCM_NEEDPASSWORDW provides an in-process password buffer, never command arguments.
Missing/bad password use DLL error codes. Multipart, link and excessive-dictionary
cases are rejected/skipped. Callback failures are converted after returning to Python.
No dependence on WinRAR installations, registry discovery or system PATH.

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
