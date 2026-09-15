"""Verify the isolated #27 Inno installer without touching an existing ArchiveLens."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/qtpdf-installer-spike"
    output.mkdir(parents=True, exist_ok=True)
    target = output / ("install-" + uuid.uuid4().hex)
    target.mkdir()
    sentinel = target / "user-owned.pdf"
    sentinel.write_bytes(b"must survive test uninstall")
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
                f"/DIR={target}",
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
                raise RuntimeError(f"Installed manifest mismatch: {name}")
        for required in (
            "_internal/PySide6/QtPdf.pyd",
            "_internal/PySide6/Qt6Pdf.dll",
        ):
            if required not in manifest:
                raise RuntimeError(f"QtPdf runtime missing: {required}")
        subprocess.run(
            [str(target / "ArchiveLens.exe"), "--self-test-report", str(report)],
            cwd=target,
            env=env,
            check=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        result = json.loads(report.read_text(encoding="utf-8"))
        required_checks = {
            "folder_flat_recursive_read_only",
            "pdf_provider_normal_many_large_bounded_render",
            "pdf_password_session_and_render_guards",
            "bounded_auto_manual_trim",
            "reading_state_v2_no_credentials",
        }
        if (
            not result["success"]
            or len(result["checks"]) < 23
            or not required_checks <= set(result["checks"])
        ):
            raise RuntimeError("Installed v1.2 self-test failed")
    finally:
        if installed and uninstall.is_file():
            subprocess.run(
                [str(uninstall), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                check=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    if (target / "ArchiveLens.exe").exists():
        raise RuntimeError("Spike uninstaller left application files")
    if sentinel.read_bytes() != b"must survive test uninstall":
        raise RuntimeError("Spike uninstaller touched the user-owned fixture")
    result = {
        "success": True,
        "checks": [
            "installed_manifest",
            "qtpdf_runtime_inventory",
            "installed_normal_password_large_pdf_self_test",
            "uninstall_cleanup",
            "user_pdf_preserved",
        ],
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
