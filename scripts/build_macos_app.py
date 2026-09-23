"""Build the unsigned/ad-hoc macOS arm64 ArchiveLens.app for v1.3 issue #46."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import qVersion

from archivelens import __version__

BASELINE_TAG = "v1.2.2"
BASELINE_COMMIT = "bb0197b0291707287517ba8bdfc3a10ce1ad1149"
DEPENDENCIES = (
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "Pillow",
    "shiboken6",
    "pyinstaller",
    "pyzipper",
    "py7zr",
    "pycryptodomex",
)
ICON_SIZES = (16, 32, 128, 256, 512)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_revision(root: Path) -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return revision, bool(status.strip())


def build_info(root: Path, *, source_commit: str, dirty: bool) -> dict[str, object]:
    backend = json.loads(
        (root / "outputs" / "backends" / "UNRAR-BACKEND.json").read_text(encoding="utf-8")
    )
    return {
        "schema_version": 1,
        "version": __version__,
        "source_commit": source_commit,
        "channel": "development",
        "development": True,
        "dirty": dirty,
        "os": "macos",
        "architecture": "arm64",
        "artifact_kind": "app",
        "python_version": platform.python_version(),
        "pyside_version": importlib.metadata.version("PySide6"),
        "qt_version": qVersion(),
        "dependencies": {name: importlib.metadata.version(name) for name in DEPENDENCIES},
        "native_backends": {
            "rar": {
                "name": backend["binary"],
                "version": backend["version"],
                "architecture": backend["architecture"],
                "sha256": backend["binary_sha256"],
            }
        },
        "parity_baseline": {"tag": BASELINE_TAG, "commit": BASELINE_COMMIT},
    }


def compiled_source_fingerprints(root: Path) -> dict[str, str]:
    paths = sorted((root / "src").rglob("*.py"))
    paths.extend(
        [
            root / "scripts" / "MacOSArchiveLens.spec",
            root / "scripts" / "build_macos_app.py",
            root / "scripts" / "frozen_entry.py",
            root / "scripts" / "verify_macos_app.py",
        ]
    )
    return {path.relative_to(root).as_posix(): sha256(path) for path in paths}


def draw_icon(size: int) -> Image.Image:
    scale = size / 1024
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(values):
        return tuple(round(value * scale) for value in values)

    draw.rounded_rectangle(box((64, 64, 960, 960)), radius=round(208 * scale), fill="#172136")
    draw.rounded_rectangle(box((190, 190, 690, 822)), radius=round(56 * scale), fill="#F5F1E8")
    draw.rounded_rectangle(box((250, 250, 630, 762)), radius=round(28 * scale), fill="#D9E7F2")
    draw.ellipse(box((520, 480, 850, 810)), width=max(1, round(72 * scale)), outline="#F2A65A")
    draw.line(box((756, 718, 902, 864)), fill="#F2A65A", width=max(1, round(82 * scale)))
    draw.line(box((300, 350, 575, 350)), fill="#5C718B", width=max(1, round(34 * scale)))
    draw.line(box((300, 445, 520, 445)), fill="#5C718B", width=max(1, round(34 * scale)))
    return image


def create_icns(output: Path) -> Path:
    iconset = output.parent / "ArchiveLens.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir(parents=True)
    for size in ICON_SIZES:
        draw_icon(size).save(iconset / f"icon_{size}x{size}.png")
        draw_icon(size * 2).save(iconset / f"icon_{size}x{size}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(output)], check=True)
    return output


def validate_inputs(root: Path) -> None:
    required = [
        root / "outputs" / "backends" / "libunrar.dylib",
        root / "outputs" / "backends" / "UNRAR-BACKEND.json",
        root / "build" / "third-party-licenses" / "upstream-sources.json",
        root / "build" / "third-party-licenses" / "UNRAR-LICENSE.txt",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing macOS bundle prerequisites: " + ", ".join(missing))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--development",
        action="store_true",
        help="Required for #46 unsigned/ad-hoc builds; official release mode belongs to #49",
    )
    args = parser.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("ArchiveLens.app must be built natively on macOS arm64")
    if not args.development:
        raise SystemExit("#46 creates development apps only; pass --development")

    root = Path(__file__).resolve().parents[1]
    validate_inputs(root)
    commit, dirty = git_revision(root)
    metadata = root / "build" / "macos-app-metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "build-info.json").write_text(
        json.dumps(build_info(root, source_commit=commit, dirty=dirty), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (metadata / "compiled-source.json").write_text(
        json.dumps(compiled_source_fingerprints(root), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    icon = create_icns(metadata / "ArchiveLens.icns")
    env = os.environ.copy()
    env["ARCHIVELENS_MACOS_METADATA_DIR"] = str(metadata)
    env["ARCHIVELENS_MACOS_ICON"] = str(icon)
    env["ARCHIVELENS_APP_VERSION"] = __version__
    env["PYINSTALLER_CONFIG_DIR"] = str(root / "build" / "pyinstaller-cache-macos")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / "build" / "pyinstaller-macos"),
            str(root / "scripts" / "MacOSArchiveLens.spec"),
        ],
        cwd=root,
        env=env,
        check=True,
    )
    app = root / "dist" / "ArchiveLens.app"
    if not app.is_dir():
        raise SystemExit("PyInstaller did not create dist/ArchiveLens.app")
    print(f"macOS development application: {app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
