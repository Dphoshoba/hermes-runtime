"""D4 — live M8 database audit. Read-only; prints a state table."""
import json, os
os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:////app/data/evosia_m8.db")

from enterprise.database import SessionLocal  # noqa: E402
from enterprise.models import (Repository, ScanJob, Finding, FindingAdjudication,
                               Mission, PreparedChange, ProjectContext)  # noqa: E402

db = SessionLocal()
def dump(name, q, fields):
    rows = q.all()
    print(f"== {name}: {len(rows)} ==")
    for r in rows:
        d = {}
        for f in fields:
            v = getattr(r, f, None)
            if f == "metadata_json" and v is not None:
                v = {"keys": sorted(v.keys()), "has_review_scope": "review_scope" in v}
            d[f] = str(v)[:80]
        print(json.dumps(d))

dump("Repositories", db.query(Repository), ["id", "name", "status", "created_at"])
dump("ScanJobs", db.query(ScanJob), ["id", "repository_id", "status", "created_at", "completed_at", "metadata_json"])
dump("Findings", db.query(Finding), ["id", "repository_id", "title", "status", "module", "created_at"])
dump("FindingAdjudications", db.query(FindingAdjudication), ["id", "finding_id", "classification", "created_at"])
dump("Missions", db.query(Mission), ["id", "mission_id", "repository_id", "status", "created_at"])
dump("PreparedChanges", db.query(PreparedChange), ["id", "mission_id", "repository_id", "status", "validation_status", "created_at"])
dump("ProjectContext", db.query(ProjectContext), ["id", "repository_id", "topic", "created_at"])
db.close()
