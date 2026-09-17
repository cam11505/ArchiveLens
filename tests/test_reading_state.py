import json
from zipfile import ZipFile

from archivelens.content.base import SourceIdentity, SourceType, source_identity_for_path
from archivelens.reading_state import ReaderState, ReadingStateStore
from archivelens.ui.main_window import MainWindow


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 1
        return f"2026-09-15T00:00:{self.value:03d}+00:00"


def identity(number=1):
    return SourceIdentity(SourceType.ARCHIVE, f"C:/books/{number}.cbz", number, number)


def test_state_round_trip_history_bookmarks_and_secret_exclusion(tmp_path):
    path = tmp_path / "reading-state.json"
    store = ReadingStateStore(path, clock=Clock())
    state = ReaderState(
        page_index=7,
        page_count=20,
        double_page=True,
        rtl=True,
        cover=False,
        fit_mode="custom",
        zoom_factor=1.75,
        rotation=90,
        trim_mode="manual",
        trim_margins=(3, 4, 5, 6),
    )
    store.update(identity(), "Book", state)
    assert store.toggle_bookmark(identity(), 7, "Page 8")
    assert store.toggle_bookmark(identity(), 12, "Page 13")

    restored = ReadingStateStore(path).get(identity())
    assert restored is not None
    assert restored.state.page_index == 7
    assert restored.state.zoom_factor == 1.75
    assert restored.state.rotation == 90
    assert restored.state.trim_mode == "manual"
    assert restored.state.trim_margins == (3, 4, 5, 6)
    assert [item.page_index for item in restored.bookmarks] == [7, 12]
    payload = path.read_text(encoding="utf-8")
    assert "password" not in payload.casefold()
    assert "credential" not in payload.casefold()

    assert not store.toggle_bookmark(identity(), 7, "Page 8")
    assert [item.page_index for item in store.bookmarks(identity())] == [12]
    store.remove_bookmark(identity(), 12)
    assert not store.bookmarks(identity())


def test_history_is_ordered_bounded_and_can_be_removed_or_cleared(tmp_path):
    store = ReadingStateStore(tmp_path / "state.json", clock=Clock())
    for number in range(105):
        store.update(identity(number), f"Book {number}", ReaderState(page_count=1))
    recent = store.recent()
    assert len(recent) == 100
    assert recent[0].display_name == "Book 104"
    assert recent[-1].display_name == "Book 5"
    store.remove_recent(recent[0].identity)
    assert all(item.identity != recent[0].identity for item in store.recent())
    store.clear_recent()
    assert store.recent() == ()


def test_source_identity_detects_replacement_without_hashing_file(tmp_path):
    source = tmp_path / "book.cbz"
    source.write_bytes(b"first")
    first = source_identity_for_path(source, SourceType.ARCHIVE)
    source.write_bytes(b"replacement-is-different")
    second = source_identity_for_path(source, SourceType.ARCHIVE)
    assert first.canonical_path == second.canonical_path
    assert first.storage_key != second.storage_key


def test_corrupt_unknown_and_v0_state_fall_back_or_migrate(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")
    corrupt = ReadingStateStore(path)
    assert corrupt.load_error
    assert corrupt.recent() == ()

    path.write_text(
        json.dumps(
            {
                "version": 0,
                "records": [
                    {
                        "identity": {
                            "source_type": "archive",
                            "canonical_path": "C:/books/old.cbz",
                        },
                        "display_name": "Old",
                        "state": {"current_page": 4, "page_count": 9},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    migrated = ReadingStateStore(path)
    assert not migrated.load_error
    assert migrated.recent()[0].state.page_index == 4

    old_payload = json.loads(path.read_text(encoding="utf-8"))
    old_payload["schema_version"] = 1
    old_payload.pop("version", None)
    path.write_text(json.dumps(old_payload), encoding="utf-8")
    version_one = ReadingStateStore(path)
    assert not version_one.load_error
    assert version_one.recent()[0].state.trim_mode == "off"

    path.write_text(json.dumps({"schema_version": 999, "records": []}), encoding="utf-8")
    unknown = ReadingStateStore(path)
    assert unknown.load_error
    assert unknown.recent() == ()


def test_gui_resume_reader_state_and_bookmark_marker(tmp_path, image_bytes, qapp, wait_until):
    source = tmp_path / "resume.cbz"
    with ZipFile(source, "w") as archive:
        for number in range(6):
            archive.writestr(f"{number}.png", image_bytes("blue"))
    state_path = tmp_path.parent / f"{tmp_path.name}-state" / "state.json"
    first = MainWindow(reading_store=ReadingStateStore(state_path))
    first.show()
    try:
        first.open_content(source)
        wait_until(lambda: not first.loading)
        first.go_to(3)
        wait_until(lambda: not first.loading)
        first.set_reading(double=True, rtl=True)
        wait_until(lambda: not first.loading)
        first.actual_current()
        first.rotate_current(90)
        first.toggle_current_bookmark()
        bookmarked_index = first.current_index
        assert bookmarked_index in first.thumbnails.catalog.bookmarks
    finally:
        first.close()
        wait_until(lambda: not first.worker.isRunning() and not first.thumbnails.worker.isRunning())
        first.close()

    restored = MainWindow(reading_store=ReadingStateStore(state_path))
    restored.show()
    try:
        restored.open_content(source)
        wait_until(lambda: not restored.loading)
        assert restored.current_index == bookmarked_index
        assert restored.double_page and restored.rtl
        assert restored.view_mode == "actual"
        assert restored.viewer.rotation == 90
        assert bookmarked_index in restored.thumbnails.catalog.bookmarks
        restored._rebuild_bookmarks_menu()
        assert any("★" not in action.text() for action in restored.bookmarks_menu.actions())
    finally:
        restored.close()
        wait_until(
            lambda: not restored.worker.isRunning() and not restored.thumbnails.worker.isRunning()
        )
        restored.close()


def test_missing_recent_source_is_recoverable(tmp_path, qapp, monkeypatch):
    store = ReadingStateStore(tmp_path / "state.json", clock=Clock())
    missing = SourceIdentity(SourceType.ARCHIVE, str(tmp_path / "missing.cbz"), 1, 1)
    store.update(missing, "Missing", ReaderState(page_count=3))
    window = MainWindow(reading_store=store)
    errors = []
    monkeypatch.setattr(window, "_show_error", errors.append)
    try:
        window._open_recent(store.recent()[0])
        assert errors == ["最近閱讀的來源已不存在或無法存取。"]
    finally:
        window.close()
