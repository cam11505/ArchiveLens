import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pytest

from archivelens import __version__
from scripts.license_audit import load_policy, validate_runtime_package_names
from scripts.prepare_licenses import MAX_LICENSE_PATH_LENGTH, bundled_license_path
from scripts.verify_release import verify_archive
from scripts.verify_release_set import verify_release_set


def release_policy():
    return {
        "schema_version": 1,
        "python_packages": {},
        "manual_components": [
            {
                "name": "UnRAR native library",
                "classification": "redistributable-non-foss",
                "approved_for_distribution": True,
            }
        ],
    }


def release_sbom():
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"ArchiveLens-{__version__}-release-sbom",
        "documentNamespace": f"https://example.invalid/ArchiveLens/{__version__}",
        "creationInfo": {"created": "2026-01-01T00:00:00Z", "creators": ["Tool: test"]},
        "packages": [
            {
                "SPDXID": "SPDXRef-Package-ArchiveLens",
                "name": "ArchiveLens",
                "versionInfo": __version__,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "MIT",
                "licenseDeclared": "MIT",
                "copyrightText": "NOASSERTION",
            }
        ],
    }


def create_portable(path, corrupt=False, development=False, sources=None):
    policy = json.dumps(release_policy()).encode()
    sbom = json.dumps(release_sbom()).encode()
    files = {
        name: b"fixture"
        for name in [
            "ArchiveLens.exe",
            "_internal/native/UnRAR64.dll",
            "licenses/UNRAR-LICENSE.txt",
            "licenses/archive-backends.json",
            "LICENSE",
            "LICENSING.md",
            "THIRD_PARTY_NOTICES.md",
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
        ]
    }
    files["licenses/license-policy.json"] = policy
    files[f"ArchiveLens-{__version__}.spdx.json"] = sbom
    files["build-info.json"] = json.dumps(
        {"version": __version__, "source_commit": "a" * 40, "development": development}
    ).encode()
    if sources is not None:
        files["licenses/upstream-sources.json"] = json.dumps(sources).encode()
    manifest = {
        name: {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        for name, content in files.items()
    }
    if corrupt:
        files["ArchiveLens.exe"] = b"changed"
    with ZipFile(path, "w") as target:
        for name, content in files.items():
            target.writestr("ArchiveLens/" + name, content)
        target.writestr("ArchiveLens/manifest.json", json.dumps(manifest))


def test_release_commit_hash_and_inventory(tmp_path):
    path = tmp_path / "portable.zip"
    create_portable(path)
    assert verify_archive(path, "a" * 40)["version"] == __version__
    with pytest.raises(ValueError, match="different commit"):
        verify_archive(path, "b" * 40)
    with ZipFile(path, "a") as target:
        target.writestr("ArchiveLens/extra.txt", "unexpected")
    with pytest.raises(ValueError, match="inventory"):
        verify_archive(path)


def test_release_content_tampering(tmp_path):
    path = tmp_path / "portable.zip"
    create_portable(path, corrupt=True)
    with pytest.raises(ValueError, match="SHA-256"):
        verify_archive(path)


def test_reject_development_and_unsafe_paths(tmp_path):
    path = tmp_path / "portable.zip"
    create_portable(path, development=True)
    with pytest.raises(ValueError, match="development"):
        verify_archive(path)
    assert verify_archive(path, allow_development=True)["development"]
    with ZipFile(path, "a") as target:
        target.writestr("../outside.txt", "unsafe")
    with pytest.raises(ValueError, match="Unsafe"):
        verify_archive(path, allow_development=True)


def test_complete_release_set_checksum_and_source_verification(tmp_path):
    source_name = "fixture-upstream.tar.gz"
    source_content = b"upstream source fixture"
    source_digest = hashlib.sha256(source_content).hexdigest()
    sources = [
        {
            "component": component,
            "source_archive": source_name,
            "sha256": source_digest,
        }
        for component in ("Pillow", "qtbase", "qtimageformats", "pyside-setup")
    ]
    sources.append(
        {
            "component": "qtpdf",
            "version": "6.11.2",
            "source_archive": "qtwebengine-everywhere-src-6.11.2.tar.xz",
            "sha256": "6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163",
            "distribution_url": (
                "https://github.com/cam11505/ArchiveLens/releases/download/v1.2.1/"
                "qtwebengine-everywhere-src-6.11.2.tar.xz"
            ),
        }
    )
    portable = tmp_path / f"ArchiveLens-{__version__}-windows-x64.zip"
    create_portable(portable, sources=sources)
    build_info = {"version": __version__, "source_commit": "a" * 40, "development": False}
    (tmp_path / "build-info.json").write_text(json.dumps(build_info), encoding="utf-8")
    (tmp_path / f"ArchiveLens-{__version__}-setup-x64.exe").write_bytes(b"installer")
    (tmp_path / f"archivelens-{__version__}-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / f"archivelens-{__version__}.tar.gz").write_bytes(b"sdist")
    (tmp_path / f"ArchiveLens-{__version__}.spdx.json").write_text(
        json.dumps(release_sbom()), encoding="utf-8"
    )
    (tmp_path / "license-policy.json").write_text(json.dumps(release_policy()), encoding="utf-8")
    (tmp_path / "LICENSING.md").write_bytes(b"fixture")
    (tmp_path / "THIRD_PARTY_NOTICES.md").write_bytes(b"fixture")
    (tmp_path / source_name).write_bytes(source_content)
    artifacts = sorted(path for path in tmp_path.iterdir() if path.is_file())
    (tmp_path / "SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts
        ),
        encoding="utf-8",
    )
    assert verify_release_set(tmp_path, "a" * 40)["version"] == __version__
    (tmp_path / source_name).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_release_set(tmp_path, "a" * 40)


def test_release_set_rejects_uncontrolled_or_duplicated_source_reference(tmp_path):
    record = {
        "component": "qtpdf",
        "source_archive": "qtwebengine-everywhere-src-6.11.2.tar.xz",
        "sha256": "6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163",
        "distribution_url": "https://download.qt.io/source.tar.xz",
    }
    from scripts.verify_release_set import verify_distribution_source

    with pytest.raises(ValueError, match="Invalid controlled source reference"):
        verify_distribution_source(record, tmp_path)
    record["distribution_url"] = (
        "https://github.com/cam11505/ArchiveLens/releases/download/v1.2.1/"
        "qtwebengine-everywhere-src-6.11.2.tar.xz"
    )
    record["version"] = "6.11.2"
    record["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Invalid controlled source reference"):
        verify_distribution_source(record, tmp_path)
    record["sha256"] = "6101c1aa00ff933d1b65ee5d167f76e8d71b9ac5b378b0111277723ebda7c163"
    (tmp_path / record["source_archive"]).write_bytes(b"duplicate")
    with pytest.raises(ValueError, match="must not be duplicated"):
        verify_distribution_source(record, tmp_path)


def test_license_policy_rejects_unreviewed_runtime_dependency():
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    validate_runtime_package_names(["PySide6", "Pillow", "py7zr"], policy)
    with pytest.raises(RuntimeError, match="Unreviewed runtime dependencies"):
        validate_runtime_package_names(["PySide6", "unreviewed-decoder"], policy)


def test_unrar_is_not_mislabeled_as_foss():
    root = Path(__file__).resolve().parents[1]
    policy = load_policy(root)
    unrar = next(
        component
        for component in policy["manual_components"]
        if component["name"] == "UnRAR native library"
    )
    assert unrar["classification"] == "redistributable-non-foss"
    assert unrar["license_expression"] == "NOASSERTION"


def test_installer_declares_pdf_open_with_without_default_association():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "ArchiveLens.iss").read_text(
        encoding="utf-8"
    )
    assert 'ValueName: ".pdf"' in script
    assert "Software\\Classes\\ArchiveLens.Pdf\\shell\\open\\command" in script
    assert 'Software\\Classes\\.pdf\\OpenWithProgids"' in script
    assert 'Software\\Classes\\.pdf"; ValueType' not in script


def test_long_upstream_license_paths_are_bounded_and_stably_indexable():
    short = PurePosixPath("LICENSES/LGPL-3.0-only.txt")
    long = PurePosixPath(
        "src/3rdparty/chromium/third_party/devtools-frontend/src/node_modules/"
        "@babel/helper-compilation-targets/node_modules/semver/LICENSE"
    )

    assert bundled_license_path(short) == Path(*short.parts)
    bundled = bundled_license_path(long)
    assert bundled.parts[0] == "_long"
    assert len(bundled.as_posix()) <= MAX_LICENSE_PATH_LENGTH
    assert bundled == bundled_license_path(long)
