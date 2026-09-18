"""Create a manifest-backed portable ZIP and a complete release checksum list."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from archivelens import __version__

if __package__:
    from scripts.license_audit import write_spdx_sbom
else:
    from license_audit import write_spdx_sbom


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--development",
        action="store_true",
        help="Allow an uncommitted local diagnostic package; not for publishing",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    )
    commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "uncommitted"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    )
    dirty = status.returncode != 0 or bool(status.stdout.strip())
    if (dirty or commit == "uncommitted") and not args.development:
        raise SystemExit("Release packaging requires a clean committed checkout.")
    bundle = root / "dist" / "ArchiveLens"
    required = [
        bundle / "ArchiveLens.exe",
        bundle / "licenses" / "upstream-sources.json",
        bundle / "licenses" / "license-policy.json",
        bundle / "LICENSE",
        bundle / "LICENSING.md",
        bundle / "THIRD_PARTY_NOTICES.md",
    ]
    if not all(path.is_file() for path in required):
        raise SystemExit("Portable files/licenses are incomplete; run build_portable.py first.")
    compiled = json.loads((bundle / "compiled-source.json").read_text(encoding="utf-8"))
    for name, fingerprint in compiled.items():
        if sha256(root / name) != fingerprint:
            raise SystemExit(f"Source changed after the EXE build: {name}; rebuild first.")
    info = {
        "version": __version__,
        "source_commit": commit,
        "development": args.development,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in [
                "PySide6",
                "PySide6_Addons",
                "PySide6_Essentials",
                "Pillow",
                "shiboken6",
                "pyinstaller",
                "pyzipper",
                "py7zr",
                "pycryptodomex",
            ]
        },
        "source_files": {
            str(path.relative_to(root)).replace("\\", "/"): sha256(path)
            for path in sorted((root / "src").rglob("*.py"))
        },
    }
    (bundle / "build-info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    sbom_name = f"ArchiveLens-{__version__}.spdx.json"
    sbom = bundle / sbom_name
    write_spdx_sbom(root, sbom, commit)
    manifest = {
        str(path.relative_to(bundle)).replace("\\", "/"): {
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(bundle.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    output = root / "dist" / "release"
    output.mkdir(parents=True, exist_ok=True)
    portable = output / f"ArchiveLens-{__version__}-windows-x64.zip"
    with ZipFile(portable, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, "ArchiveLens/" + path.relative_to(bundle).as_posix())
    sources = json.loads(
        (bundle / "licenses" / "upstream-sources.json").read_text(encoding="utf-8")
    )
    for source in sources:
        path = root / "build" / "upstream-sources" / source["source_archive"]
        if sha256(path) != source["sha256"]:
            raise SystemExit(f"Upstream source hash mismatch: {path.name}")
        if "distribution_url" not in source:
            shutil.copy2(path, output / path.name)
    shutil.copy2(bundle / "build-info.json", output / "build-info.json")
    shutil.copy2(sbom, output / sbom.name)
    shutil.copy2(root / "docs" / "LICENSING.md", output / "LICENSING.md")
    shutil.copy2(root / "license-policy.json", output / "license-policy.json")
    shutil.copy2(root / "THIRD_PARTY_NOTICES.md", output / "THIRD_PARTY_NOTICES.md")
    checksum_files = sorted(
        path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in checksum_files), encoding="utf-8"
    )
    print(f"Created {portable.name}: {portable.stat().st_size:,} bytes; commit {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
