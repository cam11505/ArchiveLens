from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QToolBar


def make_action(
    window: QMainWindow, text: str, callback: Callable, shortcuts: list[str]
) -> QAction:
    action = QAction(text, window)
    action.triggered.connect(callback)
    action.setShortcuts([QKeySequence(key) for key in shortcuts])
    window.addAction(action)
    return action


def make_toolbar(window: QMainWindow, actions: list[QAction]) -> QToolBar:
    toolbar = QToolBar("導覽", window)
    toolbar.setMovable(False)
    for action in actions:
        toolbar.addAction(action)
    window.addToolBar(toolbar)
    return toolbar
