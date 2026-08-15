"""CLI for Human Review Queue — classify and inspect findings.

Usage:
    hermes-review list [--repository ID] [--severity SEV] [--unreviewed]
    hermes-review show FINDING-ID
    hermes-review classify FINDING-ID CLASSIFICATION [--notes NOTE] [--operator NAME]
    hermes-review summary
    hermes-review export [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root -> import enterprise.*


def _get_db():
    import os
    os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:///./hermes_enterprise.db")
    from enterprise.database import SessionLocal
    return SessionLocal()


def cmd_list(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import build_review_queue
    db = _get_db()
    try:
        result = build_review_queue(
            db,
            repository_id=args.repository,
            severity=args.severity,
            reviewed=None if not args.unreviewed else False,
            limit=args.limit,
        )
        for item in result["items"]:
            status = item["current_adjudication"] or "PENDING"
            ctx = item["file_context"]
            scan_short = (item.get("scan_id") or "N/A")[:8]
            commit_short = (item.get("commit_sha") or "N/A")[:8]
            print(f"  {item['finding_id']:20s}  {item['repository_name']:20s}  {item['severity']:10s}  {ctx:15s}  scan={scan_short}  commit={commit_short}  {status}")
        print(f"\n  Total: {result['total']}  Showing: {len(result['items'])}")
        return 0
    finally:
        db.close()


def cmd_show(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import (
        classify_file_context, infer_observation_status, infer_concern_status,
        infer_actionability_status, _extract_line_count, compute_exceedance_ratio,
        classify_exceedance_tier,
    )
    from enterprise.models import Finding, Repository
    db = _get_db()
    try:
        finding = db.query(Finding).filter(Finding.id == args.finding_id).first()
        if not finding:
            print(f"Finding {args.finding_id} not found")
            return 1

        repo = db.query(Repository).filter(Repository.id == finding.repository_id).first()
        from enterprise.models import ScanJob
        scan = db.query(ScanJob).filter(
            ScanJob.repository_id == finding.repository_id,
            ScanJob.status == "completed",
        ).order_by(ScanJob.completed_at.desc()).first()
        ctx = classify_file_context(finding.module or "")
        lc = _extract_line_count(finding)
        er = compute_exceedance_ratio(lc, 300) if lc else None
        meta = finding.metadata_json or {}

        print(f"Finding:       {finding.id}")
        print(f"Scan ID:       {scan.id if scan else 'N/A'}")
        print(f"Commit SHA:    {scan.commit_sha if scan else 'N/A'}")
        print(f"Repository:    {repo.name if repo else 'UNKNOWN'}")
        print(f"Severity:      {finding.severity}")
        print(f"Category:      {finding.category}")
        print(f"Title:         {finding.title}")
        print(f"Module:        {finding.module or 'N/A'}")
        print(f"File Context:  {ctx}")
        print(f"Line Count:    {lc or 'N/A'}")
        print(f"Exceedance:    {er} ({classify_exceedance_tier(er) if er else 'N/A'})")
        print(f"Observation:   {infer_observation_status(finding)}")
        print(f"Concern:       {infer_concern_status(finding, ctx)}")
        print(f"Actionability: {infer_actionability_status(finding, ctx, er)}")
        print(f"Governance:    {meta.get('governance_decision', {}).get('decision', 'N/A')}")
        print(f"  Rationale:   {meta.get('governance_decision', {}).get('rationale', '')}")

        from enterprise.services.review_service import get_adjudications_for_finding
        adjs = get_adjudications_for_finding(db, finding.id)
        # Effective classification = most recent by reviewed_at (append-only
        # history; reclassification appends, does not overwrite).
        adjs_sorted = sorted(adjs, key=lambda a: a.reviewed_at) if adjs else []

        # Evidence & Risk Gate authority distinction (Post Cycle 8) — kept
        # SEPARATE so machine/legacy/suppression states never masquerade as
        # human actionability.
        print(f"Gate State:    {finding.gate_state or 'N/A (not yet gated)'}")
        print(f"Legacy Dec.:   {finding.legacy_decision or 'N/A'}  (advisory only; not human ACTIONABLE)")
        supp = next((a for a in adjs_sorted if getattr(a, 'policy_suppressed', False)), None)
        if supp:
            print(f"Suppressed:    YES  rule={getattr(supp, 'suppression_rule_id', None)} "
                  f"v{getattr(supp, 'suppression_rule_version', None)} by={supp.operator}")
            print(f"               (deterministic policy; distinct from human NOT_ACTIONABLE)")
        else:
            print("Suppressed:    no")
        if adjs_sorted:
            latest = adjs_sorted[-1]
            eligible = (latest.classification == "ACTIONABLE")
            print(f"Human Class.:  {latest.classification} (by {latest.operator})")
            print(f"Mission Elig.: {'YES' if eligible else 'no'} "
                  f"(true ONLY with human ACTIONABLE)")
        else:
            print("Human Class.:  none (pending human review)")
            print("Mission Elig.: no")

        if adjs_sorted:
            print(f"\nAdjudications ({len(adjs_sorted)}):")
            for a in adjs_sorted:
                print(f"  [{a.classification}] by {a.operator} at {a.reviewed_at}")
                if a.operator_notes:
                    print(f"    Note: {a.operator_notes}")
        else:
            print("\nNo adjudications yet.")

        return 0
    finally:
        db.close()


def cmd_classify(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import create_adjudication, emit_finding_reviewed
    db = _get_db()
    try:
        operator = args.operator  # required by argparse (--operator required=True)
        adj = create_adjudication(
            db,
            finding_id=args.finding_id,
            classification=args.classification,
            operator=operator,
            notes=args.notes,
        )
        emit_finding_reviewed(
            db,
            finding_id=args.finding_id,
            repository_id=adj.repository_id,
            classification=args.classification,
            operator=operator,
            notes=args.notes,
            adjudication_id=adj.id,
        )
        print(f"Adjudicated {args.finding_id} as {args.classification}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        db.close()


def cmd_summary(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import get_review_summary, get_pending_count
    db = _get_db()
    try:
        summary = get_review_summary(db)
        summary["pending_review"] = get_pending_count(db)
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        db.close()


def cmd_export(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import build_review_queue, get_review_summary
    db = _get_db()
    try:
        data = {
            "summary": get_review_summary(db),
            "queue": build_review_queue(db, limit=1000),
        }
        print(json.dumps(data, indent=2, default=str))
        return 0
    finally:
        db.close()


def cmd_suppressions(args: argparse.Namespace) -> int:
    from enterprise.services.review_service import list_suppressions
    db = _get_db()
    try:
        rows = list_suppressions(db, repository_id=args.repository)
        if not rows:
            print("No policy suppressions recorded.")
            return 0
        for r in rows:
            print(f"  {r['finding_id']:20s}  rule={r['suppression_rule_id']}  "
                  f"v{r['rule_version']}  by={r['operator']}  at={r['reviewed_at']}")
        print(f"\n  Total suppressions: {len(rows)}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Human Review Queue CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List findings for review")
    p_list.add_argument("--repository", help="Filter by repository ID")
    p_list.add_argument("--severity", help="Filter by severity")
    p_list.add_argument("--unreviewed", action="store_true", help="Only unreviewed")
    p_list.add_argument("--limit", type=int, default=50)

    p_show = sub.add_parser("show", help="Show finding details")
    p_show.add_argument("finding_id", help="Finding ID")

    p_classify = sub.add_parser("classify", help="Classify a finding (human authority)")
    p_classify.add_argument("finding_id", help="Finding ID")
    p_classify.add_argument("classification", help="Classification (human-only authority)",
                            choices=["USEFUL", "FALSE_POSITIVE", "NOT_ACTIONABLE",
                                     "NEEDS_MORE_EVIDENCE", "DUPLICATE", "UNKNOWN",
                                     "ACTIONABLE"])
    p_classify.add_argument("--notes", help="Operator notes")
    p_classify.add_argument("--operator", required=True,
                            help="Operator name (REQUIRED — human authority identity)")

    p_suppressions = sub.add_parser("suppressions", help="List deterministic policy suppressions")
    p_suppressions.add_argument("--repository", help="Filter by repository ID")

    p_summary = sub.add_parser("summary", help="Show review summary")

    p_export = sub.add_parser("export", help="Export review data")
    p_export.add_argument("--json", action="store_true")

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "classify": cmd_classify,
        "suppressions": cmd_suppressions,
        "summary": cmd_summary,
        "export": cmd_export,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
