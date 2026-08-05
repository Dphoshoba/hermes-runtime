from pathlib import Path
from hermes_v01.__main__ import inspect_repository

def test_present_and_missing(tmp_path: Path) -> None:
    repo = tmp_path / "EVOS"
    governance = repo / "governance"
    governance.mkdir(parents=True)
    (governance / "autonomous_execution_contract.md").write_text("# Contract\n", encoding="utf-8")
    report = inspect_repository(repo, [
        "governance/autonomous_execution_contract.md",
        "governance/constitution.md",
    ])
    by_artifact = {f.artifact: f for f in report.findings}
    assert by_artifact["governance/autonomous_execution_contract.md"].classification == "Verified Present"
    assert by_artifact["governance/constitution.md"].classification == "Verified Missing"

def test_missing_repo_is_unverified(tmp_path: Path) -> None:
    report = inspect_repository(tmp_path / "missing", ["governance/autonomous_execution_contract.md"])
    assert report.mission_status == "Inspection Failed"
    assert report.findings[0].classification == "Unverified"
