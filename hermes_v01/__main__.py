from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .utils import sha256_file

DEFAULT_ARTIFACTS = [
    "governance/autonomous_execution_contract.md",
    "governance/capability_specification_template.md",
    "governance/constitution.md",
    "governance/engineering_playbook.md",
    "governance/adr_policy.spec.md",
]

@dataclass(frozen=True)
class ToolStatus:
    tool: str
    status: str
    reason: str

@dataclass(frozen=True)
class Finding:
    artifact: str
    inspection_method: str
    evidence: str
    classification: str
    sha256: str | None = None
    size_bytes: int | None = None

@dataclass(frozen=True)
class Report:
    runtime: str
    runtime_version: str
    generated_at_utc: str
    repository: str
    mission_status: str
    tool_status: list[ToolStatus]
    findings: list[Finding]
    compliance_assessment: str

def inspect_repository(repo: Path, artifacts: list[str]) -> Report:
    now = datetime.now(timezone.utc).isoformat()
    if not repo.exists() or not repo.is_dir():
        reason = f"Repository directory is not accessible: {repo}"
        return Report(
            "Hermes", __version__, now, str(repo), "Inspection Failed",
            [ToolStatus("read-only filesystem inspection", "Inspection Failed", reason)],
            [Finding(str(repo), "Path.exists() and Path.is_dir()", reason, "Unverified")],
            "Deferred: repository inspection did not begin.",
        )

    findings: list[Finding] = []
    for relative in artifacts:
        target = repo / relative
        try:
            if target.exists():
                stat = target.stat()
                digest = sha256_file(target) if target.is_file() else None
                evidence = f"PRESENT\t{target}\ttype={'file' if target.is_file() else 'directory'}\tsize={stat.st_size}"
                findings.append(Finding(relative, "Path.exists(), Path.stat(), SHA-256 for files", evidence, "Verified Present", digest, stat.st_size))
            else:
                findings.append(Finding(relative, "Path.exists()", f"MISSING\t{target}", "Verified Missing"))
        except OSError as exc:
            findings.append(Finding(relative, "read-only filesystem inspection", f"Inspection error: {type(exc).__name__}: {exc}", "Unverified"))

    return Report(
        "Hermes", __version__, now, str(repo), "Observation Complete",
        [ToolStatus("read-only filesystem inspection", "Succeeded", "Requested artifacts were inspected without repository modification.")],
        findings,
        "Existence classified. Content-level governance compliance is deferred until governance rules are supplied and inspected.",
    )

def render_markdown(report: Report) -> str:
    lines = [
        "# Hermes EVOS Verification Report", "",
        f"- Runtime: `{report.runtime} {report.runtime_version}`",
        f"- Generated: `{report.generated_at_utc}`",
        f"- Repository: `{report.repository}`",
        f"- Mission Status: **{report.mission_status}**", "",
        "## Tool Status", "", "| Tool | Status | Reason |", "|---|---|---|",
    ]
    for item in report.tool_status:
        lines.append(f"| {item.tool} | {item.status} | {item.reason} |")
    lines += ["", "## Verification Record", "", "| Artifact | Inspection Method | Evidence | Classification |", "|---|---|---|---|"]
    for f in report.findings:
        lines.append(f"| `{f.artifact}` | {f.inspection_method} | `{f.evidence.replace('|', r'\|')}` | **{f.classification}** |")
    lines += ["", "## Compliance Assessment", "", report.compliance_assessment, "", "## Human Governance Required", "", "Approval, remediation, lifecycle transitions, and governance changes require a separate human decision.", ""]
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only EVOS governance artifact validation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact", action="append", dest="artifacts")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = inspect_repository(repo, args.artifacts or DEFAULT_ARTIFACTS)

    (output_dir / "verification-report.json").write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
    (output_dir / "verification-report.md").write_text(render_markdown(report), encoding="utf-8")
    print(output_dir / "verification-report.md")
    print(output_dir / "verification-report.json")
    return 0 if report.mission_status == "Observation Complete" else 2

if __name__ == "__main__":
    raise SystemExit(main())
