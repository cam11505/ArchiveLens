"""End-to-end diagnostics shared by source and frozen Windows builds."""

import base64
import hashlib
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from archivelens import __version__
from archivelens.backend_self_test import check_backends
from archivelens.diagnostic_fixtures import animated_gif
from archivelens.image.loader import decode_image
from archivelens.image.media import PageMedia
from archivelens.ui.main_window import MainWindow


def demo_image(fmt: str, label: str, color: str) -> bytes:
    image = QImage(1200, 800, QImage.Format.Format_RGB32)
    image.fill(QColor("#182b40"))
    painter = QPainter(image)
    painter.fillRect(70, 70, 1060, 660, QColor(color))
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Arial", 46))
    painter.drawText(125, 200, "ArchiveLens 1.1")
    painter.setFont(QFont("Arial", 24))
    painter.drawText(125, 285, "Archive image and comic viewer")
    painter.drawText(125, 620, label)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not image.save(buffer, fmt):
        raise RuntimeError(f"Missing image encoder: {fmt}")
    return bytes(data)


class SelfTestRunner(QObject):
    """Drive real widgets asynchronously, write a JSON result and close cleanly."""

    def __init__(self, window: MainWindow, report: Path, screenshot: Path | None) -> None:
        super().__init__(window)
        self.window = window
        self.report = report
        self.screenshot = screenshot
        self.exit_code = 1
        self._temp = TemporaryDirectory(prefix="ArchiveLens-self-test-")
        self.directory = Path(self._temp.name)
        self.archive = self.directory / "旅行照片.cbz"
        self.checks: list[str] = []
        self.started = time.monotonic()
        self.phase = 0
        self._finished = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        try:
            fixtures = [
                ("001.jpg", "JPEG", "#374e88"),
                ("002.jpg", "JPEG", "#286a72"),
                ("003.png", "PNG", "#725440"),
                ("004.webp", "WEBP", "#5f4d87"),
            ]
            with ZipFile(self.archive, "w") as archive:
                for name, fmt, color in reversed(fixtures):
                    archive.writestr(name, demo_image(fmt, name, color))
                archive.writestr("README.txt", "ignored")
            for fmt in ("JPEG", "PNG", "WEBP", "BMP"):
                decode_image(demo_image(fmt, fmt, "#286a72"))
            decode_image(
                base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
            )
            self.checks.append("required_image_decoders")
            self.checks.extend(check_backends(demo_image("PNG", "Backend", "#286a72")))
            self.source_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()
            self.window.activateWindow()
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.archive))])
            drag = QDragEnterEvent(
                QPoint(20, 20),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(self.window, drag)
            assert drag.isAccepted()
            drop = QDropEvent(
                QPointF(20, 20),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(self.window, drop)
            assert drop.isAccepted()
            self.checks.append("drag_drop_event")
            self.timer.start(80)
        except Exception as exc:
            self._finish(str(exc) or type(exc).__name__)

    def _page(self, index: int) -> None:
        assert self.window.current_index == index
        assert self.window.counter.text() == f"{index + 1} / 4"
        assert self.window.stack.currentWidget() is self.window.viewer
        assert self.window.viewer.image_size.width() == 1200

    def _tick(self) -> None:
        try:
            if time.monotonic() - self.started > 30:
                raise TimeoutError("Self-test exceeded 30 seconds")
            if self.window.loading:
                return
            viewer = self.window.viewer
            if self.phase == 0:
                self._page(0)
                self.checks.append("first_image_natural_order")
                QTest.keyClick(self.window, Qt.Key.Key_Right)
            elif self.phase == 1:
                self._page(1)
                QTest.keyClick(self.window, Qt.Key.Key_Right)
            elif self.phase == 2:
                self._page(2)
                QTest.keyClick(self.window, Qt.Key.Key_Left)
            elif self.phase == 3:
                self._page(1)
                self.checks.append("next_next_previous_counter")
                QTest.keyClick(self.window, Qt.Key.Key_1)
                assert abs(viewer.transform().m11() * viewer.devicePixelRatioF() - 1) < 0.001
                QTest.keyClick(self.window, Qt.Key.Key_Equal)
                assert viewer.zoom_factor > 1
                QTest.keyClick(self.window, Qt.Key.Key_R)
                assert viewer.rotation == 90
                QTest.keyClick(self.window, Qt.Key.Key_R, Qt.KeyboardModifier.ShiftModifier)
                assert viewer.rotation == 0
                QTest.keyClick(self.window, Qt.Key.Key_0)
                assert viewer.fit_mode
                self.checks.append("physical_100_zoom_rotate_fit")
                QTest.keyClick(self.window, Qt.Key.Key_F11)
            elif self.phase == 4:
                assert self.window.isFullScreen()
                QTest.keyClick(self.window, Qt.Key.Key_Escape)
            elif self.phase == 5:
                assert not self.window.isFullScreen()
                self.checks.append("fullscreen_escape")
                QTest.keyClick(self.window, Qt.Key.Key_End)
            elif self.phase == 6:
                self._page(3)
                QTest.keyClick(self.window, Qt.Key.Key_Right)
                self._page(3)
                self.checks.append("webp_last_page_boundary")
                self.window.go_to(1)
            elif self.phase == 7:
                self._page(1)
                if self.screenshot:
                    self.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    assert self.window.grab().save(str(self.screenshot))
                assert hashlib.sha256(self.archive.read_bytes()).hexdigest() == self.source_hash
                assert list(self.directory.iterdir()) == [self.archive]
                self.checks.append("source_unchanged_no_image_extraction")
                self.window.set_reading(double=True, rtl=True)
            elif self.phase == 8:
                assert self.window.counter.text() == "2–3 / 4"
                assert viewer._group is not None
                self.checks.append("double_page_rtl")
                self.window.thumbnail_dock.show()
            elif self.phase == 9:
                if not len(self.window.thumbnails.catalog.cache):
                    return
                self.checks.append("lazy_thumbnail_sidebar")
                gif = animated_gif()
                viewer.set_pages((PageMedia(0, decode_image(gif), gif),))
                self.gif_color = viewer._item.pixmap().toImage().pixelColor(0, 0)
            else:
                if viewer._item.pixmap().toImage().pixelColor(0, 0) == self.gif_color:
                    return
                viewer.clear_image()
                assert not viewer._movies
                self.checks.append("animated_gif_playback_cleanup")
                self._finish()
            self.phase += 1
        except Exception as exc:
            self._finish(f"Phase {self.phase}: {str(exc) or type(exc).__name__}")

    def _finish(self, error: str = "") -> None:
        if self._finished:
            return
        self._finished = True
        self.timer.stop()
        self.exit_code = 1 if error else 0
        result = {
            "version": __version__,
            "success": not error,
            "checks": self.checks,
            "error": error,
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
        }
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        self.window.close()

    def cleanup(self) -> None:
        self._temp.cleanup()
