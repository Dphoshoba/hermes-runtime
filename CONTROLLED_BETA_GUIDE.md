# CONTROLLED BETA GUIDE — Hermes Enterprise

**Version:** 1.4.0
**Status:** CONTROLLED_BETA
**Trial:** Operational Validation Trial 001 — COMPLETED
**Controlled Beta:** Cycle 6 — Mission Prioritization Promoted to Production

---

## Overview

Hermes Enterprise is in controlled beta. This guide defines the day-to-day operator workflow, safe operations, forbidden operations, and known limitations.

**Critical principle:** The Controlled Beta governance baseline is the **Evidence & Risk Gate**. Governance is an evidence-and-risk *gate* — the machine routes findings (`OBSERVED`/`CORROBORATED`/`REQUIRES_REVIEW`/`INSUFFICIENT_EVIDENCE`/`DEFERRED`/`DUPLICATE`) but never authorizes actionability. Every actionability decision requires human adjudication (human `ACTIONABLE`) before a mission can be eligible; legacy Governance `APPROVED` is replay-only and advisory.

---

## Day-to-Day Operator Workflow

### 1. Add Repository

Add a repository to Hermes for scanning:

```bash
hermes-repo add <repository-path>
```

**What happens:** Repository metadata is stored. No code is modified.

### 2. Run/Read Scheduled Scan

Scans are read-only by default. Run a scan:

```bash
hermes-scan run --repo <repository-name>
```

**What happens:** Repository Intelligence, Engineering Intelligence, and Governance analysis are produced. No code is modified.

### 3. Review Readiness

Check repository readiness before deeper analysis:

```bash
hermes-readiness check --repo <repository-name>
```

**What happens:** Pre-pipeline safety gate validates the repository is scannable.

### 4. Review Findings

Review the findings produced by the scan:

```bash
hermes-engineering show --repo <repository-name>
```

**What happens:** Findings are displayed with evidence and severity.

### 5. Review Evidence

Inspect the evidence behind each finding:

```bash
hermes-evidence show --finding-id <finding-id>
```

**What happens:** Evidence references are displayed for human evaluation.

### 6. Inspect Governance Decision

View the governance decision (ADVISORY — not authoritative):

```bash
hermes-governance show --repo <repository-name>
```

**What happens:** Governance decisions are displayed with rationale. These are advisory only.

### 7. Perform Human Review Classification

Classify each finding based on your judgment:

```bash
hermes-review classify --finding-id <finding-id> --classification <USEFUL|NOT_ACTIONABLE|NEEDS_MORE_EVIDENCE|FALSE_POSITIVE|DUPLICATE>
```

**What happens:** Your classification is persisted. This is the authoritative decision.

### 8. Review Draft Missions

Review generated mission recommendations (DRAFT only):

```bash
hermes-recommend show --repo <repository-name>
```

**What happens:** Draft missions are displayed. They are NOT approved or executed.

### 9. Approve Nothing Without Human Judgment

**Do NOT approve missions based solely on Governance decisions.** Every mission requires explicit human approval after reviewing findings, evidence, and governance rationale.

### 10. Do Not Allow Automatic Execution

**Do NOT enable automatic mission execution.** All execution requires explicit human initiation.

---

## Safe Operations

The following operations are safe during controlled beta:

| Operation | Status | Notes |
|-----------|--------|-------|
| Read-only scanning | PERMITTED | No code modification |
| Repository Intelligence | PERMITTED | Static analysis only |
| Engineering Intelligence | PERMITTED | Recommendation generation |
| Governance analysis | PERMITTED | Advisory evidence |
| Mission Recommendation | PERMITTED | DRAFT only |
| Engineering Journal | PERMITTED | Audit trail |
| Human Review | PERMITTED | Authoritative classification |

---

## Forbidden Operations

The following operations are FORBIDDEN during controlled beta:

| Operation | Status | Risk |
|-----------|--------|------|
| Autonomous repository mutation | FORBIDDEN | Could break target repos |
| Automatic PR creation | FORBIDDEN | Unauthorized changes |
| Automatic merge | FORBIDDEN | Unauthorized changes |
| Automatic mission execution | FORBIDDEN | Unverified actions |
| Governance-only approval | FORBIDDEN | Over-approval risk |
| Mission execution without human review | FORBIDDEN | Safety risk |

---

## Known Limitations

### 1. Governance Over-Approval

**Status:** PRODUCTION DEFECT — variant identified but not promoted

Production Governance defaults to APPROVED when no rule matches. This produces 81.5%–100% over-approval. Variant I (default → NEEDS_MORE_EVIDENCE) eliminates over-approval but requires further validation.

**Workaround:** Mandatory human review for every finding.

### 2. USEFUL Recall Unvalidated

**Status:** VALIDATION GAP

Only 1 USEFUL finding was available in the Day 7 blind sample. The candidate Variant I deferred that finding to NEEDS_MORE_EVIDENCE. We cannot confirm whether Variant I would reject genuinely useful findings at scale.

**Workaround:** Treat all NEEDS_MORE_EVIDENCE decisions as requiring human investigation.

### 3. CONFIGURATION Governance Unvalidated

**Status:** VALIDATION GAP

No CONFIGURATION findings were available in the Day 7 blind sample. Governance behavior for configuration findings is unknown.

**Workaround:** Manually review all configuration-related findings.

### 4. Mission Traceability Incomplete

**Status:** KNOWN LIMITATION

Mission generator does not consistently populate originating finding linkage. 0% of legacy missions have explicit finding links.

**Workaround:** Trace mission provenance manually when needed.

### 5. High-Severity Governance Unvalidated

**Status:** VALIDATION GAP

No high-severity findings were available in the Day 7 blind sample.

**Workaround:** Manually review all high-severity findings.

---

## Governance Advisory Warning

**WARNING: Governance decisions are ADVISORY during controlled beta.**

- Governance APPROVED does NOT mean "safe to implement"
- Governance NEEDS_MORE_EVIDENCE does NOT mean "reject"
- Governance REJECTED does NOT mean "never consider"

Every governance decision requires human verification. Governance provides evidence; humans make decisions.

---

## Human Review Procedure

### Step 1: Review Finding

Read the finding title, description, and affected path.

### Step 2: Review Evidence

Inspect the evidence references. Verify the evidence supports the finding.

### Step 3: Check Context

Determine if the finding is in PRODUCTION, TEST, or CONFIGURATION context.

### Step 4: Classify

Assign one of:
- **USEFUL** — Finding represents a real concern worth investigating
- **NOT_ACTIONABLE** — Finding is valid but not worth acting on
- **NEEDS_MORE_EVIDENCE** — Finding requires additional investigation
- **FALSE_POSITIVE** — Finding is incorrect
- **DUPLICATE** — Finding overlaps with another

### Step 5: Record

Persist your classification using the human review CLI.

---

## Incident Reporting

If you encounter unexpected behavior:

1. Check the Engineering Journal for audit trail
2. Review the finding and governance decision
3. Document the incident in the Friction Journal
4. Classify the incident type:
   - `unexpected_behavior`
   - `safety_concern`
   - `data_integrity`
   - `performance_issue`
   - `ui_confusion`

---

## Feedback Classification

When providing feedback on findings or governance:

| Type | When to Use |
|------|-------------|
| USEFUL | Finding is valid and worth investigating |
| NOT_ACTIONABLE | Finding is valid but not worth acting on |
| NEEDS_MORE_EVIDENCE | Finding requires additional investigation |
| FALSE_POSITIVE | Finding is incorrect |
| DUPLICATE | Finding overlaps with another |
| UNKNOWN | Insufficient information to classify |

---

## Friction Reporting

When encountering usability issues:

| Type | When to Use |
|------|-------------|
| confusing_ui | Interface is unclear |
| unnecessary_clicks | Too many steps required |
| missing_information | Required information not displayed |
| unexpected_behavior | System behaves unexpectedly |
| performance_issue | System is slow or unresponsive |

---

*Guide version: 1.0*
*Trial: Operational Validation Trial 001*
*Status: CONTROLLED_BETA*
