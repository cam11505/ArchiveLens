import ctypes

from archivelens.archive.rar_backend import backend_for_platform


def test_backend_selection_is_platform_neutral(tmp_path):
    windows = backend_for_platform("win32")
    macos = backend_for_platform("darwin")
    linux = backend_for_platform("linux")

    assert windows.filename == "UnRAR64.dll"
    assert windows.platform == "windows-x64"
    assert macos.filename == "libunrar.dylib"
    assert macos.platform == "macos"
    assert linux.filename == "libunrar.so"
    assert linux.platform == "linux"
    assert backend_for_platform("freebsd") is None
    assert macos.path(frozen=True, bundle_root=tmp_path) == tmp_path / "native/libunrar.dylib"


def test_unix_backends_use_c_abi():
    for platform in ("darwin", "linux"):
        backend = backend_for_platform(platform)
        assert backend.loader is ctypes.CDLL
        assert backend.callback_factory is ctypes.CFUNCTYPE
