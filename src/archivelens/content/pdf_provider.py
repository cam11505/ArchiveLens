from pathlib import Path

from PySide6.QtCore import QSize

from archivelens import config
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.content.base import (
    ContentCapabilities,
    ContentOpenOptions,
    ContentPage,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    PageMediaKind,
    SourceIdentity,
    SourceType,
    source_identity_for_path,
)
from archivelens.errors import (
    BadPasswordError,
    ContentAccessError,
    CorruptedPdfError,
    EmptyContentError,
    InvalidPageError,
    PasswordRequiredError,
    PdfNotOpenError,
    PdfRenderError,
    ProviderUnavailableError,
    ResourceLimitError,
    UnsupportedEncryptionError,
)


class PdfContentProvider(ContentProvider):
    """Read-only QtPdf provider whose document remains owned by one worker thread."""

    def __init__(self) -> None:
        self._document = None
        self._identity: SourceIdentity | None = None
        self._pages: tuple[PageDescriptor, ...] = ()

    @property
    def capabilities(self) -> ContentCapabilities:
        return ContentCapabilities(SourceType.PDF, supports_credentials=True)

    @property
    def source_identity(self) -> SourceIdentity:
        if self._identity is None:
            raise PdfNotOpenError()
        return self._identity

    def open(
        self,
        path: str | Path,
        *,
        credentials: ArchiveCredentials | None = None,
        options: ContentOpenOptions | None = None,
    ) -> None:
        del options
        self.close()
        source = Path(path)
        if not source.is_file():
            raise ContentAccessError()
        try:
            from PySide6.QtPdf import QPdfDocument
        except ImportError as exc:
            raise ProviderUnavailableError() from exc

        supplied = credentials is not None and credentials.password_bytes() is not None
        password = credentials.password_bytes() if credentials is not None else None
        try:
            decoded_password = password.decode("utf-8") if password is not None else ""
        except UnicodeDecodeError as exc:
            raise BadPasswordError() from exc

        document = QPdfDocument()
        if supplied:
            document.setPassword(decoded_password)
        error = document.load(str(source))
        if error != QPdfDocument.Error.None_:
            self._dispose(document)
            self._raise_load_error(error, supplied)

        # QtPdf keeps the decrypted document usable after load; do not retain plaintext.
        document.setPassword("")
        page_count = document.pageCount()
        if page_count > config.MAX_PDF_PAGES:
            self._dispose(document)
            raise ResourceLimitError()
        if page_count <= 0:
            self._dispose(document)
            raise EmptyContentError()

        pages = []
        for index in range(page_count):
            label = document.pageLabel(index).strip()
            pages.append(
                PageDescriptor(
                    index=index,
                    name=label or f"Page {index + 1}",
                    path=f"page/{index + 1}",
                    extension=".pdf",
                    media_kind=PageMediaKind.RENDERED,
                    cache_id=f"pdf-page:{index}",
                )
            )
        self._document = document
        self._pages = tuple(pages)
        self._identity = source_identity_for_path(source, SourceType.PDF)

    @staticmethod
    def _raise_load_error(error, supplied: bool) -> None:
        from PySide6.QtPdf import QPdfDocument

        if error == QPdfDocument.Error.IncorrectPassword:
            raise BadPasswordError() if supplied else PasswordRequiredError()
        if error == QPdfDocument.Error.UnsupportedSecurityScheme:
            raise UnsupportedEncryptionError()
        if error == QPdfDocument.Error.FileNotFound:
            raise ContentAccessError()
        raise CorruptedPdfError()

    def close(self) -> None:
        document, self._document = self._document, None
        self._identity = None
        self._pages = ()
        if document is not None:
            self._dispose(document)

    @staticmethod
    def _dispose(document) -> None:
        import shiboken6

        if shiboken6.isValid(document):
            document.setPassword("")
            document.close()
            shiboken6.delete(document)

    def list_pages(self) -> list[PageDescriptor]:
        if self._document is None:
            raise PdfNotOpenError()
        return list(self._pages)

    def load_page(self, page: PageDescriptor, request: PageLoadRequest) -> ContentPage:
        document = self._document
        if document is None:
            raise PdfNotOpenError()
        if not 0 <= page.index < len(self._pages) or self._pages[page.index] is not page:
            raise InvalidPageError()
        point_size = document.pagePointSize(page.index)
        target = self._target_size(point_size, request)
        image = self._render_page(page.index, target)
        if image.isNull() or image.width() != target.width() or image.height() != target.height():
            raise PdfRenderError()
        if request.thumbnail_size is None:
            base_width = max(1, point_size.width() * 96 / 72)
            base_height = max(1, point_size.height() * 96 / 72)
            image.setDevicePixelRatio(
                max(0.01, min(image.width() / base_width, image.height() / base_height))
            )
        return ContentPage(image=image)

    def _render_page(self, page_index: int, size: QSize):
        try:
            return self._document.render(page_index, size, self._render_options())
        except Exception as exc:
            raise PdfRenderError() from exc

    @staticmethod
    def _render_options():
        """Reader policy: show visual annotations and optimize text for displays."""
        from PySide6.QtPdf import QPdfDocumentRenderOptions

        options = QPdfDocumentRenderOptions()
        options.setRenderFlags(
            QPdfDocumentRenderOptions.RenderFlag.Annotations
            | QPdfDocumentRenderOptions.RenderFlag.OptimizedForLcd
        )
        return options

    @staticmethod
    def _target_size(point_size, request: PageLoadRequest) -> QSize:
        if request.thumbnail_size is not None:
            side = min(max(1, request.thumbnail_size), config.THUMBNAIL_SIZE)
            bounds = (side, side)
        elif request.render_size is not None:
            bounds = request.render_size
        else:
            bounds = (
                max(1, round(point_size.width() * 96 / 72)),
                max(1, round(point_size.height() * 96 / 72)),
            )
        bound_width, bound_height = bounds
        if bound_width <= 0 or bound_height <= 0:
            raise ResourceLimitError()
        if bound_width > config.MAX_PDF_RENDER_EDGE or bound_height > config.MAX_PDF_RENDER_EDGE:
            raise ResourceLimitError()
        page_width = point_size.width()
        page_height = point_size.height()
        if page_width <= 0 or page_height <= 0:
            raise PdfRenderError()
        scale = min(bound_width / page_width, bound_height / page_height)
        width = max(1, round(page_width * scale))
        height = max(1, round(page_height * scale))
        if (
            width > config.MAX_PDF_RENDER_EDGE
            or height > config.MAX_PDF_RENDER_EDGE
            or width * height > config.MAX_PDF_RENDER_PIXELS
        ):
            raise ResourceLimitError()
        return QSize(width, height)
