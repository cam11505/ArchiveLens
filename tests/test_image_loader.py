import base64
import io
import struct

import pytest
from PySide6.QtGui import QImage

from archivelens import config
from archivelens.errors import (
    ArchiveLensError,
    DecoderUnavailableError,
    UnsupportedImageFormatError,
)
from archivelens.image.decoders import (
    DecoderCapabilities,
    DecoderRegistry,
    ImageDecoder,
    PillowImageDecoder,
    QtImageDecoder,
)
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


def test_qt_decoder_registry_capabilities_and_content_detection(image_bytes, qapp):
    registry = DecoderRegistry()
    decoder = QtImageDecoder()
    registry.register(decoder)
    assert {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"} <= (registry.supported_extensions)
    assert registry.capabilities[0].buffer_decode
    assert ".gif" in registry.capabilities[0].animation_extensions
    # The backend sniffs content rather than trusting a mismatched filename suffix.
    image = decode_image(image_bytes("red", "PNG"), extension=".jpg", registry=registry)
    assert image.pixelColor(0, 0).name() == "#ff0000"


class FakeDecoder(ImageDecoder):
    capabilities = DecoderCapabilities("Fake", "test", frozenset({".fake"}))

    def __init__(self, available=True):
        self.available = available

    @property
    def available_extensions(self):
        return self.capabilities.extensions if self.available else frozenset()

    def can_decode(self, data):
        return data.startswith(b"fake")

    def decode(self, data, thumbnail_size=None):
        image = QImage(2, 2, QImage.Format.Format_RGB32)
        image.fill(0)
        return image


def test_decoder_registry_selection_duplicates_and_unavailable():
    registry = DecoderRegistry()
    registry.register(FakeDecoder())
    assert not registry.decode(b"fake", extension=".fake").isNull()
    assert not registry.decode(b"fake").isNull()
    with pytest.raises(ValueError):
        registry.register(FakeDecoder())
    with pytest.raises(UnsupportedImageFormatError):
        registry.decode(b"fake", extension=".unknown")
    unavailable = DecoderRegistry()
    unavailable.register(FakeDecoder(available=False))
    with pytest.raises(DecoderUnavailableError):
        unavailable.decode(b"fake", extension=".fake")


def pillow_fixture(fmt, *, orientation=None, icc_profile=None):
    from PIL import Image

    image = Image.new("RGBA", (8, 6), (20, 80, 160, 96))
    options = {}
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    if icc_profile:
        options["icc_profile"] = icc_profile
    stream = io.BytesIO()
    image.save(stream, fmt, **options)
    return stream.getvalue()


@pytest.mark.parametrize(
    "fmt,extension",
    [("AVIF", ".avif"), ("JPEG2000", ".jp2"), ("JPEG2000", ".j2k"), ("TIFF", ".tiff")],
)
def test_v12_static_codecs_decode_in_memory(fmt, extension, qapp):
    image = decode_image(pillow_fixture(fmt), extension=extension)
    assert image.size().toTuple() == (8, 6)
    assert image.hasAlphaChannel()


def test_avif_exif_orientation_icc_and_thumbnail(qapp):
    from PIL import ImageCms

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = pillow_fixture("AVIF", orientation=6, icc_profile=profile)
    image = decode_image(data, extension=".avif")
    thumbnail = decode_image(data, thumbnail_size=4, extension=".avif")
    assert image.size().toTuple() == (6, 8)
    assert image.colorSpace().isValid()
    assert max(thumbnail.width(), thumbnail.height()) == 4


@pytest.mark.parametrize("extension", [".avif", ".jp2", ".tiff"])
def test_v12_codec_malformed_input_is_recoverable(extension, qapp):
    with pytest.raises(ArchiveLensError):
        decode_image(b"malformed codec input", extension=extension)


def test_pillow_size_guard_runs_before_pixel_decode(monkeypatch, qapp):
    monkeypatch.setattr(config, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(ArchiveLensError, match="尺寸過大"):
        decode_image(pillow_fixture("AVIF"), extension=".avif")


def test_pillow_decoder_capabilities_and_missing_backend(monkeypatch):
    decoder = PillowImageDecoder()
    assert {".avif", ".jp2", ".j2k", ".j2c"} <= decoder.available_extensions
    registry = DecoderRegistry()
    registry.register(decoder)
    monkeypatch.setattr(
        PillowImageDecoder,
        "available_extensions",
        property(lambda self: frozenset()),
    )
    with pytest.raises(DecoderUnavailableError):
        registry.decode(b"anything", extension=".avif")
