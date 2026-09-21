# Minimal frozen diagnostic for the v1.3 shipped-media qualification gate.
import sys
from pathlib import Path

root = Path.cwd()

a = Analysis(
    [str(root / "scripts" / "v13_media_qualification.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["PySide6.QtPdf", "PIL.AvifImagePlugin", "PIL.Jpeg2KImagePlugin"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)


def required_binary(item):
    name = item[0].replace("\\", "/").lower()
    if sys.platform == "win32" and name.rsplit("/", 1)[-1] in {
        "icuuc.dll",
        "icudt78.dll",
    }:
        # Qt uses the compatible Windows ICU ABI; PySide's same-named copy is incompatible.
        return False
    return "qtwebengine" not in name


a.binaries = [item for item in a.binaries if required_binary(item)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ArchiveLens-v13-media",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ArchiveLens-v13-media",
)
