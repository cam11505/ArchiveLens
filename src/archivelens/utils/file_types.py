from pathlib import PurePosixPath

IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".avif",
        ".jp2",
        ".j2k",
        ".j2c",
    }
)
ARCHIVE_EXTENSIONS = frozenset({".zip", ".cbz"})


def is_image(path: str) -> bool:
    return PurePosixPath(path).suffix.casefold() in IMAGE_EXTENSIONS
