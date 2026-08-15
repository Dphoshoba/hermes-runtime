from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evosia.supervisor import AtomicJsonStateStore, ExecutionSupervisor, SupervisorState


class Clock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "EVOS"
    governance = repo / "governance"
    governance.mkdir(parents=True)
    (governance / "autonomous_execution_contract.md").write_text("# Contract\n", encoding="utf-8")
    return repo


def test_run_cycle_writes_report_and_state_without_mutating_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    output = tmp_path / "report"
    supervisor = ExecutionSupervisor(
        repository=repo,
        output_dir=output,
        artifacts=["governance/autonomous_execution_contract.md"],
        interval_seconds=0,
        clock=Clock(),
    )

    result = supervisor.run_cycle()

    assert result.exit_code == 0
    assert Path(result.report_json).exists()
    assert Path(result.report_markdown).exists()
    state = json.loads((output / "supervisor-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "QUIESCENT"
    assert state["cycle_count"] == 1
    after = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert after == before


def test_supervisor_runs_multiple_cycles_and_stops_at_budget(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    output = tmp_path / "report"
    sleeps: list[float] = []
    supervisor = ExecutionSupervisor(
        repository=repo,
        output_dir=output,
        artifacts=["governance/autonomous_execution_contract.md"],
        interval_seconds=0.25,
        sleeper=sleeps.append,
        clock=Clock(),
    )

    exit_code = supervisor.run(max_cycles=3)

    assert exit_code == 0
    state = json.loads((output / "supervisor-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED"
    assert state["stop_reason"] == "MAX_CYCLES"
    assert state["cycle_count"] == 3
    assert len(list((output / "cycles").iterdir())) == 3
    assert sleeps == [0.25, 0.25]


def test_stop_file_prevents_first_cycle(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    output = tmp_path / "report"
    stop_file = output / "STOP"
    stop_file.parent.mkdir(parents=True)
    stop_file.write_text("stop\n", encoding="utf-8")
    supervisor = ExecutionSupervisor(
        repository=repo,
        output_dir=output,
        stop_file=stop_file,
        sleeper=lambda _: None,
        clock=Clock(),
    )

    assert supervisor.run(max_cycles=2) == 0
    state = json.loads((output / "supervisor-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "STOPPED"
    assert state["stop_reason"] == "STOP_FILE"
    assert state["cycle_count"] == 0


def test_atomic_state_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = AtomicJsonStateStore(path)
    expected = SupervisorState(
        schema_version="1",
        status="QUIESCENT",
        repository="/repo",
        output_dir="/out",
        cycle_count=4,
        last_cycle_started_at_utc="2026-01-01T00:00:00+00:00",
        last_cycle_finished_at_utc="2026-01-01T00:00:01+00:00",
        last_exit_code=0,
        last_mission_status="Observation Complete",
        stop_reason=None,
    )

    store.save(expected)

    assert store.load() == expected
    assert not list(tmp_path.glob("*.tmp"))
