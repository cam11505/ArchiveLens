import hashlib
import struct
import warnings
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from archivelens import config
from archivelens.archive.catalog import image_entries
from archivelens.archive.zip_provider import ZipArchiveProvider
from archivelens.errors import (
    ArchiveAccessError,
    ArchiveLensError,
    CorruptedArchiveError,
    ResourceLimitError,
    UnsupportedArchiveError,
    UnsupportedEncryptionError,
)
from archivelens.utils.file_types import is_image
from archivelens.utils.natural_sort import natural_sort_key


@pytest.mark.parametrize(
    "names,expected",
    [
        (["10.jpg", "2.jpg", "1.jpg"], ["1.jpg", "2.jpg", "10.jpg"]),
        (["010.jpg", "002.jpg", "001.jpg"], ["001.jpg", "002.jpg", "010.jpg"]),
        (["page10.jpg", "page2.jpg", "page1.jpg"], ["page1.jpg", "page2.jpg", "page10.jpg"]),
        (["章10/1.jpg", "章2/10.jpg", "章2/2.jpg"], ["章2/2.jpg", "章2/10.jpg", "章10/1.jpg"]),
    ],
)
def test_natural_sort(names, expected):
    assert sorted(names, key=natural_sort_key) == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("日本旅行/東京/001.JPG", True),
        ("京都・清水寺.png", True),
        ("a.jpeg", True),
        ("a.webp", True),
        ("a.bmp", True),
        ("a.gif", True),
        ("readme.txt", False),
        ("data.json", False),
        ("a.jpg.exe", False),
    ],
)
def test_image_filter(path, expected):
    assert is_image(path) is expected


def make_archive(tmp_path, files, suffix=".zip"):
    path = tmp_path / ("旅行照片" + suffix)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return path


@pytest.mark.parametrize("suffix", [".zip", ".cbz", ".ZIP"])
def test_catalog_lazy_read_and_source_unchanged(tmp_path, monkeypatch, suffix):
    path = make_archive(
        tmp_path,
        [
            (name, name.encode())
            for name in ["10.jpg", "2.jpg", "1.jpg", "台北101.png", "README.txt"]
        ],
        suffix,
    )
    before = hashlib.sha256(path.read_bytes()).digest()
    with ZipArchiveProvider() as provider:
        provider.open(path)
        original = ZipFile.open
        with monkeypatch.context() as patch:
            patch.setattr(ZipFile, "open", lambda *a, **k: pytest.fail("eager entry read"))
            entries = image_entries(provider)
        assert [e.path for e in entries] == ["1.jpg", "2.jpg", "10.jpg", "台北101.png"]
        assert original is ZipFile.open
        assert provider.read_entry(entries[1]) == b"2.jpg"
    assert hashlib.sha256(path.read_bytes()).digest() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("files", [[], [("readme.txt", b"hello")]])
def test_empty_archive(tmp_path, files):
    with ZipArchiveProvider() as provider:
        provider.open(make_archive(tmp_path, files))
        assert image_entries(provider) == []


def test_duplicate_names_address_exact_entry(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        path = make_archive(tmp_path, [("1.jpg", b"first"), ("1.jpg", b"second")])
    with ZipArchiveProvider() as provider:
        provider.open(path)
        assert [provider.read_entry(e) for e in provider.list_entries()] == [b"first", b"second"]
        stale = provider.list_entries()[0]
        provider.open(path)
        with pytest.raises(ArchiveLensError, match="失效"):
            provider.read_entry(stale)


def test_invalid_and_missing_archives(tmp_path):
    path = tmp_path / "bad.zip"
    path.write_bytes(b"not a zip")
    provider = ZipArchiveProvider()
    for invalid, error in [
        (path, CorruptedArchiveError),
        (tmp_path / "missing.zip", ArchiveAccessError),
        (tmp_path / "a.rar", UnsupportedArchiveError),
    ]:
        with pytest.raises(error):
            provider.open(invalid)
    with pytest.raises(ArchiveLensError, match="尚未"):
        provider.list_entries()


@pytest.mark.parametrize(
    "setting,value",
    [
        ("MAX_ENTRY_UNCOMPRESSED_SIZE", 10),
        ("MAX_COMPRESSION_RATIO", 2),
    ],
)
def test_unsafe_entry_rejected_before_read(tmp_path, monkeypatch, setting, value):
    path = make_archive(tmp_path, [("1.png", b"x" * 4096)])
    with ZipArchiveProvider() as provider:
        provider.open(path)
        monkeypatch.setattr(config, setting, value)
        monkeypatch.setattr(ZipFile, "open", lambda *a, **k: pytest.fail("unsafe read"))
        with pytest.raises(ResourceLimitError, match="大小異常"):
            provider.read_entry(provider.list_entries()[0])


def test_encrypted_entry(tmp_path):
    path = make_archive(tmp_path, [("1.jpg", b"image")])
    data = bytearray(path.read_bytes())
    for signature, flag_offset in [(b"PK\x03\x04", 6), (b"PK\x01\x02", 8)]:
        offset = data.index(signature) + flag_offset
        flags = struct.unpack_from("<H", data, offset)[0]
        struct.pack_into("<H", data, offset, flags | 1)
    path.write_bytes(data)
    with ZipArchiveProvider() as provider:
        provider.open(path)
        with pytest.raises(UnsupportedEncryptionError, match="加密"):
            provider.read_entry(provider.list_entries()[0])
