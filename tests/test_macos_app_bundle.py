import importlib.util
import json
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from archivelens import __version__


def load_script(name):
    path = Path(__file__).parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_app(tmp_path, *, development=True, document_types=False):
    app = tmp_path / "ArchiveLens.app"
    contents = app / "Contents"
    executable = contents / "MacOS" / "ArchiveLens"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"fixture")
    plist = {
        "CFBundleIdentifier": "com.cam11505.archivelens",
        "CFBundleDisplayName": "ArchiveLens",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
    }
    if document_types:
        plist["CFBundleDocumentTypes"] = []
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(plist, stream)
    resources = contents / "Resources"
    resources.mkdir()
    info = {
        "schema_version": 1,
        "version": __version__,
        "source_commit": "a" * 40,
        "channel": "development",
        "development": development,
        "os": "macos",
        "architecture": "arm64",
        "artifact_kind": "app",
        "python_version": "3.12.0",
        "pyside_version": "6.11.2",
        "qt_version": "6.11.2",
        "native_backends": {},
        "parity_baseline": {
            "tag": "v1.2.2",
            "commit": "bb0197b0291707287517ba8bdfc3a10ce1ad1149",
        },
    }
    (resources / "build-info.json").write_text(json.dumps(info), encoding="utf-8")
    for name in (
        "compiled-source.json",
        "README.md",
        "README.zh-TW.md",
        "LICENSE",
        "LICENSING.md",
        "THIRD_PARTY_NOTICES.md",
        "QtPdf.fixture",
    ):
        (resources / name).write_bytes(b"fixture")
    licenses = resources / "licenses"
    licenses.mkdir()
    for name in ("license-policy.json", "upstream-sources.json", "UNRAR-LICENSE.txt"):
        (licenses / name).write_bytes(b"fixture")
    native = contents / "Frameworks" / "native"
    native.mkdir(parents=True)
    (native / "libunrar.dylib").write_bytes(b"fixture")
    plugins = contents / "Frameworks" / "PySide6" / "Qt" / "plugins" / "imageformats"
    plugins.mkdir(parents=True)
    for name in ("libqgif.dylib", "libqjpeg.dylib", "libqtiff.dylib", "libqwebp.dylib"):
        (plugins / name).write_bytes(b"fixture")
    return app


def test_macos_bundle_structure_and_metadata(tmp_path):
    module = load_script("verify_macos_app.py")
    report = module.inspect_structure(fake_app(tmp_path), "a" * 40, allow_development=True)
    assert report["build_info"]["parity_baseline"]["tag"] == "v1.2.2"
    assert report["plist"]["CFBundleIdentifier"] == "com.cam11505.archivelens"


def test_macos_bundle_rejects_release_claim_and_finder_scope(tmp_path):
    module = load_script("verify_macos_app.py")
    app = fake_app(tmp_path)
    with pytest.raises(ValueError, match="allow-development"):
        module.inspect_structure(app, "a" * 40, allow_development=False)
    app = fake_app(tmp_path / "finder", document_types=True)
    with pytest.raises(ValueError, match="issue #47"):
        module.inspect_structure(app, "a" * 40, allow_development=True)


def test_macos_icon_master_is_opaque_inside_transparent_canvas():
    module = load_script("build_macos_app.py")
    icon = module.draw_icon(1024)
    assert icon.size == (1024, 1024)
    assert icon.getpixel((0, 0))[3] == 0
    assert icon.getpixel((512, 512))[3] == 255


def test_macos_spec_keeps_later_issue_scope_out():
    spec = (Path(__file__).parents[1] / "scripts" / "MacOSArchiveLens.spec").read_text(
        encoding="utf-8"
    )
    assert 'target_arch="arm64"' in spec
    assert "argv_emulation=False" in spec
    assert "CFBundleDocumentTypes" not in spec
    assert "codesign_identity" not in spec


def test_macos_packaged_self_test_uses_absolute_report_path(tmp_path, monkeypatch):
    module = load_script("verify_macos_app.py")
    app = tmp_path / "ArchiveLens.app"
    executable = app / "Contents" / "MacOS" / "ArchiveLens"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"fixture")
    monkeypatch.chdir(tmp_path)

    def fake_run(command, **kwargs):
        assert Path(command[2]).is_absolute()
        assert kwargs["cwd"] == app.parent
        Path(command[2]).write_text(
            json.dumps({"success": True, "version": __version__}), encoding="utf-8"
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    report = module.run_self_test(app, Path("outputs/packaged-self-test.json"))

    assert report == {"success": True, "version": __version__}
    assert (tmp_path / "outputs" / "packaged-self-test.json").is_file()
