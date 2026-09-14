import lzma
import zlib
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from archivelens import config
from archivelens.archive.base import ArchiveEntry, ArchiveProvider
from archivelens.errors import ArchiveLensError
from archivelens.utils.file_types import ARCHIVE_EXTENSIONS, is_image


class ZipArchiveProvider(ArchiveProvider):
    """Read individual ZIP/CBZ members into RAM without extracting to disk."""

    def __init__(self) -> None:
        self._archive: ZipFile | None = None
        self._members: dict[int, tuple[ArchiveEntry, ZipInfo]] = {}

    @staticmethod
    def supports(path: str | Path) -> bool:
        return Path(path).suffix.casefold() in ARCHIVE_EXTENSIONS

    def open(self, path: str | Path) -> None:
        self.close()
        if not self.supports(path):
            raise ArchiveLensError("目前僅支援 ZIP / CBZ 壓縮檔。")
        try:
            self._archive = ZipFile(path, mode="r")
            for index, info in enumerate(self._archive.infolist()):
                if info.is_dir():
                    continue
                member_path = PurePosixPath(info.filename)
                entry = ArchiveEntry(
                    member_path.name,
                    info.filename,
                    member_path.suffix.casefold(),
                    info.compress_size,
                    info.file_size,
                    index,
                    is_image(info.filename),
                )
                self._members[index] = (entry, info)
        except (OSError, BadZipFile, UnicodeError, ValueError) as exc:
            self.close()
            raise ArchiveLensError("無法開啟壓縮檔：檔案損壞、不存在或沒有讀取權限。") from exc

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
        self._archive = None
        self._members.clear()

    def list_entries(self) -> list[ArchiveEntry]:
        if self._archive is None:
            raise ArchiveLensError("尚未開啟壓縮檔。")
        return [entry for entry, _ in self._members.values()]

    def read_entry(self, entry: ArchiveEntry) -> bytes:
        if self._archive is None:
            raise ArchiveLensError("尚未開啟壓縮檔。")
        member = self._members.get(entry.index)
        if member is None or member[0] is not entry:
            raise ArchiveLensError("圖片項目已失效，請重新開啟壓縮檔。")
        info = member[1]
        if info.flag_bits & 1:
            raise ArchiveLensError("目前版本尚未支援加密壓縮檔。")
        limit = config.MAX_ENTRY_UNCOMPRESSED_SIZE
        if (
            info.file_size > limit
            or info.file_size / max(1, info.compress_size) > config.MAX_COMPRESSION_RATIO
        ):
            raise ArchiveLensError("此檔案大小異常，已停止載入。")
        try:
            with self._archive.open(info, mode="r") as stream:
                data = stream.read(limit + 1)
            if len(data) > limit or len(data) != info.file_size:
                raise ArchiveLensError("此檔案大小異常，已停止載入。")
            return data
        except (
            OSError,
            BadZipFile,
            RuntimeError,
            NotImplementedError,
            EOFError,
            zlib.error,
            lzma.LZMAError,
        ) as exc:
            raise ArchiveLensError("無法讀取圖片：壓縮資料損壞、加密或壓縮方式不受支援。") from exc
