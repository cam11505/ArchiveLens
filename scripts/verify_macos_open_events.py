"""Exercise real cold/warm LaunchServices file opens against a packaged app."""

import argparse
import json
import subprocess
import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image


def wait_report(report: Path, count: int) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            if len(data["events"]) == count and all(e["loaded"] for e in data["events"]):
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Finder open did not load {count} expected sources")


def verify(app: Path, output: Path) -> None:
    with TemporaryDirectory(prefix="archivelens-finder-") as temporary:
        root = Path(temporary)
        copied = root / "ArchiveLens.app"
        subprocess.run(["/usr/bin/ditto", str(app.resolve()), str(copied)], check=True)
        image = root / "page.png"
        Image.new("RGB", (32, 24), "white").save(image)
        cold = root / "冷啟動.cbz"
        warm = root / "已開啟.pdf"
        with zipfile.ZipFile(cold, "w") as archive:
            archive.write(image, "page.png")
        Image.new("RGB", (32, 24), "white").save(warm, "PDF")
        report = root / "events.json"
        try:
            subprocess.run(
                [
                    "/usr/bin/open",
                    "-a",
                    str(copied),
                    str(cold),
                    "--args",
                    "--open-event-report",
                    str(report),
                ],
                check=True,
            )
            wait_report(report, 1)
            subprocess.run(["/usr/bin/open", "-a", str(copied), str(warm)], check=True)
            data = wait_report(report, 2)
            assert [e["path"] for e in data["events"]] == [str(cold), str(warm)]
            assert all(e["pages"] == 1 for e in data["events"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            report.with_suffix(".stop").touch()
            time.sleep(0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    verify(args.app, args.report)
