# Minimal cross-platform frozen diagnostic for the v1.3 RAR gate.
import sys
from pathlib import Path

root = Path.cwd()
library = {
    "win32": "UnRAR64.dll",
    "darwin": "libunrar.dylib",
}.get(sys.platform, "libunrar.so")

a = Analysis(
    [str(root / "scripts" / "v13_platform_diagnostic.py")],
    pathex=[str(root / "src")],
    binaries=[(str(root / "outputs" / "backends" / library), "native")],
    datas=[(str(root / "tests" / "fixtures" / "rar"), "self-test-rar")],
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
    name="ArchiveLens-v13-rar",
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
    name="ArchiveLens-v13-rar",
)
