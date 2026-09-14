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
