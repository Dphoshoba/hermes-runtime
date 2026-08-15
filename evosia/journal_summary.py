"""Overnight Summary Generator — aggregate journal events into daily summaries.

Produces a deterministic summary of all journal activity within a time range.
The summary is a frozen dataclass with as_dict() for serialization.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .journal_models import JournalEvent, STAGE_CATEGORIES
from .journal_store import JournalStore


@dataclass(frozen=True)
class StageSummary:
    """Summary for a single pipeline stage."""

    stage: str
    event_count: int
    event_types: tuple[str, ...]
    repositories: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "event_count": self.event_count,
            "event_types": list(self.event_types),
            "repositories": list(self.repositories),
        }


@dataclass(frozen=True)
class OvernightSummary:
    """Aggregated summary of journal activity over a time range."""

    schema_version: str
    generated_at: str
    period_start: str | None
    period_end: str | None
    total_events: int
    event_type_counts: dict[str, int]
    stage_summaries: tuple[StageSummary, ...]
    repositories: tuple[str, ...]
    actors: tuple[str, ...]
    first_event_timestamp: str | None
    last_event_timestamp: str | None
    event_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_events": self.total_events,
            "event_type_counts": dict(self.event_type_counts),
            "stage_summaries": [s.as_dict() for s in self.stage_summaries],
            "repositories": list(self.repositories),
            "actors": list(self.actors),
            "first_event_timestamp": self.first_event_timestamp,
            "last_event_timestamp": self.last_event_timestamp,
            "event_ids": list(self.event_ids),
        }

    def render_markdown(self) -> str:
        """Render the summary as human-readable Markdown."""
        lines = [
            "# Engineering Journal — Overnight Summary",
            "",
            f"**Period:** {self.period_start or '(start)'} to {self.period_end or '(end)'}",
            f"**Total Events:** {self.total_events}",
            f"**Generated:** {self.generated_at}",
            "",
        ]

        if self.repositories:
            lines.append(f"**Repositories:** {', '.join(self.repositories)}")
            lines.append("")

        if self.event_type_counts:
            lines.append("## Event Type Breakdown")
            lines.append("")
            for etype, count in sorted(self.event_type_counts.items()):
                lines.append(f"- **{etype}**: {count}")
            lines.append("")

        if self.stage_summaries:
            lines.append("## Stage Summaries")
            lines.append("")
            for stage in self.stage_summaries:
                lines.append(f"### {stage.stage}")
                lines.append(f"- Events: {stage.event_count}")
                lines.append(f"- Types: {', '.join(stage.event_types)}")
                lines.append(f"- Repositories: {', '.join(stage.repositories) or '(none)'}")
                lines.append("")

        if self.first_event_timestamp and self.last_event_timestamp:
            lines.append("## Activity Window")
            lines.append("")
            lines.append(f"- First event: {self.first_event_timestamp}")
            lines.append(f"- Last event: {self.last_event_timestamp}")
            lines.append("")

        return "\n".join(lines)


def generate_overnight_summary(
    store: JournalStore,
    *,
    after: str | None = None,
    before: str | None = None,
    generated_at: str | None = None,
) -> OvernightSummary:
    """Generate a summary of journal events within a time range.

    Args:
        store: Open journal store.
        after: Include events with timestamp > after (ISO 8601).
        before: Include events with timestamp < before (ISO 8601).
        generated_at: Override timestamp for the summary (for determinism in tests).

    Returns:
        Frozen OvernightSummary.
    """
    events = store.list_events(after=after, before=before)

    if not events:
        return OvernightSummary(
            schema_version="1.0",
            generated_at=generated_at or _utc_now_str(),
            period_start=after,
            period_end=before,
            total_events=0,
            event_type_counts={},
            stage_summaries=(),
            repositories=(),
            actors=(),
            first_event_timestamp=None,
            last_event_timestamp=None,
            event_ids=(),
        )

    # Aggregate
    type_counts: Counter[str] = Counter()
    stage_events: dict[str, list[JournalEvent]] = {}
    repos: set[str] = set()
    actors: set[str] = set()

    for ev in events:
        type_counts[ev.event_type] += 1
        stage_events.setdefault(ev.stage, []).append(ev)
        if ev.repository:
            repos.add(ev.repository)
        actors.add(ev.actor)

    # Build stage summaries
    stage_summaries = []
    for stage_name in sorted(stage_events.keys()):
        stage_evts = stage_events[stage_name]
        stage_types = tuple(sorted({e.event_type for e in stage_evts}))
        stage_repos = tuple(
            sorted({e.repository for e in stage_evts if e.repository})
        )
        stage_summaries.append(
            StageSummary(
                stage=stage_name,
                event_count=len(stage_evts),
                event_types=stage_types,
                repositories=stage_repos,
            )
        )

    return OvernightSummary(
        schema_version="1.0",
        generated_at=generated_at or _utc_now_str(),
        period_start=after,
        period_end=before,
        total_events=len(events),
        event_type_counts=dict(sorted(type_counts.items())),
        stage_summaries=tuple(stage_summaries),
        repositories=tuple(sorted(repos)),
        actors=tuple(sorted(actors)),
        first_event_timestamp=events[0].timestamp,
        last_event_timestamp=events[-1].timestamp,
        event_ids=tuple(e.event_id for e in events),
    )


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(timezone.utc).microsecond:06d}Z"
