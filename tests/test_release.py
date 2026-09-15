import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from archivelens import __version__
from scripts.verify_release import verify_archive
from scripts.verify_release_set import verify_release_set


def create_portable(path, corrupt=False, development=False, sources=None):
    files = {
        name: b"fixture"
        for name in [
            "ArchiveLens.exe",
            "_internal/native/UnRAR64.dll",
            "licenses/UNRAR-LICENSE.txt",
            "licenses/archive-backends.json",
            "LICENSE",
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
        for component in ("Pillow", "qtpdf", "qtbase", "qtimageformats", "pyside-setup")
    ]
    portable = tmp_path / f"ArchiveLens-{__version__}-windows-x64.zip"
    create_portable(portable, sources=sources)
    build_info = {"version": __version__, "source_commit": "a" * 40, "development": False}
    (tmp_path / "build-info.json").write_text(json.dumps(build_info), encoding="utf-8")
    (tmp_path / f"ArchiveLens-{__version__}-setup-x64.exe").write_bytes(b"installer")
    (tmp_path / f"archivelens-{__version__}-py3-none-any.whl").write_bytes(b"wheel")
    (tmp_path / f"archivelens-{__version__}.tar.gz").write_bytes(b"sdist")
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


def test_installer_declares_pdf_open_with_without_default_association():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "ArchiveLens.iss").read_text(
        encoding="utf-8"
    )
    assert 'ValueName: ".pdf"' in script
    assert "Software\\Classes\\ArchiveLens.Pdf\\shell\\open\\command" in script
    assert 'Software\\Classes\\.pdf\\OpenWithProgids"' in script
    assert 'Software\\Classes\\.pdf"; ValueType' not in script
