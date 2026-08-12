# Validation Evidence Provenance Policy

**Status:** Enforced (post Cycle 7 Provenance Repair)
**Applies to:** All controlled-beta scans feeding governance-validation datasets
**Scope:** Operational evidence vs. Strict reproducible validation evidence

---

## 1. Why this policy exists

During the Cycle 7 Governance Promotion Readiness Validation, the frozen
review dataset (`cycle7_frozen_review_set.json`) was found to carry **only
repository names** — no `scan_id`, no `commit_sha`, no `provider`, no
`repository_id`, and (for one repository) an incorrect name. The Enterprise
database held **no** Cycle 7 scan lineage: `scan_jobs`, `findings`, and
`operator_feedback` contained only seed/demo data. One repository
(`cognikid_app`) could not be tied to an exact Cycle 7 commit.

This made strict, independent reproduction of historical governance evidence
dependent on manual reconstruction and left a class of findings
potentially unreproducible. This policy prevents recurrence.

---

## 2. Two classes of evidence

### 2.1 Operational evidence
Evidence used for live engineering recommendations, mission suggestions, and
daily operations. It must be current and useful, but it is allowed to be
tied only loosely to exact historical identity (e.g. "scanned repo X at
roughly HEAD").

Operational evidence may enter the running system without the full strict
provenance set below. It is **not** eligible to become strict
calibration/holdout evidence.

### 2.2 Strict reproducible validation evidence
Evidence used to calibrate, promote, or reject a Governance candidate (e.g.
the Cycle 7 frozen review set, any Cycle 8 holdout). It MUST be reproducibly
reconstructable by an independent operator from first principles:

```
repository identity  (provider + identifier + remote/local canonical)
        AND
scan UUID            (persisted scan record)
        AND
exact commit SHA     (the commit the scan observed)
        AND
finding UUID         (stable per-finding identifier)
        AND
affected path        (exact file/module the finding references)
```

Without all five, the finding is **operational only**.

---

## 3. Provenance status enum

Every finding in a validation dataset is assigned exactly one status:

| Status | Meaning |
|---|---|
| `EXACT_RECONSTRUCTED` | Repo identity known, exact commit available, finding + path reproduce exactly |
| `EXACT_COMMIT_AVAILABLE` | Repo identity + commit known, but full metric reproduction not yet verified |
| `PARTIALLY_RECONSTRUCTED` | Repo + commit known, but an affected path/metric is wrong or missing |
| `IDENTITY_MISMATCH` | The repository name in the dataset does not resolve to a verifiable identity |
| `COMMIT_UNKNOWN` | Repo identity known, but no exact Cycle 7 commit can be proven |
| `UNRECONSTRUCTABLE` | The finding cannot be tied to source state at all |

---

## 4. Provenance quality gate — `VALIDATION_EVIDENCE_REPRODUCIBLE`

A finding MAY enter a **frozen governance-validation dataset** only if all of:

- `repository_db_uuid` present
- `provider` present
- `repository_identifier` present
- `remote_url` / local canonical identity present
- `scan_uuid` present
- `branch` present
- `commit_sha` present
- `finding_uuid` present
- `affected_path` present
- `human_adjudication_id` present
- `classification_timestamp` present

If **any** required field is missing/unpersisted, the finding is routed to:

```
EXCLUDE_FROM_STRICT_VALIDATION
```

It remains operational evidence but must not be used as calibration/holdout
evidence.

---

## 5. Mandatory persisted fields (going forward)

Before any controlled-beta scan may contribute validation evidence, the scan
pipeline MUST persist, and the export MUST carry automatically:

```
repository_db_uuid
provider
repository_identifier
remote_url / local canonical identity
scan_uuid
branch
exact commit_sha
finding_uuid
affected_path
human adjudication ID
classification timestamp
```

No manual reconstruction should ever be required again.

---

## 6. Additive reconstruction convention

When historical evidence lacks provenance, do **not** rewrite the original
frozen dataset or its hash. Instead produce an additive artifact:

```
<dataset>_provenance_v2.json
```

that references the original file and hash, adds the reconstructed identity,
and records explicit `MISSING` / `NOT_PERSISTED` / `UNRESOLVED` states rather
than invented values.

---

## 7. Recorded Cycle 7 defects (for traceability)

| Defect code | Class | Summary |
|---|---|---|
| `CYCLE7_SCAN_LINEAGE_PERSISTENCE_GAP` | HIGH | Enterprise DB had no Cycle 7 scan_jobs/findings/feedback; only seed data |
| `FROZEN_DATASET_SELF_HASH_INCONSISTENT` | MEDIUM | `metadata.dataset_hash` inside the frozen file did not match the file's actual SHA-256 |
| `COGNIKID_NAME_MISMATCH` | MEDIUM | Manifest labeled the repo `cognikid-web`; the Cycle 7 dataset used `cognikid_app` (a different repository) |
| `INSPIREVOICE_PATH_DEFECT` | MEDIUM | Frozen affected paths (`frontend-backend-temp/...`, `frontend-old/...`) do not exist at baseline; actual path is `Frontend/src/App.js` |
| `COGNIKID_COMMIT_UNKNOWN` | MEDIUM | `cognikid_app` has only 3 commits (all 2025-11-12); exact Cycle 7 commit unprovable; `ccd1fd51` recorded as CANDIDATE only |

---

## 8. Enforcement

Enforced by `tests/test_cycle7_provenance.py` (Additive Provenance Regression
Suite). New validation datasets must pass the same lineage/mismatch/hash
checks before promotion.

---

## 9. Safety invariants preserved

- Original frozen dataset hash is preserved (bytes unaltered).
- Production Governance unchanged.
- No target repositories modified.
- Enrichment not begun until provenance is resolved per repo.
