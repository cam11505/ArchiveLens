class ArchiveLensError(Exception):
    """A recoverable error whose message can be displayed to the user."""

    default_message = "載入失敗，請嘗試其他圖片或重新開啟壓縮檔。"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class PasswordRequiredError(ArchiveLensError):
    default_message = "此內容來源需要密碼。"


class BadPasswordError(ArchiveLensError):
    default_message = "密碼不正確，請重新輸入。"


class UnsupportedEncryptionError(ArchiveLensError):
    default_message = "目前版本尚未支援此內容來源的加密方式。"


class CorruptedArchiveError(ArchiveLensError):
    default_message = "無法開啟或讀取壓縮檔：壓縮資料已損壞。"


class CorruptedPdfError(ArchiveLensError):
    default_message = "無法開啟或讀取 PDF：檔案可能已損壞。"


class PdfRenderError(ArchiveLensError):
    default_message = "PDF 頁面轉譯失敗，檔案可能損壞或超過資源限制。"


class PdfNotOpenError(ArchiveLensError):
    default_message = "尚未開啟 PDF。"


class ResourceLimitError(ArchiveLensError):
    default_message = "此檔案大小異常，已停止載入。"


class ProviderUnavailableError(ArchiveLensError):
    default_message = "此壓縮格式的讀取元件目前無法使用。"


class UnsupportedArchiveError(ArchiveLensError):
    default_message = "目前尚未支援此壓縮檔格式。"


class UnsupportedCompressionError(ArchiveLensError):
    default_message = "目前尚未支援此壓縮方式。"


class ArchiveAccessError(ArchiveLensError):
    default_message = "無法開啟或讀取壓縮檔：檔案不存在或沒有讀取權限。"


class ArchiveNotOpenError(ArchiveLensError):
    default_message = "尚未開啟壓縮檔。"


class InvalidArchiveEntryError(ArchiveLensError):
    default_message = "圖片項目已失效，請重新開啟壓縮檔。"


class InvalidPageError(InvalidArchiveEntryError):
    default_message = "頁面項目已失效，請重新開啟內容來源。"


class EmptyArchiveError(ArchiveLensError):
    default_message = "此壓縮檔中沒有找到可顯示的圖片。"


class EmptyContentError(ArchiveLensError):
    default_message = "此來源中沒有找到可顯示的圖片。"


class ContentAccessError(ArchiveLensError):
    default_message = "無法開啟或讀取內容來源：路徑不存在或沒有讀取權限。"


class ContentScanCancelledError(ArchiveLensError):
    default_message = "內容掃描已取消。"


class UnsupportedContentError(ArchiveLensError):
    default_message = "目前尚未支援此內容來源。"


class ImageDecodeError(ArchiveLensError):
    default_message = "圖片解碼失敗，圖片可能損壞、格式不受支援或超過記憶體限制。"


class ImageSizeError(ResourceLimitError):
    default_message = "圖片尺寸過大，基於安全考量未載入。"


class UnsupportedImageFormatError(ArchiveLensError):
    default_message = "目前尚未支援此圖片格式。"


class DecoderUnavailableError(ArchiveLensError):
    default_message = "此圖片格式的解碼元件目前無法使用。"
