"""Collect exact-version upstream sources and their license/attribution files."""

import hashlib
import importlib.metadata
import json
import shutil
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

MAX_LICENSE_PATH_LENGTH = 140


def bundled_license_path(relative: PurePosixPath) -> Path:
    """Keep installer paths bounded while preserving the upstream path in an index."""
    if len(relative.as_posix()) <= MAX_LICENSE_PATH_LENGTH:
        return Path(*relative.parts)
    digest = hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
    return Path("_long") / f"{digest}{relative.suffix}"


def fetch_source(source: tuple[str, str], root: Path, version: str) -> dict:
    name, location = source
    if location.startswith("https://"):
        url = location.format(version=version)
        filename = url.rsplit("/", 1)[-1]
        with urllib.request.urlopen(url + ".meta4", timeout=30) as response:
            metalink = ET.fromstring(response.read())
        expected_sha256 = next(
            item.text
            for item in metalink.iter("{urn:ietf:params:xml:ns:metalink}hash")
            if item.attrib.get("type") == "sha-256"
        )
    else:
        url = f"https://codeload.github.com/{location}/tar.gz/refs/tags/v{version}"
        filename = f"{name}-{version}.tar.gz"
        expected_sha256 = None
    archive = root / "build" / "upstream-sources" / filename
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        partial = archive.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(archive)
    destination = root / "build" / "third-party-licenses" / name
    shutil.rmtree(destination, ignore_errors=True)
    count = 0
    relocated = {}
    with tarfile.open(archive, "r:*") as source_tar:
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
            relative = PurePosixPath(*path.parts[1:])
            bundled = bundled_license_path(relative)
            if bundled.as_posix() != relative.as_posix():
                relocated[relative.as_posix()] = bundled.as_posix()
            target = destination / bundled
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source_tar.extractfile(member)
            if content is not None:
                with content, target.open("wb") as output:
                    shutil.copyfileobj(content, output)
                count += 1
    if count == 0:
        raise RuntimeError(f"No upstream licenses found in {archive}")
    if relocated:
        (destination / "PATHS.json").write_text(
            json.dumps(relocated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise RuntimeError(f"Official source checksum mismatch for {archive.name}")
    return {
        "component": name,
        "version": version,
        "source_url": url,
        "source_archive": archive.name,
        "sha256": digest,
        "official_sha256_verified": bool(expected_sha256),
        "license_files": count,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = importlib.metadata.version("PySide6")
    sources = [
        ("qtbase", "qt/qtbase"),
        ("qtimageformats", "qt/qtimageformats"),
        (
            "qtpdf",
            "https://download.qt.io/archive/qt/6.11/{version}/submodules/"
            "qtwebengine-everywhere-src-{version}.tar.xz",
        ),
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
    inno_license = destination / "Inno-Setup-LICENSE.txt"
    if not inno_license.exists():
        with urllib.request.urlopen(
            "https://raw.githubusercontent.com/jrsoftware/issrc/is-6_7_3/license.txt", timeout=30
        ) as response:
            inno_license.write_bytes(response.read())
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
    backend_names = [
        "Pillow",
        "pyzipper",
        "pycryptodomex",
        "py7zr",
        "backports.zstd",
        "brotli",
        "inflate64",
        "multivolumefile",
        "psutil",
        "pybcj",
        "pyppmd",
        "texttable",
    ]
    backend_records = []
    for name in backend_names:
        dependency = importlib.metadata.distribution(name)
        count = 0
        for item in dependency.files or []:
            if any(word in item.name.casefold() for word in ("license", "copying", "copyright")):
                source = dependency.locate_file(item)
                if source.is_file():
                    target = destination / name / item.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    count += 1
        if not count:
            raise RuntimeError(f"Missing installed license for {name}")
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{name}/{dependency.version}/json", timeout=30
        ) as response:
            package = json.load(response)
        source = next(item for item in package["urls"] if item["packagetype"] == "sdist")
        archive = root / "build/upstream-sources" / source["filename"]
        if not archive.exists():
            with (
                urllib.request.urlopen(source["url"], timeout=60) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != source["digests"]["sha256"]:
            raise RuntimeError(f"Source checksum mismatch for {name}")
        records.append(
            {
                "component": name,
                "version": dependency.version,
                "source_url": source["url"],
                "source_archive": archive.name,
                "sha256": digest,
                "license_files": count,
            }
        )
        backend_records.append(
            {"name": name, "version": dependency.version, "license_files": count}
        )
    shutil.copy2(root / "outputs/backends/UNRAR-LICENSE.txt", destination / "UNRAR-LICENSE.txt")
    (destination / "archive-backends.json").write_text(
        json.dumps(backend_records, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "upstream-sources.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(records, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
