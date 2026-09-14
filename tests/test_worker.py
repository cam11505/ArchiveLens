from threading import Event
from zipfile import ZipFile

from archivelens.image.worker import ImageWorker, LoadRequest


def test_prefetch_window_and_cache_hits(tmp_path, image_bytes, qapp, wait_until, monkeypatch):
    import archivelens.image.worker as module

    archive = tmp_path / "many.zip"
    with ZipFile(archive, "w") as target:
        for i in range(12):
            target.writestr(f"{i}.png", image_bytes())
    reads = []
    original = module.ZipArchiveProvider.read_entry
    prefetched = Event()
    original_prefetch = ImageWorker._prefetch

    def read(provider, entry):
        reads.append(entry.index)
        return original(provider, entry)

    def prefetch(*args):
        original_prefetch(*args)
        prefetched.set()

    monkeypatch.setattr(module.ZipArchiveProvider, "read_entry", read)
    monkeypatch.setattr(ImageWorker, "_prefetch", prefetch)
    results = []
    worker = ImageWorker()
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, archive, 5))
        wait_until(prefetched.is_set)
        assert reads == [5, 6, 7, 4]
        assert len(results) == 1
        prefetched.clear()
        worker.submit(LoadRequest(2, 1, archive, 6))
        wait_until(prefetched.is_set)
        assert reads == [5, 6, 7, 4, 8]
        assert results[-1].index == 6
        # Reopening even the same path invalidates the previous session's cache.
        prefetched.clear()
        worker.submit(LoadRequest(3, 2, archive, 5))
        wait_until(prefetched.is_set)
        assert reads[-4:] == [5, 6, 7, 4]
    finally:
        worker.stop()
        assert worker.wait(5000)


def test_pending_navigation_takes_priority_over_prefetch(
    tmp_path, image_bytes, wait_until, monkeypatch
):
    import archivelens.image.worker as module

    archive = tmp_path / "priority.zip"
    with ZipFile(archive, "w") as target:
        for i in range(10):
            target.writestr(f"{i}.png", image_bytes())
    entered, release = Event(), Event()
    reads = []
    original = module.ZipArchiveProvider.read_entry

    def read(provider, entry):
        reads.append(entry.index)
        if entry.index == 1:
            entered.set()
            assert release.wait(5)
        return original(provider, entry)

    monkeypatch.setattr(module.ZipArchiveProvider, "read_entry", read)
    results = []
    worker = ImageWorker()
    worker.result_ready.connect(results.append)
    worker.start()
    try:
        worker.submit(LoadRequest(1, 1, archive, 0))
        wait_until(entered.is_set)
        worker.submit(LoadRequest(2, 1, archive, 5))
        worker.submit(LoadRequest(3, 1, archive, 8))
        release.set()
        wait_until(lambda: any(result.token == 3 for result in results))
        assert reads[:3] == [0, 1, 8]
        assert 5 not in reads
        assert not any(result.token == 2 for result in results)
    finally:
        release.set()
        worker.stop()
        assert worker.wait(5000)
