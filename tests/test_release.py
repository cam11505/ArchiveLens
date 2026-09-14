import hashlib
import json
from zipfile import ZipFile

import pytest

from scripts.verify_release import verify_archive


def create_portable(path, corrupt=False, development=False):
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
        ]
    }
    files["build-info.json"] = json.dumps(
        {"version": "1.1.0", "source_commit": "a" * 40, "development": development}
    ).encode()
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
    assert verify_archive(path, "a" * 40)["version"] == "1.1.0"
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
