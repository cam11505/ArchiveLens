from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.utils.natural_sort import natural_sort_key


def image_entries(provider: ArchiveProvider) -> list[ArchiveEntry]:
    return sorted(
        (entry for entry in provider.list_entries() if entry.is_image),
        key=lambda entry: natural_sort_key(entry.path),
    )
