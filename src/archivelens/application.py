"""Application-level source opening shared by every desktop entry point."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication


class SourceOpenRouter:
    """Queue cold-start requests and dispatch warm requests through one handler."""

    def __init__(self) -> None:
        self._handler: Callable[[Path], None] | None = None
        self._pending: list[Path] = []

    def set_handler(self, handler: Callable[[Path], None]) -> None:
        self._handler = handler
        pending, self._pending = self._pending, []
        for path in pending:
            handler(path)

    def open_source(self, path: str | Path) -> None:
        source = Path(path)
        if self._handler is None:
            self._pending.append(source)
        else:
            self._handler(source)


class ArchiveLensApplication(QApplication):
    """Qt application that routes Finder and other opens to ``open_source``."""

    def __init__(self, arguments) -> None:
        self._source_router = SourceOpenRouter()
        super().__init__(arguments)

    def set_open_source_handler(self, handler: Callable[[Path], None]) -> None:
        self._source_router.set_handler(handler)

    def open_source(self, path: str | Path) -> None:
        self._source_router.open_source(path)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.FileOpen:
            file_event = event
            if isinstance(file_event, QFileOpenEvent) and file_event.file():
                self.open_source(file_event.file())
                event.accept()
                return True
        return super().event(event)
