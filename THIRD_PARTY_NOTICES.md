# Third-party notices

ArchiveLens application source is MIT licensed. Its third-party components retain
their own licenses; the MIT license does not relicense Python, Qt or PySide6.

## Windows portable distribution

- **Python 3.12** — Python Software Foundation License and included third-party terms.
  See `licenses/Python-LICENSE.txt` in the portable package.
- **Qt 6.11.2 / PySide6 6.11.2 / Shiboken6 6.11.2** — the applicable Qt/PySide
  components are used under LGPL-3.0. Qt's third-party libraries have their own
  licenses and copyright notices. The bundle includes Qt Core, Gui, Widgets,
  Network (a PySide packaging dependency), Test (local diagnostics), platform/style
  plugins, and JPEG/GIF/WebP image plugins. PNG/BMP decoding is provided by Qt Gui.
  No application feature uses Qt Network to send data.
- **PyInstaller bootloader** — GPL-2.0-or-later with the PyInstaller bootloader
  exception permitting distributions of applications under their own licenses.
- **OpenSSL 3.x** — Apache-2.0, used by Python/Qt runtime dependencies when bundled.
  See `licenses/OpenSSL-LICENSE.txt`; exact DLL versions depend on the Python build.
- **Microsoft Visual C++ runtime** — Microsoft redistributable runtime components
  distributed with Python/Qt retain Microsoft's terms. They are not MIT licensed.

Full upstream license texts and attribution files are under `licenses/qtbase/`,
`licenses/qtimageformats/`, `licenses/pyside-setup/` and `licenses/PyInstaller/`.
This collection includes notices for the upstream source trees, a superset of the
components actually used. `licenses/upstream-sources.json` records exact source
URLs, versions, filenames and SHA-256 hashes.

## Source availability and replacement

Unmodified corresponding Qt/PySide source archives are provided alongside the
portable ZIP in the GitHub release. They are also available at:

- [Qt Base v6.11.2](https://github.com/qt/qtbase/tree/v6.11.2)
- [Qt Image Formats v6.11.2](https://github.com/qt/qtimageformats/tree/v6.11.2)
- [PySide / Shiboken v6.11.2](https://github.com/pyside/pyside-setup/tree/v6.11.2)
- [Python source](https://www.python.org/downloads/source/)

Qt/PySide are dynamically loaded from the portable directory. You may replace
compatible DLLs and bindings with modified builds. ArchiveLens does not prohibit
reverse engineering for debugging modifications to those libraries. Rebuilding
instructions and the PyInstaller spec are included in the project source.

References: [Qt licensing](https://doc.qt.io/qt-6/licensing.html),
[Qt third-party notices](https://doc.qt.io/qt-6/licenses-used-in-qt.html),
[PyInstaller license](https://pyinstaller.org/en/stable/license.html).

## Archive backends added in 1.1

- pyzipper 0.4.0: MIT and inherited Python license; pycryptodomex 3.23.0:
  BSD/public-domain components.
- py7zr 1.1.3, pybcj 1.0.8, pyppmd 1.3.1, inflate64 1.0.4,
  multivolumefile 0.2.3: LGPL-2.1-or-later.
- Brotli 1.2.0 and texttable 1.7.0: MIT; psutil 7.2.2: BSD-3-Clause;
  backports.zstd 1.7.0: PSF-2.0 with bundled Zstandard license notices.
- UnRAR64.dll 7.21: official UnRAR DLL freeware license, copyright Alexander Roshal.
  The SDK permits use in software handling RAR archives. Full license:
  `licenses/UNRAR-LICENSE.txt`. No WinRAR compressor is distributed.
- Diagnostic RAR fixtures: Copyright Marko Kreen, ISC; license accompanies fixtures.
- Inno Setup 6.7.3: installer engine by Jordan Russell and Martijn Laan;
  see https://github.com/jrsoftware/issrc/blob/is-6_7_3/license.txt .

Exact package license files are under `licenses/<package>/`, with version records
in `licenses/archive-backends.json`. Corresponding source distributions accompany
the release and are hashed in `licenses/upstream-sources.json`.
ArchiveLens permits reverse engineering for debugging modifications to LGPL
libraries. Its MIT source and build scripts allow rebuilding with modified versions;
compatible native libraries can also be replaced in the installed `_internal` folder.
See [backend decisions](docs/BACKENDS.md) for provenance and limitations.
