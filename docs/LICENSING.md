# ArchiveLens licensing and distribution policy

This document explains how ArchiveLens describes the licensing of its source code and
official binary distributions. It is a project compliance summary; the actual license
texts distributed with the project and its dependencies remain authoritative.

## Short version

- **ArchiveLens application source code is MIT-licensed free and open-source software.**
- **Official binary distributions are mixed-license distributions.** The MIT license
  does not relicense Python, Qt/PySide, Pillow, archive libraries, UnRAR, Microsoft
  runtime components, or other third-party software bundled with an artifact.
- Most bundled dependencies are FOSS under licenses such as LGPL, MIT, BSD, HPND,
  Apache-2.0, and the PSF license.
- The Windows distribution currently includes **UnRAR64.dll**, which is redistributed
  under the upstream UnRAR freeware license. ArchiveLens does **not** classify this
  component as FOSS because its license contains use/reverse-engineering restrictions,
  including restrictions related to recreating the proprietary RAR compression
  algorithm.
- Windows artifacts may also contain Microsoft redistributable runtime components under
  Microsoft's own terms. They are not MIT-licensed or part of the ArchiveLens source
  license.

Accordingly, preferred wording is:

> ArchiveLens application source is MIT-licensed open-source software. Official
> binaries are mixed-license distributions containing separately licensed third-party
> components; see `THIRD_PARTY_NOTICES.md` and the release SBOM.

Avoid describing the complete Windows binary bundle as "all MIT" or "100% FOSS".

## ArchiveLens source

The source files owned by the ArchiveLens project are distributed under the MIT license
in the repository `LICENSE` file. The project license permits use, modification,
redistribution, and commercial use subject to the MIT notice requirements.

Third-party source copied or bundled into a release is not relicensed by ArchiveLens.
Its original terms remain in effect.

## Windows runtime distribution

The current Windows portable and installer releases combine components with different
licenses. The exact version/source/license files collected for a release are packaged
under `licenses/`, described in `THIRD_PARTY_NOTICES.md`, and recorded in the release
SBOM.

| Component family | Project classification | Primary terms used by ArchiveLens distribution |
| --- | --- | --- |
| ArchiveLens application source | FOSS | MIT |
| Python | FOSS | Python Software Foundation License |
| Qt / PySide6 / Shiboken6 | FOSS | LGPL-3.0 for the open-source distribution path |
| Qt PDF | FOSS | LGPL-3.0 for the Qt module; bundled PDFium/third-party notices retain their own terms |
| PDFium in Qt PDF | FOSS | BSD-family license plus bundled third-party notices |
| Pillow | FOSS | HPND |
| pyzipper / Brotli / texttable | FOSS | MIT |
| py7zr and several compression helpers | FOSS | LGPL-2.1-or-later |
| psutil | FOSS | BSD-3-Clause |
| backports.zstd | FOSS | PSF-2.0 plus bundled Zstandard notices |
| OpenSSL when bundled by the runtime | FOSS | Apache-2.0 |
| PyInstaller bootloader | FOSS with distribution exception | GPL-2.0-or-later plus PyInstaller bootloader exception |
| UnRAR64.dll | Redistributable, not classified by ArchiveLens as FOSS | Upstream UnRAR freeware license |
| Microsoft Visual C++ runtime | Proprietary redistributable | Microsoft runtime terms |
| Inno Setup installer engine | Separately licensed installer component | Inno Setup license |

This table is intentionally a summary. For mixed-license packages such as
PyCryptodome/pycryptodomex, and for third-party code embedded in Qt/PDFium, consult the
bundled upstream notices rather than treating a single table cell as a complete license
inventory.

## Qt / PySide LGPL compliance approach

ArchiveLens uses the open-source Qt/PySide distribution path and treats the applicable
shipped Qt/PySide components as LGPL-3.0 components. The release process is designed to
preserve the practical requirements relevant to this distribution model:

- Qt/PySide libraries are dynamically loaded from the application distribution rather
  than being incorporated into ArchiveLens source under the MIT license.
- Corresponding upstream Qt/PySide source archives and license/attribution material are
  published under ArchiveLens project control. A release may reference an identical,
  hash-verified source asset from an earlier ArchiveLens release instead of uploading a
  duplicate; `licenses/upstream-sources.json` records the controlled URL and SHA-256.
- The application and build scripts do not prohibit replacement of compatible Qt/PySide
  libraries with modified builds.
- ArchiveLens does not prohibit reverse engineering for the purpose of debugging
  modifications to LGPL-covered libraries.
- Qt's own third-party components retain their original licenses and notices.

See `THIRD_PARTY_NOTICES.md` and `licenses/upstream-sources.json` in a packaged release
for exact versions and source hashes.

Official Qt references:

- <https://doc.qt.io/qt-6/licensing.html>
- <https://doc.qt.io/qtforpython-6/>
- <https://doc.qt.io/qt-6/qtpdf-licensing.html>
- <https://doc.qt.io/qt-6/licenses-used-in-qt.html>

## UnRAR status

ArchiveLens currently bundles the official UnRAR library on Windows so RAR/CBR files can
be read without invoking a password-bearing command line or extracting an entire book to
a visible temporary directory.

UnRAR is redistributed under its own upstream terms. The license permits redistribution
of UnRAR components subject to restrictions and expressly restricts use/reverse
engineering to recreate the proprietary RAR compression algorithm. Because those terms
are not an unrestricted open-source license, ArchiveLens classifies the component as
`redistributable-non-foss` in `license-policy.json`.

This classification does **not** change the MIT license of ArchiveLens source code.
A future RAR backend may be evaluated separately if it can preserve ArchiveLens security,
password-privacy, resource-bound, compatibility, and packaging requirements.

Upstream reference: <https://www.rarlab.com/license.htm>

## Machine-readable policy and SBOM

`license-policy.json` is the audited release policy used by the license gate. It records:

- approved Python runtime distributions;
- a project classification for each component;
- SPDX expressions where a single appropriate expression is available;
- `NOASSERTION` where a custom/mixed/proprietary license should not be simplified into a
  misleading SPDX expression;
- manually tracked native/runtime/build components such as Python, Qt, UnRAR, Microsoft
  runtime files, the PyInstaller bootloader, and Inno Setup.

Each release produces:

`ArchiveLens-<version>.spdx.json`

The SPDX document is an inventory, not a substitute for the full license texts. Where a
component is mixed-license or uses custom redistribution terms, the SBOM points back to
the policy/notice material rather than inventing a license conclusion.

## Dependency license gate

The release policy is intentionally fail-closed for Python runtime dependencies:

1. The audit tool derives the installed dependency closure starting from the runtime
   dependencies declared by ArchiveLens.
2. Every discovered runtime distribution must have an entry in `license-policy.json`.
3. Every discovered entry must be explicitly marked `approved_for_distribution`.
4. An unknown/new runtime package fails CI and release packaging until its license,
   source, redistribution terms, package-size/resource behavior, and notices are reviewed.

This prevents a new decoder/archive/helper dependency from becoming part of an official
binary merely because it was added to `pyproject.toml` or pulled in transitively.

Changing a dependency's version can still require a fresh manual review even if the
package name is already allowlisted. The corresponding source/license collection remains
the source of truth for exact-version artifacts.

## Release artifact expectations

A publishable release should contain or make available at least:

- `LICENSE` for ArchiveLens;
- `THIRD_PARTY_NOTICES.md`;
- `LICENSING.md`;
- `licenses/` with collected upstream license/attribution files;
- `licenses/upstream-sources.json` with exact source archive hashes;
- `licenses/license-policy.json`;
- `ArchiveLens-<version>.spdx.json`;
- corresponding source archives required by the project's distribution obligations,
  or a project-controlled prior-release asset reference with the exact SHA-256;
- `SHA256SUMS.txt` covering the final release set.

Release verification must fail if required licensing/SBOM artifacts are absent or if an
unreviewed runtime dependency is detected.
