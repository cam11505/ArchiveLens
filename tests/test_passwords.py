import hashlib
from zipfile import ZipFile

import pytest
import pyzipper

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.zip_provider import ZipArchiveProvider
from archivelens.errors import BadPasswordError, PasswordRequiredError
from archivelens.ui.main_window import MainWindow
from archivelens.ui.password_dialog import PasswordDialog


@pytest.mark.parametrize("bits", [128, 192, 256])
def test_aes_password_and_immutability(tmp_path, image_bytes, bits):
    path = tmp_path / "加密.cbz"
    data = image_bytes()
    with pyzipper.AESZipFile(str(path), "w", encryption=pyzipper.WZ_AES) as archive:
        archive.setpassword(b"correct")
        archive.setencryption(pyzipper.WZ_AES, nbits=bits)
        archive.writestr("台北/1.png", data)
    original = hashlib.sha256(path.read_bytes()).digest()
    with ZipArchiveProvider() as provider:
        provider.open(path)
        with pytest.raises(PasswordRequiredError):
            provider.read_entry(provider.list_entries()[0])
        with ArchiveCredentials(b"wrong") as creds:
            provider.open(path, credentials=creds)
            with pytest.raises(BadPasswordError):
                provider.read_entry(provider.list_entries()[0])
        with ArchiveCredentials(b"correct") as creds:
            provider.open(path, credentials=creds)
            assert provider.read_entry(provider.list_entries()[0]) == data
    assert hashlib.sha256(path.read_bytes()).digest() == original
    assert list(tmp_path.iterdir()) == [path]


def test_password_dialog_retry_cancel_and_switch(tmp_path, image_bytes, wait_until):
    path = tmp_path / "encrypted.zip"
    with pyzipper.AESZipFile(str(path), "w", encryption=pyzipper.WZ_AES) as archive:
        archive.setpassword(b"correct")
        archive.writestr("1.png", image_bytes())
    window = MainWindow()
    try:
        window.open_archive(path)
        wait_until(lambda: bool(window._dialogs))
        dialog = window._dialogs[0]
        assert isinstance(dialog, PasswordDialog)
        dialog.password.setText("wrong")
        dialog.accept()
        wait_until(lambda: bool(window._dialogs))
        window._dialogs[0].password.setText("correct")
        window._dialogs[0].accept()
        wait_until(lambda: window.viewer._item is not None)
        window.open_archive(path)
        wait_until(lambda: bool(window._dialogs))
        dialog = window._dialogs[0]
        dialog.password.setText("discard")
        dialog.reject()
        assert dialog.password.text() == ""
        assert not window.loading
        plain = tmp_path / "plain.zip"
        with ZipFile(plain, "w") as archive:
            archive.writestr("1.png", image_bytes())
        window.open_archive(plain)
        wait_until(lambda: window.viewer._item is not None)
    finally:
        window.close()
        wait_until(lambda: not window.worker.isRunning())


def test_zipcrypto(tmp_path, image_bytes):
    from archivelens.diagnostic_fixtures import zipcrypto_fixture

    path = tmp_path / "traditional.zip"
    data = image_bytes()
    path.write_bytes(zipcrypto_fixture(data))
    with ArchiveCredentials(b"diagnostic-only") as creds, ZipArchiveProvider() as provider:
        provider.open(path, credentials=creds)
        assert provider.read_entry(provider.list_entries()[0]) == data
    with ArchiveCredentials(b"wrong") as creds, ZipArchiveProvider() as provider:
        provider.open(path, credentials=creds)
        with pytest.raises(BadPasswordError):
            provider.read_entry(provider.list_entries()[0])
