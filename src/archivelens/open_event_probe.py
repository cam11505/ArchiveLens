"""Opt-in packaged Finder qualification using the production source-open path."""

import json
from pathlib import Path

from PySide6.QtCore import QTimer


class OpenEventProbe:
    def __init__(self, app, window, report: Path):
        self.app = app
        self.window = window
        self.report = report
        self.events = []
        self.recorded = None
        app.set_open_source_handler(self.open_source)
        self.timer = QTimer(window)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        QTimer.singleShot(60000, app.quit)

    def open_source(self, path: Path) -> None:
        self.events.append({"path": str(path), "loaded": False})
        self.window.open_content(path)

    def poll(self) -> None:
        if self.report.with_suffix(".stop").exists():
            self.app.quit()
            return
        if not self.events or self.window.loading or not self.window.entries:
            return
        current = self.events[-1]
        if self.window.source_path != Path(current["path"]):
            return
        current["loaded"] = True
        current["pages"] = len(self.window.entries)
        state = json.dumps({"events": self.events}, ensure_ascii=False)
        if state != self.recorded:
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.report.write_text(state, encoding="utf-8")
            self.recorded = state
