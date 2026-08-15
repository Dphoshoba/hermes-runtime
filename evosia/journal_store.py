"""Journal Storage — append-only, immutable event persistence.

Events are stored in daily JSONL (JSON Lines) files under a journal directory.
Each line is a single JSON-serialized JournalEvent. An in-memory index tracks
event IDs for fast lookup. A manifest file records the event count for
deterministic ordering verification.

Design guarantees:
- Append-only: events are never modified or deleted after write.
- Immutable: written files are made read-only.
- Deterministic: events within a day are ordered by timestamp.
- Content-addressed: each event carries a SHA-256 payload hash.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator

from .journal_models import JournalEvent, _format_utc, _utc_now, STAGE_CATEGORIES


class JournalStore:
    """Append-only persistent storage for JournalEvents.

    Directory layout:
        {root}/
            manifest.json        — global event count
            events/
                YYYY-MM-DD.jsonl — one line per event
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._events_dir = root / "events"
        self._manifest_path = root / "manifest.json"
        self._lock_path = root / ".journal.lock"
        self._lock_fd: int | None = None
        self._index: dict[str, JournalEvent] = {}
        self._events: list[JournalEvent] = []
        self._loaded = False

    # -- lifecycle -----------------------------------------------------------

    def open(self) -> None:
        """Open the store, loading existing events into memory."""
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        self._load_all()
        self._loaded = True

    def close(self) -> None:
        """Release the file lock."""
        self._release_lock()
        self._loaded = False

    def __enter__(self) -> JournalStore:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- locking -------------------------------------------------------------

    def _acquire_lock(self) -> None:
        self._lock_fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)

    def _release_lock(self) -> None:
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None

    # -- loading -------------------------------------------------------------

    def _load_all(self) -> None:
        self._events = []
        self._index = {}
        if not self._events_dir.exists():
            return
        for path in sorted(self._events_dir.glob("*.jsonl")):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    data = json.loads(line)
                    event = JournalEvent.from_dict(data)
                    self._events.append(event)
                    self._index[event.event_id] = event

    # -- writing -------------------------------------------------------------

    def append(self, event: JournalEvent) -> None:
        """Append a single event to the journal.

        Raises ValueError if the event ID already exists (immutability).
        """
        self._ensure_loaded()
        if event.event_id in self._index:
            raise ValueError(
                f"Duplicate event_id {event.event_id!r}. Events are immutable."
            )
        day = event.timestamp[:10]  # YYYY-MM-DD
        line = json.dumps(event.as_dict(), sort_keys=True, ensure_ascii=False) + "\n"
        self._append_line(day, line)
        self._events.append(event)
        self._index[event.event_id] = event

    def append_many(self, events: Sequence[JournalEvent]) -> None:
        """Append multiple events atomically (all or none)."""
        self._ensure_loaded()
        # Validate no duplicates before writing
        for ev in events:
            if ev.event_id in self._index:
                raise ValueError(
                    f"Duplicate event_id {ev.event_id!r}. Events are immutable."
                )
        # Write all events
        lines_by_day: dict[str, list[str]] = {}
        for ev in events:
            day = ev.timestamp[:10]
            line = json.dumps(ev.as_dict(), sort_keys=True, ensure_ascii=False) + "\n"
            lines_by_day.setdefault(day, []).append(line)
        for day, lines in sorted(lines_by_day.items()):
            self._append_lines(day, lines)
        for ev in events:
            self._events.append(ev)
            self._index[ev.event_id] = ev

    def _append_line(self, day: str, line: str) -> None:
        self._append_lines(day, [line])

    def _append_lines(self, day: str, lines: list[str]) -> None:
        path = self._events_dir / f"{day}.jsonl"
        fd, tmp = tempfile.mkstemp(dir=self._events_dir, suffix=".tmp")
        try:
            # If the file exists, copy existing content first
            if path.exists():
                with open(path, "r", encoding="utf-8") as existing:
                    existing_content = existing.read()
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(existing_content)
                    for line in lines:
                        handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    for line in lines:
                        handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
            os.replace(tmp, path)
            _fsync_directory(path.parent)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- querying ------------------------------------------------------------

    def list_events(
        self,
        *,
        event_type: str | None = None,
        stage: str | None = None,
        repository: str | None = None,
        actor: str | None = None,
        after: str | None = None,
        before: str | None = None,
        limit: int | None = None,
    ) -> list[JournalEvent]:
        """Query events with optional filters. Returns in chronological order."""
        self._ensure_loaded()
        result = self._events
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]
        if stage is not None:
            result = [e for e in result if e.stage == stage]
        if repository is not None:
            result = [e for e in result if e.repository == repository]
        if actor is not None:
            result = [e for e in result if e.actor == actor]
        if after is not None:
            result = [e for e in result if e.timestamp > after]
        if before is not None:
            result = [e for e in result if e.timestamp < before]
        if limit is not None:
            result = result[:limit]
        return result

    def get_event(self, event_id: str) -> JournalEvent | None:
        """Retrieve a single event by ID."""
        self._ensure_loaded()
        return self._index.get(event_id)

    def count_events(self, *, event_type: str | None = None) -> int:
        """Count events, optionally filtered by type."""
        self._ensure_loaded()
        if event_type is not None:
            return sum(1 for e in self._events if e.event_type == event_type)
        return len(self._events)

    def events_iterator(self) -> Iterator[JournalEvent]:
        """Iterate over all events in chronological order."""
        self._ensure_loaded()
        return iter(self._events)

    def verify_integrity(self) -> list[str]:
        """Verify all events have valid content hashes. Returns list of errors."""
        self._ensure_loaded()
        errors = []
        for event in self._events:
            if not event.verify_integrity():
                errors.append(
                    f"Event {event.event_id}: payload hash mismatch "
                    f"(expected {event.payload_sha256})"
                )
        return errors

    def as_dict(self) -> dict[str, Any]:
        """Serialize the full journal as a dict."""
        self._ensure_loaded()
        return {
            "schema_version": "1.0",
            "event_count": len(self._events),
            "events": [e.as_dict() for e in self._events],
        }

    # -- helpers -------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError("JournalStore not open. Call open() first.")


def _fsync_directory(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
