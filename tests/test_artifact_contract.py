import copy
import hashlib

import pytest

from archivelens import __version__
from scripts.artifact_contract import (
    verify_build_info,
    verify_checksums,
    verify_file_record,
    verify_license_metadata,
    verify_source_metadata,
)
from tests.test_release import release_build_info, release_policy, release_sbom


def check_info(info):
    verify_build_info(
        info,
        version=__version__,
        commit="a" * 40,
        os_name=info["os"],
        architecture=info["architecture"],
        kind=info["artifact_kind"],
        allow_development=True,
    )


@pytest.mark.parametrize(
    "os_name,architecture,kind", [("windows", "x64", "portable"), ("macos", "arm64", "app")]
)
def test_shared_build_contract(os_name, architecture, kind):
    info = release_build_info(True)
    info.update(os=os_name, architecture=architecture, artifact_kind=kind)
    info["native_backends"]["rar"]["architecture"] = architecture
    check_info(info)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("source_commit", "b" * 40),
        ("development", "false"),
        ("channel", "development"),
        ("parity_baseline", {}),
        ("python_version", ""),
        ("pyside_version", ""),
        ("qt_version", ""),
        ("native_backends", {}),
    ],
)
def test_bad_build_metadata(key, value):
    info = release_build_info()
    info[key] = value
    with pytest.raises(ValueError):
        check_info(info)


def test_missing_field_and_native_mismatch():
    info = release_build_info()
    del info["qt_version"]
    with pytest.raises(ValueError, match="Missing"):
        check_info(info)
    for key, value in [("architecture", "arm64"), ("sha256", "invalid")]:
        info = release_build_info()
        info["native_backends"]["rar"][key] = value
        with pytest.raises(ValueError, match="architecture/hash"):
            check_info(info)


@pytest.mark.parametrize(
    "key,value",
    [("os", "linux"), ("architecture", "arm64"), ("artifact_kind", "dmg"), ("version", "0.0.0")],
)
def test_platform_expectations_are_not_supplied_by_artifact(key, value):
    info = release_build_info()
    info[key] = value
    with pytest.raises(ValueError):
        verify_build_info(
            info,
            version=__version__,
            commit="a" * 40,
            os_name="windows",
            architecture="x64",
            kind="portable",
            allow_development=False,
        )


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "a\\b", "a//b", "a/./b"])
def test_manifest_rejects_unsafe_paths(name):
    with pytest.raises(ValueError, match="Unsafe"):
        verify_file_record(name, {"size": 1, "sha256": "a" * 64})


@pytest.mark.parametrize(
    "record",
    [
        {"size": True, "sha256": "a" * 64},
        {"size": -1, "sha256": "a" * 64},
        {"size": 1, "sha256": "bad"},
    ],
)
def test_manifest_rejects_invalid_records(record):
    with pytest.raises(ValueError):
        verify_file_record("file", record)


def test_checksum_inventory_tampering_and_duplicates(tmp_path):
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"fixture")
    line = f"{hashlib.sha256(b'fixture').hexdigest()}  artifact\n"
    checksums = tmp_path / "SHA256SUMS.txt"
    checksums.write_text(line, encoding="utf-8")
    assert set(verify_checksums(tmp_path)) == {"artifact"}
    checksums.write_text(line * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="record"):
        verify_checksums(tmp_path)
    checksums.write_text(line, encoding="utf-8")
    (tmp_path / "unexpected").write_bytes(b"extra")
    with pytest.raises(ValueError, match="inventory"):
        verify_checksums(tmp_path)
    artifact.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_checksums(tmp_path, expected_files={"artifact"})
    artifact.unlink()
    with pytest.raises(ValueError):
        verify_checksums(tmp_path, expected_files={"artifact"})


def test_license_and_sbom_negative_cases():
    policy, sbom = release_policy(), release_sbom()
    verify_license_metadata(policy, sbom, version=__version__, commit="a" * 40)
    for mutation in ("commit", "unreviewed", "license", "duplicate", "missing"):
        changed = copy.deepcopy(sbom)
        if mutation == "commit":
            changed["documentNamespace"] += "wrong"
        elif mutation == "unreviewed":
            changed["packages"].append({"name": "unreviewed", "licenseDeclared": "MIT"})
        elif mutation == "license":
            changed["packages"][1]["licenseDeclared"] = "MIT"
        elif mutation == "duplicate":
            changed["packages"].append(changed["packages"][1])
        else:
            changed["packages"].pop()
        with pytest.raises(ValueError):
            verify_license_metadata(policy, changed, version=__version__, commit="a" * 40)
    policy["manual_components"][0]["classification"] = "foss"
    with pytest.raises(ValueError, match="UnRAR"):
        verify_license_metadata(policy, sbom, version=__version__, commit="a" * 40)


def test_sources_reject_uncontrolled_reuse_and_bad_metadata():
    sources = [
        {
            "component": name,
            "version": "1",
            "source_archive": "source.tar.gz",
            "source_url": "https://example.test/source",
            "sha256": "a" * 64,
        }
        for name in ("Pillow", "qtpdf", "qtbase", "qtimageformats", "pyside-setup")
    ]
    verify_source_metadata(sources)
    for key, value in [
        ("distribution_url", "https://example.test/reuse"),
        ("source_archive", "../escape"),
        ("sha256", "bad"),
        ("source_url", "http://example.test/source"),
    ]:
        changed = copy.deepcopy(sources)
        changed[0][key] = value
        with pytest.raises(ValueError):
            verify_source_metadata(changed)
    with pytest.raises(ValueError):
        verify_source_metadata(sources[:-1])
