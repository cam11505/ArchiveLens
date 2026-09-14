"""Collect exact-version upstream sources and their license/attribution files."""

import hashlib
import importlib.metadata
import json
import shutil
import sys
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath


def fetch_source(source: tuple[str, str], root: Path, version: str) -> dict:
    name, repository = source
    archive = root / "build" / "upstream-sources" / f"{name}-{version}.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/{repository}/tar.gz/refs/tags/v{version}"
    if not archive.exists():
        partial = archive.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(archive)
    destination = root / "build" / "third-party-licenses" / name
    count = 0
    with tarfile.open(archive, "r:gz") as source_tar:
        for member in source_tar:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                continue
            filename = path.name.casefold()
            if not (
                filename.startswith(("license", "copying", "copyright", "notice"))
                or filename == "qt_attribution.json"
                or "LICENSES" in path.parts
            ):
                continue
            if member.size > 4 * 1024 * 1024:
                continue
            relative = Path(*path.parts[1:])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source_tar.extractfile(member)
            if content is not None:
                with content, target.open("wb") as output:
                    shutil.copyfileobj(content, output)
                count += 1
    if count == 0:
        raise RuntimeError(f"No upstream licenses found in {archive}")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "component": name,
        "version": version,
        "source_url": url,
        "source_archive": archive.name,
        "sha256": digest,
        "license_files": count,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = importlib.metadata.version("PySide6")
    sources = [
        ("qtbase", "qt/qtbase"),
        ("qtimageformats", "qt/qtimageformats"),
        ("pyside-setup", "pyside/pyside-setup"),
    ]
    with ThreadPoolExecutor(max_workers=3) as executor:
        records = list(executor.map(lambda source: fetch_source(source, root, version), sources))
    destination = root / "build" / "third-party-licenses"
    openssl_license = destination / "OpenSSL-LICENSE.txt"
    if not openssl_license.exists():
        url = "https://raw.githubusercontent.com/openssl/openssl/openssl-3.6.4/LICENSE.txt"
        with urllib.request.urlopen(url, timeout=60) as response:
            openssl_license.write_bytes(response.read())
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python's bundled LICENSE.txt is missing")
    shutil.copy2(python_license, destination / "Python-LICENSE.txt")
    dist = importlib.metadata.distribution("pyinstaller")
    for item in dist.files or []:
        if "license" in str(item).casefold() or item.name in {"COPYING.txt"}:
            path = dist.locate_file(item)
            if path.is_file():
                target = destination / "PyInstaller" / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    (destination / "upstream-sources.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(records, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
