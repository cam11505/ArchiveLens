import argparse
import sys

from archivelens.archive.catalog import image_entries
from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.errors import ArchiveLensError


def main() -> int:
    parser = argparse.ArgumentParser(description="List archive images in natural order.")
    parser.add_argument("archive")
    args = parser.parse_args()
    try:
        with DEFAULT_REGISTRY.create(args.archive) as provider:
            provider.open(args.archive)
            entries = image_entries(provider)
            for entry in entries:
                print(entry.path)
            if not entries:
                print("此壓縮檔中沒有找到可顯示的圖片。", file=sys.stderr)
    except ArchiveLensError as exc:
        print(type(exc).default_message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
