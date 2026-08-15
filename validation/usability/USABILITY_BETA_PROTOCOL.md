# Guided Mode Usability Beta Protocol (M8)

## Status

REAL_USER_USABILITY = NOT_OBSERVED

Real non-technical users are not available for this pass. This protocol defines the
test infrastructure and acceptance criteria so that when users become available,
the beta can be run consistently.

## Test Protocol

### Participants

- Target: competent computer users who do NOT rely on Git / terminal / software
  architecture knowledge.
- Minimum recommended: 5 users.

### Scenario

The participant is asked to operate EVOSIA on a real project (pre-loaded fixture).

### Task Sequence

1. **Connect / open a project.**
2. **Understand EVOSIA' project summary** — explain what EVOSIA found.
3. **Identify an issue needing attention.**
4. **Answer a missing-context question.**
5. **Understand a proposed mission.**
6. **Approve PREPARATION** of a change.
7. **Review a prepared change.**
8. **Correctly understand that the change has NOT been deployed / executed.**

### Measurements

| Metric | How collected |
|--------|---------------|
| task_completion_rate | % of tasks completed without facilitator help |
| time_to_first_useful_result | seconds from connect to first actionable summary |
| context_question_completion | % of context questions answered |
| mission_decision_accuracy | % whose stated decision matches the actual control |
| authority_comprehension_rate | % who correctly identify that approve != execute/deploy |
| accidental_execution_assumption_rate | % who incorrectly believe a change was executed |
| help_required_rate | % who needed facilitator explanation of EVOSIA itself |
| abandonment_rate | % who quit before completing all tasks |

### Acceptance Question

Can a competent non-technical person operate EVOSIA safely without another
person explaining EVOSIA itself?

- PASS: >= 80% task completion, 0% accidental-execution assumption.
- NOT_OBSERVED: real users unavailable.

## Fixture

A pre-scanned repository with:
- 1 security-relevant finding (hardcoded credential).
- Several structural findings (large modules, isolated modules).
- 2-3 context questions (intentional isolation, dependency choices).
- 1 DRAFT mission.
