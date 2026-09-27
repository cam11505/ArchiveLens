"""Issue #48: qualify mounted case-sensitive/insensitive APFS and detach failures."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from archivelens.content.folder_provider import FolderContentProvider
from archivelens.errors import ContentAccessError


def qualify(output: Path) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("APFS qualification requires macOS")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = []
    with TemporaryDirectory(prefix="archivelens-apfs-") as temporary:
        root = Path(temporary)
        for filesystem, sensitive in (("APFS", False), ("Case-sensitive APFS", True)):
            image = root / f"{filesystem}.dmg"
            mount = root / f"mount-{filesystem}"
            subprocess.run(
                [
                    "hdiutil",
                    "create",
                    "-size",
                    "64m",
                    "-fs",
                    filesystem,
                    "-volname",
                    "ArchiveLens48",
                    str(image),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    "-nobrowse",
                    "-mountpoint",
                    str(mount),
                    str(image),
                ],
                check=True,
            )
            try:
                environment = os.environ.copy()
                environment.update(
                    {
                        "QT_QPA_PLATFORM": "offscreen",
                        "ARCHIVELENS_TEST_VOLUME": str(mount),
                        "ARCHIVELENS_CASE_SENSITIVE": "1" if sensitive else "0",
                    }
                )
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "tests/test_v13_retina_paths.py::test_actual_mounted_volume_case_and_identity",
                        f"--junitxml={output / (filesystem + '.xml')}",
                    ],
                    env=environment,
                    check=True,
                )
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True)
            provider = FolderContentProvider()
            try:
                provider.open(mount)
            except ContentAccessError:
                detached_result = "inaccessible"
            else:
                if provider.list_pages():
                    raise RuntimeError("Detached volume exposed stale pages")
                detached_result = "empty mountpoint (reader rejects empty content)"
            finally:
                provider.close()
            report.append(
                {
                    "filesystem": filesystem,
                    "case_sensitive": sensitive,
                    "detached_source_result": detached_result,
                }
            )
    (output / "volumes.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    qualify(parser.parse_args().output)
