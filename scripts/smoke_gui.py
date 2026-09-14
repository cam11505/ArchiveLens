"""Exercise the native Qt window with synthetic images and save a review screenshot."""

import sys
from pathlib import Path
from zipfile import ZipFile

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QImageReader, QPainter
from PySide6.QtWidgets import QApplication

from archivelens.config import IMAGE_ALLOCATION_LIMIT_MB
from archivelens.ui.main_window import MainWindow


def demo_image(label: str, color: str) -> bytes:
    image = QImage(1200, 800, QImage.Format.Format_RGB32)
    image.fill(QColor("#182b40"))
    painter = QPainter(image)
    painter.fillRect(70, 70, 1060, 660, QColor(color))
    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 46))
    painter.drawText(125, 200, "ArchiveLens")
    painter.setFont(QFont("Segoe UI", 24))
    painter.drawText(125, 280, "In-memory archive image viewer")
    painter.drawText(125, 620, label)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(data)


def main() -> int:
    output = Path(__file__).resolve().parents[1] / "outputs" / "smoke"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    QImageReader.setAllocationLimit(IMAGE_ALLOCATION_LIMIT_MB)
    archive = output / "ArchiveLens-demo.cbz"
    with ZipFile(archive, "w") as target:
        for number, color in [(10, "#725440"), (2, "#286a72"), (1, "#374e88")]:
            target.writestr(f"{number}.png", demo_image(f"Page {number}", color))
    window = MainWindow()
    window.show()
    window.open_archive(archive)
    state = {"phase": 0, "code": 1}
    timer = QTimer()

    def check() -> None:
        if window.loading:
            return
        if window.stack.currentWidget() is not window.viewer:
            timer.stop()
            window.close()
            return
        if state["phase"] == 0:
            state["phase"] = 1
            window.next_action.trigger()
        else:
            timer.stop()
            assert window.counter.text() == "2 / 3"
            assert window.grab().save(str(output / "ArchiveLens-window.png"))
            state["code"] = 0
            print(f"Native Qt smoke passed; screenshot: {output / 'ArchiveLens-window.png'}")
            window.close()

    timer.timeout.connect(check)
    timer.start(150)
    QTimer.singleShot(15000, window.close)
    app.exec()
    return state["code"]


if __name__ == "__main__":
    raise SystemExit(main())
