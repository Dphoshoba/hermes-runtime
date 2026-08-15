# Controlled Beta Phase 6 — Deeper Call-Graph & Repository-Local Evidence Mining

**Program:** CONTROLLED_BETA_PHASE_6_DEEPER_CALLGRAPH_MINING
**Authorization:** Operator CONTINUATION AUTHORIZATION (read-only deeper mining)
**Prior:** Phase 5 HUMAN_CONTEXT_REQUIRED_FOR_FURTHER_PROGRESS (commit `ed676aa…`)
**Governance baseline:** EVIDENCE_RISK_GATE · **EVOSIA version:** 1.3.0
**Autonomous execution:** DISABLED · **Repository mutation:** DISABLED

## Authorization scope

Operator authorized the remaining safe read-only avenue: deeper call-graph and
repository-local evidence mining. Explicitly does NOT expand execution/mutation
authority. Mission #1 stays APPROVE_FOR_FUTURE_EXECUTION but NON-EXECUTABLE;
#2–#5,#7–#13 stay DEFERRED; #6 stays NEEDS_REFINEMENT (path now resolved).

## Evidence avenues attempted (all read-only, provenance-preserving)

1. **Extraction at exact recorded commits** via `git archive` into /tmp (no
   target-repo mutation, no worktrees/branches/commits in target repos).
2. **Real Repository Intelligence scan** (`scan_repository`) on all 3 cohorts:
   faithtech 570 source files / 3042 imports; inspirevoice 5 source files;
   cognikid 20 files.
3. **Real import-graph construction** for 11 faithtech deferred targets:
   inbound callers, outbound callees, entry-point/route reachability.
4. **Repository-local architectural intent**: 15 docs in faithtech (incl.
   ADVANCED_ROADMAP, DEPLOYMENT_GUIDE, API_DOCUMENTATION), 1 in cognikid, 0 in
   inspirevoice. Explicit intent comments in 5 sampled target files: **0**.
5. **Discriminating-subcohort scan** of the 829 remaining findings.
6. (Carried from Phase 5) bug/fix correlation (0), test relationships.

## Material evidence gained

- **Call-graph (OBSERVED, real import edges):**
  - #3 (analytics.tsx): **inbound=27** — confirmed high fan-in via real graph
    (prior grep "174 caller files" was string-match inflated; real imports=27).
  - #10/#11 (Profile.tsx / Profile.js): inbound=1 each (real graph, not 174).
  - Most targets: inbound 0–2, outbound 6–12 → weakly coupled, corroborates DEFER.
  - #4 (ResetPassword.js): **route_reachable=True** — production-reachable.
  - #6 (App.js, inspirevoice): 225 LOC, 5 imports, 1 commit, EXISTS_AT_COMMIT.
- **Architectural intent:** docs exist but establish NO per-module isolation-by-
  design rationale; 0 intent comments in targets. Gap remains human-dependent.
- **Discriminating subcohort:** 5/829 findings are non-structural
  (Dependencies ×2, Public API ×2, Configuration ×1) — the only decision-
  distinguishing cluster in the remaining cohort.

## Did any disposition change?

**No.** The deeper evidence *corroborates* the existing DEFER/NEEDS_REFINEMENT
dispositions; it does not reverse any. No NME was converted to ACTIONABLE or
NOT_ACTIONABLE (human actionability authority remains exclusive). No mission
was approved for execution.

## NME candidates ready for human re-adjudication

The 5 discriminating subcohort findings (still WEAK/UNKNOWN, evidence deficiency
NOT materially resolved by this pass, but distinct from structural noise):
- FINDING-125 (faithtech) Unpinned runtime dependencies: axios, cors, express
- FINDING-031 (inspirevoice) Unpinned deps: @google-cloud/text-to-speech, axios, cors, dotenv, express
- FINDING-052 (inspirevoice) Missing configuration: .gitignore
- FINDING-766 (faithtech) Large public API surface (963 symbols)
- FINDING-103 (inspirevoice) Large public API surface (82 symbols)

Recommended (not auto-applied): surface these 5 for **human re-adjudication** —
they are the only remaining findings where repository-local evidence quality is
materially stronger than the structural-coupling mass.

## NME remaining genuinely context-dependent

The other **824/829** remaining findings are uniformly WEAK-evidence / ISOLATED
coupling — architectural intent, runtime criticality, and business impact cannot
be established from repository-local evidence. These are genuinely human/business-
context dependent (this is a VALID EXPERIMENTAL RESULT, not a failure).

## Deferred missions whose evidence materially changed

**None changed disposition.** Evidence added (call-graph corroboration) is
supporting, not decision-reversing. #3's real fan-in (27) actually *raises*
regression exposure, reinforcing DEFER per the operator's stated bar.

## Mission #6 final refinement status

RESOLVED path (`Frontend/src/App.js` @ `83f1c009…`, 225 LOC, 5 imports, exists
at commit). Disposition remains **NEEDS_REFINEMENT** (operator re-decision
pending) — not auto-approved.

## Decision-discriminating cohort/subcohort findings

Only the 5-item config/dependency/public-API subcohort is decision-discriminating.
The 824 structural-coupling findings are NOT decision-discriminating; expanding
review over them would reproduce the same NME/DEFER outcome.

## Metrics

- Evidence-resolution rate (NME material): **64.5%** (40/62, from Phase 4);
  Phase 6 added call-graph *corroboration* but converted 0 NME.
- unsafe_automation_rate = **0.0**
- mission_traceability = **100%**
- non-ACTIONABLE leakage = **0**
- journal_integrity = **PASS**
- canonical backend suite = **1434 passed** (no source change in Phase 6)
- defects_found = 0 · defects_resolved = 0
- operator_interventions_required = 1 (recommend surfacing the 5 NME for re-adjudication)
- mission_executions = 0 · target_repository_mutations = 0 · push/tag/PR = 0

## Termination

Exhaustive read-only analysis confirms architectural intent, runtime criticality,
and business impact are not establishable from repository-local evidence. Per the
authorization's TERMINATION RULE this is a valid experimental result. No further
materially useful read-only avenue remains within this envelope.

## Recommended next authority decision

**HUMAN_CONTEXT_REQUIRED_FOR_FURTHER_PROGRESS** (re-affirmed with deeper evidence).
To progress, supply: (a) human re-adjudication of the 5 discriminating NME;
(b) architectural-intent / business-impact context; or (c) an approved non-
destructive runtime/behavioral telemetry source. The Evidence & Risk Gate remains
a safe, correct, low-burden Controlled Beta governance baseline.
