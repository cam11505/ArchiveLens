"""Platform-neutral artifact metadata, inventory and licensing checks.

These checks never approve native execution, signing or notarization.
"""

import hashlib
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

BASELINE = {"tag": "v1.2.2", "commit": "bb0197b0291707287517ba8bdfc3a10ce1ad1149"}
CONTROLLED_SOURCE_REFERENCES = {
    (
        "https://github.com/cam11505/ArchiveLens/releases/download/v1.2.1/"
        "qtwebengine-everywhere-src-6.11.2.tar.xz"
    ): {
        "component": "qtpdf",
        "version": "6.11.2",
        "source_archive": "qtwebengine-everywhere-src-6.11.2.tar.xz",
        "sha256": "6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163",
    }
}
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


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_relative_name(name: str) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and (
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            and ":" not in name
            and all(part not in {"", "."} for part in name.split("/"))
        )
    )


def verify_build_info(
    info: dict,
    *,
    version: str,
    commit: str | None,
    os_name: str,
    architecture: str,
    kind: str,
    allow_development: bool,
) -> None:
    if not isinstance(info, dict) or REQUIRED_BUILD_INFO - info.keys():
        raise ValueError("Missing common build-info fields")
    if type(info["schema_version"]) is not int or info["schema_version"] != 1:
        raise ValueError("Unsupported build-info schema")
    if type(info["development"]) is not bool:
        raise ValueError("Invalid development channel marker")
    if info["development"] and not allow_development:
        raise ValueError(
            "This is a development package, not a release; requires --allow-development"
        )
    expected = {
        "version": version,
        "os": os_name,
        "architecture": architecture,
        "artifact_kind": kind,
        "parity_baseline": BASELINE,
        "channel": "development" if info["development"] else "release",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f"Unexpected common build-info {key}")
    if not re.fullmatch(r"[a-f0-9]{40}", str(info["source_commit"])) or (
        commit is not None and info["source_commit"] != commit
    ):
        raise ValueError("Artifact was built from a different commit or invalid commit")
    for key in ("python_version", "pyside_version", "qt_version"):
        if not isinstance(info[key], str) or not info[key].strip():
            raise ValueError(f"Missing runtime version: {key}")
    if not isinstance(info["native_backends"], dict) or not info["native_backends"]:
        raise ValueError("Native backend metadata is missing")
    for record in info["native_backends"].values():
        if not isinstance(record, dict) or not all(
            record.get(key) for key in ("name", "version", "architecture")
        ):
            raise ValueError("Invalid native backend metadata")
        if record["architecture"] != architecture or not re.fullmatch(
            r"[a-f0-9]{64}", str(record.get("sha256", ""))
        ):
            raise ValueError("Native backend architecture/hash mismatch")


def verify_file_record(name: str, record: dict) -> None:
    if not safe_relative_name(name) or not isinstance(record, dict):
        raise ValueError("Unsafe artifact manifest path")
    if (
        type(record.get("size")) is not int
        or record["size"] < 0
        or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", "")))
    ):
        raise ValueError("Invalid artifact manifest size/hash")


def verify_checksums(directory: Path, *, expected_files: set[str] | None = None) -> dict:
    checksums = directory / "SHA256SUMS.txt"
    if not checksums.is_file():
        raise ValueError("SHA256SUMS.txt is missing")
    records = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or not safe_relative_name(name)
            or "/" in name
            or name in records
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("Invalid release checksum record")
        records[name] = digest
    actual = (
        expected_files
        if expected_files is not None
        else {path.name for path in directory.iterdir() if path.is_file() and path != checksums}
    )
    if not records or set(records) != actual:
        raise ValueError("Release checksum inventory mismatch")
    for name, digest in records.items():
        file = directory / name
        if file.is_symlink() or not file.is_file() or sha256(file) != digest:
            raise ValueError(f"Release SHA-256 mismatch: {name}")
    return records


def verify_license_metadata(policy: dict, sbom: dict, *, version: str, commit: str) -> None:
    if policy.get("schema_version") != 1:
        raise ValueError("Unsupported bundled license-policy schema")
    records = {record["name"]: record for record in policy.get("manual_components", [])}
    unrar = records.get("UnRAR native library", {})
    if (
        unrar.get("classification") != "redistributable-non-foss"
        or unrar.get("approved_for_distribution") is not True
    ):
        raise ValueError("Bundled UnRAR licensing classification is missing")
    if (
        sbom.get("spdxVersion") != "SPDX-2.3"
        or sbom.get("dataLicense") != "CC0-1.0"
        or not sbom.get("documentNamespace", "").endswith(f"/{version}/{commit}")
    ):
        raise ValueError("SPDX SBOM schema/source commit mismatch")
    packages = sbom.get("packages", [])
    names = [record.get("name") for record in packages]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate SPDX component")
    application = next((record for record in packages if record.get("name") == "ArchiveLens"), {})
    if application.get("versionInfo") != version or application.get("licenseDeclared") != "MIT":
        raise ValueError("SPDX SBOM does not describe this ArchiveLens version/license")
    approved = {**policy.get("python_packages", {}), **records}
    for package in packages:
        name = package.get("name")
        if name == "ArchiveLens":
            continue
        record = approved.get(name, {})
        if record.get("approved_for_distribution") is not True or package.get(
            "licenseDeclared"
        ) != record.get("license_expression", "NOASSERTION"):
            raise ValueError("Unapproved or mismatched SPDX component license")
    if "UnRAR native library" not in names:
        raise ValueError("SPDX SBOM is missing the approved native backend")


def verify_source_metadata(sources: list) -> None:
    if not isinstance(sources, list) or not sources:
        raise ValueError("Upstream source metadata is missing")
    components = set()
    for record in sources:
        name = record.get("component")
        archive = record.get("source_archive", "")
        url = urlparse(record.get("source_url", ""))
        if (
            not isinstance(name, str)
            or not name
            or name in components
            or not safe_relative_name(archive)
            or "/" in archive
            or not record.get("version")
            or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", "")))
            or url.scheme != "https"
            or not url.netloc
        ):
            raise ValueError("Invalid upstream source metadata")
        components.add(name)
        if "distribution_url" in record:
            expected = CONTROLLED_SOURCE_REFERENCES.get(record["distribution_url"])
            if expected is None or any(record.get(key) != value for key, value in expected.items()):
                raise ValueError(f"Invalid controlled source reference: {name}")
    if not {"Pillow", "qtpdf", "qtbase", "qtimageformats", "pyside-setup"} <= components:
        raise ValueError("Required v1.2 source/license components are missing")
