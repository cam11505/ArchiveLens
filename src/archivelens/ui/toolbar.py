from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QToolBar


def make_action(
    window: QMainWindow,
    text: str,
    callback: Callable,
    shortcuts: list[str],
    *,
    standard_key: QKeySequence.StandardKey | None = None,
    menu_role: QAction.MenuRole = QAction.MenuRole.NoRole,
) -> QAction:
    action = QAction(text, window)
    action.triggered.connect(callback)
    keys = QKeySequence.keyBindings(standard_key) if standard_key is not None else []
    for key in shortcuts:
        sequence = QKeySequence(key)
        if sequence not in keys:
            keys.append(sequence)
    action.setShortcuts(keys)
    action.setMenuRole(menu_role)
    window.addAction(action)
    return action


def make_toolbar(window: QMainWindow, actions: list[QAction]) -> QToolBar:
    toolbar = QToolBar("導覽", window)
    toolbar.setObjectName("navigation_toolbar")
    toolbar.setMovable(False)
    for action in actions:
        toolbar.addAction(action)
    window.addToolBar(toolbar)
    return toolbar
