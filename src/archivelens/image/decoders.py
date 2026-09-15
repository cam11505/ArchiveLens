import io
from abc import ABC, abstractmethod
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QColorSpace, QImage, QImageReader

from archivelens import config
from archivelens.errors import (
    DecoderUnavailableError,
    ImageDecodeError,
    ImageSizeError,
    UnsupportedImageFormatError,
)


@dataclass(frozen=True, slots=True)
class DecoderCapabilities:
    name: str
    backend: str
    extensions: frozenset[str]
    animation_extensions: frozenset[str] = frozenset()
    buffer_decode: bool = True

    def __post_init__(self) -> None:
        extensions = frozenset(item.casefold() for item in self.extensions)
        animated = frozenset(item.casefold() for item in self.animation_extensions)
        if any(not item.startswith(".") for item in extensions | animated):
            raise ValueError("Decoder extensions must include a leading dot")
        if not animated <= extensions:
            raise ValueError("Animated extensions must also be decoder extensions")
        object.__setattr__(self, "extensions", extensions)
        object.__setattr__(self, "animation_extensions", animated)


class ImageDecoder(ABC):
    capabilities: DecoderCapabilities

    @property
    @abstractmethod
    def available_extensions(self) -> frozenset[str]: ...

    @abstractmethod
    def can_decode(self, data: bytes) -> bool: ...

    @abstractmethod
    def decode(self, data: bytes, thumbnail_size: int | None = None) -> QImage: ...


class QtImageDecoder(ImageDecoder):
    capabilities = DecoderCapabilities(
        "Qt raster",
        "PySide6.QtGui.QImageReader",
        frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}),
        frozenset({".gif"}),
    )
    _format_aliases = {
        ".jpg": frozenset({"jpg", "jpeg", "jfif"}),
        ".jpeg": frozenset({"jpg", "jpeg", "jfif"}),
        ".png": frozenset({"png"}),
        ".webp": frozenset({"webp"}),
        ".bmp": frozenset({"bmp"}),
        ".gif": frozenset({"gif"}),
        ".tif": frozenset({"tif", "tiff"}),
        ".tiff": frozenset({"tif", "tiff"}),
    }

    @property
    def available_extensions(self) -> frozenset[str]:
        formats = {
            bytes(item).decode("ascii").casefold() for item in QImageReader.supportedImageFormats()
        }
        return frozenset(
            extension for extension, aliases in self._format_aliases.items() if aliases & formats
        )

    def can_decode(self, data: bytes) -> bool:
        reader, buffer = self._reader(data)
        try:
            return reader.canRead()
        finally:
            buffer.close()

    def decode(self, data: bytes, thumbnail_size: int | None = None) -> QImage:
        reader, buffer = self._reader(data)
        try:
            reader.setAutoTransform(True)
            size = reader.size()
            if not size.isValid() or size.isEmpty():
                raise ImageDecodeError()
            if size.width() * size.height() > config.MAX_IMAGE_PIXELS:
                raise ImageSizeError()
            if thumbnail_size:
                reader.setScaledSize(
                    size.scaled(
                        QSize(thumbnail_size, thumbnail_size),
                        Qt.AspectRatioMode.KeepAspectRatio,
                    )
                )
            image = reader.read()
            if image.isNull():
                raise ImageDecodeError()
            if image.width() * image.height() > config.MAX_IMAGE_PIXELS:
                raise ImageSizeError()
            return image
        finally:
            buffer.close()

    @staticmethod
    def _reader(data: bytes) -> tuple[QImageReader, QBuffer]:
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        reader.setDecideFormatFromContent(True)
        return reader, buffer


class PillowImageDecoder(ImageDecoder):
    """Static AVIF/JPEG 2000 decoder using Pillow's tested Windows wheels."""

    capabilities = DecoderCapabilities(
        "Pillow raster",
        "Pillow",
        frozenset({".avif", ".jp2", ".j2k", ".j2c"}),
    )
    _format_extensions = {
        "AVIF": frozenset({".avif"}),
        "JPEG2000": frozenset({".jp2", ".j2k", ".j2c"}),
    }

    @property
    def available_extensions(self) -> frozenset[str]:
        try:
            from PIL import features
        except ImportError:
            return frozenset()
        available = set()
        if features.check("avif"):
            available.update(self._format_extensions["AVIF"])
        if features.check("jpg_2000"):
            available.update(self._format_extensions["JPEG2000"])
        return frozenset(available)

    def can_decode(self, data: bytes) -> bool:
        try:
            from PIL import Image
        except ImportError:
            return False
        try:
            with Image.open(io.BytesIO(data)) as image:
                return image.format in self._format_extensions
        except (Image.DecompressionBombError, OSError, SyntaxError, ValueError):
            return False

    def decode(self, data: bytes, thumbnail_size: int | None = None) -> QImage:
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise DecoderUnavailableError() from exc
        try:
            with Image.open(io.BytesIO(data)) as source:
                self._guard_size(*source.size)
                image = ImageOps.exif_transpose(source)
                self._guard_size(*image.size)
                if thumbnail_size:
                    image.thumbnail((thumbnail_size, thumbnail_size), Image.Resampling.LANCZOS)
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                self._guard_size(*image.size)
                raw = image.tobytes()
                qt_format = (
                    QImage.Format.Format_RGBA8888
                    if has_alpha
                    else QImage.Format.Format_RGB888
                )
                result = QImage(
                    raw,
                    image.width,
                    image.height,
                    image.width * len(image.getbands()),
                    qt_format,
                ).copy()
                icc_profile = source.info.get("icc_profile") or image.info.get("icc_profile")
                if icc_profile:
                    color_space = QColorSpace.fromIccProfile(QByteArray(icc_profile))
                    if color_space.isValid():
                        result.setColorSpace(color_space)
                if result.isNull():
                    raise ImageDecodeError()
                return result
        except ImageSizeError:
            raise
        except (Image.DecompressionBombError, MemoryError) as exc:
            raise ImageSizeError() from exc
        except (OSError, SyntaxError, ValueError, RuntimeError) as exc:
            raise ImageDecodeError() from exc

    @staticmethod
    def _guard_size(width: int, height: int) -> None:
        if width <= 0 or height <= 0 or width * height > config.MAX_IMAGE_PIXELS:
            raise ImageSizeError()


class DecoderRegistry:
    def __init__(self) -> None:
        self._decoders: list[ImageDecoder] = []

    def register(self, decoder: ImageDecoder) -> None:
        overlap = decoder.capabilities.extensions & self.registered_extensions
        if overlap:
            raise ValueError(f"Decoder extension already registered: {sorted(overlap)[0]}")
        self._decoders.append(decoder)

    @property
    def registered_extensions(self) -> frozenset[str]:
        return frozenset(
            extension for decoder in self._decoders for extension in decoder.capabilities.extensions
        )

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(
            extension for decoder in self._decoders for extension in decoder.available_extensions
        )

    @property
    def capabilities(self) -> tuple[DecoderCapabilities, ...]:
        return tuple(decoder.capabilities for decoder in self._decoders)

    def decode(
        self,
        data: bytes,
        thumbnail_size: int | None = None,
        extension: str | None = None,
    ) -> QImage:
        normalized = extension.casefold() if extension else None
        candidates = [
            decoder
            for decoder in self._decoders
            if normalized is None or normalized in decoder.capabilities.extensions
        ]
        if not candidates:
            raise UnsupportedImageFormatError()
        available = [
            decoder
            for decoder in candidates
            if normalized is None or normalized in decoder.available_extensions
        ]
        if not available:
            raise DecoderUnavailableError()
        last_error = None
        for decoder in available:
            if normalized is None and not decoder.can_decode(data):
                continue
            try:
                return decoder.decode(data, thumbnail_size)
            except ImageSizeError:
                raise
            except ImageDecodeError as exc:
                last_error = exc
        raise ImageDecodeError() from last_error


DEFAULT_DECODER_REGISTRY = DecoderRegistry()
DEFAULT_DECODER_REGISTRY.register(QtImageDecoder())
DEFAULT_DECODER_REGISTRY.register(PillowImageDecoder())
