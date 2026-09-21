import importlib.util
from pathlib import Path


def _qualification_module():
    path = Path(__file__).parents[1] / "scripts" / "v13_media_qualification.py"
    spec = importlib.util.spec_from_file_location("v13_media_qualification", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v13_media_qualification_schema(qapp):
    module = _qualification_module()
    report = module.build_report()

    assert report["schema_version"] == 1
    assert report["success"] is True
    assert set(module.SHIPPED_EXTENSIONS) <= set(report["decoder_extensions"]["available"])
    assert report["decoder_extensions"]["deferred_absent"] == [".heic", ".heif", ".jxl"]
    assert report["providers"]["folder"] == {
        "pages": len(module.SHIPPED_EXTENSIONS),
        "decoded": True,
    }
    assert report["providers"]["zip"] == {
        "pages": len(module.SHIPPED_EXTENSIONS),
        "decoded": True,
    }
    assert report["raster"]["avif_metadata"] == {
        "orientation_size": [6, 8],
        "icc": True,
        "alpha": True,
    }
    assert report["raster"]["resource_guard"] is True
    assert report["pdf"]["ordinary"]["opaque_white_background"] is True
    assert report["pdf"]["many_pages"] == 125
    assert all(report["pdf"]["password"].values())
    assert report["pdf"]["malformed_rejected"] is True
