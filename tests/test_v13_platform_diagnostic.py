import importlib.util
from pathlib import Path


def _diagnostic_module():
    path = Path(__file__).parents[1] / "scripts" / "v13_platform_diagnostic.py"
    spec = importlib.util.spec_from_file_location("v13_platform_diagnostic", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_platform_diagnostic_schema(qapp):
    report = _diagnostic_module().build_report()

    assert report["schema_version"] == 1
    assert report["runtime"]["machine"]
    assert report["qt"]["qimage_smoke"] is True
    assert report["qt"]["qwidget_smoke"] is True
    assert report["qt"]["qtpdf_smoke"] is True
    pdf_render = report["qt"]["qtpdf_production_render"]
    assert pdf_render["pages"] == 1
    assert pdf_render["width"] > 0
    assert pdf_render["height"] > 0
    assert pdf_render["has_alpha_channel"] is False
    assert pdf_render["corner_rgba"] == [255, 255, 255, 255]
    assert pdf_render["opaque_white_background"] is True
    assert {".zip", ".cbz", ".7z"} <= set(report["backends"]["archive_available"])
    assert {".jpg", ".png", ".webp", ".avif", ".jp2"} <= set(
        report["backends"]["decoder_available"]
    )
    assert report["backends"]["rar"]["extensions"] == [".cbr", ".rar"]
