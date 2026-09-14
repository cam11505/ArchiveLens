# PyInstaller one-folder layout keeps Qt DLLs replaceable and startup predictable.
from pathlib import Path
import os

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "scripts" / "frozen_entry.py")],
    pathex=[str(root / "src")],
    binaries=[(str(root / "outputs/backends/UnRAR64.dll"), "native")],
    datas=[(str(root / "tests/fixtures/rar"), "self-test-rar")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["setuptools", "pkg_resources", "tkinter", "PySide6.QtPdf", "PySide6.QtSvg", "PySide6.QtQml",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
allowed_images = {"qjpeg.dll", "qgif.dll", "qwebp.dll"}
def required_binary(item):
    name = item[0].replace("\\", "/").lower()
    if any(part in name for part in ("virtualkeyboard", "qt6qml", "qt6quick")):
        return False
    if "/imageformats/" in name:
        return name.rsplit("/", 1)[-1] in allowed_images
    # Qt uses the Windows ICU ABI; a different ICU found on PATH is incompatible.
    return name.rsplit("/", 1)[-1] not in {"qt6pdf.dll", "qt6svg.dll", "icuuc.dll", "icudt78.dll"}
a.binaries = [item for item in a.binaries if required_binary(item)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="ArchiveLens",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=bool(os.environ.get("ARCHIVELENS_CONSOLE")), disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ArchiveLens")
