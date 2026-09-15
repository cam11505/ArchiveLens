from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

from archivelens.image.trim import TrimMargins, trim_rect


def bordered_image(background: str, content: str = "red") -> QImage:
    image = QImage(200, 120, QImage.Format.Format_RGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    painter.fillRect(QRect(20, 10, 160, 100), QColor(content))
    painter.end()
    return image


def test_auto_trim_detects_obvious_light_and_dark_borders():
    expected = QRect(20, 10, 160, 100)
    assert trim_rect(bordered_image("white"), "auto") == expected
    assert trim_rect(bordered_image("black", "white"), "auto") == expected


def test_auto_trim_conservatively_keeps_artwork_and_is_sample_bounded():
    artwork = QImage(200, 120, QImage.Format.Format_RGB32)
    for y in range(artwork.height()):
        for x in range(artwork.width()):
            artwork.setPixelColor(x, y, QColor(x % 256, y % 256, (x + y) % 256))
    assert trim_rect(artwork, "auto") == artwork.rect()

    large = bordered_image("white").scaled(2000, 1200)
    result = trim_rect(large, "auto")
    assert result.width() < large.width()
    assert result.height() < large.height()


def test_manual_trim_is_per_edge_bounded_and_predictable():
    image = QImage(1000, 500, QImage.Format.Format_RGB32)
    assert trim_rect(image, "manual", TrimMargins(10, 20, 30, 5)) == QRect(
        100, 100, 600, 375
    )
    assert TrimMargins(-1, 99, 5, 6).normalized() == TrimMargins(0, 40, 5, 6)
    assert trim_rect(image, "invalid") == image.rect()
