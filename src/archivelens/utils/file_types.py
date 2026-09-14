from pathlib import PurePosixPath

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"})
ARCHIVE_EXTENSIONS = frozenset({".zip", ".cbz"})


def is_image(path: str) -> bool:
    return PurePosixPath(path).suffix.casefold() in IMAGE_EXTENSIONS
