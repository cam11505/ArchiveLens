"""Build or fetch the pinned official UnRAR 7.23 in-process backend."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

VERSION = "7.23"
SOURCE_URL = "https://www.rarlab.com/rar/unrarsrc-7.2.3.tar.gz"
SOURCE_SHA256 = "3995af0aa32b1505a566da053725551a1f0698dc42b2fdf7ba7d65db0d004e33"
WINDOWS_SDK_URL = "https://www.rarlab.com/rar/unrardll-723.exe"
WINDOWS_SDK_SHA256 = "68b064b34691988158c4126d3cf422f4e74a7d1d618c26bafc93b4e502b88b55"
WINDOWS_DLL_SHA256 = "894b7d2db8d6363eb12f30c7b89f48eab9e71963b8b438675bdd64c12dd59bcc"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, expected_sha256: str, destination: Path) -> None:
    if not destination.is_file():
        urllib.request.urlretrieve(url, destination)
    if digest(destination) != expected_sha256:
        raise SystemExit(f"Official download checksum mismatch: {destination.name}")


def extract_source(archive: Path, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(destination, filter="data")
    source = destination / "unrar"
    if not (source / "makefile").is_file() or not (source / "license.txt").is_file():
        raise SystemExit("Official UnRAR source layout is invalid")
    return source


def prepare_windows(target: Path) -> tuple[Path, str, str]:
    sdk = target / "unrardll-723.exe"
    download(WINDOWS_SDK_URL, WINDOWS_SDK_SHA256, sdk)
    unpack = target / "sdk723"
    if unpack.exists():
        shutil.rmtree(unpack)
    unpack.mkdir()
    subprocess.run(
        [str(sdk), "-s", f"-d{unpack}"],
        check=True,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    binary = unpack / "x64" / "UnRAR64.dll"
    if digest(binary) != WINDOWS_DLL_SHA256:
        raise SystemExit("UnRAR DLL checksum mismatch")
    staged = target / "UnRAR64.dll"
    shutil.copy2(binary, staged)
    shutil.copy2(unpack / "license.txt", target / "UNRAR-LICENSE.txt")
    return staged, WINDOWS_SDK_URL, WINDOWS_SDK_SHA256


def prepare_unix(target: Path) -> tuple[Path, str, str]:
    archive = target / "unrarsrc-7.2.3.tar.gz"
    download(SOURCE_URL, SOURCE_SHA256, archive)
    source = extract_source(archive, target / "unrar-7.2.3")
    if sys.platform == "darwin":
        makefile = source / "makefile"
        content = makefile.read_text(encoding="utf-8")
        original = "$(LINK) -shared -o libunrar.so"
        replacement = (
            "$(LINK) -dynamiclib -Wl,-install_name,@rpath/libunrar.dylib -o libunrar.dylib"
        )
        if original not in content:
            raise SystemExit("UnRAR makefile shared-library rule changed")
        makefile.write_text(content.replace(original, replacement), encoding="utf-8")
        filename = "libunrar.dylib"
    elif sys.platform.startswith("linux"):
        filename = "libunrar.so"
    else:
        raise SystemExit(f"Unsupported UnRAR backend platform: {sys.platform}")
    subprocess.run(["make", "-f", "makefile", "lib"], cwd=source, check=True, timeout=300)
    binary = source / filename
    if not binary.is_file():
        raise SystemExit(f"UnRAR build did not produce {filename}")
    staged = target / filename
    shutil.copy2(binary, staged)
    shutil.copy2(source / "license.txt", target / "UNRAR-LICENSE.txt")
    return staged, SOURCE_URL, SOURCE_SHA256


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "outputs" / "backends"
    target.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        binary, source_url, source_sha256 = prepare_windows(target)
    else:
        binary, source_url, source_sha256 = prepare_unix(target)
    metadata = {
        "architecture": platform.machine(),
        "binary": binary.name,
        "binary_sha256": digest(binary),
        "license": "UnRAR freeware license (non-FOSS)",
        "platform": sys.platform,
        "source_sha256": source_sha256,
        "source_url": source_url,
        "version": VERSION,
    }
    (target / "UNRAR-BACKEND.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Verified UnRAR {VERSION} {platform.machine()} backend ready: {binary.name}")


if __name__ == "__main__":
    main()
