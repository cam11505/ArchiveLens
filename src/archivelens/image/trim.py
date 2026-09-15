from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage

from archivelens.config import AUTO_TRIM_MAX_DIMENSION, AUTO_TRIM_MAX_FRACTION


@dataclass(frozen=True, slots=True)
class TrimMargins:
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    def normalized(self) -> "TrimMargins":
        return TrimMargins(*(max(0, min(int(value), 40)) for value in self.as_tuple()))

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom


def trim_rect(image: QImage, mode: str, margins: TrimMargins | None = None) -> QRect:
    full = image.rect()
    if image.isNull() or mode == "off":
        return full
    if mode == "manual":
        return _manual_rect(image, (margins or TrimMargins()).normalized())
    if mode == "auto":
        return _auto_rect(image)
    return full


def _manual_rect(image: QImage, margins: TrimMargins) -> QRect:
    width, height = image.width(), image.height()
    left = round(width * margins.left / 100)
    top = round(height * margins.top / 100)
    right = round(width * margins.right / 100)
    bottom = round(height * margins.bottom / 100)
    if left + right >= width or top + bottom >= height:
        return image.rect()
    return QRect(left, top, width - left - right, height - top - bottom)


def _auto_rect(image: QImage) -> QRect:
    scale = min(1.0, AUTO_TRIM_MAX_DIMENSION / max(image.width(), image.height()))
    sample = image.scaled(
        max(1, round(image.width() * scale)),
        max(1, round(image.height() * scale)),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    ).convertToFormat(QImage.Format.Format_RGB32)
    corners = [
        sample.pixelColor(0, 0),
        sample.pixelColor(sample.width() - 1, 0),
        sample.pixelColor(0, sample.height() - 1),
        sample.pixelColor(sample.width() - 1, sample.height() - 1),
    ]
    average = tuple(
        round(sum(color.getRgb()[channel] for color in corners) / 4) for channel in range(3)
    )
    if not (max(average) <= 32 or min(average) >= 223):
        return image.rect()
    if any(
        abs(color.getRgb()[channel] - average[channel]) > 12
        for color in corners
        for channel in range(3)
    ):
        return image.rect()

    width, height = sample.width(), sample.height()
    max_x = int(width * AUTO_TRIM_MAX_FRACTION)
    max_y = int(height * AUTO_TRIM_MAX_FRACTION)

    def background(x: int, y: int) -> bool:
        rgb = sample.pixelColor(x, y).getRgb()
        return all(abs(rgb[channel] - average[channel]) <= 18 for channel in range(3))

    def clear_row(y: int) -> bool:
        return sum(background(x, y) for x in range(width)) >= width * 0.995

    def clear_column(x: int) -> bool:
        return sum(background(x, y) for y in range(height)) >= height * 0.995

    left = next((x for x in range(max_x + 1) if not clear_column(x)), 0)
    right = next((x for x in range(max_x + 1) if not clear_column(width - 1 - x)), 0)
    top = next((y for y in range(max_y + 1) if not clear_row(y)), 0)
    bottom = next((y for y in range(max_y + 1) if not clear_row(height - 1 - y)), 0)
    # One sample pixel is commonly antialiasing/noise; avoid unstable micro-crops.
    left = left if left >= 2 else 0
    right = right if right >= 2 else 0
    top = top if top >= 2 else 0
    bottom = bottom if bottom >= 2 else 0
    if not any((left, top, right, bottom)):
        return image.rect()
    sampled = QRect(left, top, width - left - right, height - top - bottom)
    if sampled.width() < width * 0.6 or sampled.height() < height * 0.6:
        return image.rect()
    x_ratio = image.width() / width
    y_ratio = image.height() / height
    x = max(0, int(sampled.x() * x_ratio))
    y = max(0, int(sampled.y() * y_ratio))
    right_edge = min(image.width(), round((sampled.x() + sampled.width()) * x_ratio))
    bottom_edge = min(image.height(), round((sampled.y() + sampled.height()) * y_ratio))
    return QRect(x, y, right_edge - x, bottom_edge - y)
