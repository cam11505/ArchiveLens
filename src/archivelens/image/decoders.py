from abc import ABC, abstractmethod
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader

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
        frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}),
        frozenset({".gif"}),
    )
    _format_aliases = {
        ".jpg": frozenset({"jpg", "jpeg", "jfif"}),
        ".jpeg": frozenset({"jpg", "jpeg", "jfif"}),
        ".png": frozenset({"png"}),
        ".webp": frozenset({"webp"}),
        ".bmp": frozenset({"bmp"}),
        ".gif": frozenset({"gif"}),
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
