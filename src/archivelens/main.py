import argparse
import sys
from pathlib import Path

from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import QApplication

from archivelens import __version__
from archivelens.config import IMAGE_ALLOCATION_LIMIT_MB
from archivelens.logging_setup import configure_logging
from archivelens.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description="ArchiveLens ZIP / CBZ image viewer")
    parser.add_argument("archive", nargs="?")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--version", action="version", version=f"ArchiveLens {__version__}")
    parser.add_argument("--self-test-report", type=Path, help="Run GUI diagnostics and write JSON")
    parser.add_argument("--self-test-screenshot", type=Path, help="Save the diagnostic window")
    args = parser.parse_args()
    QImageReader.setAllocationLimit(IMAGE_ALLOCATION_LIMIT_MB)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ArchiveLens")
    app.setOrganizationName("ArchiveLens")
    app.setApplicationVersion(__version__)
    configure_logging(
        args.debug, args.self_test_report.parent / "logs" if args.self_test_report else None
    )
    settings = None
    reading_store = None
    if args.self_test_report:
        from PySide6.QtCore import QSettings

        settings = QSettings(
            str(args.self_test_report.with_suffix(".ini")), QSettings.Format.IniFormat
        )
        settings.clear()
        from archivelens.reading_state import ReadingStateStore

        reading_store = ReadingStateStore(args.self_test_report.with_suffix(".reading-state.json"))
    window = MainWindow(settings=settings, reading_store=reading_store)
    window.show()
    if args.self_test_report:
        from PySide6.QtCore import QTimer

        from archivelens.self_test import SelfTestRunner

        runner = SelfTestRunner(window, args.self_test_report, args.self_test_screenshot)
        QTimer.singleShot(0, runner.start)
        app.exec()
        runner.cleanup()
        return runner.exit_code
    if args.archive:
        window.open_archive(args.archive)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
