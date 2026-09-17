"""Build the Windows portable directory; no network requests are made by this script."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if sys.platform != "win32":
        raise SystemExit("The v1.0 portable build targets Windows x64.")
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(root / "build" / "pyinstaller-cache")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(root / "dist"),
            "--workpath",
            str(root / "build" / "pyinstaller"),
            str(root / "scripts" / "ArchiveLens.spec"),
        ],
        cwd=root,
        env=env,
        check=True,
    )
    target = root / "dist" / "ArchiveLens"
    for name in ("README.md", "README.zh-TW.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / name, target / name)
    shutil.copy2(root / "docs" / "LICENSING.md", target / "LICENSING.md")
    licenses = root / "build" / "third-party-licenses"
    if not licenses.is_dir():
        raise SystemExit("Run scripts/prepare_licenses.py before packaging a distribution.")
    shutil.copytree(licenses, target / "licenses", dirs_exist_ok=True)
    shutil.copy2(root / "license-policy.json", target / "licenses" / "license-policy.json")
    source_paths = sorted((root / "src").rglob("*.py")) + [root / "scripts" / "ArchiveLens.spec"]
    fingerprints = {}
    for path in source_paths:
        with path.open("rb") as stream:
            fingerprints[path.relative_to(root).as_posix()] = hashlib.file_digest(
                stream, "sha256"
            ).hexdigest()
    (target / "compiled-source.json").write_text(
        json.dumps(fingerprints, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Portable application: {target / 'ArchiveLens.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
