from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from archivelens import config
from archivelens.errors import ImageDecodeError, ImageSizeError


def decode_image(data: bytes, thumbnail_size: int | None = None) -> QImage:
    """Decode the first frame, respecting EXIF orientation and size limits."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.isEmpty():
        raise ImageDecodeError()
    if size.width() * size.height() > config.MAX_IMAGE_PIXELS:
        raise ImageSizeError()
    if thumbnail_size:
        reader.setScaledSize(
            size.scaled(QSize(thumbnail_size, thumbnail_size), Qt.AspectRatioMode.KeepAspectRatio)
        )
    image = reader.read()
    if image.isNull():
        raise ImageDecodeError()
    if image.width() * image.height() > config.MAX_IMAGE_PIXELS:
        raise ImageSizeError()
    return image
