"""Fail-closed macOS signing/notarization and a separate development DMG probe.

No publication happens here. Credential-bearing command output is never printed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import plistlib
import re
import secrets
import shlex
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from archivelens import __version__

try:
    from scripts.artifact_contract import verify_checksums
except ModuleNotFoundError:
    from artifact_contract import verify_checksums

SECRET_NAMES = (
    "MACOS_CERTIFICATE_P12_BASE64",
    "MACOS_CERTIFICATE_PASSWORD",
    "MACOS_SIGNING_IDENTITY",
    "APPLE_TEAM_ID",
    "APPLE_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
)
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


class ReleaseError(RuntimeError):
    """Safe, deliberately non-sensitive diagnostic."""


def run(command: list[str], *, stage: str, timeout: int = 600, env=None, cwd=None) -> str:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseError(f"{stage} could not complete; no official artifact approved") from None
    if result.returncode:
        # CalledProcessError / raw stdout/stderr can include passwords or identities.
        raise ReleaseError(f"{stage} failed; no official artifact approved")
    return result.stdout + result.stderr


def credentials(env) -> dict[str, str]:
    missing = [name for name in SECRET_NAMES if not env.get(name)]
    if missing:
        raise ReleaseError("Missing official credentials: " + ", ".join(missing))
    values = {name: env[name] for name in SECRET_NAMES}
    if not re.fullmatch(r"[A-Z0-9]{10}", values["APPLE_TEAM_ID"]):
        raise ReleaseError("Invalid Apple Team ID format")
    identity = values["MACOS_SIGNING_IDENTITY"]
    if not identity.startswith("Developer ID Application: ") or not identity.endswith(
        f"({values['APPLE_TEAM_ID']})"
    ):
        raise ReleaseError("A matching Developer ID Application identity is required")
    try:
        if not base64.b64decode(values["MACOS_CERTIFICATE_P12_BASE64"], validate=True):
            raise ValueError
    except ValueError:
        raise ReleaseError("Invalid certificate encoding") from None
    return values


@contextmanager
def signing_session(values):
    """Isolated ephemeral keychain; restore search list and remove private material."""
    original = shlex.split(run(["security", "list-keychains", "-d", "user"], stage="Keychain list"))
    with TemporaryDirectory(prefix="ArchiveLens-signing-") as temporary:
        directory = Path(temporary)
        keychain = directory / "signing.keychain-db"
        certificate = directory / "certificate.p12"
        certificate.write_bytes(base64.b64decode(values["MACOS_CERTIFICATE_P12_BASE64"]))
        certificate.chmod(0o600)
        password = secrets.token_urlsafe(32)
        profile = "ArchiveLens-notary"
        created = False
        try:
            run(
                ["security", "create-keychain", "-p", password, str(keychain)],
                stage="Create keychain",
            )
            created = True
            run(
                ["security", "set-keychain-settings", "-lut", "21600", str(keychain)],
                stage="Keychain settings",
            )
            run(
                ["security", "unlock-keychain", "-p", password, str(keychain)],
                stage="Unlock keychain",
            )
            run(
                ["security", "list-keychains", "-d", "user", "-s", str(keychain), *original],
                stage="Keychain search list",
            )
            run(
                [
                    "security",
                    "import",
                    str(certificate),
                    "-k",
                    str(keychain),
                    "-P",
                    values["MACOS_CERTIFICATE_PASSWORD"],
                    "-T",
                    "/usr/bin/codesign",
                ],
                stage="Import certificate",
            )
            run(
                [
                    "security",
                    "set-key-partition-list",
                    "-S",
                    "apple-tool:,apple:,codesign:",
                    "-s",
                    "-k",
                    password,
                    str(keychain),
                ],
                stage="Keychain partition access",
            )
            available = run(
                ["security", "find-identity", "-v", "-p", "codesigning", str(keychain)],
                stage="Signing identity",
            )
            if f'"{values["MACOS_SIGNING_IDENTITY"]}"' not in available:
                raise ReleaseError("Requested valid signing identity is not available")
            run(
                [
                    "xcrun",
                    "notarytool",
                    "store-credentials",
                    profile,
                    "--keychain",
                    str(keychain),
                    "--apple-id",
                    values["APPLE_ID"],
                    "--team-id",
                    values["APPLE_TEAM_ID"],
                    "--password",
                    values["APPLE_APP_SPECIFIC_PASSWORD"],
                ],
                stage="Validate notary credentials",
            )
            yield keychain, profile
        finally:
            try:
                run(
                    ["security", "list-keychains", "-d", "user", "-s", *original],
                    stage="Restore keychains",
                )
            finally:
                if created:
                    run(
                        ["security", "delete-keychain", str(keychain)],
                        stage="Delete signing keychain",
                    )


def macho_files(app: Path) -> list[Path]:
    files = []
    for path in app.rglob("*"):
        if path.is_symlink():
            if not path.resolve().is_relative_to(app.resolve()):
                raise ReleaseError("Bundle symlink escapes app")
            continue
        if path.is_file():
            with path.open("rb") as stream:
                if stream.read(4) in MACHO_MAGIC:
                    files.append(path)
    if not files:
        raise ReleaseError("Bundle has no native code")
    return sorted(files, key=lambda path: (-len(path.parts), str(path)))


def sign_app(app: Path, identity: str, keychain: Path, entitlements: Path) -> None:
    if plistlib.loads(entitlements.read_bytes()) != {}:
        raise ReleaseError("Unreviewed hardened-runtime entitlement exception")
    bundles = [
        path
        for path in app.rglob("*")
        if not path.is_symlink() and path.is_dir() and path.suffix in {".framework", ".app", ".xpc"}
    ]
    # Sign innermost code first. --deep is only a verification option, never a signing shortcut.
    targets = sorted(macho_files(app) + bundles, key=lambda path: (-len(path.parts), str(path)))
    for target in [*targets, app]:
        if target == app:
            # Signing changes native bytes. Preserve provenance hash and record the actual
            # signed backend hash before sealing the outer app's resource envelope.
            info_path = app / "Contents/Resources/build-info.json"
            if info_path.is_file():
                info = json.loads(info_path.read_text(encoding="utf-8"))
                backend = app / "Contents/Frameworks/native/libunrar.dylib"
                with backend.open("rb") as stream:
                    info["native_backends"]["rar"]["signed_sha256"] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
                info_path.write_text(
                    json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
        run(
            [
                "codesign",
                "--force",
                "--sign",
                identity,
                "--keychain",
                str(keychain),
                "--options",
                "runtime",
                "--timestamp",
                "--entitlements",
                str(entitlements),
                str(target),
            ],
            stage="Nested code signing",
        )


def inspect_signature(target: Path, team: str, *, runtime: bool) -> None:
    run(
        ["codesign", "--verify", "--strict", "--verbose=2", str(target)],
        stage="Code signature verification",
    )
    details = run(
        ["codesign", "--display", "--verbose=4", str(target)], stage="Signature inspection"
    )
    lines = details.splitlines()
    if (
        f"TeamIdentifier={team}" not in lines
        or not any(line.startswith("Authority=Developer ID Application:") for line in lines)
        or not any(line.startswith("Timestamp=") for line in lines)
    ):
        raise ReleaseError("Developer ID/team/timestamp verification failed")
    if runtime:
        if not re.search(r"flags=.*\bruntime\b", details):
            raise ReleaseError("Hardened runtime verification failed")
        raw = run(
            ["codesign", "--display", "--entitlements", ":-", str(target)],
            stage="Entitlements inspection",
        )
        start = raw.find("<?xml")
        end = raw.find("</plist>")
        if start >= 0:
            try:
                entitlements = plistlib.loads(raw[start : end + len("</plist>")].encode())
            except Exception:
                raise ReleaseError("Entitlements could not be inspected") from None
            if entitlements:
                raise ReleaseError("Unexpected entitlement exception")
        elif raw.strip():
            # No plist is valid only for absent entitlements, not arbitrary tool output.
            if any(not line.startswith("Executable=") for line in raw.splitlines() if line):
                raise ReleaseError("Entitlements could not be inspected")


def verify_signed_app(app: Path, team: str, *, stapled: bool) -> None:
    info = json.loads((app / "Contents/Resources/build-info.json").read_text(encoding="utf-8"))
    with (app / "Contents/Frameworks/native/libunrar.dylib").open("rb") as stream:
        backend_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if info["native_backends"]["rar"].get("signed_sha256") != backend_hash:
        raise ReleaseError("Signed backend hash does not match sealed metadata")
    for target in [*macho_files(app), app]:
        inspect_signature(target, team, runtime=True)
    run(
        ["codesign", "--verify", "--deep", "--strict", str(app)],
        stage="Complete bundle verification",
    )
    if stapled:
        run(["xcrun", "stapler", "validate", str(app)], stage="App staple validation")
        run(
            ["spctl", "--assess", "--type", "execute", "--verbose=4", str(app)],
            stage="App Gatekeeper assessment",
        )


def notarize(target: Path, keychain: Path, profile: str) -> str:
    output = run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(target),
            "--keychain-profile",
            profile,
            "--keychain",
            str(keychain),
            "--wait",
            "--timeout",
            "30m",
            "--output-format",
            "json",
        ],
        stage="Notarization",
        timeout=1900,
    )
    try:
        result = json.loads(output)
    except ValueError:
        raise ReleaseError("Notarization returned invalid JSON") from None
    if result.get("status") != "Accepted" or not re.fullmatch(
        r"[0-9a-fA-F-]{36}", str(result.get("id", ""))
    ):
        raise ReleaseError("Notarization was not Accepted")
    return result["id"]


def staple(target: Path) -> None:
    run(["xcrun", "stapler", "staple", str(target)], stage="Staple")
    run(["xcrun", "stapler", "validate", str(target)], stage="Staple validation")


def create_dmg(app: Path, destination: Path) -> None:
    if destination.exists():
        raise ReleaseError("Refusing to overwrite an existing DMG")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ArchiveLens-dmg-stage-") as temporary:
        stage = Path(temporary)
        run(["ditto", str(app), str(stage / "ArchiveLens.app")], stage="DMG app staging")
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        run(
            [
                "hdiutil",
                "create",
                "-volname",
                "ArchiveLens",
                "-fs",
                "HFS+",
                "-format",
                "UDZO",
                "-srcfolder",
                str(stage),
                str(destination),
            ],
            stage="DMG creation",
        )


def verify_dmg(dmg: Path, commit: str, *, team: str | None = None) -> dict:
    # No trust in a sidecar success flag: mount and verify the actual distributed app.
    from verify_macos_app import inspect_structure, run_self_test, verify_native_architecture

    run(["hdiutil", "verify", str(dmg)], stage="DMG integrity")
    if team:
        inspect_signature(dmg, team, runtime=False)
        run(["xcrun", "stapler", "validate", str(dmg)], stage="DMG staple validation")
        run(
            [
                "spctl",
                "--assess",
                "--type",
                "open",
                "--context",
                "context:primary-signature",
                str(dmg),
            ],
            stage="DMG Gatekeeper assessment",
        )
    with TemporaryDirectory(prefix="ArchiveLens-dmg-mount-") as temporary:
        mount = Path(temporary) / "volume"
        attached = False
        try:
            run(
                [
                    "hdiutil",
                    "attach",
                    str(dmg),
                    "-readonly",
                    "-nobrowse",
                    "-mountpoint",
                    str(mount),
                ],
                stage="DMG mount",
            )
            attached = True
            names = {path.name for path in mount.iterdir()} - {
                ".DS_Store",
                ".Trashes",
                ".fseventsd",
            }
            if names != {"ArchiveLens.app", "Applications"}:
                raise ReleaseError("Unexpected DMG contents")
            if (
                not (mount / "Applications").is_symlink()
                or os.readlink(mount / "Applications") != "/Applications"
            ):
                raise ReleaseError("Invalid Applications install link")
            app = mount / "ArchiveLens.app"
            result = inspect_structure(app, commit, allow_development=team is None)
            result["native_count"] = len(verify_native_architecture(app))
            if team:
                verify_signed_app(app, team, stapled=True)
            # ditto + LaunchServices from an isolated writable directory, not the mounted image.
            result["self_test"] = run_self_test(app, Path(temporary) / "self-test.json")
            return {
                "success": True,
                "development": team is None,
                "channel": "development" if team is None else "release",
                "version": result["build_info"]["version"],
                "source_commit": result["build_info"]["source_commit"],
                "os": "macos",
                "architecture": "arm64",
                "artifact_kind": "dmg",
                "parity_baseline": result["build_info"]["parity_baseline"],
                "native_count": result["native_count"],
            }
        finally:
            if attached:
                run(["hdiutil", "detach", str(mount)], stage="DMG detach")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def development_inventory(dmg: Path, commit: str, result: dict) -> dict:
    """Record download integrity, not signing/notarization approval."""
    if result.get("development") is not True or result.get("source_commit") != commit:
        raise ReleaseError("Development inventory must match the verified development app")
    inventory = {
        **result,
        "schema_version": 1,
        "release_eligible": False,
        "artifact": dmg.name,
        "sha256": file_sha256(dmg),
        "signing": "unsigned-or-ad-hoc",
        "notarization": "not-performed",
    }
    (dmg.parent / "development-manifest.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    (dmg.parent / "SHA256SUMS.txt").write_text(
        f"{inventory['sha256']}  {dmg.name}\n", encoding="utf-8"
    )
    return inventory


def verify_development_inventory(dmg: Path, commit: str) -> dict:
    expected_name = f"ArchiveLens-{__version__}-macos-arm64-development.dmg"
    if dmg.name != expected_name or dmg.is_symlink() or not dmg.is_file():
        raise ReleaseError("Expected a clearly named development DMG file")
    try:
        inventory = json.loads(
            (dmg.parent / "development-manifest.json").read_text(encoding="utf-8")
        )
        checksums = (dmg.parent / "SHA256SUMS.txt").read_text(encoding="utf-8")
    except (OSError, ValueError):
        raise ReleaseError("Missing or invalid development download inventory") from None
    try:
        verify_checksums(dmg.parent, expected_files={dmg.name})
    except (OSError, ValueError):
        raise ReleaseError("Development SHA-256/commit/channel inventory mismatch") from None
    expected = {
        "schema_version": 1,
        "channel": "development",
        "version": __version__,
        "source_commit": commit,
        "os": "macos",
        "architecture": "arm64",
        "artifact_kind": "dmg",
        "artifact": expected_name,
        "signing": "unsigned-or-ad-hoc",
        "notarization": "not-performed",
        "sha256": file_sha256(dmg),
    }
    if (
        any(inventory.get(key) != value for key, value in expected.items())
        or inventory.get("development") is not True
        or inventory.get("release_eligible") is not False
        or checksums != f"{expected['sha256']}  {expected_name}\n"
    ):
        raise ReleaseError("Development SHA-256/commit/channel inventory mismatch")
    return inventory


def official(root: Path, commit: str, values: dict) -> dict:
    from verify_macos_app import inspect_structure, run_self_test, verify_native_architecture

    actual = run(["git", "rev-parse", "HEAD"], stage="Source commit", cwd=root).strip()
    if (
        actual != commit
        or run(["git", "status", "--porcelain"], stage="Clean source", cwd=root).strip()
    ):
        raise ReleaseError("Official build requires the exact clean source commit")
    destination = (
        root / "dist" / "macos-official-candidate" / f"ArchiveLens-{__version__}-macos-arm64.dmg"
    )
    if destination.exists():
        raise ReleaseError("Existing candidate must not be reused")
    with signing_session(values) as (keychain, profile):
        env = {key: value for key, value in os.environ.items() if key not in SECRET_NAMES}
        env["ARCHIVELENS_OFFICIAL_BUILD"] = "1"
        run(
            [sys.executable, str(root / "scripts/build_macos_app.py"), "--official"],
            stage="Official app build",
            env=env,
        )
        app = root / "dist/ArchiveLens.app"
        inspect_structure(app, commit, allow_development=False)
        verify_native_architecture(app)
        sign_app(
            app,
            values["MACOS_SIGNING_IDENTITY"],
            keychain,
            root / "scripts/macos-entitlements.plist",
        )
        team = values["APPLE_TEAM_ID"]
        verify_signed_app(app, team, stapled=False)
        # Credential-free execution environment for packaged runtime loadability.
        for name in SECRET_NAMES:
            os.environ.pop(name, None)
        run_self_test(app, root / "outputs/macos-official/packaged-self-test.json")
        with TemporaryDirectory(prefix="ArchiveLens-notary-") as temporary:
            archive = Path(temporary) / "ArchiveLens.zip"
            run(
                ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)],
                stage="Notary archive",
            )
            app_request = notarize(archive, keychain, profile)
        staple(app)
        verify_signed_app(app, team, stapled=True)
        create_dmg(app, destination)
        run(
            [
                "codesign",
                "--force",
                "--sign",
                values["MACOS_SIGNING_IDENTITY"],
                "--keychain",
                str(keychain),
                "--timestamp",
                str(destination),
            ],
            stage="DMG signing",
        )
        dmg_request = notarize(destination, keychain, profile)
        staple(destination)
        result = verify_dmg(destination, commit, team=team)
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        **result,
        "source_commit": commit,
        "artifact": destination.name,
        "sha256": digest,
        "app_notarization_id": app_request,
        "dmg_notarization_id": dmg_request,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("official", "development-dmg", "verify-development", "verify")
    )
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--dmg", type=Path)
    parser.add_argument("--team-id")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.report.exists():
            raise ReleaseError("Refusing to reuse a previous verification report")
        if not re.fullmatch(r"[a-f0-9]{40}", args.expected_commit):
            raise ReleaseError("Expected a full source commit")
        values = credentials(os.environ) if args.mode == "official" else None
        if sys.platform != "darwin" or platform.machine() != "arm64":
            raise ReleaseError("This workflow requires native macOS arm64")
        root = Path(__file__).resolve().parents[1]
        if args.mode == "official":
            result = official(root, args.expected_commit, values)
        elif args.mode == "development-dmg":
            from verify_macos_app import inspect_structure

            app = root / "dist/ArchiveLens.app"
            inspect_structure(app, args.expected_commit, allow_development=True)
            dmg = (
                root
                / "outputs/macos-dmg-development"
                / f"ArchiveLens-{__version__}-macos-arm64-development.dmg"
            )
            create_dmg(app, dmg)
            result = verify_dmg(dmg, args.expected_commit)
            result = development_inventory(dmg, args.expected_commit, result)
        elif args.mode == "verify-development":
            if not args.dmg or args.team_id:
                raise ReleaseError(
                    "Development verify requires --dmg and no official team identity"
                )
            dmg = args.dmg.absolute()
            inventory = verify_development_inventory(dmg, args.expected_commit)
            result = {
                **inventory,
                **verify_dmg(dmg, args.expected_commit),
                "release_eligible": False,
            }
        else:
            if not args.dmg or not args.team_id or not re.fullmatch(r"[A-Z0-9]{10}", args.team_id):
                raise ReleaseError("Official verify requires --dmg and --team-id")
            result = verify_dmg(args.dmg.resolve(), args.expected_commit, team=args.team_id)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("macOS candidate verification succeeded; no release was published")
        return 0
    except ReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print(
            "macOS release gate failed; raw diagnostics suppressed for credential safety",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
