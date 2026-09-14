import base64
import struct

import pytest

from archivelens import config
from archivelens.errors import ArchiveLensError
from archivelens.image.loader import decode_image


@pytest.mark.parametrize("fmt", ["JPG", "JPEG", "PNG", "WEBP", "BMP"])
def test_in_memory_formats(image_bytes, fmt):
    image = decode_image(image_bytes(fmt=fmt))
    assert (image.width(), image.height()) == (32, 24)


def test_gif_first_frame(qapp):
    image = decode_image(
        base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    )
    assert (image.width(), image.height()) == (1, 1)


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n"])
def test_corrupt_image_is_recoverable(qapp, data):
    with pytest.raises(ArchiveLensError):
        decode_image(data)


def test_large_image_guard(image_bytes, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ArchiveLensError, match="尺寸過大"):
        decode_image(image_bytes())


def test_exif_orientation(image_bytes):
    jpeg = image_bytes(fmt="JPEG", width=40, height=20)
    # Minimal little-endian TIFF IFD containing Orientation=6 (90 degrees clockwise).
    tiff = b"II" + struct.pack("<HIH", 42, 8, 1)
    tiff += struct.pack("<HHI", 0x112, 3, 1) + struct.pack("<H", 6) + b"\0\0"
    tiff += struct.pack("<I", 0)
    exif = b"Exif\0\0" + tiff
    oriented = jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif + jpeg[2:]
    image = decode_image(oriented)
    assert (image.width(), image.height()) == (20, 40)
