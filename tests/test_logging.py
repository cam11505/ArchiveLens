import logging

from archivelens.logging_setup import configure_logging


def test_debug_log_and_unwritable_directory(tmp_path):
    path = configure_logging(True, tmp_path / "logs")
    logger = logging.getLogger("archivelens.test")
    logger.debug("diagnostic record")
    assert "diagnostic record" in path.read_text(encoding="utf-8")
    configure_logging(False, tmp_path / "logs")
    logger.debug("must not be logged")
    assert "must not be logged" not in path.read_text(encoding="utf-8")
    bad_directory = tmp_path / "file"
    bad_directory.write_text("not a directory")
    assert configure_logging(False, bad_directory) is None
