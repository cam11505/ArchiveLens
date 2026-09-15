import hashlib
import os
import stat as stat_module
from pathlib import Path

from archivelens import config
from archivelens.archive.credentials import ArchiveCredentials
from archivelens.content.base import (
    ContentCapabilities,
    ContentOpenOptions,
    ContentPage,
    ContentProvider,
    PageDescriptor,
    PageLoadRequest,
    PageMediaKind,
    SourceIdentity,
    SourceType,
    source_identity_for_path,
)
from archivelens.errors import (
    ContentAccessError,
    ContentScanCancelledError,
    InvalidPageError,
    ResourceLimitError,
)
from archivelens.utils.file_types import is_image
from archivelens.utils.natural_sort import natural_sort_key


class FolderContentProvider(ContentProvider):
    """Read image files from one directory tree without following reparse points."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._identity: SourceIdentity | None = None
        self._pages: tuple[PageDescriptor, ...] = ()
        self._files: tuple[Path, ...] = ()

    @property
    def capabilities(self) -> ContentCapabilities:
        return ContentCapabilities(SourceType.FOLDER, allows_prefetch=True)

    @property
    def source_identity(self) -> SourceIdentity:
        if self._identity is None:
            raise ContentAccessError()
        return self._identity

    def open(
        self,
        path: str | Path,
        *,
        credentials: ArchiveCredentials | None = None,
        options: ContentOpenOptions | None = None,
    ) -> None:
        del credentials
        self.close()
        root = Path(path)
        if not root.is_dir():
            raise ContentAccessError()
        options = options or ContentOpenOptions()
        discovered = self._discover(root, options)
        discovered.sort(key=lambda item: natural_sort_key(item[0]))
        digest = hashlib.sha256()
        pages = []
        files = []
        for index, (relative, file, stat) in enumerate(discovered):
            digest.update(relative.encode("utf-8", errors="surrogatepass"))
            digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
            extension = file.suffix.casefold()
            pages.append(
                PageDescriptor(
                    index,
                    file.name,
                    relative,
                    extension,
                    PageMediaKind.RASTER,
                    f"folder-file:{relative}:{stat.st_size}:{stat.st_mtime_ns}",
                    stat.st_size,
                )
            )
            files.append(file)
        self._root = root
        self._pages = tuple(pages)
        self._files = tuple(files)
        self._identity = source_identity_for_path(
            root, SourceType.FOLDER, scan_signature=digest.hexdigest()
        )

    def close(self) -> None:
        self._root = None
        self._identity = None
        self._pages = ()
        self._files = ()

    def list_pages(self) -> list[PageDescriptor]:
        if self._root is None:
            raise ContentAccessError()
        return list(self._pages)

    def load_page(self, page: PageDescriptor, request: PageLoadRequest) -> ContentPage:
        del request
        if self._root is None:
            raise ContentAccessError()
        if not 0 <= page.index < len(self._pages) or self._pages[page.index] is not page:
            raise InvalidPageError()
        file = self._files[page.index]
        try:
            stat_result = file.stat(follow_symlinks=False)
            if _is_reparse_or_symlink(file, stat_result) or not stat_module.S_ISREG(
                stat_result.st_mode
            ):
                raise ContentAccessError()
            size = stat_result.st_size
            if size > config.MAX_ENTRY_UNCOMPRESSED_SIZE:
                raise ResourceLimitError()
            with file.open("rb") as stream:
                data = stream.read(config.MAX_ENTRY_UNCOMPRESSED_SIZE + 1)
        except ResourceLimitError:
            raise
        except OSError as exc:
            raise ContentAccessError() from exc
        if len(data) > config.MAX_ENTRY_UNCOMPRESSED_SIZE or len(data) != size:
            raise ResourceLimitError()
        return ContentPage(encoded=data)

    @staticmethod
    def _discover(root: Path, options: ContentOpenOptions):
        discovered = []
        stack = [(root, Path(), 0)]
        while stack:
            if options.cancelled():
                raise ContentScanCancelledError()
            directory, relative_root, depth = stack.pop()
            try:
                children = list(directory.iterdir())
            except OSError as exc:
                if directory == root:
                    raise ContentAccessError() from exc
                continue
            children.sort(key=lambda item: natural_sort_key(item.name), reverse=True)
            for child in children:
                if options.cancelled():
                    raise ContentScanCancelledError()
                relative_path = relative_root / child.name
                try:
                    stat = child.stat(follow_symlinks=False)
                except OSError:
                    continue
                if _is_reparse_or_symlink(child, stat):
                    continue
                if child.is_dir():
                    if options.recursive and depth < config.MAX_FOLDER_DEPTH:
                        stack.append((child, relative_path, depth + 1))
                    elif options.recursive and depth >= config.MAX_FOLDER_DEPTH:
                        raise ResourceLimitError()
                    continue
                relative = relative_path.as_posix()
                if child.is_file() and is_image(relative):
                    discovered.append((relative, child, stat))
                    if len(discovered) > config.MAX_FOLDER_ENTRIES:
                        raise ResourceLimitError()
        return discovered


def _is_reparse_or_symlink(path: Path, stat_result: os.stat_result) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(stat_result, "st_file_attributes", 0)
    reparse_flag = getattr(stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)
