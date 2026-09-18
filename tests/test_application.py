import pytest
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from archivelens.application import SourceOpenRouter
from archivelens.platform_paths import native_backend_path, runtime_root


def test_source_open_router_queues_cold_open_then_dispatches_warm_open(tmp_path):
    opened = []
    router = SourceOpenRouter()
    cold = tmp_path / "cold.cbz"
    warm = tmp_path / "warm.pdf"

    router.open_source(cold)
    router.set_handler(opened.append)
    router.open_source(warm)

    assert opened == [cold, warm]


def test_application_routes_file_open_event_through_common_boundary(qapp, tmp_path):
    opened = []
    qapp.set_open_source_handler(opened.append)
    source = tmp_path / "Finder 開啟.cbz"

    QApplication.sendEvent(qapp, QFileOpenEvent(str(source)))

    assert opened == [source]


def test_runtime_paths_are_deterministic_for_source_and_frozen_layouts(tmp_path):
    source_root = runtime_root(frozen=False)
    assert (source_root / "pyproject.toml").is_file()
    assert native_backend_path("backend.dll", frozen=False) == (
        source_root / "outputs" / "backends" / "backend.dll"
    )
    assert runtime_root(frozen=True, bundle_root=tmp_path) == tmp_path.resolve()
    assert (
        native_backend_path("backend.dylib", frozen=True, bundle_root=tmp_path)
        == tmp_path.resolve() / "native" / "backend.dylib"
    )


def test_frozen_runtime_requires_a_bundle_root(monkeypatch):
    monkeypatch.delattr("sys._MEIPASS", raising=False)
    with pytest.raises(RuntimeError, match="Frozen runtime root"):
        runtime_root(frozen=True)
