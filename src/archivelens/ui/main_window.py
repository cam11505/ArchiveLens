from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
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
from archivelens.archive.base import ArchiveEntry
from archivelens.image.worker import ImageWorker, LoadRequest, LoadResult
from archivelens.ui.image_viewer import ImageViewer
from archivelens.ui.toolbar import make_action, make_toolbar
from archivelens.utils.file_types import ARCHIVE_EXTENSIONS


class MainWindow(QMainWindow):
    """Open archives, navigate images and present only the latest load result."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ArchiveLens")
        self.resize(1100, 780)
        self.setWindowIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.setAcceptDrops(True)
        self.entries: tuple[ArchiveEntry, ...] = ()
        self.current_index = 0
        self.archive_path: Path | None = None
        self.loading = False
        self._token = 0
        self._generation = 0
        self._closing = False
        self._normal_state = Qt.WindowState.WindowNoState
        self._dialogs: list[QMessageBox] = []
        self.viewer = ImageViewer(self)
        self.message = QLabel("拖曳 ZIP / CBZ 到這裡")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("font-size: 22px; padding: 24px;")
        self.open_button = QPushButton("開啟壓縮檔")
        self.open_button.clicked.connect(self.choose_archive)
        welcome = QWidget()
        layout = QVBoxLayout(welcome)
        layout.addStretch()
        layout.addWidget(self.message)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.addWidget(welcome)
        self.stack.addWidget(self.viewer)
        self.setCentralWidget(self.stack)
        self.open_action = make_action(self, "開啟…", self.choose_archive, ["Ctrl+O"])
        self.previous_action = make_action(
            self, "上一張", lambda: self.navigate(-1), ["Left", "PgUp", "Backspace"]
        )
        self.next_action = make_action(
            self, "下一張", lambda: self.navigate(1), ["Right", "PgDown", "Space"]
        )
        self.first_action = make_action(self, "第一張", lambda: self.go_to(0), ["Home"])
        self.last_action = make_action(
            self, "最後一張", lambda: self.go_to(len(self.entries) - 1), ["End"]
        )
        self.fit_action = make_action(self, "符合視窗", self.viewer.fit_image, ["0"])
        self.zoom_out_action = make_action(self, "縮小", self.viewer.zoom_out, ["-"])
        self.zoom_in_action = make_action(self, "放大", self.viewer.zoom_in, ["+", "="])
        self.actual_action = make_action(self, "100%", self.viewer.actual_size, ["1"])
        self.rotate_left_action = make_action(
            self, "向左旋轉", lambda: self.viewer.rotate_image(-90), ["Shift+R"]
        )
        self.rotate_right_action = make_action(
            self, "向右旋轉", lambda: self.viewer.rotate_image(90), ["R"]
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
                self.previous_action,
                self.next_action,
                *self._viewer_actions,
                self.fullscreen_action,
            ],
        )
        menu = self.menuBar().addMenu("檔案")
        menu.addAction(self.open_action)
        menu.addSeparator()
        menu.addAction(make_action(self, "結束", self.close, ["Ctrl+Q"]))
        view_menu = self.menuBar().addMenu("檢視")
        view_menu.addActions([*self._viewer_actions, self.fullscreen_action])
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
        self.worker = ImageWorker(self)
        self.worker.result_ready.connect(self._on_result)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
        self._update_navigation()

    @Slot()
    def choose_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "開啟壓縮檔", "", "圖片壓縮檔 (*.zip *.cbz *.ZIP *.CBZ)"
        )
        if path:
            self.open_archive(path)

    def open_archive(self, path: str | Path) -> None:
        if self._closing:
            return
        self.archive_path = Path(path)
        self.entries = ()
        self.current_index = 0
        self.viewer.reset_view_state()
        for dialog in self._dialogs[:]:
            dialog.close()
        self._generation += 1
        self.setWindowTitle(f"{self.archive_path.name} — ArchiveLens")
        self._request_image()

    def navigate(self, offset: int) -> None:
        self.go_to(self.current_index + offset)

    def go_to(self, index: int) -> None:
        if not self.entries or self._closing:
            return
        index = max(0, min(index, len(self.entries) - 1))
        if index != self.current_index:
            self.current_index = index
            self._request_image()

    def _request_image(self) -> None:
        if self.archive_path is None:
            return
        self._token += 1
        self.loading = True
        self.viewer.clear_image()
        self.message.setText("載入中…")
        self.stack.setCurrentIndex(0)
        self.statusBar().showMessage(self.archive_path.name)
        self._update_navigation()
        self.worker.submit(
            LoadRequest(self._token, self._generation, self.archive_path, self.current_index)
        )

    @Slot(object)
    def _on_result(self, result: LoadResult) -> None:
        if self._closing or result.token != self._token:
            return
        self.loading = False
        self.entries = result.entries
        self.current_index = result.index if self.entries else 0
        self._update_navigation()
        if self.entries:
            entry = self.entries[self.current_index]
            self.setWindowTitle(f"{entry.name} — {self.archive_path.name} — ArchiveLens")
        if result.error:
            self.message.setText(result.error)
            self.stack.setCurrentIndex(0)
            self._show_error(result.error)
        elif result.image is not None:
            self.stack.setCurrentIndex(1)
            self.viewer.set_image(result.image)
        self._update_navigation()

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
        has_next = bool(self.entries) and self.current_index < len(self.entries) - 1
        self.previous_action.setEnabled(has_previous)
        self.first_action.setEnabled(has_previous)
        self.next_action.setEnabled(has_next)
        self.last_action.setEnabled(has_next)
        for action in self._viewer_actions:
            action.setEnabled(self.viewer._item is not None and not self.loading)
        page = self.current_index + 1 if self.entries else 0
        self.counter.setText(f"{page} / {len(self.entries)}")

    @Slot(float)
    def _show_zoom(self, factor: float) -> None:
        if self.entries and self.archive_path:
            entry = self.entries[self.current_index]
            size = self.viewer.image_size
            self.statusBar().showMessage(
                f"{entry.path}  |  {size.width()} × {size.height()}  |  "
                f"{entry.extension[1:].upper()} · {entry.uncompressed_size / (1024 * 1024):.1f} MB"
                f"  |  {factor:.0%}  |  {self.archive_path.name}"
            )

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
            "Ctrl+O：開啟 ZIP / CBZ\n"
            "← / →、PageUp / PageDown：上一張 / 下一張\n"
            "Backspace / Space：上一張 / 下一張\nHome / End：第一張 / 最後一張\n"
            "+ / = / -：縮放　0：符合視窗　1：100%\n"
            "R / Shift+R：向右 / 向左旋轉\nF / F11：全螢幕　Esc：離開全螢幕\n"
            "Ctrl+滾輪：縮放；一般滾輪：捲動；按住滑鼠左鍵：拖移\n\n"
            "100% 表示一個圖片像素對應一個螢幕實體像素。\n"
            "翻頁保留縮放模式，旋轉會重設。圖片與壓縮檔均不會被修改。",
        )

    @Slot()
    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "關於 ArchiveLens",
            f"ArchiveLens {__version__}\n直接瀏覽 ZIP / CBZ 內的圖片。\n\n"
            "本機操作、唯讀、無遙測。\nMIT License · PySide6 / Qt\n"
            "第三方元件授權請參閱隨附 THIRD_PARTY_NOTICES.md。",
        )

    @staticmethod
    def _drop_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.casefold() in ARCHIVE_EXTENSIONS:
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
        if self.worker.isRunning():
            self._closing = True
            self.setEnabled(False)
            self.statusBar().showMessage("正在結束圖片讀取…")
            self.worker.stop()
            event.ignore()
        else:
            event.accept()

    @Slot()
    def _on_worker_finished(self) -> None:
        if self._closing:
            self.close()
