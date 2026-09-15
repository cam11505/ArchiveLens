from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QActionGroup, QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from archivelens import __version__
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY, ArchiveProviderRegistry
from archivelens.content.base import PageDescriptor, SourceIdentity, source_identity_for_path
from archivelens.content.factory import create_content_registry
from archivelens.errors import BadPasswordError, PasswordRequiredError
from archivelens.image.reading import spread_indices
from archivelens.image.worker import ImageWorker, LoadRequest, LoadResult
from archivelens.reading_state import (
    ReaderState,
    ReadingRecord,
    ReadingStateStore,
    create_reading_state_store,
)
from archivelens.ui.image_viewer import ImageViewer
from archivelens.ui.password_dialog import PasswordDialog
from archivelens.ui.settings import create_settings, read_bool
from archivelens.ui.thumbnails import ThumbnailSidebar
from archivelens.ui.toolbar import make_action, make_toolbar


class MainWindow(QMainWindow):
    """Open content sources, navigate pages and present only the latest load result."""

    def __init__(
        self,
        *,
        registry: ArchiveProviderRegistry | None = None,
        settings=None,
        reading_store: ReadingStateStore | None = None,
    ) -> None:
        super().__init__()
        self.settings = create_settings() if settings is None else settings
        self.registry = DEFAULT_REGISTRY if registry is None else registry
        self.content_registry = create_content_registry(self.registry)
        self.reading_store = (
            create_reading_state_store(self.settings) if reading_store is None else reading_store
        )
        self.setWindowTitle("ArchiveLens")
        self.resize(1100, 780)
        self.setWindowIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.setAcceptDrops(True)
        self.entries: tuple[PageDescriptor, ...] = ()
        self.current_index = 0
        self.source_path: Path | None = None
        self.source_identity: SourceIdentity | None = None
        self._identity_resolved = False
        self.double_page = read_bool(self.settings, "double_page", False)
        self.rtl = read_bool(self.settings, "rtl", False)
        self.cover = read_bool(self.settings, "cover", True)
        self.recursive_folders = read_bool(self.settings, "recursive_folders", False)
        self.view_mode = "fit_page"
        self.page_zoom_factor = 1.0
        self.page_rotation = 0
        self._applying_reader_state = False
        self.loading = False
        self._token = 0
        self._generation = 0
        self._closing = False
        self._normal_state = Qt.WindowState.WindowNoState
        self._dialogs: list[QMessageBox] = []
        self.viewer = ImageViewer(self)
        self.message = QLabel(f"拖曳 {self.registry.format_label()} 到這裡")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("font-size: 22px; padding: 24px;")
        self.open_button = QPushButton("開啟壓縮檔")
        self.open_button.clicked.connect(self.choose_archive)
        self.open_folder_button = QPushButton("開啟圖片資料夾")
        self.open_folder_button.clicked.connect(self.choose_folder)
        welcome = QWidget()
        layout = QVBoxLayout(welcome)
        layout.addStretch()
        layout.addWidget(self.message)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.open_folder_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.viewer)
        self.setCentralWidget(self.stack)
        self.thumbnails = ThumbnailSidebar(
            self.registry, self, content_registry=self.content_registry
        )
        self.thumbnails.page_selected.connect(self.go_to)
        self.thumbnail_dock = QDockWidget("縮圖", self)
        self.thumbnail_dock.setObjectName("thumbnail_sidebar")
        self.thumbnail_dock.setWidget(self.thumbnails)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.thumbnail_dock)
        self.thumbnail_dock.setVisible(read_bool(self.settings, "thumbnails", False))
        self.thumbnails.worker.finished.connect(self._on_worker_finished)
        self.open_action = make_action(self, "開啟…", self.choose_archive, ["Ctrl+O"])
        self.open_folder_action = make_action(
            self, "開啟資料夾…", self.choose_folder, ["Ctrl+Shift+O"]
        )
        self.previous_action = make_action(
            self, "上一張", lambda: self.navigate(-1), ["PgUp", "Backspace"]
        )
        self.next_action = make_action(
            self, "下一張", lambda: self.navigate(1), ["PgDown", "Space"]
        )
        make_action(self, "向左翻頁", lambda: self.navigate(1 if self.rtl else -1), ["Left"])
        make_action(self, "向右翻頁", lambda: self.navigate(-1 if self.rtl else 1), ["Right"])
        self.first_action = make_action(self, "第一張", lambda: self.go_to(0), ["Home"])
        self.last_action = make_action(
            self, "最後一張", lambda: self.go_to(len(self.entries) - 1), ["End"]
        )
        self.fit_action = make_action(self, "符合視窗", self.fit_current, ["0"])
        self.zoom_out_action = make_action(self, "縮小", lambda: self.zoom_current(False), ["-"])
        self.zoom_in_action = make_action(self, "放大", lambda: self.zoom_current(True), ["+", "="])
        self.actual_action = make_action(self, "100%", self.actual_current, ["1"])
        self.rotate_left_action = make_action(
            self, "向左旋轉", lambda: self.rotate_current(-90), ["Shift+R"]
        )
        self.rotate_right_action = make_action(
            self, "向右旋轉", lambda: self.rotate_current(90), ["R"]
        )
        self.fullscreen_action = make_action(self, "全螢幕", self.toggle_fullscreen, ["F", "F11"])
        self.fullscreen_action.setCheckable(True)
        make_action(self, "離開全螢幕", self.exit_fullscreen, ["Esc"])
        self._viewer_actions = [
            self.zoom_out_action,
            self.zoom_in_action,
            self.fit_action,
            self.actual_action,
            self.rotate_left_action,
            self.rotate_right_action,
        ]
        self.toolbar = make_toolbar(
            self,
            [
                self.open_action,
                self.open_folder_action,
                self.previous_action,
                self.next_action,
                *self._viewer_actions,
                self.fullscreen_action,
            ],
        )
        menu = self.menuBar().addMenu("檔案")
        menu.addAction(self.open_action)
        menu.addAction(self.open_folder_action)
        self.recent_menu = menu.addMenu("最近閱讀")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        menu.addSeparator()
        menu.addAction(make_action(self, "結束", self.close, ["Ctrl+Q"]))
        view_menu = self.menuBar().addMenu("檢視")
        self.single_action = make_action(self, "單頁", lambda: self.set_reading(double=False), [])
        self.double_action = make_action(self, "雙頁", lambda: self.set_reading(double=True), [])
        display_group = QActionGroup(self)
        for action in (self.single_action, self.double_action):
            action.setCheckable(True)
            display_group.addAction(action)
        self.single_action.setChecked(not self.double_page)
        self.double_action.setChecked(self.double_page)
        thumbnail_action = self.thumbnail_dock.toggleViewAction()
        thumbnail_action.setShortcut("T")
        view_menu.addActions(
            [
                self.single_action,
                self.double_action,
                thumbnail_action,
                *self._viewer_actions,
                self.fullscreen_action,
            ]
        )
        reading_menu = self.menuBar().addMenu("閱讀")
        self.ltr_action = make_action(self, "由左至右", lambda: self.set_reading(rtl=False), [])
        self.rtl_action = make_action(self, "由右至左", lambda: self.set_reading(rtl=True), [])
        direction_group = QActionGroup(self)
        for action in (self.ltr_action, self.rtl_action):
            action.setCheckable(True)
            direction_group.addAction(action)
        self.ltr_action.setChecked(not self.rtl)
        self.rtl_action.setChecked(self.rtl)
        self.cover_action = make_action(self, "第一頁為封面", self.toggle_cover, [])
        self.cover_action.setCheckable(True)
        self.cover_action.setChecked(self.cover)
        reading_menu.addActions([self.ltr_action, self.rtl_action, self.cover_action])
        self.recursive_action = make_action(
            self, "資料夾包含子資料夾", self.toggle_recursive_folders, []
        )
        self.recursive_action.setCheckable(True)
        self.recursive_action.setChecked(self.recursive_folders)
        reading_menu.addAction(self.recursive_action)
        reading_menu.addSeparator()
        self.bookmark_action = make_action(
            self, "加入／移除目前頁書籤", self.toggle_current_bookmark, ["Ctrl+B"]
        )
        reading_menu.addAction(self.bookmark_action)
        self.bookmarks_menu = reading_menu.addMenu("頁面書籤")
        self.bookmarks_menu.aboutToShow.connect(self._rebuild_bookmarks_menu)
        navigation_menu = self.menuBar().addMenu("導覽")
        navigation_menu.addActions(
            [self.first_action, self.previous_action, self.next_action, self.last_action]
        )
        help_menu = self.menuBar().addMenu("說明")
        help_menu.addAction(make_action(self, "操作說明", self.show_help, ["F1"]))
        help_menu.addAction(make_action(self, "關於 ArchiveLens", self.show_about, []))
        self.counter = QLabel("0 / 0")
        self.statusBar().addPermanentWidget(self.counter)
        self.viewer.zoom_changed.connect(self._show_zoom)
        self.viewer.view_mode_changed.connect(self._on_view_mode_changed)
        self.worker = ImageWorker(
            self, registry=self.registry, content_registry=self.content_registry
        )
        self.worker.result_ready.connect(self._on_result)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
        geometry = self.settings.value("geometry")
        state = self.settings.value("state")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
                if state is not None:
                    self.restoreState(state)
            except TypeError:
                pass
        self._update_navigation()

    @Slot()
    def choose_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "開啟壓縮檔", "", self.registry.file_dialog_filter()
        )
        if path:
            self.open_archive(path)

    @Slot()
    def choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "開啟圖片資料夾")
        if path:
            self.open_content(path)

    def open_archive(self, path: str | Path) -> None:
        self.open_content(path)

    def open_content(self, path: str | Path) -> None:
        if self._closing:
            return
        self.thumbnails.reset_session()
        self.source_path = Path(path)
        source_type = self.content_registry.source_type(self.source_path)
        self.source_identity = source_identity_for_path(self.source_path, source_type)
        saved = self.reading_store.get(self.source_identity)
        self._identity_resolved = False
        self.entries = ()
        self.current_index = saved.state.page_index if saved else 0
        if saved:
            self._restore_record(saved)
        else:
            self.view_mode = "fit_page"
            self.page_zoom_factor = 1.0
            self.page_rotation = 0
        self._sync_reading_actions()
        self.viewer.reset_view_state()
        for dialog in self._dialogs[:]:
            dialog.close()
        self._generation += 1
        self.setWindowTitle(f"{self.source_path.name} — ArchiveLens")
        self._request_image()

    def set_reading(self, *, double=None, rtl=None):
        if double is not None:
            self.double_page = double
        if rtl is not None:
            self.rtl = rtl
        self._sync_reading_actions()
        if self.entries:
            self.current_index = spread_indices(
                self.current_index, len(self.entries), self.double_page, self.cover
            )[0]
            self._request_image()

    def toggle_cover(self):
        self.cover = self.cover_action.isChecked()
        self.set_reading()

    def toggle_recursive_folders(self) -> None:
        self.recursive_folders = self.recursive_action.isChecked()
        if self.source_path is not None and self.source_path.is_dir():
            self.open_content(self.source_path)

    def _sync_reading_actions(self) -> None:
        self.single_action.setChecked(not self.double_page)
        self.double_action.setChecked(self.double_page)
        self.ltr_action.setChecked(not self.rtl)
        self.rtl_action.setChecked(self.rtl)
        self.cover_action.setChecked(self.cover)

    def navigate(self, offset: int) -> None:
        indices = spread_indices(
            self.current_index, len(self.entries), self.double_page, self.cover
        )
        if indices:
            self.go_to(indices[-1] + 1 if offset > 0 else indices[0] - 1)

    def go_to(self, index: int) -> None:
        if not self.entries or self._closing:
            return
        index = spread_indices(index, len(self.entries), self.double_page, self.cover)[0]
        if index != self.current_index:
            self.current_index = index
            self._request_image()

    def _request_image(self, credentials: ArchiveCredentials | None = None) -> None:
        if self.source_path is None:
            return
        self._token += 1
        self.loading = True
        self.viewer.clear_image()
        self.message.setText("載入中…")
        self.stack.setCurrentIndex(0)
        self.statusBar().showMessage(self.source_path.name)
        self._update_navigation()
        self.worker.submit(
            LoadRequest(
                self._token,
                self._generation,
                self.source_path,
                self.current_index,
                credentials,
                self.double_page,
                self.cover,
                recursive=self.recursive_folders,
            )
        )

    @Slot(object)
    def _on_result(self, result: LoadResult) -> None:
        if self._closing or result.token != self._token:
            return
        self.loading = False
        self.entries = result.entries
        if result.source_identity is not None:
            previous_identity = self.source_identity
            self.source_identity = result.source_identity
            if not self._identity_resolved:
                self._identity_resolved = True
                if previous_identity != result.source_identity:
                    saved = self.reading_store.get(result.source_identity)
                    if saved is not None:
                        self._restore_record(saved)
                        self.current_index = saved.state.page_index
                        self._request_image()
                        return
        self.current_index = result.index if self.entries else 0
        self._update_navigation()
        if self.entries:
            entry = self.entries[self.current_index]
            self.setWindowTitle(f"{entry.name} — {self.source_path.name} — ArchiveLens")
        if result.error_type in (PasswordRequiredError, BadPasswordError):
            self.message.setText(result.error)
            self._ask_password(result.error)
            return
        if result.error:
            self.message.setText(result.error)
            self.stack.setCurrentIndex(0)
            self._show_error(result.error)
        elif result.image is not None:
            revision, credentials = self.worker.credential_snapshot()
            self.thumbnails.set_session(
                self.source_path,
                self._generation,
                self.entries,
                revision,
                credentials,
                recursive=self.recursive_folders,
            )
            self.thumbnails.setCurrentIndex(self.thumbnails.catalog.index(self.current_index))
            self.stack.setCurrentIndex(1)
            self.viewer.set_pages(
                result.pages, self.rtl
            ) if result.pages else self.viewer.set_image(result.image)
            self._apply_reader_view_state()
            self._refresh_bookmark_markers()
            self._save_reading_state()
        self._update_navigation()

    def _ask_password(self, message: str) -> None:
        token = self._token
        dialog = PasswordDialog(message, self)
        self._dialogs.append(dialog)

        def finished(code):
            self._dialogs.remove(dialog)
            if not self._closing and token == self._token:
                if code == dialog.DialogCode.Accepted:
                    self._request_image(ArchiveCredentials(dialog.password.text().encode("utf-8")))
                else:
                    self.worker.cancel_session()
                    self.thumbnails.reset_session()
                    self.message.setText("已取消密碼輸入，可重新開啟壓縮檔。")
            dialog.password.clear()
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.open()

    def _show_error(self, message: str) -> None:
        dialog = QMessageBox(
            QMessageBox.Icon.Warning, "ArchiveLens", message, QMessageBox.StandardButton.Ok, self
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._dialogs.append(dialog)
        dialog.finished.connect(lambda _: self._dialogs.remove(dialog))
        dialog.open()

    def _update_navigation(self) -> None:
        has_previous = bool(self.entries) and self.current_index > 0
        indices = spread_indices(
            self.current_index, len(self.entries), self.double_page, self.cover
        )
        has_next = bool(indices) and indices[-1] < len(self.entries) - 1
        self.previous_action.setEnabled(has_previous)
        self.first_action.setEnabled(has_previous)
        self.next_action.setEnabled(has_next)
        self.last_action.setEnabled(has_next)
        for action in self._viewer_actions:
            action.setEnabled(self.viewer._item is not None and not self.loading)
        self.bookmark_action.setEnabled(bool(self.entries) and not self.loading)
        page = self.current_index + 1 if self.entries else 0
        self.counter.setText(
            f"{page}–{indices[-1] + 1} / {len(self.entries)}"
            if len(indices) > 1
            else f"{page} / {len(self.entries)}"
        )

    @Slot(float)
    def _show_zoom(self, factor: float) -> None:
        if self.entries and self.source_path:
            entry = self.entries[self.current_index]
            size = self.viewer.image_size
            self.statusBar().showMessage(
                f"{entry.path}  |  {size.width()} × {size.height()}  |  "
                f"{entry.extension[1:].upper()}"
                + (
                    f" · {entry.size_bytes / (1024 * 1024):.1f} MB"
                    if entry.size_bytes is not None
                    else ""
                )
                + f"  |  {factor:.0%}  |  {self.source_path.name}"
            )

    def fit_current(self) -> None:
        self.viewer.fit_image()

    def actual_current(self) -> None:
        self.viewer.actual_size()

    def zoom_current(self, zoom_in: bool) -> None:
        (self.viewer.zoom_in if zoom_in else self.viewer.zoom_out)()

    @Slot(str, float)
    def _on_view_mode_changed(self, mode: str, factor: float) -> None:
        if self._applying_reader_state:
            return
        self.view_mode = mode
        self.page_zoom_factor = factor
        self._save_reading_state()

    def rotate_current(self, degrees: int) -> None:
        self.page_rotation = (self.page_rotation + degrees) % 360
        self.viewer.rotate_image(degrees)
        self._save_reading_state()

    def _apply_reader_view_state(self) -> None:
        self._applying_reader_state = True
        try:
            if self.view_mode == "fit_page":
                self.viewer.fit_image()
            elif self.view_mode == "actual":
                self.viewer.actual_size()
            else:
                self.viewer.set_zoom(self.page_zoom_factor)
            if self.page_rotation:
                self.viewer.rotate_image(self.page_rotation)
        finally:
            self._applying_reader_state = False

    def _save_reading_state(self) -> None:
        if not self.entries or self.source_identity is None or self.source_path is None:
            return
        self.reading_store.update(
            self.source_identity,
            self.source_path.name,
            ReaderState(
                page_index=self.current_index,
                page_count=len(self.entries),
                double_page=self.double_page,
                rtl=self.rtl,
                cover=self.cover,
                fit_mode=self.view_mode,
                zoom_factor=self.page_zoom_factor,
                rotation=self.page_rotation,
            ),
        )

    def _restore_record(self, record: ReadingRecord) -> None:
        self.double_page = record.state.double_page
        self.rtl = record.state.rtl
        self.cover = record.state.cover
        self.view_mode = record.state.fit_mode
        self.page_zoom_factor = record.state.zoom_factor
        self.page_rotation = record.state.rotation
        self._sync_reading_actions()

    def toggle_current_bookmark(self) -> None:
        if not self.entries or self.source_identity is None:
            return
        entry = self.entries[self.current_index]
        self.reading_store.toggle_bookmark(self.source_identity, self.current_index, entry.name)
        self._refresh_bookmark_markers()

    def _refresh_bookmark_markers(self) -> None:
        indices = (
            {item.page_index for item in self.reading_store.bookmarks(self.source_identity)}
            if self.source_identity is not None
            else set()
        )
        self.thumbnails.catalog.set_bookmarks(indices)
        self.bookmark_action.setEnabled(bool(self.entries))

    @Slot()
    def _rebuild_bookmarks_menu(self) -> None:
        self.bookmarks_menu.clear()
        bookmarks = (
            self.reading_store.bookmarks(self.source_identity)
            if self.source_identity is not None
            else ()
        )
        if not bookmarks:
            action = self.bookmarks_menu.addAction("沒有書籤")
            action.setEnabled(False)
            return
        for bookmark in bookmarks:
            action = self.bookmarks_menu.addAction(f"{bookmark.page_index + 1}. {bookmark.label}")
            action.triggered.connect(
                lambda checked=False, index=bookmark.page_index: self.go_to(index)
            )

    @Slot()
    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self.reading_store.recent()
        if not recent:
            action = self.recent_menu.addAction("沒有最近閱讀紀錄")
            action.setEnabled(False)
        for record in recent:
            action = self.recent_menu.addAction(self._recent_label(record))
            action.triggered.connect(lambda checked=False, item=record: self._open_recent(item))
        if recent:
            self.recent_menu.addSeparator()
            remove_action = self.recent_menu.addAction("從最近閱讀移除目前項目")
            remove_action.setEnabled(self.source_identity is not None)
            remove_action.triggered.connect(self._remove_current_recent)
            clear_action = self.recent_menu.addAction("清除最近閱讀")
            clear_action.triggered.connect(self.reading_store.clear_recent)

    @staticmethod
    def _recent_label(record: ReadingRecord) -> str:
        return f"{record.display_name} — {record.state.page_index + 1}/{record.state.page_count}"

    def _open_recent(self, record: ReadingRecord) -> None:
        path = Path(record.identity.canonical_path)
        if not path.exists():
            self._show_error("最近閱讀的來源已不存在或無法存取。")
            return
        self.open_content(path)

    def _remove_current_recent(self) -> None:
        if self.source_identity is not None:
            self.reading_store.remove_recent(self.source_identity)

    @Slot()
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self._normal_state = self.windowState()
            self.menuBar().hide()
            self.toolbar.hide()
            self.statusBar().hide()
            self.showFullScreen()
            self.fullscreen_action.setChecked(True)

    @Slot()
    def exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.setWindowState(self._normal_state)
            self.menuBar().show()
            self.toolbar.show()
            self.statusBar().show()
        self.fullscreen_action.setChecked(False)

    @Slot()
    def show_help(self) -> None:
        QMessageBox.information(
            self,
            "操作說明",
            f"Ctrl+O：開啟 {self.registry.format_label()}；Ctrl+Shift+O：開啟資料夾\n"
            "← / →：依閱讀方向翻頁；PageUp / PageDown：上一頁 / 下一頁\n"
            "Backspace / Space：上一張 / 下一張\nHome / End：第一張 / 最後一張\n"
            "+ / = / -：縮放　0：符合視窗　1：100%\n"
            "R / Shift+R：向右 / 向左旋轉\nF / F11：全螢幕　Esc：離開全螢幕\n"
            "Ctrl+滾輪：縮放；一般滾輪：捲動；按住滑鼠左鍵：拖移\n"
            "T：縮圖側欄；檢視／閱讀選單：雙頁、封面與左右閱讀方向\n\n"
            "100% 表示一個圖片像素對應一個螢幕實體像素。\n"
            "閱讀位置、閱讀模式、旋轉與書籤會保存在本機；密碼不會保存。\n"
            "圖片與壓縮檔均不會被修改。",
        )

    @Slot()
    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "關於 ArchiveLens",
            f"ArchiveLens {__version__}\n直接瀏覽 {self.registry.format_label()} 內的圖片。\n\n"
            "本機操作、唯讀、無遙測。\nMIT License · PySide6 / Qt\n"
            "第三方元件授權請參閱隨附 THIRD_PARTY_NOTICES.md。",
        )

    def _drop_path(self, event: QDragEnterEvent | QDropEvent) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if self.content_registry.supports(path):
                return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._drop_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._drop_path(event)
        if path is not None:
            self.open_archive(path)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_reading_state()
        if self.worker.isRunning() or self.thumbnails.worker.isRunning():
            self._closing = True
            self.setEnabled(False)
            self.statusBar().showMessage("正在結束圖片讀取…")
            for dialog in self._dialogs[:]:
                dialog.close()
            self.viewer.clear_image()
            self.thumbnails.shutdown()
            self.worker.stop()
            event.ignore()
        else:
            if not self.isFullScreen():
                self.settings.setValue("geometry", self.saveGeometry())
                self.settings.setValue("state", self.saveState())
            for key, value in (
                ("double_page", self.double_page),
                ("rtl", self.rtl),
                ("cover", self.cover),
                ("recursive_folders", self.recursive_folders),
                ("thumbnails", self.thumbnail_dock.isVisible()),
            ):
                self.settings.setValue(key, value)
            self.settings.sync()
            event.accept()

    @Slot()
    def _on_worker_finished(self) -> None:
        if self._closing and not self.worker.isRunning() and not self.thumbnails.worker.isRunning():
            self.close()
