# M8 Participant 1 — Second Retest Protocol

Commit under test: `3828d41eb41904c3db219e6ac4676c7331e845bb`
Prior evidence preserved: M8-P1-001 (RESOLVED), M8-P1-002 (improved), M8-P1-003/004/005/006 (remediated, unverified by human)

---

## Participant Message (send exactly this)

> We've made further improvements based on your feedback — including showing what EVOSIA looked at and making the buttons respond properly. Please open EVOSIA again and continue using it as you naturally would. Please tell us whenever something is confusing, unclear, unexpected, or you are unsure what to do next.

Do NOT explain the new features. Do NOT point at the review-scope section, the
"Found in" text, the finding→mission bridge, or the fixed buttons. The
participant must discover them unaided.

---

## Pre-Session Checklist

- [ ] Railway deployment serving commit `3828d41`
- [ ] Fixture RESET → SEED → VERIFY completed (`git_initialized: true`, 4 findings, 1 actionable, 1 DRAFT mission)
- [ ] Pre-session target repository hash captured
- [ ] Participant credentials still valid; screen-share consented
- [ ] Observation sheet ready (P01 record)

---

## Prior-Finding Re-Observation (do NOT prompt — observe only)

| Prior finding | What to watch for |
|---|---|
| P1-003 scope | Does the participant find "What EVOSIA inspected" unprompted? Do they ask "what folders?" again? |
| P1-004 evidence | Can they say where a problem was found without opening Technical details? |
| P1-005 controls | Do they click "Not now" / "Needs clarification"? Does anything appear dead? |
| P1-006 bridge | Do they connect a proposed work item to its concern? Ask Task 10 naturally. |

---

## Critical Acceptance Tasks (verbatim capture)

- Task 9: "Has EVOSIA changed your project?"
- Task 10: "What would happen if you approved preparation?"

Record answers verbatim BEFORE any classification. Do not confirm correctness.

---

## Stop Conditions

If any control appears dead, any state hangs indefinitely, or the participant
believes a change was made to their project: stop that journey, preserve the
observation and screenshots, and report before remediation.

No repository changes during the session. No Participant 2.
