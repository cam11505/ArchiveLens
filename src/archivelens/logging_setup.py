import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from archivelens.config import LOG_BACKUP_COUNT, LOG_MAX_BYTES


def configure_logging(debug: bool = False, directory: Path | None = None) -> Path | None:
    """Keep diagnostics local and bounded; tolerate read-only application directories."""
    logger = logging.getLogger("archivelens")
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)
    logger.propagate = False
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    log_path = None
    try:
        base = (
            directory
            or Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation
                )
            )
            / "logs"
        )
        base.mkdir(parents=True, exist_ok=True)
        log_path = base / "ArchiveLens.log"
        handler = RotatingFileHandler(
            log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except OSError:
        logger.warning("Cannot create a local diagnostic log")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return log_path
