"""Verify the unsigned/ad-hoc macOS arm64 ArchiveLens.app produced by issue #46."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from archivelens import __version__

REQUIRED_BUILD_INFO = {
    "schema_version",
    "version",
    "source_commit",
    "channel",
    "development",
    "os",
    "architecture",
    "artifact_kind",
    "python_version",
    "pyside_version",
    "qt_version",
    "native_backends",
    "parity_baseline",
}
BASELINE = {"tag": "v1.2.2", "commit": "bb0197b0291707287517ba8bdfc3a10ce1ad1149"}


def one_match(root: Path, pattern: str) -> Path:
    matches = [path for path in root.rglob(pattern) if path.is_file()]
    if len(matches) != 1:
        raise ValueError(f"Expected one {pattern} in app bundle; found {len(matches)}")
    return matches[0]


def required_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError(f"Required app resource is missing: {path}")
    return path


def inspect_structure(app: Path, expected_commit: str, *, allow_development: bool) -> dict:
    if app.name != "ArchiveLens.app" or not app.is_dir():
        raise ValueError("Expected an ArchiveLens.app directory")
    plist_path = app / "Contents" / "Info.plist"
    executable = app / "Contents" / "MacOS" / "ArchiveLens"
    if not plist_path.is_file() or not executable.is_file():
        raise ValueError("Bundle is missing Info.plist or the main executable")
    with plist_path.open("rb") as stream:
        plist = plistlib.load(stream)
    expected_plist = {
        "CFBundleIdentifier": "com.cam11505.archivelens",
        "CFBundleDisplayName": "ArchiveLens",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
    }
    for key, value in expected_plist.items():
        if plist.get(key) != value:
            raise ValueError(f"Unexpected Info.plist {key}")
    if "CFBundleDocumentTypes" in plist or "UTExportedTypeDeclarations" in plist:
        raise ValueError("Finder document declarations belong to issue #47")

    resources = app / "Contents" / "Resources"
    frameworks = app / "Contents" / "Frameworks"
    info_path = required_file(resources / "build-info.json")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    missing = REQUIRED_BUILD_INFO - info.keys()
    if missing:
        raise ValueError("build-info.json is missing: " + ", ".join(sorted(missing)))
    expected = {
        "schema_version": 1,
        "version": __version__,
        "source_commit": expected_commit,
        "channel": "development",
        "os": "macos",
        "architecture": "arm64",
        "artifact_kind": "app",
        "parity_baseline": BASELINE,
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f"Unexpected build-info.json {key}")
    if info.get("development") and not allow_development:
        raise ValueError("Development app requires --allow-development")

    required = {
        "compiled-source.json": resources / "compiled-source.json",
        "README.md": resources / "README.md",
        "README.zh-TW.md": resources / "README.zh-TW.md",
        "LICENSE": resources / "LICENSE",
        "LICENSING.md": resources / "LICENSING.md",
        "THIRD_PARTY_NOTICES.md": resources / "THIRD_PARTY_NOTICES.md",
        "license-policy.json": resources / "licenses" / "license-policy.json",
        "upstream-sources.json": resources / "licenses" / "upstream-sources.json",
        "UNRAR-LICENSE.txt": resources / "licenses" / "UNRAR-LICENSE.txt",
        "libunrar.dylib": frameworks / "native" / "libunrar.dylib",
    }
    located = {name: str(required_file(path).relative_to(app)) for name, path in required.items()}
    if any("qtwebengine" in path.name.casefold() for path in app.rglob("*")):
        raise ValueError("QtWebEngine must not be bundled")
    image_plugins = frameworks / "PySide6" / "Qt" / "plugins" / "imageformats"
    for plugin in ("libqgif.dylib", "libqjpeg.dylib", "libqtiff.dylib", "libqwebp.dylib"):
        required_file(image_plugins / plugin)
    if not any("qtpdf" in path.name.casefold() for path in app.rglob("*") if path.is_file()):
        raise ValueError("QtPdf runtime is missing")
    return {
        "app": str(app.resolve()),
        "build_info": info,
        "executable": str(executable),
        "located": located,
        "plist": expected_plist,
    }


def verify_native_architecture(app: Path) -> dict[str, str]:
    checked = {}
    for path in sorted(item for item in app.rglob("*") if item.is_file()):
        description = subprocess.run(
            ["file", "-b", str(path)], capture_output=True, text=True, check=True
        ).stdout.strip()
        if "Mach-O" not in description:
            continue
        subprocess.run(["lipo", str(path), "-verify_arch", "arm64"], check=True)
        checked[str(path.relative_to(app))] = description
    if not checked:
        raise ValueError("No Mach-O files were found in the app bundle")
    return checked


def run_self_test(app: Path, report: Path) -> dict:
    # Resolve the report before changing the launch directory. A relative path would
    # otherwise be written below the isolated staging directory and read from the repo.
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(key, None)
    with TemporaryDirectory(prefix="ArchiveLens-Finder-launch-") as directory:
        launch_root = Path(directory)
        staged_app = launch_root / app.name
        subprocess.run(["/usr/bin/ditto", str(app), str(staged_app)], check=True)
        subprocess.run(
            [
                "/usr/bin/open",
                "-W",
                "-n",
                str(staged_app),
                "--args",
                "--self-test-report",
                str(report),
            ],
            cwd=launch_root,
            env=env,
            check=True,
            timeout=180,
        )
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not payload.get("success") or payload.get("version") != __version__:
        raise ValueError("Packaged self-test failed")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--allow-development", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/macos-app-verification/report.json")
    )
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("macOS app verification must run on macOS")
    result = inspect_structure(
        args.app.resolve(), args.expected_commit, allow_development=args.allow_development
    )
    result["native_files"] = verify_native_architecture(args.app.resolve())
    if args.run:
        result["self_test"] = run_self_test(
            args.app.resolve(), args.output.parent / "packaged-self-test.json"
        )
    result["success"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Verified ArchiveLens.app: {len(result['native_files'])} arm64 Mach-O files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
