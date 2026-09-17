"""Install/self-test/uninstall an RC in an isolated directory; preserve user defaults."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    import winreg

    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    parser.add_argument("--expected-commit")
    args = parser.parse_args()

    def registry_value(key, name=""):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                return winreg.QueryValueEx(handle, name)[0]
        except FileNotFoundError:
            return None

    app_key = r"Software\Classes\Applications\ArchiveLens.exe"
    if registry_value(app_key, "FriendlyAppName") is not None:
        raise SystemExit(
            "An existing ArchiveLens installation must not be overwritten by this test"
        )
    original_defaults = {
        ext: registry_value("Software\\Classes\\" + ext)
        for ext in (".zip", ".rar", ".7z", ".cbz", ".cbr", ".pdf")
    }
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs" / "installer-verification"
    output.mkdir(parents=True, exist_ok=True)
    # QtPdf's complete license tree can exceed Windows path limits when nested
    # below a long checkout. Keep the real install target intentionally shallow.
    target = Path(tempfile.gettempdir()) / ("ArchiveLens-install-" + uuid.uuid4().hex[:8])
    target.mkdir()
    sentinel = target / "user-owned-archive.cbz"
    sentinel.write_bytes(b"user-owned fixture; installer must preserve")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "QT_", "QML", "VIRTUAL_ENV"))
    }
    system = Path(os.environ["SystemRoot"])
    env["PATH"] = str(system / "System32") + os.pathsep + str(system)
    report = output / "installed-self-test.json"
    uninstall = target / "unins000.exe"
    installed = False
    try:
        subprocess.run(
            [
                str(args.installer.resolve()),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/NOICONS",
                f"/DIR={target}",
                f"/LOG={output / 'install.log'}",
            ],
            check=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        installed = True
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        for name, record in manifest.items():
            path = target / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise RuntimeError("Installed manifest mismatch")
        info = json.loads((target / "build-info.json").read_text(encoding="utf-8"))
        if args.expected_commit and info["source_commit"] != args.expected_commit:
            raise RuntimeError("Installer source commit mismatch")
        command = registry_value(app_key + r"\shell\open\command")
        if command != f'"{target}\\ArchiveLens.exe" "%1"':
            raise RuntimeError("Open With command mismatch")
        pdf_command = registry_value(r"Software\Classes\ArchiveLens.Pdf\shell\open\command")
        if pdf_command != f'"{target}\\ArchiveLens.exe" "%1"':
            raise RuntimeError("PDF Open With command mismatch")
        if registry_value(r"Software\Classes\.pdf\OpenWithProgids", "ArchiveLens.Pdf") is None:
            raise RuntimeError("PDF Open With ProgID is missing")
        subprocess.run(
            [str(target / "ArchiveLens.exe"), "--self-test-report", str(report)],
            cwd=target,
            env=env,
            check=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        results = json.loads(report.read_text(encoding="utf-8"))
        if not results["success"] or len(results["checks"]) < 23:
            raise RuntimeError("Installed self-test failed")
    finally:
        if installed and uninstall.is_file():
            subprocess.run(
                [
                    str(uninstall),
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    f"/LOG={output / 'uninstall.log'}",
                ],
                check=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    if (target / "ArchiveLens.exe").exists() or registry_value(app_key, "FriendlyAppName"):
        raise RuntimeError("Uninstall left application files or Open With registration")
    if sentinel.read_bytes() != b"user-owned fixture; installer must preserve":
        raise RuntimeError("Uninstaller touched a user-owned file")
    if original_defaults != {
        ext: registry_value("Software\\Classes\\" + ext) for ext in original_defaults
    }:
        raise RuntimeError("Installer changed default archive associations")
    result = {
        "success": True,
        "version": info["version"],
        "source_commit": info["source_commit"],
        "checks": [
            "installed_manifest",
            "open_with_registration",
            "pdf_open_with_registration",
            "installed_self_test",
            "uninstall_cleanup",
            "user_file_preserved",
            "default_associations_unchanged",
        ],
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
