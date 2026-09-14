"""Refresh checksums after all release artifacts (including setup) have been built."""

import hashlib
from pathlib import Path


def main():
    output = Path(__file__).resolve().parents[1] / "dist/release"
    records = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            records.append(f"{digest}  {path.name}\n")
    (output / "SHA256SUMS.txt").write_text("".join(records), encoding="utf-8")


if __name__ == "__main__":
    main()
