from zipfile import ZipFile

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest

from archivelens.image.reading import spread_indices
from archivelens.ui.main_window import MainWindow


def animated_gif():
    header = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\x00\x00\x00\xff\x00"
    loop = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"

    def frame(pixel):
        return (
            b"\x21\xf9\x04\x00\x05\x00\x00\x00"
            + b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            + bytes([pixel, 1])
            + b"\x00"
        )

    return header + loop + frame(0x44) + frame(0x4C) + b"\x3b"


@pytest.mark.parametrize("count", range(1, 8))
@pytest.mark.parametrize("cover", [True, False])
def test_spread_partition(count, cover):
    pages = []
    index = 0
    while index < count:
        spread = spread_indices(index, count, True, cover)
        pages.extend(spread)
        assert all(spread_indices(i, count, True, cover) == spread for i in spread)
        index = spread[-1] + 1
    assert pages == list(range(count))
    assert len(spread_indices(0, count, True, cover)) == (1 if cover else min(2, count))


def test_gif_spread_rtl_thumbnails_settings(tmp_path, image_bytes, wait_until, qapp):
    path = tmp_path / "comic.cbz"
    with ZipFile(path, "w") as archive:
        archive.writestr("0.gif", animated_gif())
        for index in range(1, 40):
            archive.writestr(f"{index}.png", image_bytes("blue", width=600, height=800))
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    window.show()
    try:
        window.open_archive(path)
        wait_until(lambda: not window.loading)
        assert len(window.viewer._movies) == 1
        movie, buffer = window.viewer._movies[0]
        first = window.viewer._item.pixmap().toImage().pixelColor(0, 0)
        wait_until(lambda: window.viewer._item.pixmap().toImage().pixelColor(0, 0) != first)
        assert movie.cacheMode() == movie.CacheMode.CacheNone
        window.set_reading(double=True, rtl=True)
        wait_until(lambda: not window.loading)
        window.navigate(1)
        wait_until(lambda: not window.loading)
        assert not window.viewer._movies
        assert window.current_index == 1
        assert window.counter.text() == "2–3 / 40"
        assert window.viewer._group is not None
        window.viewer.fit_image()
        QTest.keyClick(window, Qt.Key.Key_Left)
        wait_until(lambda: not window.loading)
        assert window.current_index == 3
        window.thumbnail_dock.show()
        wait_until(lambda: len(window.thumbnails.catalog.cache) > 0)
        assert len(window.thumbnails.catalog.cache) < 10
        assert window.thumbnails.catalog.cache.current_bytes <= 64 * 1024 * 1024
        window.thumbnails.scrollTo(window.thumbnails.catalog.index(30))
        wait_until(lambda: window.thumbnails.catalog.cache.get(30) is not None)
        assert window.thumbnails.catalog.cache.get(30).width() <= 144
        window.thumbnails.page_selected.emit(30)
        wait_until(lambda: not window.loading)
        assert window.current_index == 29
    finally:
        window.close()
        wait_until(
            lambda: not window.worker.isRunning() and not window.thumbnails.worker.isRunning()
        )
        window.close()
    assert settings.value("double_page", type=bool)
    assert settings.value("rtl", type=bool)
    assert set(settings.allKeys()) <= {
        "geometry",
        "state",
        "double_page",
        "rtl",
        "cover",
        "thumbnails",
    }
    restored = MainWindow(settings=settings)
    try:
        assert restored.double_page and restored.rtl and restored.cover
    finally:
        restored.close()
        wait_until(
            lambda: not restored.worker.isRunning() and not restored.thumbnails.worker.isRunning()
        )


def test_bad_settings_defaults(tmp_path, qapp, wait_until):
    settings = QSettings(str(tmp_path / "invalid.ini"), QSettings.Format.IniFormat)
    settings.setValue("double_page", "not-a-bool")
    settings.setValue("geometry", "not-a-bytearray")
    window = MainWindow(settings=settings)
    try:
        assert not window.double_page
    finally:
        window.close()
        wait_until(
            lambda: not window.worker.isRunning() and not window.thumbnails.worker.isRunning()
        )
