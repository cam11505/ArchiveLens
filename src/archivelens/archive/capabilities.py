from dataclasses import dataclass
from enum import StrEnum


class RandomAccess(StrEnum):
    EFFICIENT = "efficient"
    EXPENSIVE = "expensive"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ArchiveCapabilities:
    """Backend metadata; a provider may override this for the opened archive."""

    format_name: str
    extensions: frozenset[str]
    supports_passwords: bool = False
    random_access: RandomAccess = RandomAccess.UNKNOWN
    solid: bool | None = None
    available: bool = True

    def __post_init__(self) -> None:
        normalized = frozenset(extension.casefold() for extension in self.extensions)
        if not normalized or any(not ext.startswith(".") or len(ext) < 2 for ext in normalized):
            raise ValueError("Archive extensions must include a leading dot")
        object.__setattr__(self, "extensions", normalized)

    @property
    def allows_prefetch(self) -> bool:
        return (
            self.available and self.random_access == RandomAccess.EFFICIENT and self.solid is False
        )
