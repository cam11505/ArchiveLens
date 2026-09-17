"""Verify every portable file, then optionally run the EXE without Python on PATH."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from archivelens import __version__


def verify_archive(
    path: Path, expected_commit: str | None = None, allow_development: bool = False
) -> dict:
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        for name in names:
            parts = PurePosixPath(name)
            if (
                parts.is_absolute()
                or ".." in parts.parts
                or "\\" in name
                or ":" in name
                or not name.startswith("ArchiveLens/")
            ):
                raise ValueError("Unsafe portable archive path")
        if archive.testzip() is not None:
            raise ValueError("Portable ZIP CRC failure")
        manifest = json.loads(archive.read("ArchiveLens/manifest.json"))
        expected = {"ArchiveLens/" + name for name in manifest} | {"ArchiveLens/manifest.json"}
        if set(names) != expected:
            raise ValueError("Portable file inventory does not match its manifest")
        for name, record in manifest.items():
            info = archive.getinfo("ArchiveLens/" + name)
            if info.file_size != record["size"]:
                raise ValueError(f"Size mismatch: {name}")
            with archive.open(info) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != record["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {name}")
        sbom_name = f"ArchiveLens-{__version__}.spdx.json"
        required = {
            "ArchiveLens.exe",
            "_internal/native/UnRAR64.dll",
            "licenses/UNRAR-LICENSE.txt",
            "licenses/archive-backends.json",
            "licenses/license-policy.json",
            "LICENSE",
            "LICENSING.md",
            "THIRD_PARTY_NOTICES.md",
            sbom_name,
            "build-info.json",
            "licenses/upstream-sources.json",
            "_internal/PySide6/plugins/platforms/qwindows.dll",
            "_internal/PySide6/plugins/imageformats/qjpeg.dll",
            "_internal/PySide6/plugins/imageformats/qgif.dll",
            "_internal/PySide6/plugins/imageformats/qwebp.dll",
            "_internal/PySide6/plugins/imageformats/qtiff.dll",
            "_internal/PySide6/QtPdf.pyd",
            "_internal/PySide6/Qt6Pdf.dll",
            "licenses/Pillow/LICENSE",
            "licenses/qtpdf/LICENSE.Chromium",
        }
        if not required.issubset(manifest):
            raise ValueError("Required application files are missing")
        if any(PurePosixPath(name).name.lower() == "icuuc.dll" for name in manifest):
            raise ValueError("Bundled ICU would shadow the Windows system ICU ABI")
        if any(
            any(part in name.lower() for part in ("virtualkeyboard", "qt6qml", "qt6quick"))
            for name in manifest
        ):
            raise ValueError("Unused Qt modules must not be distributed")
        build = json.loads(archive.read("ArchiveLens/build-info.json"))
        if build["version"] != __version__:
            raise ValueError("Unexpected release version")
        if build["development"] and not allow_development:
            raise ValueError("This is a development package, not a release")
        if expected_commit and build["source_commit"] != expected_commit:
            raise ValueError("The release was built from a different commit")
        policy = json.loads(archive.read("ArchiveLens/licenses/license-policy.json"))
        if policy.get("schema_version") != 1:
            raise ValueError("Unsupported bundled license-policy schema")
        unrar = next(
            (
                component
                for component in policy.get("manual_components", [])
                if component.get("name") == "UnRAR64.dll"
            ),
            None,
        )
        if not unrar or unrar.get("classification") != "redistributable-non-foss":
            raise ValueError("Bundled UnRAR licensing classification is missing")
        sbom = json.loads(archive.read("ArchiveLens/" + sbom_name))
        if sbom.get("spdxVersion") != "SPDX-2.3" or sbom.get("dataLicense") != "CC0-1.0":
            raise ValueError("Invalid SPDX SBOM header")
        application = next(
            (
                package
                for package in sbom.get("packages", [])
                if package.get("name") == "ArchiveLens"
            ),
            None,
        )
        if not application or application.get("versionInfo") != __version__:
            raise ValueError("SPDX SBOM does not describe this ArchiveLens version")
        return build


def run_packaged_test(path: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    # This extracts the application distribution, never an end-user photo archive.
    with tempfile.TemporaryDirectory(prefix="ArchiveLens-release-") as temp:
        target = Path(temp)
        with ZipFile(path) as archive:
            archive.extractall(target)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(("PYTHON", "QT_", "QML", "VIRTUAL_ENV"))
        }
        system = Path(os.environ["SystemRoot"])
        env["PATH"] = os.pathsep.join([str(system / "System32"), str(system)])
        report = (output / "packaged-self-test.json").resolve()
        report.unlink(missing_ok=True)
        command = [
            str(target / "ArchiveLens" / "ArchiveLens.exe"),
            "--self-test-report",
            str(report),
            "--self-test-screenshot",
            str((output / "packaged-window.png").resolve()),
        ]
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        subprocess.run(command, cwd=target, env=env, startupinfo=startup, check=True, timeout=60)
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result["success"] or len(result["checks"]) < 23:
            raise ValueError("Packaged application did not pass all acceptance checks")
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-commit")
    parser.add_argument("--allow-development", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("outputs/release-verification"))
    args = parser.parse_args()
    build = verify_archive(args.archive, args.expected_commit, args.allow_development)
    print(f"Manifest verified: {build['version']} at {build['source_commit']}")
    if args.run:
        if sys.platform != "win32":
            parser.error("The portable application must be tested on Windows")
        print(json.dumps(run_packaged_test(args.archive.resolve(), args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
