from PySide6.QtCore import QSettings


def create_settings():
    return QSettings("ArchiveLens", "ArchiveLens")


def read_bool(settings, key, default):
    value = settings.value(key, default)
    if isinstance(value, bool):
        return value
    if value in ("true", "false"):
        return value == "true"
    return default
