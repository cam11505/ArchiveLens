import pytest
from PySide6.QtGui import QAction, QFileOpenEvent, QKeySequence
from PySide6.QtWidgets import QApplication

from archivelens.application import SourceOpenRouter
from archivelens.macos_documents import document_types, verify_document_types
from archivelens.ui.main_window import MainWindow


def test_native_menu_roles_and_standard_shortcuts(qapp):
    window = MainWindow()
    try:
        assert window.about_action.menuRole() == QAction.MenuRole.AboutRole
        assert window.quit_action.menuRole() == QAction.MenuRole.QuitRole
        assert window.open_action.shortcuts() == QKeySequence.keyBindings(
            QKeySequence.StandardKey.Open
        )
        for sequence in QKeySequence.keyBindings(QKeySequence.StandardKey.FullScreen):
            assert sequence in window.fullscreen_action.shortcuts()
        assert QKeySequence("Ctrl+B") in window.bookmark_action.shortcuts()
        assert QKeySequence("Ctrl+Shift+O") in window.open_folder_action.shortcuts()
        assert window.next_action.menuRole() == QAction.MenuRole.NoRole
    finally:
        window.close()


def test_preferences_role_uses_existing_settings(qapp, monkeypatch):
    monkeypatch.setattr("archivelens.ui.main_window.sys.platform", "darwin")
    window = MainWindow()
    try:
        assert window.preferences_action.menuRole() == QAction.MenuRole.PreferencesRole
        assert window.preferences_action.shortcuts() == QKeySequence.keyBindings(
            QKeySequence.StandardKey.Preferences
        )
    finally:
        window.close()


def test_finder_cold_and_warm_events_share_open_boundary(qapp, tmp_path):
    router = SourceOpenRouter()
    monkey_router = qapp._source_router
    qapp._source_router = router
    opened = []
    cold = tmp_path / "冷啟動.cbz"
    warm = tmp_path / "已開啟.pdf"
    try:
        assert QApplication.sendEvent(qapp, QFileOpenEvent(str(cold)))
        assert opened == []
        qapp.set_open_source_handler(opened.append)
        assert QApplication.sendEvent(qapp, QFileOpenEvent(str(warm)))
        assert opened == [cold, warm]
    finally:
        qapp._source_router = monkey_router


def test_finder_declares_only_alternate_readers():
    plist = {"CFBundleDocumentTypes": document_types()}
    verify_document_types(plist)
    assert [item["CFBundleTypeExtensions"] for item in document_types()] == [
        ["cbz"],
        ["cbr"],
        ["zip"],
        ["rar"],
        ["7z"],
        ["pdf"],
    ]
    assert all(item["LSHandlerRank"] == "Alternate" for item in document_types())


@pytest.mark.parametrize("extension", ["png", "jpg", "*", "folder"])
def test_finder_rejects_out_of_scope_types(extension):
    types = document_types()
    types.append({"CFBundleTypeExtensions": [extension]})
    with pytest.raises(ValueError, match="allowlist"):
        verify_document_types({"CFBundleDocumentTypes": types})
