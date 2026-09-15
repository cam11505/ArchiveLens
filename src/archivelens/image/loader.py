from PySide6.QtGui import QImage

from archivelens.image.decoders import DEFAULT_DECODER_REGISTRY, DecoderRegistry


def decode_image(
    data: bytes,
    thumbnail_size: int | None = None,
    extension: str | None = None,
    *,
    registry: DecoderRegistry | None = None,
) -> QImage:
    """Decode through the registry while preserving the v1.0 convenience API."""
    decoder_registry = DEFAULT_DECODER_REGISTRY if registry is None else registry
    return decoder_registry.decode(data, thumbnail_size, extension)
