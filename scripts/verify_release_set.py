"""Verify the complete release directory and its final SHA-256 inventory."""

import argparse
import hashlib
import json
from pathlib import Path, PurePath
from zipfile import ZipFile

from archivelens import __version__

if __package__:
    from scripts.verify_release import verify_archive
else:
    from verify_release import verify_archive


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_release_set(directory: Path, expected_commit: str | None = None) -> dict:
    checksums = directory / "SHA256SUMS.txt"
    if not checksums.is_file():
        raise ValueError("SHA256SUMS.txt is missing")
    records = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not name
            or PurePath(name).name != name
            or name in records
        ):
            raise ValueError("Invalid release checksum record")
        records[name] = digest
    actual = {path.name for path in directory.iterdir() if path.is_file() and path != checksums}
    if set(records) != actual:
        raise ValueError("Release checksum inventory mismatch")
    for name, digest in records.items():
        if sha256(directory / name) != digest:
            raise ValueError(f"Release SHA-256 mismatch: {name}")

    prefix = f"ArchiveLens-{__version__}"
    portable = directory / f"{prefix}-windows-x64.zip"
    installer = directory / f"{prefix}-setup-x64.exe"
    wheel = directory / f"archivelens-{__version__}-py3-none-any.whl"
    source_dist = directory / f"archivelens-{__version__}.tar.gz"
    sbom = directory / f"{prefix}.spdx.json"
    required = {
        portable,
        installer,
        wheel,
        source_dist,
        directory / "build-info.json",
        directory / "LICENSING.md",
        directory / "THIRD_PARTY_NOTICES.md",
        directory / "license-policy.json",
        sbom,
    }
    if not all(path.is_file() for path in required):
        raise ValueError("Required v1.2 release artifacts are missing")
    if any(
        path.name.startswith("ArchiveLens-") and not path.name.startswith(prefix)
        for path in directory.iterdir()
    ):
        raise ValueError("Release directory contains another ArchiveLens version")
    build = verify_archive(portable, expected_commit)
    standalone_build = json.loads((directory / "build-info.json").read_text(encoding="utf-8"))
    if standalone_build != build:
        raise ValueError("Standalone build metadata differs from portable metadata")
    with ZipFile(portable) as archive:
        sources = json.loads(archive.read("ArchiveLens/licenses/upstream-sources.json"))
        bundled_sbom = json.loads(archive.read(f"ArchiveLens/{prefix}.spdx.json"))
        bundled_policy = json.loads(archive.read("ArchiveLens/licenses/license-policy.json"))
        bundled_licensing = archive.read("ArchiveLens/LICENSING.md")
        bundled_notices = archive.read("ArchiveLens/THIRD_PARTY_NOTICES.md")
    standalone_sbom = json.loads(sbom.read_text(encoding="utf-8"))
    if standalone_sbom != bundled_sbom:
        raise ValueError("Standalone SPDX SBOM differs from portable metadata")
    standalone_policy = json.loads((directory / "license-policy.json").read_text(encoding="utf-8"))
    if standalone_policy != bundled_policy:
        raise ValueError("Standalone license policy differs from portable metadata")
    if (directory / "LICENSING.md").read_bytes() != bundled_licensing:
        raise ValueError("Standalone licensing guide differs from portable metadata")
    if (directory / "THIRD_PARTY_NOTICES.md").read_bytes() != bundled_notices:
        raise ValueError("Standalone third-party notices differ from portable metadata")
    if standalone_sbom.get("spdxVersion") != "SPDX-2.3":
        raise ValueError("Standalone SPDX SBOM has the wrong schema version")
    components = {record["component"] for record in sources}
    if not {"Pillow", "qtpdf", "qtbase", "qtimageformats", "pyside-setup"} <= components:
        raise ValueError("Required v1.2 source/license components are missing")
    for record in sources:
        source = directory / record["source_archive"]
        if not source.is_file() or sha256(source) != record["sha256"]:
            raise ValueError(f"Upstream source mismatch: {record['component']}")
    return {"version": __version__, "source_commit": build["source_commit"], "files": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path, nargs="?", default=Path("dist/release"))
    parser.add_argument("--expected-commit")
    args = parser.parse_args()
    print(json.dumps(verify_release_set(args.directory, args.expected_commit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
