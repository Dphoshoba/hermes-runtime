"""D5+D6 — reset and reseed the disposable M8 fixture on the live deployment."""
import os
os.environ.setdefault("EVOSIA_DATABASE_URL", "sqlite:////app/data/evosia_m8.db")

from enterprise.database import SessionLocal  # noqa: E402
from enterprise.services.m8_fixture import reset_m8_fixture, seed_m8_fixture, verify_m8_fixture  # noqa: E402

db = SessionLocal()
print("RESET:", reset_m8_fixture(db))
print("SEED:", seed_m8_fixture(db))
result = verify_m8_fixture(db)
print("VERIFY status:", result.get("status"))
print("git_initialized:", result.get("git_initialized"))
print("findings:", len(result.get("findings", [])))
missions = result.get("missions", [])
print("missions:", [(m.get("mission_id"), m.get("status")) for m in missions])
db.close()
