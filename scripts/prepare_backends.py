"""Fetch the pinned official Windows UnRAR SDK and stage the redistributable DLL."""

import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SDK_URL = "https://www.rarlab.com/rar/unrardll-721.exe"
SDK_SHA256 = "e1dd2126d13dc75aa7c0c1a3964176fb3c8f728bbccfb0ce129f3a6c02542c1d"
DLL_SHA256 = "4b4a5cf24a5d60102f31b9d0c591064085ea9ac2336dd31c4bee483091dcbc9f"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.platform != "win32":
        raise SystemExit("UnRAR DLL packaging targets Windows x64")
    root = Path(__file__).resolve().parents[1]
    target = root / "outputs" / "backends"
    target.mkdir(parents=True, exist_ok=True)
    sdk = target / "unrardll-721.exe"
    if not sdk.is_file():
        urllib.request.urlretrieve(SDK_URL, sdk)
    if digest(sdk) != SDK_SHA256:
        raise SystemExit("Official SDK checksum mismatch")
    unpack = target / "sdk721"
    subprocess.run(
        [str(sdk), "-s", f"-d{unpack}"],
        check=True,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    binary = unpack / "x64" / "UnRAR64.dll"
    if digest(binary) != DLL_SHA256:
        raise SystemExit("UnRAR DLL checksum mismatch")
    shutil.copy2(binary, target / "UnRAR64.dll")
    shutil.copy2(unpack / "license.txt", target / "UNRAR-LICENSE.txt")
    print("Verified UnRAR 7.21 x64 backend ready")


if __name__ == "__main__":
    main()
