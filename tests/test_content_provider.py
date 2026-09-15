from pathlib import Path
from threading import Event
from zipfile import ZipFile

import pytest
from PySide6.QtGui import QColor, QImage

from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.content.archive_provider import ArchiveContentProvider
from archivelens.content.base import (
    ContentCapabilities,
    ContentPage,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    PageMediaKind,
    SourceIdentity,
    SourceType,
)
from archivelens.content.factory import create_content_registry
from archivelens.errors import ArchiveNotOpenError, InvalidArchiveEntryError
from archivelens.image.worker import ImageWorker, LoadRequest, PageCacheKey


def test_archive_content_provider_descriptors_and_lifecycle(tmp_path, image_bytes):
    source = tmp_path / "內容.cbz"
    with ZipFile(source, "w") as archive:
        archive.writestr("chapter/10.png", image_bytes("blue"))
        archive.writestr("chapter/2.png", image_bytes("green"))
        archive.writestr("notes.txt", b"ignored")

    provider = ArchiveContentProvider(DEFAULT_REGISTRY)
    with pytest.raises(ArchiveNotOpenError):
        provider.list_pages()
    provider.open(source)
    pages = provider.list_pages()
    assert [page.path for page in pages] == ["chapter/2.png", "chapter/10.png"]
    assert [page.index for page in pages] == [0, 1]
    assert all(page.media_kind is PageMediaKind.RASTER for page in pages)
    assert all(not hasattr(page, "compressed_size") for page in pages)
    assert provider.source_identity == SourceIdentity(SourceType.ARCHIVE, str(source.resolve()))
    assert provider.load_page(pages[0], PageLoadRequest()).encoded == image_bytes("green")

    copied = PageDescriptor(**{field: getattr(pages[0], field) for field in pages[0].__slots__})
    with pytest.raises(InvalidArchiveEntryError):
        provider.load_page(copied, PageLoadRequest())
    provider.close()
    with pytest.raises(ArchiveNotOpenError):
        _ = provider.source_identity


def test_content_registry_wraps_archives_without_ui_format_branches():
    registry = create_content_registry()
    assert registry.supports("book.CBZ")
    assert isinstance(registry.create("book.cbz"), ArchiveContentProvider)
    assert "*.CBZ" in registry.file_dialog_filter()


def test_source_aware_cache_keys_do_not_collide():
    first = SourceIdentity(SourceType.ARCHIVE, "C:/books/one.cbz")
    second = SourceIdentity(SourceType.ARCHIVE, "C:/books/two.cbz")
    assert PageCacheKey(first, "page:0") != PageCacheKey(second, "page:0")
    assert PageCacheKey(first, "page:0") != PageCacheKey(first, "page:0", (800, 1200))


class RenderedContentProvider(ContentProvider):
    def __init__(self, closed: Event):
        self.closed = closed
        self._open = False
        self._identity = SourceIdentity(SourceType.PDF, "C:/book.pdf")
        self._page = PageDescriptor(0, "Page 1", "1", ".pdf", PageMediaKind.RENDERED, "pdf-page:0")

    @property
    def capabilities(self):
        return ContentCapabilities(SourceType.PDF)

    @property
    def source_identity(self):
        if not self._open:
            raise ArchiveNotOpenError()
        return self._identity

    def open(self, path, *, credentials=None):
        self._open = True

    def close(self):
        self._open = False
        self.closed.set()

    def list_pages(self):
        return [self._page]

    def load_page(self, page, request):
        image = QImage(2, 2, QImage.Format.Format_ARGB32)
        image.fill(QColor("magenta"))
        return ContentPage(image=image)


def test_worker_accepts_rendered_content_without_archive_semantics(wait_until, monkeypatch):
    closed = Event()
    provider = RenderedContentProvider(closed)

    class Registry:
        def create(self, path):
            return provider

    def should_not_decode(*args):
        raise AssertionError("rendered content must bypass the raster decoder")

    monkeypatch.setattr("archivelens.image.worker.decode_image", should_not_decode)
    worker = ImageWorker(content_registry=Registry())
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, Path("book.pdf"), 0))
        wait_until(lambda: bool(results))
        assert results[0].error_type is None
        assert results[0].entries[0].media_kind is PageMediaKind.RENDERED
        assert results[0].image.pixelColor(0, 0) == QColor("magenta")
    finally:
        worker.stop()
        assert worker.wait(5000)
    assert closed.is_set()
