# Self-contained macOS arm64 application bundle for ArchiveLens v1.3 issue #46.
import os
from pathlib import Path

root = Path(SPECPATH).parent
metadata_dir = Path(os.environ["ARCHIVELENS_MACOS_METADATA_DIR"])
icon = Path(os.environ["ARCHIVELENS_MACOS_ICON"])
version = os.environ["ARCHIVELENS_APP_VERSION"]

a = Analysis(
    [str(root / "scripts" / "frozen_entry.py")],
    pathex=[str(root / "src")],
    binaries=[(str(root / "outputs" / "backends" / "libunrar.dylib"), "native")],
    datas=[
        (str(root / "tests" / "fixtures" / "rar"), "self-test-rar"),
        (str(metadata_dir / "build-info.json"), "."),
        (str(metadata_dir / "compiled-source.json"), "."),
        (str(root / "README.md"), "."),
        (str(root / "README.zh-TW.md"), "."),
        (str(root / "LICENSE"), "."),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
        (str(root / "docs" / "LICENSING.md"), "."),
        (str(root / "license-policy.json"), "licenses"),
        (str(root / "build" / "third-party-licenses"), "licenses"),
    ],
    hiddenimports=["PySide6.QtPdf", "PIL.AvifImagePlugin", "PIL.Jpeg2KImagePlugin"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "setuptools",
        "pkg_resources",
        "tkinter",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    noarchive=False,
)


def required_binary(item):
    name = item[0].replace("\\", "/").lower()
    if any(part in name for part in ("virtualkeyboard", "qtqml", "qtquick")):
        return False
    if "/imageformats/" in name:
        return name.rsplit("/", 1)[-1] in {
            "libqgif.dylib",
            "libqjpeg.dylib",
            "libqtiff.dylib",
            "libqwebp.dylib",
        }
    return "qtwebengine" not in name


a.binaries = [item for item in a.binaries if required_binary(item)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ArchiveLens",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch="arm64",
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ArchiveLens")
app = BUNDLE(
    coll,
    name="ArchiveLens.app",
    icon=str(icon),
    bundle_identifier="com.cam11505.archivelens",
    version=version,
    info_plist={
        "CFBundleDisplayName": "ArchiveLens",
        "CFBundleName": "ArchiveLens",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "NSHighResolutionCapable": True,
    },
)
