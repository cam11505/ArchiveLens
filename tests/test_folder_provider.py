import hashlib
from pathlib import Path
from threading import Event

import pytest

from archivelens import config
from archivelens.content.base import ContentOpenOptions, PageLoadRequest, SourceType
from archivelens.content.factory import create_content_registry
from archivelens.content.folder_provider import FolderContentProvider, _is_reparse_or_symlink
from archivelens.errors import ContentAccessError, ContentScanCancelledError, ResourceLimitError
from archivelens.image.worker import ImageWorker, LoadRequest
from archivelens.reading_state import ReadingStateStore
from archivelens.ui.main_window import MainWindow


def write_image(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def inventory(root: Path):
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def test_flat_and_recursive_natural_unicode_discovery(tmp_path, image_bytes):
    root = tmp_path / "漫畫"
    write_image(root / "10.png", image_bytes("blue"))
    write_image(root / "2.png", image_bytes("green"))
    write_image(root / "章節一" / "10.png", image_bytes("red"))
    write_image(root / "章節一" / "2.png", image_bytes("yellow"))
    write_image(root / "章節一" / "notes.txt", b"ignored")
    before = inventory(root)

    provider = FolderContentProvider()
    provider.open(root)
    assert [page.path for page in provider.list_pages()] == ["2.png", "10.png"]
    provider.open(root, options=ContentOpenOptions(recursive=True))
    pages = provider.list_pages()
    assert [page.path for page in pages] == [
        "2.png",
        "10.png",
        "章節一/2.png",
        "章節一/10.png",
    ]
    assert provider.source_identity.source_type is SourceType.FOLDER
    assert provider.source_identity.scan_signature
    assert provider.load_page(pages[2], PageLoadRequest()).encoded == image_bytes("yellow")
    assert inventory(root) == before


def test_folder_provider_discovers_v12_codec_extensions(tmp_path):
    from archivelens.diagnostic_fixtures import pillow_image_fixture
    from archivelens.image.loader import decode_image

    root = tmp_path / "新格式"
    root.mkdir()
    for name, fmt in (("1.avif", "AVIF"), ("2.jp2", "JPEG2000"), ("3.tiff", "TIFF")):
        write_image(root / name, pillow_image_fixture(fmt))
    write_image(root / "unsupported.heic", b"not supported")
    provider = FolderContentProvider()
    provider.open(root)
    pages = provider.list_pages()
    assert [page.path for page in pages] == ["1.avif", "2.jp2", "3.tiff"]
    for page in pages:
        content = provider.load_page(page, PageLoadRequest())
        assert decode_image(content.encoded, extension=page.extension).size().toTuple() == (8, 6)


def test_folder_entry_depth_and_file_size_limits(tmp_path, image_bytes, monkeypatch):
    root = tmp_path / "root"
    write_image(root / "1.png", image_bytes())
    write_image(root / "2.png", image_bytes())
    provider = FolderContentProvider()
    monkeypatch.setattr(config, "MAX_FOLDER_ENTRIES", 1)
    with pytest.raises(ResourceLimitError):
        provider.open(root)

    monkeypatch.setattr(config, "MAX_FOLDER_ENTRIES", 10)
    monkeypatch.setattr(config, "MAX_FOLDER_DEPTH", 0)
    write_image(root / "nested" / "3.png", image_bytes())
    with pytest.raises(ResourceLimitError):
        provider.open(root, options=ContentOpenOptions(recursive=True))

    monkeypatch.setattr(config, "MAX_FOLDER_DEPTH", 10)
    provider.open(root)
    monkeypatch.setattr(config, "MAX_ENTRY_UNCOMPRESSED_SIZE", 1)
    with pytest.raises(ResourceLimitError):
        provider.load_page(provider.list_pages()[0], PageLoadRequest())


def test_folder_scan_cancellation_and_deleted_file_recovery(tmp_path, image_bytes):
    root = tmp_path / "root"
    write_image(root / "1.png", image_bytes())
    provider = FolderContentProvider()
    with pytest.raises(ContentScanCancelledError):
        provider.open(root, options=ContentOpenOptions(cancelled=lambda: True))
    provider.open(root)
    page = provider.list_pages()[0]
    (root / "1.png").unlink()
    with pytest.raises(ContentAccessError):
        provider.load_page(page, PageLoadRequest())


def test_symlink_directory_is_not_followed(tmp_path, image_bytes):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    write_image(root / "1.png", image_bytes())
    write_image(outside / "hidden.png", image_bytes())
    link = root / "loop"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    provider = FolderContentProvider()
    provider.open(root, options=ContentOpenOptions(recursive=True))
    assert [page.path for page in provider.list_pages()] == ["1.png"]


def test_inaccessible_child_is_skipped_and_reparse_flag_is_rejected(
    tmp_path, image_bytes, monkeypatch
):
    root = tmp_path / "root"
    blocked = root / "blocked"
    write_image(root / "1.png", image_bytes())
    write_image(blocked / "hidden.png", image_bytes())
    original = Path.iterdir

    def selective_iterdir(path):
        if path == blocked:
            raise PermissionError("fixture")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", selective_iterdir)
    provider = FolderContentProvider()
    provider.open(root, options=ContentOpenOptions(recursive=True))
    assert [page.path for page in provider.list_pages()] == ["1.png"]

    class PlainPath:
        @staticmethod
        def is_symlink():
            return False

    class ReparseStat:
        st_file_attributes = 0x400

    assert _is_reparse_or_symlink(PlainPath(), ReparseStat())


def test_source_switch_during_folder_scan_suppresses_stale_result(
    tmp_path, image_bytes, wait_until, monkeypatch
):
    first, second = tmp_path / "first", tmp_path / "second"
    write_image(first / "first.png", image_bytes("red"))
    write_image(second / "second.png", image_bytes("blue"))
    entered, release = Event(), Event()
    original = FolderContentProvider._discover

    def delayed(root, options):
        if root == first:
            entered.set()
            assert release.wait(5)
        return original(root, options)

    monkeypatch.setattr(FolderContentProvider, "_discover", staticmethod(delayed))
    worker = ImageWorker()
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, first, 0))
        wait_until(entered.is_set)
        worker.submit(LoadRequest(2, 2, second, 0))
        release.set()
        wait_until(lambda: bool(results))
        assert [result.token for result in results] == [2]
        assert results[0].entries[0].name == "second.png"
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)


def test_gui_folder_recursive_thumbnails_double_page_and_resume(tmp_path, image_bytes, wait_until):
    root = tmp_path / "book"
    write_image(root / "1.png", image_bytes("red"))
    write_image(root / "chapter" / "2.png", image_bytes("blue"))
    state_path = tmp_path.parent / f"{tmp_path.name}-folder-state.json"
    store = ReadingStateStore(state_path)
    first = MainWindow(reading_store=store)
    first.show()
    try:
        first.recursive_folders = True
        first.recursive_action.setChecked(True)
        first.open_content(root)
        wait_until(lambda: not first.loading)
        assert [page.path for page in first.entries] == ["1.png", "chapter/2.png"]
        first.cover = False
        first.set_reading(double=True)
        wait_until(lambda: not first.loading)
        assert len(first.viewer._group.childItems()) == 2
        first.thumbnail_dock.show()
        wait_until(lambda: len(first.thumbnails.catalog.cache) > 0)
        first.go_to(1)
        wait_until(lambda: not first.loading)
        first.toggle_current_bookmark()
    finally:
        first.close()
        wait_until(lambda: not first.worker.isRunning() and not first.thumbnails.worker.isRunning())
        first.close()

    restored = MainWindow(reading_store=ReadingStateStore(state_path))
    restored.show()
    try:
        restored.recursive_folders = True
        restored.recursive_action.setChecked(True)
        restored.open_content(root)
        wait_until(lambda: not restored.loading)
        assert restored.current_index == 0  # Double-page spread containing bookmarked page 2.
        assert 0 in restored.thumbnails.catalog.bookmarks
    finally:
        restored.close()
        wait_until(
            lambda: not restored.worker.isRunning() and not restored.thumbnails.worker.isRunning()
        )
        restored.close()


def test_content_registry_selects_directories(tmp_path):
    registry = create_content_registry()
    assert registry.supports(tmp_path)
    assert registry.source_type(tmp_path) is SourceType.FOLDER
    assert isinstance(registry.create(tmp_path), FolderContentProvider)
