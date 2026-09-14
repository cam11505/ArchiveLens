import pytest
from PySide6.QtGui import QColor, QImage

from archivelens.image.cache import ImageCache


def make_image(width=10, height=10):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    return image


def test_lru_eviction_uses_bytes_and_reads_update_recency():
    cache = ImageCache(800)
    assert cache.put(1, make_image())
    assert cache.put(2, make_image())
    assert cache.get(1) is not None
    assert cache.put(3, make_image())
    assert cache.get(2) is None
    assert cache.get(1) is not None
    assert cache.current_bytes == 800


def test_large_image_evicts_multiple_small_images():
    cache = ImageCache(1200)
    for key in range(3):
        cache.put(key, make_image())
    cache.put(4, make_image(20, 10))
    assert len(cache) == 2
    assert cache.get(0) is None
    assert cache.get(1) is None
    assert cache.get(2) is not None
    assert cache.current_bytes == 1200


def test_cache_replacement_retain_and_clear():
    cache = ImageCache(4000)
    cache.put(1, make_image())
    cache.put(1, make_image(20, 10))
    assert cache.current_bytes == 800
    cache.put(2, make_image())
    cache.retain([2, 3])
    assert cache.current_bytes == 400
    cache.clear()
    assert len(cache) == cache.current_bytes == 0


def test_oversize_and_zero_budget_do_not_evict_existing_images():
    cache = ImageCache(400)
    cache.put(1, make_image())
    assert not cache.put(2, make_image(20, 10))
    assert cache.get(1) is not None
    assert not ImageCache(0).put(1, make_image())
    assert not cache.put(2, QImage())
    with pytest.raises(ValueError):
        ImageCache(-1)


def test_returned_image_cannot_mutate_cached_pixels():
    cache = ImageCache()
    original = make_image()
    cache.put(1, original)
    original.fill(QColor("blue"))
    copy = cache.get(1)
    copy.fill(QColor("green"))
    assert cache.get(1).pixelColor(0, 0) == QColor("red")
