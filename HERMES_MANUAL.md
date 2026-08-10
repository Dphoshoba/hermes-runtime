Absolutely. Here is the kind of manual I would give to a new operator who has never used Hermes before.

# Hermes Operator Manual

## Day-to-Day Use of the Evidence-Governed Engineering Platform

**Repository:** `https://github.com/Dphoshoba/hermes-runtime`
**Current operating philosophy:** Observe → Understand → Govern → Approve → Execute → Verify → Report.

The most important rule is simple:

> **Hermes does not begin by changing code. Hermes begins by deciding whether it is safe and sensible to change code at all.**

---

# 1. What Hermes is

Think of Hermes as a careful engineering team living inside one platform.

Different parts of Hermes play different roles:

```text
Repository Readiness
        ↓
"Is it safe to work here?"

Repository Intelligence
        ↓
"What exists in this project?"

Engineering Intelligence
        ↓
"What appears to need attention?"

Engineering Governance
        ↓
"Should we actually act on it?"

Mission Recommendation
        ↓
"What job should we perform?"

Human Approval
        ↓
"Do I authorize this job?"

Mission Planner
        ↓
"How should the job be done?"

Mission Runner
        ↓
"Do the work."

Evidence Recorder
        ↓
"What actually happened?"

Independent Reviewer
        ↓
"Was the work really valid?"

Health
        ↓
"Is everything healthy?"

Mission Report
        ↓
"Tell the human the final result."
```

You should normally move through those stages in that order.

---

# 2. The golden rule

**Never start with:**

```text
Fix my project.
```

Start with:

```text
Assess this repository first.
Do not modify anything until readiness, intelligence, and governance are complete.
```

That one habit prevents a huge number of mistakes.

---

# 3. The normal daily routine

Use this sequence whenever you begin work on a repository.

1. Open the target repository.
2. Check its Git status manually.
3. Run Hermes Readiness.
4. If safe, run Repository Intelligence.
5. Generate Engineering Intelligence.
6. Run Engineering Governance.
7. Generate candidate missions.
8. Review the proposed missions yourself.
9. Approve **one** mission.
10. Execute it on an isolated branch or worktree.
11. Run tests/build/lint.
12. Review Hermes' evidence and independent review.
13. Inspect the Git diff yourself.
14. Merge only if you agree.
15. Record what happened in an operations log.

That is the standard Hermes operating cycle.

---

# 4. Morning: choose a repository

Suppose your project is:

```text
/Users/david/Desktop/inspirevoice-frontend
```

Start in Terminal:

```bash
cd /Users/david/Desktop/inspirevoice-frontend
git status
git log --oneline -5
```

You are looking for two things:

```text
Which branch am I on?

Does the repository contain uncommitted work?
```

If you see modified or untracked files, **do not panic**. Hermes can still analyze the repository, but execution may need to be blocked or isolated.

---

# 5. Step One: Repository Readiness

Run:

```bash
hermes-ready /Users/david/Desktop/inspirevoice-frontend
```

For machine-readable output:

```bash
hermes-ready --json /Users/david/Desktop/inspirevoice-frontend
```

Hermes should tell you whether autonomous execution is allowed.

A healthy result might conceptually say:

```text
Repository Ready: YES

Git repository: YES
Valid HEAD: YES
Supported language: JavaScript
Committed source: YES
Working tree: CLEAN
Execution allowed: YES
```

A blocked repository may say:

```text
Repository Ready: NO

Reason:
Significant uncommitted user work detected.

Recommendation:
Analyze only or use an isolated worktree.
```

### Exact OpenCode prompt

```text
Run Hermes Repository Readiness against the current repository.

Do not modify anything.

Report:

Repository:
Branch:
Commit:
Working Tree:
Languages:
Readiness State:
Execution Allowed:
Protected Paths:
Reasons:
Recommendation:

If execution_allowed is false, stop after reporting.
```

---

# 6. Step Two: Repository Intelligence

If readiness allows analysis, run Repository Intelligence.

Typical CLI:

```bash
hermes-repo scan \
  --repo /Users/david/Desktop/inspirevoice-frontend \
  --output-dir /tmp/inspirevoice-ri
```

Then inspect the summary:

```bash
hermes-repo summary \
  --repo /Users/david/Desktop/inspirevoice-frontend
```

Hermes is now answering:

> "What is actually here?"

For a React project it may discover:

```text
JavaScript / TypeScript

React

Components

Hooks

Routes

Imports

Fetch/API calls

package.json

Tailwind

PostCSS

Tests

Configuration

Complexity signals
```

### Exact OpenCode prompt

```text
Run Hermes Repository Intelligence against the current repository.

This stage is observational only.

Do not modify files.

Verify:

- detected languages
- frameworks
- source files
- components/modules
- dependencies
- routes
- tests
- configuration
- complexity signals
- technical-debt signals

Flag anything that appears unsupported or obviously incorrect.

Return a concise Repository Intelligence summary.
```

---

# 7. Step Three: Engineering Intelligence

Repository Intelligence says:

> "This file has 17 hooks."

Engineering Intelligence asks:

> "Does that suggest engineering work?"

Run the Engineering Intelligence stage against the generated RI artifact.

Conceptually:

```bash
hermes-engineering scan ...
```

Then:

```bash
hermes-engineering findings ...
```

or:

```bash
hermes-engineering summary ...
```

Now Hermes may produce:

```text
Finding:
High hook concentration

Evidence:
src/App.js
17 hooks
threshold: 5

Severity:
Low/Medium

Recommendation:
Consider reducing component responsibility.
```

### Exact OpenCode prompt

```text
Run Engineering Intelligence using the Repository Intelligence artifact.

Do not modify the repository.

For every finding report:

Finding ID:
Category:
Severity:
Confidence:
Affected File:
Evidence:
Recommendation:

Reject any finding that cannot be traced to actual repository evidence.
```

---

# 8. Step Four: Engineering Governance

This is where Hermes critiques its own recommendations.

Run:

```bash
hermes-governance scan ...
```

Then:

```bash
hermes-governance approved ...
```

Hermes may decide:

```text
APPROVED

APPROVED_WITH_NOTES

NEEDS_MORE_EVIDENCE

DEFERRED

REJECTED
```

This is important.

A recommendation is **not work merely because Engineering Intelligence produced it**.

### Exact OpenCode prompt

```text
Run Engineering Governance against the current Engineering Intelligence artifact.

Do not execute anything.

For each recommendation report:

Recommendation:
Decision:
Evidence Quality:
Architecture Impact:
Risk:
Rationale:

Only recommendations with sufficient evidence should be eligible for mission generation.
```

---

# 9. Step Five: Generate candidate missions

Now Hermes converts approved recommendations into possible engineering jobs.

Run:

```bash
hermes-recommend generate ...
```

Then:

```bash
hermes-recommend summary ...
```

You might receive:

```text
Mission:
Reduce App.js complexity

Status:
DRAFT

Originating Finding:
FINDING-001

Risk:
Moderate

Priority:
6.2

Evidence:
src/App.js uses 17 hooks.
```

**Nothing should execute yet.**

### Exact OpenCode prompt

```text
Generate draft missions only from governance-approved recommendations.

Do not approve them.

Do not enqueue them.

Do not execute them.

For each draft mission show:

Mission ID:
Title:
Objective:
Originating Findings:
Evidence:
Affected Files:
Estimated Risk:
Estimated Effort:
Prerequisites:
```

---

# 10. The human approval point

This is where **you** become the boss.

Ask yourself:

```text
Do I actually want this change?

Do I understand why Hermes wants it?

Is the evidence convincing?

Are the target files safe to touch?
```

Approve one mission only.

For example:

```bash
hermes-recommend approve <mission-id>
```

### Exact OpenCode prompt

```text
Review the proposed Hermes missions as a human engineering lead.

Do not approve anything automatically.

Recommend exactly one mission that is:

- evidence-backed
- low risk
- narrowly scoped
- reversible
- easy to validate

If none qualify, say:

NO SAFE MISSION AVAILABLE.
```

---

# 11. Planning the approved mission

Now Hermes Planner decides how the mission should be performed.

Conceptually:

```bash
hermes-plan validate mission.json
```

Then:

```bash
hermes-plan build mission.json --output plan.json
```

You should see tasks and dependencies.

For example:

```text
Task A
Extract interface

Task B
Update import
depends on Task A

Task C
Run TypeScript validation
depends on Task B
```

### Exact prompt

```text
Take the approved Hermes mission and run Mission Planner.

Do not execute yet.

Return:

Mission:
Validation Result:
Tasks:
Dependencies:
Capabilities Required:
Constraints:
Risk:
Planned Files:
Validation Commands:

Stop if the mission plan exceeds its approved scope.
```

---

# 12. Execution should happen in isolation

This is critical.

Do not let Hermes experiment directly on `main`.

Use:

```text
hermes/<mission-name>
```

or a Git worktree.

Example:

```bash
git worktree add \
  /tmp/my-project-hermes \
  -b hermes/mission-001
```

Hermes should then work inside:

```text
/tmp/my-project-hermes
```

not your original working directory.

---

# 13. Declare the permitted change before execution

One of the most important safety improvements we built was **diff scope validation**.

Before Hermes edits anything, say:

```text
Allowed existing files:

src/example.ts

Allowed new files:

src/types.ts

Maximum files changed:
2

Maximum insertions:
40

Maximum deletions:
20

No other files may change.
```

### Exact prompt

```text
Before execution, declare an explicit Git diff scope.

Allowed existing files:
<paths>

Allowed new files:
<paths or NONE>

Maximum changed files:
<number>

Maximum insertions:
<number>

Maximum deletions:
<number>

Do not execute if the mission cannot remain inside this scope.
```

---

# 14. Execute the mission

Now—and only now—Hermes may work.

The execution pipeline becomes:

```text
Mission
↓
Planner
↓
Queue
↓
Runner
↓
Evidence
↓
Review
↓
Health
↓
Report
```

### Exact prompt

```text
Execute the approved Hermes mission using the existing Hermes execution pipeline.

Do not broaden scope.

Do not make opportunistic improvements.

After execution:

- run relevant tests
- run build where configured
- run lint/type checks where configured
- compare actual Git diff with declared scope
- verify original repository remains unchanged
- produce evidence
- run independent review
- generate mission report

Do not commit unless all required validation succeeds.
```

---

# 15. After execution: trust Git more than the report

This lesson came directly from our Chrono Fracture pilot.

Always check:

```bash
git status
git diff --stat
git diff
```

And if there is a commit:

```bash
git show --stat HEAD
git show HEAD
```

If Hermes says:

```text
2 lines changed
```

but Git says:

```text
848 lines added
```

**Git wins.**

Do not merge.

---

# 16. Testing your application

Hermes tests are only one part of the story.

For the target project, use whatever tests the project already provides.

For a JavaScript project that might be:

```bash
npm test
npm run build
npm run lint
```

For Python:

```bash
pytest
```

For TypeScript:

```bash
npx tsc --noEmit
```

Only use commands actually supported by the project.

---

# 17. Testing Hermes itself

When you change Hermes, go to the Hermes repository:

```bash
cd ~/Downloads/hermes-runtime-v0.3-runtime
```

Run the complete test suite:

```bash
python -m pytest -q
```

Or:

```bash
pytest -q
```

A focused test might be:

```bash
pytest tests/test_readiness.py -q
```

or:

```bash
pytest tests/test_js_scanner.py -q
```

Then run everything before committing.

Your present benchmark is roughly:

```text
988 passing tests
```

based on the latest operating milestone you've shared.

---

# 18. How to use Hermes with a log file

This is where things get especially useful.

Suppose your application logs:

```text
ERROR
ModuleNotFoundError: foo
```

Do **not** simply tell OpenCode:

```text
Fix this error.
```

Use:

```text
Analyze the attached log using Hermes engineering principles.

Stage 1:
Identify the observed error only.

Stage 2:
Locate repository evidence associated with the error.

Stage 3:
Determine likely root cause.

Stage 4:
Generate an Engineering Intelligence finding.

Stage 5:
Run governance against the proposed fix.

Stage 6:
If approved, generate a DRAFT mission.

Do not modify code yet.

Return:

Observed Error:
Affected Component:
Repository Evidence:
Likely Root Cause:
Confidence:
Recommended Fix:
Governance Decision:
Draft Mission:
```

Then approve if it makes sense.

---

# 19. Can Hermes automatically fix every log error?

**No—and it shouldn't.**

There are three broad cases.

### Case A — Hermes can probably fix it

For example:

```text
Incorrect import

Missing internal configuration

Type error

Broken test

Small code defect

Invalid function usage
```

If Hermes can observe the code, prove the cause, propose a narrow fix, and validate it, then yes—it can potentially fix it.

### Case B — Hermes may help but cannot fully fix it

Example:

```text
AWS service unavailable

database credentials missing

API key expired

third-party endpoint down
```

Hermes can identify the cause and possibly change configuration, but it may need human credentials or access.

### Case C — Hermes should refuse

Example:

```text
The log is ambiguous.

There isn't enough evidence.

Fixing it requires touching protected user work.

The repository is not ready.

The proposed repair exceeds the allowed scope.
```

The correct Hermes outcome is then:

```text
NEEDS_MORE_EVIDENCE

or

NO SAFE MISSION AVAILABLE
```

That is success.

---

# 20. Your daily OpenCode master prompt

If you want one prompt you can paste most mornings, use this:

```text
Act as the Hermes operator for this repository.

Use the repository as the source of truth.

Follow the full Hermes operating sequence:

1. Repository Readiness
2. Repository Intelligence
3. Engineering Intelligence
4. Engineering Governance
5. Mission Recommendation

Stop at the human approval boundary.

Do not modify anything yet.

Report:

Repository:
Branch:
Commit:
Working Tree:
Readiness:
Supported Languages:
Frameworks:
Top Findings:
Governance Decisions:
Draft Missions:
Risks:
Protected User Work:
Recommended Mission:

If no safe evidence-backed mission exists, report:

NO SAFE MISSION AVAILABLE.
```

---

# 21. Master prompt after you approve a mission

Paste:

```text
I approve mission <MISSION-ID>.

Execute only this mission.

Before execution:

- create an isolated branch/worktree
- preserve the source repository
- declare the permitted diff scope
- confirm target files are not protected user work

Then run:

Mission Planner
→ Work Queue
→ Mission Runner
→ Evidence
→ Independent Review
→ Health
→ Mission Report

Run all appropriate project validation.

Compare actual Git diff against declared mission scope.

Do not commit if validation fails.

Return:

Mission:
Branch:
Files Changed:
Actual Diff:
Tests:
Build:
Lint/Type Check:
Evidence:
Independent Review:
Health:
Mission Report:
Commit:
Recommendation:

APPROVE FOR HUMAN REVIEW
or
DO NOT MERGE.
```

---

# 22. End-of-day routine

At the end of the day, ask:

```text
Prepare today's Hermes Operations Log entry.

Include:

Date:
Repository:
Readiness Outcome:
Findings:
Mission Proposed:
Mission Approved:
Mission Executed:
Files Changed:
Tests:
Review Outcome:
Merged:
Blocked:
Safety Intervention:
False Positives:
Lessons Learned:
Potential Hermes Improvement:

Do not propose a new Hermes feature unless the same need has appeared repeatedly or is supported by verified operational evidence.
```

That creates the evidence base that should guide future Hermes development.

---

# 23. How a normal successful day should look

```text
9:00
Open repository

9:05
hermes-ready

9:10
Repository Intelligence

9:15
Engineering Intelligence

9:20
Governance

9:25
Review candidate missions

9:30
Approve one

9:35
Create isolated worktree

9:40
Execute

10:00
Tests/build/lint

10:10
Evidence + Independent Review

10:15
Human Git diff review

10:20
Merge or reject

End of day
Record Operations Log
```

Sometimes the entire correct result will instead be:

```text
09:00 Repository assessed

09:03 Hermes says:

NO SAFE MISSION AVAILABLE.

Done.
```

That's perfectly healthy.

---

# 24. Three rules I would print beside the computer

```text
1. Never let Hermes touch code before readiness and governance.

2. Never trust a mission report without checking the actual Git diff.

3. Hermes refusing to act is sometimes the best possible result.
```

That's the core operating philosophy of the platform you've built.

**Confidence: High.**
