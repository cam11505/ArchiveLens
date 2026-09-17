import hashlib
from pathlib import Path
from threading import Event

import pytest

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.content.base import PageLoadRequest, PageMediaKind, SourceType
from archivelens.content.factory import create_content_registry
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.diagnostic_fixtures import (
    annotation_pdf_fixture,
    password_pdf_fixture,
    write_pdf_fixture,
)
from archivelens.errors import (
    BadPasswordError,
    CorruptedPdfError,
    InvalidPageError,
    PasswordRequiredError,
    PdfNotOpenError,
    ResourceLimitError,
)
from archivelens.image.worker import ImageWorker, LoadRequest


def test_pdf_provider_lists_stable_pages_and_renders_bounded_images(tmp_path, qapp):
    source = tmp_path / "reader.pdf"
    write_pdf_fixture(source, pages=3)
    before = hashlib.sha256(source.read_bytes()).digest()
    provider = PdfContentProvider()

    with pytest.raises(PdfNotOpenError):
        provider.list_pages()
    provider.open(source)
    pages = provider.list_pages()
    assert provider.source_identity.source_type is SourceType.PDF
    assert [page.index for page in pages] == [0, 1, 2]
    assert [page.path for page in pages] == ["page/1", "page/2", "page/3"]
    assert all(page.media_kind is PageMediaKind.RENDERED for page in pages)
    assert all(page.cache_id == f"pdf-page:{page.index}" for page in pages)

    full = provider.load_page(pages[0], PageLoadRequest(render_size=(800, 600))).image
    thumbnail = provider.load_page(pages[0], PageLoadRequest(thumbnail_size=500)).image
    assert full is not None and full.width() <= 800 and full.height() <= 600
    assert thumbnail is not None and thumbnail.width() <= 144 and thumbnail.height() <= 144
    assert full.width() * full.height() <= 16_000_000

    copied = type(pages[0])(**{field: getattr(pages[0], field) for field in pages[0].__slots__})
    with pytest.raises(InvalidPageError):
        provider.load_page(copied, PageLoadRequest(render_size=(100, 100)))
    provider.close()
    assert hashlib.sha256(source.read_bytes()).digest() == before


def test_pdf_provider_password_retry_and_session_cleanup(tmp_path, qapp):
    source = tmp_path / "protected.pdf"
    source.write_bytes(password_pdf_fixture())
    provider = PdfContentProvider()
    secret = ArchiveCredentials(b"reader-secret")

    with pytest.raises(PasswordRequiredError):
        provider.open(source)
    with pytest.raises(BadPasswordError):
        provider.open(source, credentials=ArchiveCredentials(b"wrong"))
    provider.open(source, credentials=secret)
    assert (
        provider.load_page(provider.list_pages()[0], PageLoadRequest(render_size=(320, 480))).image
        is not None
    )
    assert provider._document.password() == ""
    provider.close()
    secret.clear()
    assert b"reader-secret" not in repr(provider).encode()


def test_pdf_provider_explicitly_renders_annotations_and_optimizes_for_lcd(tmp_path, qapp):
    from PySide6.QtPdf import QPdfDocumentRenderOptions

    source = tmp_path / "annotation.pdf"
    source.write_bytes(annotation_pdf_fixture())
    provider = PdfContentProvider()
    provider.open(source)
    page = provider.list_pages()[0]
    target = provider._target_size(
        provider._document.pagePointSize(0), PageLoadRequest(render_size=(600, 600))
    )
    no_annotations = provider._document.render(0, target)
    rendered = provider.load_page(page, PageLoadRequest(render_size=(600, 600))).image
    flags = provider._render_options().renderFlags()

    assert flags & QPdfDocumentRenderOptions.RenderFlag.Annotations
    assert flags & QPdfDocumentRenderOptions.RenderFlag.OptimizedForLcd
    assert rendered is not None
    assert rendered != no_annotations
    provider.close()


def test_pdf_provider_corruption_page_and_render_guards(tmp_path, qapp, monkeypatch):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    with pytest.raises(CorruptedPdfError):
        PdfContentProvider().open(broken)

    source = tmp_path / "guarded.pdf"
    write_pdf_fixture(source, pages=2)
    provider = PdfContentProvider()
    monkeypatch.setattr("archivelens.config.MAX_PDF_PAGES", 1)
    with pytest.raises(ResourceLimitError):
        provider.open(source)

    monkeypatch.setattr("archivelens.config.MAX_PDF_PAGES", 100_000)
    provider.open(source)
    page = provider.list_pages()[0]
    with pytest.raises(ResourceLimitError):
        provider.load_page(page, PageLoadRequest(render_size=(8193, 10)))
    with pytest.raises(ResourceLimitError):
        provider.load_page(page, PageLoadRequest(render_size=(0, 100)))
    provider.close()


def test_pdf_registry_open_dialog_and_case_insensitive_selection():
    registry = create_content_registry()
    assert registry.supports("book.PDF")
    assert registry.source_type(Path("book.PDF")) is SourceType.PDF
    assert isinstance(registry.create("book.pdf"), PdfContentProvider)
    assert "*.pdf" in registry.file_dialog_filter()
    assert ".pdf" in registry.supported_extensions


def test_pdf_render_navigation_suppresses_stale_result(tmp_path, qapp, wait_until, monkeypatch):
    source = tmp_path / "rapid.pdf"
    write_pdf_fixture(source, pages=2)
    entered, release = Event(), Event()
    original = PdfContentProvider._render_page

    def delayed(provider, page_index, size):
        if page_index == 0 and not entered.is_set():
            entered.set()
            assert release.wait(5)
        return original(provider, page_index, size)

    monkeypatch.setattr(PdfContentProvider, "_render_page", delayed)
    worker = ImageWorker()
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, source, 0, render_size=(400, 400)))
        wait_until(entered.is_set)
        worker.submit(LoadRequest(2, 1, source, 1, render_size=(400, 400)))
        release.set()
        wait_until(lambda: bool(results))
        assert [result.token for result in results] == [2]
        assert results[0].index == 1
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)
