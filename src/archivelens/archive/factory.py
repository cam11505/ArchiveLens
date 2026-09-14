from pathlib import Path

from archivelens.archive.base import ArchiveProvider
from archivelens.archive.zip_provider import ZipArchiveProvider
from archivelens.errors import ProviderUnavailableError, UnsupportedArchiveError


class ArchiveProviderRegistry:
    """Explicit provider registration shared by workers, CLI and UI format discovery."""

    def __init__(self) -> None:
        self._providers: dict[str, type[ArchiveProvider]] = {}

    def register(self, provider: type[ArchiveProvider]) -> None:
        extensions = provider.capabilities.extensions
        if extensions & self._providers.keys():
            raise ValueError("Archive extension already registered")
        self._providers.update(dict.fromkeys(extensions, provider))

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(
            ext for ext, provider in self._providers.items() if provider.capabilities.available
        )

    def supports(self, path: str | Path) -> bool:
        return Path(path).suffix.casefold() in self.supported_extensions

    def create(self, path: str | Path) -> ArchiveProvider:
        provider = self._providers.get(Path(path).suffix.casefold())
        if provider is None:
            raise UnsupportedArchiveError()
        if not provider.capabilities.available:
            raise ProviderUnavailableError()
        try:
            return provider()
        except (ImportError, OSError) as exc:
            raise ProviderUnavailableError() from exc

    def file_dialog_filter(self) -> str:
        patterns = [
            pattern
            for ext in sorted(self.supported_extensions)
            for pattern in (f"*{ext}", f"*{ext.upper()}")
        ]
        return f"圖片壓縮檔 ({' '.join(patterns)})" if patterns else "圖片壓縮檔 ()"

    def format_label(self) -> str:
        return " / ".join(ext[1:].upper() for ext in sorted(self.supported_extensions))


DEFAULT_REGISTRY = ArchiveProviderRegistry()
DEFAULT_REGISTRY.register(ZipArchiveProvider)
