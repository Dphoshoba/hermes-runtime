# M9 — Real User Usability Test Protocol

## Purpose

Determine whether a genuinely non-technical user can safely operate EVOSIA
Guided Mode from first run through understanding and approving a prepared
change, without requiring Git, terminal, repository, governance, or
software-engineering knowledge.

## Participant Eligibility

**Include:**
- Comfortable with ordinary software (web browsers, email, documents)
- No professional software-engineering requirement

**Exclude:**
- Current EVOSIA contributors
- People who have seen this protocol before
- Anyone coached on the EVOSIA workflow prior to the session

Target: 5–8 participants.

## Facilitator Rules

### Say ONLY:

> "EVOSIA has reviewed this project. Work out whether anything needs your
> attention and decide what you want EVOSIA to prepare."

### DO NOT:
- explain the interface
- explain Git, repositories, branches, commits
- explain EVOSIA governance (gate states, mission eligibility, journal)
- point at buttons or features
- explain what "Prepare" or "Approve" means
- correct misunderstandings during the task unless safety requires it
- lead the participant toward any answer

### DO:
- record where the participant hesitates
- record every question they ask
- record every intervention you make
- record technical terminology that confuses them
- record exact Task 9 and Task 10 responses verbatim

## Task Sequence

| # | Task | Observe |
|---|------|---------|
| 1 | Open EVOSIA | Can they find their way in? |
| 2 | Select a project | Do they understand project selection? |
| 3 | Start analysis | Do they know what "Analyze" means? |
| 4 | Explain what EVOSIA found | Can they interpret the summary? |
| 5 | Respond to one context question | Can they answer in their own words? |
| 6 | Inspect one recommendation | Do they understand what's proposed? |
| 7 | Inspect one prepared change | Can they explain what would change? |
| 8 | Decide whether to approve | Can they make a decision? |
| 9 | **"Has EVOSIA changed your project?"** | Critical: must say **No** |
| 10 | **"What would happen if you approved?"** | Must **not** say deploy/execute |

## Authority-Comprehension Acceptance Criteria

**PASS:** participant correctly answers both:
- Task 9: "Has EVOSIA changed your project?" → **No** (or equivalent)
- Task 10: "What would happen if you approved?" → does **not** imply deployment/execution

**FAIL:** participant believes EVOSIA has already modified the project, or
that approval would deploy/execute the change.

Any FAIL constitutes an **AUTHORITY_UX_DEFECT** requiring remediation before
any future execution authority.

## Recording Rules

1. Use `M9_PARTICIPANT_TEMPLATE.json` for each participant.
2. Record observations **verbatim** where possible.
3. Do **not** infer success — record what you saw and heard.
4. Mark `completed: false` if the participant could not finish without
   intervention; record the intervention.
5. Record `duration_seconds` for each task where feasible.

## Privacy Guidance

- Use participant IDs only (P01, P02, ...).
- Do not record names, emails, or other personally identifying information.
- Store completed records in `validation/usability/participants/`.
- Treat completed records as containing potentially sensitive feedback.

## PASS / FAIL Rules

| Measure | PASS threshold |
|---------|---------------|
| task_completion_rate | ≥ 80% |
| authority_comprehension_rate | 100% |
| critical_usability_failures | 0 |

**Overall PASS:** all three thresholds met.

**Overall FAIL:** any threshold not met → remediate and retest.

## After Testing

1. Aggregate results into `M9_RESULTS_SUMMARY_TEMPLATE.json`.
2. If PASS: proceed to M10.
3. If FAIL: remediate authority-UX defects, then retest.
