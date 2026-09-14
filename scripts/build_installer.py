"""Compile the per-user Windows installer from the verified portable directory."""

import argparse
import shutil
import subprocess
from pathlib import Path

from archivelens import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    compiler = args.iscc or shutil.which("ISCC") or root / "outputs/inno/ISCC.exe"
    subprocess.run(
        [str(compiler), "/Q", f"/DAppVersion={__version__}", str(root / "scripts/ArchiveLens.iss")],
        check=True,
    )


if __name__ == "__main__":
    main()
