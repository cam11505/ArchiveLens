"""Install the pinned Inno compiler under outputs, used only for building installers."""

import hashlib
import subprocess
import sys
import urllib.request
from pathlib import Path

URL = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
SHA256 = "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732"


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs"
    output.mkdir(exist_ok=True)
    download = output / "innosetup-6.7.3.exe"
    if not download.is_file():
        urllib.request.urlretrieve(URL, download)
    if hashlib.sha256(download.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Inno Setup checksum mismatch")
    subprocess.run(
        [
            str(download),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CURRENTUSER",
            "/NOICONS",
            f"/DIR={output / 'inno'}",
        ],
        check=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


if __name__ == "__main__":
    main()
