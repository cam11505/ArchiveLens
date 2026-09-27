"""Verify the complete release directory and its final SHA-256 inventory."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from archivelens import __version__

if __package__:
    from scripts.artifact_contract import (
        CONTROLLED_SOURCE_REFERENCES,
        verify_checksums,
        verify_source_metadata,
    )
    from scripts.verify_release import verify_archive
else:
    from artifact_contract import (
        CONTROLLED_SOURCE_REFERENCES,
        verify_checksums,
        verify_source_metadata,
    )
    from verify_release import verify_archive


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_distribution_source(record: dict, directory: Path) -> None:
    source = directory / record["source_archive"]
    distribution_url = record.get("distribution_url")
    if distribution_url:
        expected = CONTROLLED_SOURCE_REFERENCES.get(distribution_url)
        parsed = urlparse(distribution_url)
        expected_path = f"/cam11505/ArchiveLens/releases/download/v1.2.1/{record['source_archive']}"
        if (
            expected is None
            or any(record.get(name) != value for name, value in expected.items())
            or parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or parsed.path != expected_path
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"Invalid controlled source reference: {record['component']}")
        if source.exists():
            raise ValueError(f"Reused source must not be duplicated: {record['component']}")
        return
    if not source.is_file() or sha256(source) != record["sha256"]:
        raise ValueError(f"Upstream source mismatch: {record['component']}")


def verify_release_set(directory: Path, expected_commit: str | None = None) -> dict:
    records = verify_checksums(directory)

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
        raise ValueError("Required release artifacts are missing")
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
    verify_source_metadata(sources)
    for record in sources:
        verify_distribution_source(record, directory)
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
