"""Small synthetic media/ZipCrypto fixtures for source and packaged diagnostics."""

import io
import struct
import zipfile


def pillow_image_fixture(
    fmt: str,
    *,
    size: tuple[int, int] = (8, 6),
    alpha: int = 127,
    orientation: int | None = None,
    icc_profile: bytes | None = None,
) -> bytes:
    """Create a tiny codec fixture without adding binary test assets."""
    from PIL import Image

    image = Image.new("RGBA", size, (32, 96, 192, alpha))
    options = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    if icc_profile is not None:
        options["icc_profile"] = icc_profile
    stream = io.BytesIO()
    image.save(stream, fmt, **options)
    return stream.getvalue()


def animated_gif():
    header = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\x00\x00\x00\xff\x00"
    loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"

    def frame(pixel):
        return (
            b"\x21\xf9\x04\x00\x05\x00\x00\x00"
            + b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            + bytes([pixel, 1])
            + b"\x00"
        )

    return header + loop + frame(0x44) + frame(0x4C) + b"\x3b"


def zipcrypto_fixture(data, password=b"diagnostic-only"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("1.png", data)
    raw = bytearray(stream.getvalue())
    central = raw.index(b"PK\x01\x02")
    start = 30 + struct.unpack_from("<H", raw, 26)[0] + struct.unpack_from("<H", raw, 28)[0]
    crc = struct.unpack_from("<I", raw, 14)[0]
    zipfile._ZipDecrypter(b"")  # Initialize the stdlib's ZipCrypto CRC table.
    keys = [0x12345678, 0x23456789, 0x34567890]

    def update(value):
        keys[0] = zipfile._crctable[(keys[0] ^ value) & 255] ^ (keys[0] >> 8)
        keys[1] = ((keys[1] + (keys[0] & 255)) * 134775813 + 1) & 0xFFFFFFFF
        keys[2] = zipfile._crctable[(keys[2] ^ (keys[1] >> 24)) & 255] ^ (keys[2] >> 8)

    for value in password:
        update(value)
    encrypted = bytearray()
    for value in b"\0" * 11 + bytes([crc >> 24]) + data:
        temp = keys[2] | 2
        encrypted.append(value ^ ((temp * (temp ^ 1) >> 8) & 255))
        update(value)
    struct.pack_into("<H", raw, 6, 1)
    struct.pack_into("<I", raw, 18, len(data) + 12)
    struct.pack_into("<H", raw, central + 8, 1)
    struct.pack_into("<I", raw, central + 20, len(data) + 12)
    end = raw.index(b"PK\x05\x06")
    struct.pack_into("<I", raw, end + 16, central + 12)
    return bytes(raw[:start] + encrypted + raw[central:])
