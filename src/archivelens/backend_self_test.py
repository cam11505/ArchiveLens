"""Real-backend smoke checks also executed inside the frozen application."""

import hashlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import py7zr
import pyzipper

from archivelens.archive.credentials import ArchiveCredentials
from archivelens.archive.factory import DEFAULT_REGISTRY
from archivelens.diagnostic_fixtures import zipcrypto_fixture
from archivelens.platform_paths import is_frozen_runtime, runtime_root


def check_backends(image):
    checks = []
    with TemporaryDirectory(prefix="ArchiveLens-backends-") as directory:
        root = Path(directory)
        zip_path = root / "encrypted.zip"
        with pyzipper.AESZipFile(str(zip_path), "w", encryption=pyzipper.WZ_AES) as archive:
            archive.setpassword(b"diagnostic-only")
            archive.writestr("1.png", image)
        crypto = root / "traditional.cbz"
        crypto.write_bytes(zipcrypto_fixture(image))
        seven = root / "encrypted.7z"
        with py7zr.SevenZipFile(
            seven, "w", password="diagnostic-only", header_encryption=True
        ) as archive:
            archive.writestr(image, "1.png")
        for path in (zip_path, crypto, seven):
            before = hashlib.sha256(path.read_bytes()).digest()
            with (
                ArchiveCredentials(b"diagnostic-only") as creds,
                DEFAULT_REGISTRY.create(path) as provider,
            ):
                provider.open(path, credentials=creds)
                assert provider.read_entry(provider.list_entries()[0]) == image
            assert hashlib.sha256(path.read_bytes()).digest() == before
            checks.append(
                {
                    "encrypted.zip": "aes_zip_backend",
                    "traditional.cbz": "zipcrypto_backend",
                    "encrypted.7z": "encrypted_7z_backend",
                }[path.name]
            )
        if sys.platform == "win32":
            relative = "self-test-rar" if is_frozen_runtime() else "tests/fixtures/rar"
            fixtures = runtime_root() / relative
            for name in ("rar3-solid.rar", "rar5-solid.rar", "rar5-hpsw.rar"):
                path = fixtures / name
                with (
                    ArchiveCredentials(b"password") as creds,
                    DEFAULT_REGISTRY.create(path) as provider,
                ):
                    provider.open(path, credentials=creds)
                    assert all(
                        len(provider.read_entry(e)) == e.uncompressed_size
                        for e in provider.list_entries()
                    )
            checks.append("bundled_rar4_rar5_solid_encrypted_backend")
        assert set(root.iterdir()) == {zip_path, crypto, seven}
    return checks
