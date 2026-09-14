from dataclasses import dataclass, field

from PySide6.QtGui import QImage


@dataclass(frozen=True)
class PageMedia:
    index: int
    image: QImage = field(repr=False)
    animation: bytes = field(default=b"", repr=False)
