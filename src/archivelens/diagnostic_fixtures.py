"""Small synthetic media/ZipCrypto fixtures for source and packaged diagnostics."""
# ruff: noqa: E501 -- embedded encrypted fixture is intentionally immutable base64.

import base64
import io
import struct
import zipfile

_PASSWORD_PDF = """JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgPDUyZjg1NWJhYmE+Cj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9UeXBlIC9QYWdlcwovQ291bnQgMQovS2lkcyBbIDQgMCBSIF0KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL0NhdGFsb2cKL1BhZ2VzIDIgMCBSCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9UeXBlIC9QYWdlCi9Db250ZW50cyA1IDAgUgovUmVzb3VyY2VzIDYgMCBSCi9Bbm5vdHMgMTEgMCBSCi9NZWRpYUJveCBbIDAgMCA1OTUgODQyIF0KL1RyaW1Cb3ggWyAwIDAgNTk1IDg0MiBdCi9QYXJlbnQgMiAwIFIKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL0ZpbHRlciAvRmxhdGVEZWNvZGUKL0xlbmd0aCAzNzQKPj4Kc3RyZWFtCr8JppIfcewx8qU4tcvIpx7wb1dhqcZmqFTzZKkb4FhEZnuRLz3sotR69Q6CQ6iWBMYpi51ueAaNqXZNPmOZSkISLwrW7d0CYD9a0sIF97SafSrsV1WAv18lgbPL/fk6GcqEWDIfatQPAQrkqPJRAhhIfxftPkpgJjflclgrfH+aCI/4LFaEM6/YtILvU5BTdOX07K7kzbhJVGgMMQ9AiXIhrOsW3dxQg2ZSgJq375yf+V075M7pn7q9IIhbcWwMtecHz8VLXqPt5uhX4hSVqOXU/9PLII0ieP8yPp5Nap2cB3DafaiuzOQb2YffhSt67/4lD0DC4NAz1XZh4hAP6WWkCS87ScWHwNSHNv2lojAIAP8B0vej778uK1kD1JMVQdWZEgRq2O40sfzOjGdXcYGEzEHPLfzdyecR+ChaWUIv3D1ZtUhHTEbzUbJIo3jtetmJ2EwQZeNBFwGR/nRvCbbm2SZdGBR1i4J/ImnW04ET7tT0SNk8CmVuZHN0cmVhbQplbmRvYmoKNiAwIG9iago8PAovQ29sb3JTcGFjZSA8PAovUENTcCA3IDAgUgovUENTcGcgOCAwIFIKL1BDU3BjbXlrIDkgMCBSCi9DU3AgL0RldmljZVJHQgovQ1NwZyAvRGV2aWNlR3JheQovQ1NwY215ayAvRGV2aWNlQ01ZSwo+PgovRXh0R1N0YXRlIDw8Ci9HU2EgMTAgMCBSCj4+Ci9QYXR0ZXJuIDw8Cj4+Ci9Gb250IDw8Cj4+Ci9YT2JqZWN0IDw8Cj4+Cj4+CmVuZG9iago3IDAgb2JqClsgL1BhdHRlcm4gL0RldmljZVJHQiBdCmVuZG9iago4IDAgb2JqClsgL1BhdHRlcm4gL0RldmljZUdyYXkgXQplbmRvYmoKOSAwIG9iagpbIC9QYXR0ZXJuIC9EZXZpY2VDTVlLIF0KZW5kb2JqCjEwIDAgb2JqCjw8Ci9UeXBlIC9FeHRHU3RhdGUKL1NBIHRydWUKL1NNIDAuMDIKL2NhIDEKL0NBIDEKL0FJUyBmYWxzZQovU01hc2sgL05vbmUKPj4KZW5kb2JqCjExIDAgb2JqClsgXQplbmRvYmoKMTIgMCBvYmoKPDwKL1YgMgovUiAzCi9MZW5ndGggMTI4Ci9QIDQyOTQ5NjcyOTIKL0ZpbHRlciAvU3RhbmRhcmQKL08gPDNkODY3YzA4MWY1NDdkYjUxYTNmZTZiOGE3YTExMGYyMGU1NTlhYmYwZTY4ZWJhYWZlN2Y2MjUwNmE2ZmUxNjA+Ci9VIDw0YzhkYWU1MDIzZTVkNTk2MGZlOGExMjJjNzRmZjVmZDI4YmY0ZTVlNGU3NThhNDE2NDAwNGU1NmZmZmEwMTA4Pgo+PgplbmRvYmoKeHJlZgowIDEzCjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAxNSAwMDAwMCBuIAowMDAwMDAwMDU5IDAwMDAwIG4gCjAwMDAwMDAxMTggMDAwMDAgbiAKMDAwMDAwMDE2NyAwMDAwMCBuIAowMDAwMDAwMzEzIDAwMDAwIG4gCjAwMDAwMDA3NTkgMDAwMDAgbiAKMDAwMDAwMDk2NSAwMDAwMCBuIAowMDAwMDAxMDA0IDAwMDAwIG4gCjAwMDAwMDEwNDQgMDAwMDAgbiAKMDAwMDAwMTA4NCAwMDAwMCBuIAowMDAwMDAxMTc3IDAwMDAwIG4gCjAwMDAwMDExOTcgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSAxMwovUm9vdCAzIDAgUgovSW5mbyAxIDAgUgovSUQgWyA8NjEzMDYxMzg2MTMzMzY2NDMyMzkzOTYxMzQzMTMzNjQzNjMxMzkzMzYzNjQ2NTY1MzA2MTMzNjYzNzM2MzkzOT4gPDYxMzA2MTM4NjEzMzM2NjQzMjM5Mzk2MTM0MzEzMzY0MzYzMTM5MzM2MzY0NjU2NTMwNjEzMzY2MzczNjM5Mzk+IF0KL0VuY3J5cHQgMTIgMCBSCj4+CnN0YXJ0eHJlZgoxNDEzCiUlRU9GCg=="""


def password_pdf_fixture() -> bytes:
    """One-page standard-encryption PDF; user password is ``reader-secret``."""
    return base64.b64decode(_PASSWORD_PDF)


def write_pdf_fixture(path, pages: int = 1, page_mm: tuple[float, float] | None = None) -> None:
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QPageSize, QPainter, QPdfWriter

    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    if page_mm:
        writer.setPageSize(QPageSize(QSizeF(*page_mm), QPageSize.Unit.Millimeter, "Fixture"))
    painter = QPainter(writer)
    for index in range(pages):
        painter.drawText(72, 72, f"ArchiveLens PDF page {index + 1}")
        if index + 1 < pages:
            writer.newPage()
    painter.end()


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
