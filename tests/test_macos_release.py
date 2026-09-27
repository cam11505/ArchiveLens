import base64
import importlib.util
import json
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest


def module():
    path = Path(__file__).parents[1] / "scripts/macos_release.py"
    spec = importlib.util.spec_from_file_location("macos_release", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def values():
    return {
        "MACOS_CERTIFICATE_P12_BASE64": base64.b64encode(b"private-test-certificate").decode(),
        "MACOS_CERTIFICATE_PASSWORD": "private-test-password",
        "MACOS_SIGNING_IDENTITY": "Developer ID Application: Fixture (ABCDEFGHIJ)",
        "APPLE_TEAM_ID": "ABCDEFGHIJ",
        "APPLE_ID": "private-test@example.invalid",
        "APPLE_APP_SPECIFIC_PASSWORD": "private-app-password",
    }


def test_missing_credentials_fails_before_any_command(monkeypatch):
    loaded = module()
    monkeypatch.setattr(loaded.subprocess, "run", lambda *a, **k: pytest.fail("Must not execute"))
    with pytest.raises(loaded.ReleaseError, match="Missing official credentials"):
        loaded.credentials({})


@pytest.mark.parametrize(
    "name,bad",
    [
        ("MACOS_CERTIFICATE_P12_BASE64", "not base64"),
        ("MACOS_SIGNING_IDENTITY", "-"),
        ("MACOS_SIGNING_IDENTITY", "Apple Development: Fixture (ABCDEFGHIJ)"),
        ("APPLE_TEAM_ID", "OTHERTEAMXX"),
    ],
)
def test_invalid_credentials_rejected(name, bad):
    loaded = module()
    env = values()
    env[name] = bad
    with pytest.raises(loaded.ReleaseError):
        loaded.credentials(env)


def test_command_failure_never_exposes_secrets(monkeypatch):
    loaded = module()
    monkeypatch.setattr(
        loaded.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=1, stdout="private-test-password", stderr="private-app-password"
        ),
    )
    with pytest.raises(loaded.ReleaseError) as error:
        loaded.run(["tool", "private-test-password"], stage="Notarization")
    assert "private" not in str(error.value)


@pytest.mark.parametrize("status", ["Invalid", "In Progress", "Rejected", None])
def test_notary_nonaccepted_is_fail_closed(monkeypatch, status):
    loaded = module()
    monkeypatch.setattr(loaded, "run", lambda *a, **k: json.dumps({"status": status}))
    with pytest.raises(loaded.ReleaseError, match="not Accepted"):
        loaded.notarize(Path("candidate.dmg"), Path("keychain"), "profile")


def test_notary_accepted_requires_request_id(monkeypatch):
    loaded = module()
    request = "12345678-1234-1234-1234-123456789abc"
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return json.dumps({"status": "Accepted", "id": request})

    monkeypatch.setattr(loaded, "run", run)
    assert loaded.notarize(Path("candidate.dmg"), Path("keychain"), "profile") == request
    assert "--wait" in commands[0]
    assert "--password" not in commands[0]


def test_nested_signing_inside_out_and_minimal_entitlements(tmp_path, monkeypatch):
    loaded = module()
    app = tmp_path / "ArchiveLens.app"
    native = app / "Contents/Frameworks/QtCore.framework/Versions/A/QtCore"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
    executable = app / "Contents/MacOS/ArchiveLens"
    executable.parent.mkdir()
    executable.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
    entitlements = tmp_path / "entitlements.plist"
    entitlements.write_bytes(plistlib.dumps({}))
    commands = []
    monkeypatch.setattr(loaded, "run", lambda command, **kw: commands.append(command))
    loaded.sign_app(app, "identity", Path("keychain"), entitlements)
    assert commands[0][-1] == str(native)
    assert commands[-1][-1] == str(app)
    assert all("--deep" not in command and "--timestamp" in command for command in commands)
    assert all(command[command.index("--options") + 1] == "runtime" for command in commands)
    entitlements.write_bytes(
        plistlib.dumps({"com.apple.security.cs.disable-library-validation": True})
    )
    with pytest.raises(loaded.ReleaseError, match="Unreviewed"):
        loaded.sign_app(app, "identity", Path("keychain"), entitlements)


@pytest.mark.parametrize(
    "details",
    [
        "TeamIdentifier=ABCDEFGHIJ\nSignature=adhoc\nflags=0x10000(runtime)\nTimestamp=now",
        "Authority=Developer ID Application: Fixture\nTeamIdentifier=OTHER\n"
        "flags=0x10000(runtime)\nTimestamp=now",
        "Authority=Developer ID Application: Fixture\nTeamIdentifier=ABCDEFGHIJ\n"
        "flags=0x0\nTimestamp=now",
        "Authority=Developer ID Application: Fixture\nTeamIdentifier=ABCDEFGHIJ\n"
        "flags=0x10000(runtime)",
    ],
)
def test_bad_signature_rejected(monkeypatch, details):
    loaded = module()
    monkeypatch.setattr(
        loaded, "run", lambda command, **kw: details if "--display" in command else ""
    )
    with pytest.raises(loaded.ReleaseError):
        loaded.inspect_signature(Path("app"), "ABCDEFGHIJ", runtime=True)


def test_failed_staple_cannot_succeed(monkeypatch):
    loaded = module()

    def run(command, **kw):
        if "validate" in command:
            raise loaded.ReleaseError("Staple validation failed")
        return ""

    monkeypatch.setattr(loaded, "run", run)
    with pytest.raises(loaded.ReleaseError, match="Staple validation failed"):
        loaded.staple(Path("candidate.dmg"))


def test_keychain_cleanup_even_when_import_fails(monkeypatch):
    loaded = module()
    commands = []
    created_paths = []

    def run(command, **kwargs):
        commands.append(command)
        if command[:2] == ["security", "list-keychains"] and "-s" not in command:
            return '"/existing/login.keychain-db"'
        if "import" in command:
            created_paths.append(Path(command[2]))
            assert created_paths[0].is_file()
            raise loaded.ReleaseError("Import certificate failed")
        return ""

    monkeypatch.setattr(loaded, "run", run)
    with pytest.raises(loaded.ReleaseError, match="Import"):
        with loaded.signing_session(values()):
            pytest.fail("Invalid import must not yield")
    assert not created_paths[0].exists()
    assert any(command[:2] == ["security", "delete-keychain"] for command in commands)
    assert [
        "security",
        "list-keychains",
        "-d",
        "user",
        "-s",
        "/existing/login.keychain-db",
    ] in commands


def test_existing_dmg_is_not_overwritten(tmp_path):
    loaded = module()
    dmg = tmp_path / "candidate.dmg"
    dmg.write_bytes(b"existing")
    with pytest.raises(loaded.ReleaseError, match="overwrite"):
        loaded.create_dmg(tmp_path / "ArchiveLens.app", dmg)
    assert dmg.read_bytes() == b"existing"


def test_dmg_detached_after_invalid_contents(tmp_path, monkeypatch):
    loaded = module()
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[:2] == ["hdiutil", "attach"]:
            mount = Path(command[-1])
            mount.mkdir()
            (mount / "unapproved-extra-file").write_text("fixture")
        return ""

    monkeypatch.setattr(loaded, "run", run)
    with pytest.raises(loaded.ReleaseError, match="Unexpected DMG contents"):
        loaded.verify_dmg(tmp_path / "candidate.dmg", "a" * 40)
    assert commands[-1][:2] == ["hdiutil", "detach"]


def test_unstapled_dmg_never_mounted(tmp_path, monkeypatch):
    loaded = module()
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[:3] == ["xcrun", "stapler", "validate"]:
            raise loaded.ReleaseError("DMG staple validation failed")
        return ""

    monkeypatch.setattr(loaded, "run", run)
    monkeypatch.setattr(loaded, "inspect_signature", lambda *a, **k: None)
    with pytest.raises(loaded.ReleaseError, match="staple"):
        loaded.verify_dmg(tmp_path / "candidate.dmg", "a" * 40, team="ABCDEFGHIJ")
    assert not any(command[:2] == ["hdiutil", "attach"] for command in commands)


def test_unexpected_entitlements_rejected(monkeypatch):
    loaded = module()

    def run(command, **kwargs):
        if "--entitlements" in command:
            return plistlib.dumps({"com.apple.security.get-task-allow": True}).decode()
        if "--display" in command:
            return (
                "Authority=Developer ID Application: Fixture\nTeamIdentifier=ABCDEFGHIJ\n"
                "flags=0x10000(runtime)\nTimestamp=now"
            )
        return ""

    monkeypatch.setattr(loaded, "run", run)
    with pytest.raises(loaded.ReleaseError, match="Unexpected entitlement"):
        loaded.inspect_signature(Path("candidate"), "ABCDEFGHIJ", runtime=True)


def test_signature_without_exceptions_accepted(monkeypatch):
    loaded = module()

    def run(command, **kwargs):
        if "--entitlements" in command:
            return plistlib.dumps({}).decode()
        if "--display" in command:
            return (
                "Authority=Developer ID Application: Fixture\nTeamIdentifier=ABCDEFGHIJ\n"
                "flags=0x10000(runtime)\nTimestamp=now"
            )
        return ""

    monkeypatch.setattr(loaded, "run", run)
    loaded.inspect_signature(Path("candidate"), "ABCDEFGHIJ", runtime=True)


def test_signed_backend_hash_sealed_before_outer_signature(tmp_path, monkeypatch):
    import hashlib

    loaded = module()
    app = tmp_path / "ArchiveLens.app"
    backend = app / "Contents/Frameworks/native/libunrar.dylib"
    backend.parent.mkdir(parents=True)
    backend.write_bytes(b"\xcf\xfa\xed\xfefixture")
    info_path = app / "Contents/Resources/build-info.json"
    info_path.parent.mkdir(parents=True)
    info_path.write_text(json.dumps({"native_backends": {"rar": {"sha256": "input"}}}))
    entitlements = tmp_path / "entitlements.plist"
    entitlements.write_bytes(plistlib.dumps({}))
    outer_signed = []

    def run(command, **kwargs):
        if command[-1] == str(backend):
            backend.write_bytes(backend.read_bytes() + b"signature")
        if command[-1] == str(app):
            sealed = json.loads(info_path.read_text())["native_backends"]["rar"]
            assert sealed["sha256"] == "input"
            assert sealed["signed_sha256"] == hashlib.sha256(backend.read_bytes()).hexdigest()
            outer_signed.append(True)
        return ""

    monkeypatch.setattr(loaded, "run", run)
    loaded.sign_app(app, "identity", Path("keychain"), entitlements)
    assert outer_signed == [True]
    backend.write_bytes(b"tampered")
    with pytest.raises(loaded.ReleaseError, match="Signed backend hash"):
        loaded.verify_signed_app(app, "ABCDEFGHIJ", stapled=True)


def test_workflow_official_is_separated_and_success_only():
    root = Path(__file__).parents[1]
    workflow = (root / ".github/workflows/v13-macos-official.yml").read_text()
    assert "environment: macos-release" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "pull_request:" not in workflow
    assert "if: always()" not in workflow
    assert "contents: read" in workflow
    assert "gh release" not in workflow
    assert plistlib.loads((root / "scripts/macos-entitlements.plist").read_bytes()) == {}
