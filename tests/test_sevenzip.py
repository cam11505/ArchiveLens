import hashlib

import py7zr
import pytest

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.sevenzip_provider import SevenZipArchiveProvider
from archivelens.errors import BadPasswordError, PasswordRequiredError


@pytest.mark.parametrize("password,header", [(None, False), ("secret", False), ("secret", True)])
def test_sevenzip_memory_password_order(tmp_path, image_bytes, password, header):
    path = tmp_path / "照片.7z"
    data = image_bytes()
    with py7zr.SevenZipFile(path, "w", password=password, header_encryption=header) as archive:
        archive.writestr(data, "台北/2.png")
        archive.writestr(data, "台北/1.png")
    digest = hashlib.sha256(path.read_bytes()).digest()
    if password:
        with SevenZipArchiveProvider() as provider, pytest.raises(PasswordRequiredError):
            provider.open(path)
            provider.read_entry(provider.list_entries()[0])
        with ArchiveCredentials(b"wrong") as creds:
            with SevenZipArchiveProvider() as provider, pytest.raises(BadPasswordError):
                provider.open(path, credentials=creds)
                provider.read_entry(provider.list_entries()[0])
    with ArchiveCredentials(password.encode() if password else None) as creds:
        with SevenZipArchiveProvider() as provider:
            provider.open(path, credentials=creds)
            assert not provider.capabilities.allows_prefetch
            for entry in reversed(provider.list_entries()):
                assert provider.read_entry(entry) == data
    assert hashlib.sha256(path.read_bytes()).digest() == digest
    assert list(tmp_path.iterdir()) == [path]
