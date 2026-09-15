import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from archivelens.config import (
    BOOKMARKS_PER_SOURCE_LIMIT,
    MAX_ZOOM,
    MIN_ZOOM,
    READING_STATE_MAX_BYTES,
    READING_STATE_SCHEMA_VERSION,
    READING_STATE_SOURCE_LIMIT,
    RECENT_HISTORY_LIMIT,
)
from archivelens.content.base import SourceIdentity, SourceType


@dataclass(frozen=True, slots=True)
class ReaderState:
    page_index: int = 0
    page_count: int = 0
    last_opened: str = ""
    double_page: bool = False
    rtl: bool = False
    cover: bool = True
    fit_mode: str = "fit_page"
    zoom_factor: float = 1.0
    rotation: int = 0
    trim_mode: str = "off"
    trim_margins: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class PageBookmark:
    page_index: int
    label: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ReadingRecord:
    identity: SourceIdentity
    display_name: str
    state: ReaderState
    bookmarks: tuple[PageBookmark, ...] = ()
    in_history: bool = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def default_reading_state_path(settings: QSettings | None = None) -> Path:
    del settings
    root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(root) / "reading-state.json"


class ReadingStateStore:
    """Versioned, bounded metadata store. It never accepts credential/content payloads."""

    def __init__(self, path: str | Path, *, clock: Callable[[], str] = _utc_now) -> None:
        self.path = Path(path)
        self._clock = clock
        self._records: dict[str, ReadingRecord] = {}
        self.load_error = False
        self.last_write_error = False
        self._load()

    def get(self, identity: SourceIdentity) -> ReadingRecord | None:
        return self._records.get(identity.storage_key)

    def update(self, identity: SourceIdentity, display_name: str, state: ReaderState) -> None:
        key = identity.storage_key
        existing = self._records.get(key)
        timestamped = replace(
            state,
            page_index=max(0, state.page_index),
            page_count=max(0, state.page_count),
            last_opened=self._clock(),
            rotation=state.rotation % 360,
        )
        self._records[key] = ReadingRecord(
            identity,
            display_name,
            timestamped,
            existing.bookmarks if existing else (),
            True,
        )
        self._prune()
        self._write()

    def recent(self) -> tuple[ReadingRecord, ...]:
        records = (record for record in self._records.values() if record.in_history)
        return tuple(
            sorted(records, key=lambda record: record.state.last_opened, reverse=True)[
                :RECENT_HISTORY_LIMIT
            ]
        )

    def remove_recent(self, identity: SourceIdentity) -> None:
        key = identity.storage_key
        record = self._records.get(key)
        if record is not None:
            self._records[key] = replace(record, in_history=False)
            self._write()

    def clear_recent(self) -> None:
        self._records = {
            key: replace(record, in_history=False) for key, record in self._records.items()
        }
        self._write()

    def bookmarks(self, identity: SourceIdentity) -> tuple[PageBookmark, ...]:
        record = self.get(identity)
        return record.bookmarks if record else ()

    def toggle_bookmark(self, identity: SourceIdentity, page_index: int, label: str) -> bool:
        record = self.get(identity)
        if record is None or page_index < 0:
            return False
        bookmarks = list(record.bookmarks)
        existing = next((item for item in bookmarks if item.page_index == page_index), None)
        if existing is not None:
            bookmarks.remove(existing)
            added = False
        else:
            if len(bookmarks) >= BOOKMARKS_PER_SOURCE_LIMIT:
                return False
            bookmarks.append(PageBookmark(page_index, label, self._clock()))
            bookmarks.sort(key=lambda item: item.page_index)
            added = True
        self._records[identity.storage_key] = replace(record, bookmarks=tuple(bookmarks))
        self._write()
        return added

    def remove_bookmark(self, identity: SourceIdentity, page_index: int) -> None:
        record = self.get(identity)
        if record is None:
            return
        bookmarks = tuple(item for item in record.bookmarks if item.page_index != page_index)
        if bookmarks != record.bookmarks:
            self._records[identity.storage_key] = replace(record, bookmarks=bookmarks)
            self._write()

    def _prune(self) -> None:
        history = list(self.recent())
        keep_history = {record.identity.storage_key for record in history}
        for key, record in tuple(self._records.items()):
            if record.in_history and key not in keep_history:
                self._records[key] = replace(record, in_history=False)
        if len(self._records) <= READING_STATE_SOURCE_LIMIT:
            return
        ranked = sorted(
            self._records.items(),
            key=lambda item: (bool(item[1].bookmarks), item[1].state.last_opened),
            reverse=True,
        )
        self._records = dict(ranked[:READING_STATE_SOURCE_LIMIT])

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            if self.path.stat().st_size > READING_STATE_MAX_BYTES:
                raise ValueError("reading-state file is too large")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            version = payload.get("schema_version", payload.get("version"))
            if version not in (0, 1, READING_STATE_SCHEMA_VERSION):
                raise ValueError("unsupported reading-state schema")
            records = payload.get("records", [])
            if not isinstance(records, list):
                raise ValueError("invalid reading-state records")
            loaded = {}
            for raw in records[:READING_STATE_SOURCE_LIMIT]:
                record = self._parse_record(raw, version)
                loaded[record.identity.storage_key] = record
            self._records = loaded
            self._prune()
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            self._records = {}
            self.load_error = True

    @staticmethod
    def _parse_record(raw: dict, version: int) -> ReadingRecord:
        identity_raw = raw["identity"]
        identity = SourceIdentity(
            SourceType(identity_raw["source_type"]),
            str(identity_raw["canonical_path"]),
            _optional_int(identity_raw.get("size_bytes")),
            _optional_int(identity_raw.get("modified_ns")),
            str(identity_raw.get("scan_signature", "")),
        )
        state_raw = raw["state"]
        page_key = "current_page" if version == 0 else "page_index"
        state = ReaderState(
            page_index=max(0, int(state_raw.get(page_key, 0))),
            page_count=max(0, int(state_raw.get("page_count", 0))),
            last_opened=str(state_raw.get("last_opened", "")),
            double_page=_strict_bool(state_raw.get("double_page", False)),
            rtl=_strict_bool(state_raw.get("rtl", False)),
            cover=_strict_bool(state_raw.get("cover", True)),
            fit_mode=_fit_mode(state_raw.get("fit_mode", "fit_page")),
            zoom_factor=max(MIN_ZOOM, min(float(state_raw.get("zoom_factor", 1.0)), MAX_ZOOM)),
            rotation=int(state_raw.get("rotation", 0)) % 360,
            trim_mode=_trim_mode(state_raw.get("trim_mode", "off")),
            trim_margins=_trim_margins(state_raw.get("trim_margins", (0, 0, 0, 0))),
        )
        bookmarks = tuple(
            PageBookmark(
                max(0, int(item["page_index"])),
                str(item.get("label", "")),
                str(item.get("created_at", "")),
            )
            for item in raw.get("bookmarks", [])[:BOOKMARKS_PER_SOURCE_LIMIT]
            if isinstance(item, dict)
        )
        return ReadingRecord(
            identity,
            str(raw.get("display_name", Path(identity.canonical_path).name)),
            state,
            tuple(sorted(bookmarks, key=lambda item: item.page_index)),
            _strict_bool(raw.get("in_history", True)),
        )

    def _write(self) -> None:
        payload = {
            "schema_version": READING_STATE_SCHEMA_VERSION,
            "records": [self._record_dict(record) for record in self._records.values()],
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if len(encoded) > READING_STATE_MAX_BYTES:
            self.last_write_error = True
            return
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(encoded)
            os.replace(temporary, self.path)
            self.last_write_error = False
        except OSError:
            self.last_write_error = True
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _record_dict(record: ReadingRecord) -> dict:
        return {
            "identity": {
                "source_type": record.identity.source_type,
                "canonical_path": record.identity.canonical_path,
                "size_bytes": record.identity.size_bytes,
                "modified_ns": record.identity.modified_ns,
                "scan_signature": record.identity.scan_signature,
            },
            "display_name": record.display_name,
            "state": asdict(record.state),
            "bookmarks": [asdict(item) for item in record.bookmarks],
            "in_history": record.in_history,
        }


def _strict_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("invalid boolean")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    return parsed if parsed >= 0 else None


def _fit_mode(value: object) -> str:
    return (
        str(value)
        if value in {"fit_page", "fit_width", "fit_height", "actual", "custom"}
        else "fit_page"
    )


def _trim_mode(value: object) -> str:
    return str(value) if value in {"off", "auto", "manual"} else "off"


def _trim_margins(value: object) -> tuple[int, int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return (0, 0, 0, 0)
    return tuple(max(0, min(int(item), 40)) for item in value)


def create_reading_state_store(settings: QSettings | None = None) -> ReadingStateStore:
    return ReadingStateStore(default_reading_state_path(settings))
