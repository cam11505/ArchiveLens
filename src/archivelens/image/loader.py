from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageReader

from archivelens import config
from archivelens.errors import ArchiveLensError


def decode_image(data: bytes) -> QImage:
    """Decode the first frame, respecting EXIF orientation and size limits."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.isEmpty():
        raise ArchiveLensError("無法辨識圖片尺寸，圖片可能損壞或格式不受支援。")
    if size.width() * size.height() > config.MAX_IMAGE_PIXELS:
        raise ArchiveLensError("圖片尺寸過大，基於安全考量未載入。")
    image = reader.read()
    if image.isNull():
        raise ArchiveLensError("圖片解碼失敗，檔案可能損壞或超過記憶體限制。")
    if image.width() * image.height() > config.MAX_IMAGE_PIXELS:
        raise ArchiveLensError("圖片尺寸過大，基於安全考量未載入。")
    return image
