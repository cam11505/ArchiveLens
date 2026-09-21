import hashlib
from pathlib import Path

import pytest

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.rar_provider import RarArchiveProvider
from archivelens.errors import BadPasswordError, PasswordRequiredError

ROOT = Path(__file__).parent / "fixtures" / "rar"
pytestmark = pytest.mark.skipif(
    not RarArchiveProvider.capabilities.available, reason="Bundled UnRAR library required"
)


@pytest.mark.parametrize(
    "name",
    [
        "rar3-solid.rar",
        "rar5-solid.rar",
        "rar5-crc.rar",
        "rar5-hpsw.rar",
        "rar5-psw.rar",
        "unicode2.rar",
    ],
)
def test_rar_single_entry_immutable(name, tmp_path):
    path = tmp_path / "照片.cbr"
    path.write_bytes((ROOT / name).read_bytes())
    before = hashlib.sha256(path.read_bytes()).digest()
    with ArchiveCredentials(b"password") as creds, RarArchiveProvider() as provider:
        provider.open(path, credentials=creds)
        assert not provider.capabilities.allows_prefetch
        for entry in reversed(provider.list_entries()):
            assert len(provider.read_entry(entry)) == entry.uncompressed_size
    assert hashlib.sha256(path.read_bytes()).digest() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("name", ["rar5-hpsw.rar", "rar5-psw.rar"])
def test_rar_credentials(name):
    for password, error in [(None, PasswordRequiredError), (b"wrong", BadPasswordError)]:
        with ArchiveCredentials(password) as creds, RarArchiveProvider() as provider:
            with pytest.raises(error):
                provider.open(ROOT / name, credentials=creds)
                provider.read_entry(provider.list_entries()[0])
