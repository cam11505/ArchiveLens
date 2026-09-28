"""Development-only integrated reader regressions; never an official RC gate."""

import hashlib
from threading import Event
from zipfile import ZipFile

import pytest

from archivelens.content.base import SourceType, source_identity_for_path
from archivelens.content.pdf_provider import PdfContentProvider
from archivelens.diagnostic_fixtures import write_pdf_fixture
from archivelens.image.trim import TrimMargins
from archivelens.image.worker import ImageWorker, LoadRequest
from archivelens.reading_state import ReadingStateStore
from archivelens.ui.main_window import MainWindow


def snapshot(directory):
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def sources(directory, image_bytes):
    directory.mkdir()
    archive = directory / "閱讀.cbz"
    folder = directory / "資料夾"
    folder.mkdir()
    with ZipFile(archive, "w") as target:
        for index in range(4):
            content = image_bytes("blue", width=100, height=80)
            target.writestr(f"{index}.png", content)
            (folder / f"{index}.png").write_bytes(content)
    pdf = directory / "閱讀.pdf"
    write_pdf_fixture(pdf, pages=4)
    return {"archive": archive, "folder": folder, "pdf": pdf}


@pytest.mark.parametrize("kind", ["archive", "folder", "pdf"])
def test_reader_state_round_trip_across_source_types(tmp_path, image_bytes, qapp, wait_until, kind):
    root = tmp_path / "sources"
    books = sources(root, image_bytes)
    before = snapshot(root)
    state = tmp_path / "appdata/reading-state.json"
    errors = []
    window = MainWindow(reading_store=ReadingStateStore(state))
    window._show_error = errors.append
    window.show()
    try:
        window.open_content(books[kind])
        wait_until(lambda: not window.loading)
        assert len(window.entries) == 4
        window.set_reading(double=True, rtl=True)
        wait_until(lambda: not window.loading)
        window.go_to(1)
        wait_until(lambda: not window.loading)
        window.fit_width_current()
        window.set_trim_mode("manual", TrimMargins(5, 5, 5, 5))
        wait_until(lambda: not window.loading)
        window.toggle_current_bookmark()
        index = window.current_index
        # Switching provider types must not overwrite the original book's state.
        other = "archive" if kind == "pdf" else "pdf"
        window.open_content(books[other])
        wait_until(lambda: not window.loading)
        window.open_content(books[kind])
        wait_until(lambda: not window.loading)
        assert window.current_index == index
        assert window.double_page and window.rtl
        assert window.view_mode == "fit_width"
        assert window.trim_mode == "manual"
        assert window.trim_margins.as_tuple() == (5, 5, 5, 5)
        assert index in window.thumbnails.catalog.bookmarks
        assert not errors
    finally:
        window.close()
        wait_until(
            lambda: not window.worker.isRunning() and not window.thumbnails.worker.isRunning()
        )
        window.close()
    record = ReadingStateStore(state).get(window.source_identity)
    assert record is not None and record.state.page_index == index
    assert "password" not in state.read_text(encoding="utf-8").casefold()
    assert snapshot(root) == before


def test_active_pdf_render_switches_to_latest_provider_without_stale_result(
    tmp_path, image_bytes, qapp, wait_until, monkeypatch
):
    root = tmp_path / "sources"
    books = sources(root, image_bytes)
    before = snapshot(root)
    entered, release = Event(), Event()
    original = PdfContentProvider._render_page

    def delayed(provider, index, size):
        entered.set()
        assert release.wait(5)
        return original(provider, index, size)

    monkeypatch.setattr(PdfContentProvider, "_render_page", delayed)
    worker = ImageWorker()
    results = []
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, books["pdf"], 0, render_size=(320, 240)))
        wait_until(entered.is_set)
        worker.submit(LoadRequest(2, 2, books["folder"], 1))
        worker.submit(LoadRequest(3, 3, books["archive"], 2))
        release.set()
        wait_until(lambda: bool(results))
        assert [result.token for result in results] == [3]
        assert results[0].error_type is None and results[0].index == 2
        assert results[0].source_identity == source_identity_for_path(
            books["archive"], SourceType.ARCHIVE
        )
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)
    assert snapshot(root) == before
