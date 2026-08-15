# GOOGLE AI STUDIO — EVOSIA BUILD PROMPT

Build a complete, production-quality web application called **EVOSIA**.

---

## 1. PRODUCT IDENTITY

**Application name:** EVOSIA  
**Descriptor:** Autonomous Intelligence for Safe, Governed Execution  
**Parent organization:** Echoes & Visions  
**Platform:** EVOS  

Do NOT invent an expansion of the word EVOSIA. It is the name of the autonomous intelligence and execution agent.

Do NOT use the word "Hermes" anywhere in the public-facing product. The previous internal name must not appear.

The application is the public-facing interface for EVOSIA — the governed autonomous intelligence system within EVOS, under Echoes & Visions.

---

## 2. PRODUCT PURPOSE

EVOSIA reviews projects, finds issues, explains them in plain language, proposes work, and can prepare changes in an isolated workspace — but it never executes, merges, deploys, or modifies production without explicit human approval at each authority boundary.

The core workflow is:

**Review → Understand → Prepare → Approve → Execute**

Each step is a distinct authority boundary. Preparing a change is NOT the same as executing it. Approving preparation does NOT mean the project has been modified.

The product must be usable by a non-technical person who wants AI assistance with their project without needing to understand Git, repositories, CLI commands, runtime protocols, governance architecture, or software engineering terminology.

Technical architecture exists underneath the experience but must not dominate the user interface.

---

## 3. TARGET USER

Design primarily for **non-technical users** — competent computer users who do NOT rely on Git, terminal, software architecture knowledge, or engineering terminology.

The user may be:
- A project owner who wants to understand what EVOSIA found in their project
- Someone who needs to decide whether to let EVOSIA prepare a proposed change
- A person who must correctly understand whether EVOSIA has already changed their project

A secondary audience is technical users who want access to detailed evidence, technical findings, and governance data. Provide an expert/technical view as progressive disclosure, not as the default surface.

---

## 4. FIRST-RUN EXPERIENCE

When a user first opens EVOSIA, before they have selected a project, present a **first-run onboarding** experience that:

1. **Explains what EVOSIA does** in ordinary language — it reviews projects, finds things worth discussing, proposes work, and can prepare changes in a safe isolated space.

2. **Explains what EVOSIA will NOT do without permission** — it will not merge, deploy, execute, or change production. It will not act on its own.

3. **Shows the authority model plainly** — EVOSIA can inspect, explain, and propose. Preparing changes requires your approval. Executing changes is a separate boundary that is not available in this experience.

4. **Introduces the central safety question** — "Has EVOSIA changed my project?" — and states clearly that the answer is always no until you explicitly take an execution action, which is a separate step.

5. **Explains the "Needs your attention" concept** — EVOSIA may find things worth discussing. That does not mean something is broken; it means EVOSIA noticed something and wants you to decide.

6. **Provides a skip option** — the onboarding should be skippable but easy to return to.

The onboarding must use calm, confident, non-alarming language. Avoid stereotypical "AI assistant" imagery. The tone should be intelligent, clear, and trustworthy — like a careful engineering reviewer who explains things plainly.

---

## 5. MAIN APPLICATION EXPERIENCE

The primary experience is **Guided Mode** — a decision-centered, plain-language workflow. Build it as a polished single-page application with a clear step progression. Expert/technical views are available as secondary surfaces.

### 5.1 Guided Mode Flow

The Guided Mode experience follows this progression:

**Step 1 — Project Selection**
- User chooses a project via a "Choose Project" / "Open Folder" flow.
- The product discovers and validates the selected project.
- If the project is not suitable, explain the problem and next action in plain language.
- Do NOT expose raw stack traces as primary user feedback.
- After selection, EVOSIA performs a read-only analysis.

**Step 2 — Analysis (read-only)**
- One obvious primary action: "Analyze Project".
- During analysis, communicate:
  - what EVOSIA is doing
  - that analysis is read-only
  - progress/status
  - what happens next
- Analysis must NOT mutate the selected project.

**Step 3 — Summary / Overview**
- EVOSIA presents a plain-language headline summarizing the review.
- The headline format (from the existing implementation):
  - "I reviewed your project. N things examined. M worth discussing. K questions need your help. J important issue. P proposed change. 0 changes made."
- Show statistics: total examined, worth discussing, need your help, important issues, proposed changes.
- Always display a visible safety badge: "0 changes made".
- Show what EVOSIA can do at the current authority level.

**Step 4 — Needs Your Attention**
- Items that a human reviewer flagged as worth addressing.
- For each item show:
  - plain-language title
  - why it matters (one line, non-alarming)
  - category and severity
  - technical details available as expandable progressive disclosure

**Step 5 — Needs Context**
- When EVOSIA lacks enough information, ask questions a non-technical owner can reasonably answer.
- Examples of questions EVOSIA may ask:
  - "I found several modules that appear deliberately separate. Are these intentionally isolated because they perform independent jobs?"
  - "I found some modules that look large or complex. Are these intentionally built this way, or would you prefer they be simpler?"
  - "I found areas where many responsibilities seem concentrated. Is this intentional design, or could it be simplified?"
  - "I found some dependency choices that may affect reliability. Are these versions intentionally left flexible?"
  - "I found some configuration items that may be missing. Are these intentionally omitted or could they be needed?"
  - "I found code that may involve sensitive access. Is this an area where extra caution is intended?"
- For each question show:
  - the topic
  - the question
  - why EVOSIA is asking (so the user understands this is about reducing noise, not about authorizing change)
  - how many findings are affected
  - answer options including "I don't know" and "Ask someone else / later"
- Explicitly state: EVOSIA will never treat your answer as a decision to change code. Your answers help EVOSIA understand your project.

**Step 6 — Proposed Work / Mission Decision**
- Show proposed changes based on items that were flagged.
- For each proposed change show:
  - plain-language title
  - What: what the change involves
  - Why: why EVOSIA is proposing it
  - Expected benefit
  - Risk
  - What could change (scope)
  - How EVOSIA would verify
  - How to undo
  - Authority consequence statement (mandatory)
- The authority consequence statement must say something like: "Approving here permits EVOSIA to PREPARE a proposed change in an isolated workspace. It will NOT merge, deploy, or change production."
- When the user approves preparation, show a clear confirmation that:
  - the change is approved for preparation
  - EVOSIA may prepare it in an isolated workspace
  - nothing has been executed or deployed
  - the status is now "Approved for preparation"
- Show proposed work in distinct visual states:
  - DRAFT — "Proposed work"
  - APPROVED_FOR_FUTURE_EXECUTION — "Approved for preparation"
  - PREPARED — "Prepared change"

**Step 7 — Prepared Change Review**
- When a change has been prepared, show:
  - What will change
  - Why
  - Files affected
  - Expected benefit
  - Possible risk
  - How it will be verified
  - How it can be undone
- Use ordinary language first; technical diff/details may be expandable.
- Always display: "Nothing has been merged, deployed, or applied to production."

**Step 8 — Empty States**
- When nothing needs attention: show "Nothing needs your attention right now." with "EVOSIA will let you know when something changes."
- When evidence is exhausted: show "EVOSIA has inspected the available evidence and cannot draw firmer conclusions without new information."
- When no proposed work: show "No proposed work right now."

**Step 9 — Error States**
- Show a friendly error state with a "Try again" action.
- Do not expose raw error details as the primary message.

### 5.2 Navigation

Guided Mode should have a clear step navigation with chips/buttons for:
- Overview
- Needs your attention (with count badge)
- Needs context (with count badge)
- Proposed work (with count badge)

And a persistent safety badge in the header: "0 changes made".

Include a Refresh button.

### 5.3 Expert / Technical Views (secondary)

Provide access to technical/expert views as a separate section, not as the default. These are for users who want detail. Include:

- Findings detail (technical evidence, severity, category)
- Mission queue status
- Journal / activity log
- Reports
- Human review classification

These views should be clearly labeled as technical/expert and should not be required for normal operation.

### 5.4 Account & Session

- Login / sign-in flow.
- Session management with logout.
- The user should see their current authority level displayed somewhere visible.

---

## 6. CONVERSATIONAL INTELLIGENCE

EVOSIA should be able to interact with the user in plain language. Use Gemini (or equivalent) to power conversational and interpretive experiences where appropriate, but EVOSIA remains the governed system architecture — Gemini powers the conversation, not the authority model.

### 6.1 Conversational Tone

- Plain language. No jargon.
- Calm, confident, non-alarming.
- Explains technical findings in terms of:
  - what was found
  - why it matters
  - what EVOSIA recommends
  - what EVOSIA can prepare
  - what requires the user's approval
  - whether anything has actually changed

### 6.2 Conversation Principles

- EVOSIA should never imply that a project has been modified unless it actually has.
- EVOSIA should never imply that approving a recommendation means execution.
- EVOSIA should clearly distinguish between "I found this" and "I recommend this" and "I have prepared this" and "I have executed this".
- When EVOSIA does not know something, it should say so rather than guess.

### 6.3 Conversational Entry Points

- A chat/conversation interface where the user can ask EVOSIA questions about their project.
- EVOSIA should be able to explain findings, answer "why does this matter?", and describe proposed changes in plain language.
- The conversation should complement, not replace, the structured Guided Mode flow.

---

## 7. AUTHORITY UX — MANDATORY

This is the most important part of the product. The UI must make it impossible, as far as reasonably achievable, for a non-technical user to confuse **Prepared** with **Executed**.

### 7.1 Authority Levels

Display the current authority level clearly. Use these levels:

- **Level 0 — Observe:** EVOSIA inspects and explains. No changes proposed.
- **Level 1 — Recommend:** EVOSIA proposes work. No changes prepared.
- **Level 2 — Prepare:** EVOSIA creates changes in an isolated workspace. Nothing deployed.

### 7.2 Action State Communication

Every important action must communicate:
- current state
- proposed action
- authority required
- whether project mutation has occurred

### 7.3 The Central Safety Distinction

The product must make these distinctions unmistakable:

- **ANALYZE** does not modify the project.
- **RECOMMEND** does not modify the project.
- **PREPARE CHANGE** does not modify the project.
- **APPROVE FOR FUTURE EXECUTION** does not execute the change.
- **EXECUTE CHANGE** would be a separate authority boundary and is NOT available in this experience.

### 7.4 Visual Authority States

Use distinct visual badges for:
- DRAFT — "Proposed work" (yellow/amber)
- APPROVED_FOR_FUTURE_EXECUTION — "Approved for preparation" (green)
- PREPARED — "Prepared change" (green)

### 7.5 Safety Badge

Always display a persistent safety badge: "0 changes made" (or the current count of actual changes applied). This badge must be visible in the header throughout the Guided Mode experience.

### 7.6 Approval Confirmation

When the user approves preparation, the confirmation message must state:
- what was approved
- that EVOSIA may now prepare the change in an isolated workspace
- that nothing has been executed or deployed
- the new status

### 7.7 Execution Boundary

If the product ever supports an "execute" action, it must be:
- clearly separated from preparation
- require explicit, separate authority
- show a clear confirmation that execution is about to happen
- never be implied by approval

For this build, do NOT implement execution. The execution boundary is noted as a future authority level that is not available.

### 7.8 Authority Comprehension Test

The design must target 100% comprehension of execution authority. A first-time non-technical user must be able to correctly answer:

- "Has EVOSIA changed my project?" → No.
- "What will happen if I approve this?" → EVOSIA will prepare the change in an isolated workspace; nothing will be merged, deployed, or applied to production.

These questions correspond to the M8 authority-comprehension gate. Design the UI so that the correct answer is obvious.

---

## 8. SAFETY

Carry forward EVOSIA's established governance principles. Do not weaken existing safety boundaries.

### 8.1 Core Safety Rules

- Do not fabricate successful execution.
- Do not claim project mutation without evidence.
- Do not represent simulated results as real execution.
- Do not introduce autonomous repository mutation merely because the platform supports agentic capabilities.
- Preparing a change must never be represented as executing it.
- Approval must not falsely imply that a project has already been modified.

### 8.2 What EVOSIA Does NOT Do

- Never auto-approves missions.
- Never auto-enqueues missions.
- Never auto-executes missions.
- Never bypasses human approval.
- Never modifies production without explicit, separate authority.

### 8.3 Evidence Integrity

- Evidence records are immutable once published.
- The product should reflect that findings are based on evidence, not speculation.

---

## 9. VISUAL DIRECTION

Create a **premium, calm, trustworthy** interface appropriate for **Echoes & Visions**.

### 9.1 Aesthetic

- Dark theme (deep background, elevated cards, subtle borders).
- Calm, confident typography — clean sans-serif.
- Muted color palette with a single distinctive accent.
- Avoid stereotypical futuristic AI imagery (no glowing brains, no extreme sci-fi, no "AI assistant" robot avatars).
- The product should communicate: intelligence, clarity, trust, human authority, governance, confidence without intimidation.

### 9.2 Color Palette

Use a palette similar to:
- Background: deep near-black (#0f1117 or similar)
- Card background: slightly elevated dark (#1a1d27 or similar)
- Border: subtle dark gray (#2e3142 or similar)
- Text: light neutral (#e4e6f0 or similar)
- Muted text: softer neutral (#8b8fa3 or similar)
- Accent: a calm indigo/violet (#6366f1 or similar) — use sparingly as the distinctive brand accent
- Success/green: calm green (#22c55e or similar)
- Warning/amber: warm amber (#eab308 or similar)
- Danger/red: restrained red (#ef4444 or similar) — use sparingly, not alarmingly

### 9.3 EVOSIA Branding

- Use "EVOSIA" prominently as the product identity.
- The logo/wordmark should feel premium and distinctive — not a generic AI icon.
- Echoes & Visions may appear as a subtle brand reference in the footer or about section.

### 9.4 Components

- Cards: elevated, subtle border, rounded corners.
- Badges: distinct colors for status (green for approved/prepared, amber for draft/proposed, red reserved for actual problems).
- Buttons: clear hierarchy — primary action distinct from secondary.
- Safety badge: persistent, visually distinct, always visible in Guided Mode.
- Progressive disclosure: technical details hidden behind "show technical details" expanders.

---

## 10. TECHNICAL INTEGRATION

### 10.1 Existing Contracts Are Authoritative

Where the application needs backend functionality, use the existing EVOSIA API contracts. The existing backend behavior remains authoritative. Do not silently replace the EVOSIA runtime with Gemini-generated business logic.

### 10.2 Existing API Endpoints (Guided Mode)

The following backend endpoints exist and should be used:

- `GET /api/guided/summary` — project summary (headline, stats, authority level, safety status)
- `GET /api/guided/needs-attention` — items worth discussing
- `GET /api/guided/needs-context` — context questions
- `GET /api/guided/missions` — proposed work
- `POST /api/guided/missions/{mission_id}/approve-preparation` — approve preparation
- `POST /api/guided/missions/{mission_id}/prepare` — prepare change
- `GET /api/guided/permission` — current authority level
- `GET /api/guided/context` — project context
- `POST /api/guided/context` — add context
- `DELETE /api/guided/context/{context_id}` — remove context
- `GET /api/guided/prepared-changes` — list prepared changes

### 10.3 Existing Full-Stack API Endpoints

The existing full application also has:

- `GET /api/health` — health check
- `POST /api/auth/register` — register user
- `POST /api/auth/login` — login (returns JWT)
- `GET /api/auth/me` — current user
- `GET/POST /api/repositories` — list/create repositories
- `GET/PATCH/DELETE /api/repositories/{id}` — repository CRUD
- `POST /api/repositories/{id}/sync` — sync GitHub metadata
- `GET/POST /api/scans` — list/create scan jobs
- `GET /api/scans/{id}` — scan status + timings
- `POST /api/scans/{id}/start` — start a pending scan
- `POST /api/scans/{id}/cancel` — cancel a queued/running scan
- `POST /api/scans/{id}/retry` — retry a failed/cancelled scan
- `GET /api/scans/{id}/history` — scan stage history
- `GET /api/dashboard/stats` — aggregated statistics
- `GET /api/dashboard/activity` — recent journal activity
- `GET /api/journal` — query journal events
- `GET /api/journal/{event_id}` — single event
- `GET /api/findings` — query findings
- `GET /api/findings/{id}` — single finding
- `GET /api/missions` — query missions
- `GET /api/missions/{id}` — single mission
- `GET /api/reports` — query reports
- `GET /api/reports/{id}` — single report

### 10.4 Integration Boundaries

Where Google AI Studio needs backend functionality that cannot safely be implemented from the available repository evidence, instruct it to create a clearly separated integration boundary rather than inventing APIs. Gemini may power conversational or interpretive experiences where appropriate, but EVOSIA remains the governed system architecture.

### 10.5 Technology Stack

Build with:
- **Frontend:** React + TypeScript (the existing GUI uses React Router, a custom API client with JWT auth, and a dark theme CSS design system)
- **Backend:** FastAPI-style Python (the existing backend uses FastAPI routers, SQLAlchemy models, JWT + bcrypt auth, SQLite for development / PostgreSQL for production)
- **API:** REST, JSON
- **Auth:** JWT Bearer tokens, stored in localStorage (key: `evosia_token` — note: the existing codebase uses `hermes_token` as the localStorage key, which should be renamed to `evosia_token` in the new build)

---

## 11. ACCEPTANCE CRITERIA

The generated application must allow a first-time non-technical user to answer correctly:

1. **"Has EVOSIA changed my project?"** → No.
2. **"What will happen if I approve this?"** → EVOSIA will prepare the change in an isolated workspace; nothing will be merged, deployed, or applied to production.

These questions correspond directly to the M8 authority-comprehension gate.

### 11.1 Design Target

- 100% comprehension of execution authority.
- 0% accidental-execution assumption.
- The safety distinction between Prepared and Executed must be unmistakable.

### 11.2 What Success Looks Like

A competent non-technical person can:
1. Open EVOSIA.
2. Select a project.
3. Start analysis.
4. Understand what EVOSIA found.
5. Respond to one context question.
6. Inspect one recommendation.
7. Inspect one prepared change.
8. Decide whether they would approve it.
9. Correctly explain in their own words whether EVOSIA has changed their project.
10. Correctly explain what would happen if they approved the recommendation.

without another person explaining EVOSIA itself.

---

## 12. OUT OF SCOPE FOR THIS BUILD

- Autonomous execution of changes.
- Deployment to production.
- Repository mutation without explicit human authority.
- Any feature that would weaken the Prepare ≠ Execute distinction.
- Any feature that would imply execution has occurred when it has not.

---

## 13. BUILD INSTRUCTION SUMMARY

Build a complete, polished, production-quality web application that:

1. Presents EVOSIA as a calm, trustworthy, premium product under Echoes & Visions.
2. Has a first-run onboarding that explains what EVOSIA does and does not do.
3. Has a Guided Mode experience with: project selection, read-only analysis, summary overview, needs-attention review, context questions, proposed work with approval, prepared change review, and clear empty/error states.
4. Has a persistent "0 changes made" safety badge throughout Guided Mode.
5. Has distinct visual states for DRAFT, APPROVED_FOR_FUTURE_EXECUTION, and PREPARED.
6. Has a clear authority level display (Observe / Recommend / Prepare).
7. Has a conversational interface powered by Gemini for plain-language interaction.
8. Has expert/technical views as progressive disclosure.
9. Uses the existing EVOSIA API contracts as the authoritative backend integration.
10. Targets 100% authority comprehension — a non-technical user must never confuse Prepared with Executed.
11. Does NOT implement autonomous execution or repository mutation.

---

# REPOSITORY EVIDENCE USED

The following files and features from the certified EVOSIA repository (`/Users/david/Downloads/hermes-runtime-v0.3-runtime`, baseline `1d350e1`, version `1.3.0`) were inspected to produce this specification:

| Source | What was derived |
|--------|-----------------|
| `ARCHITECTURE.md` | EVOSIA Runtime architecture, module structure, data flow, pipeline execution, mission lifecycle, mission recommendation integration (approval boundary, state transitions, traceability), Engineering Command Center architecture (React + TypeScript frontend, FastAPI backend, SQLAlchemy ORM, SQLite/PostgreSQL), API endpoints, scan lifecycle, database schema, running instructions |
| `validation/PRODUCT_ACCEPTANCE_REPORT.md` | M0–M13 milestone status: M0 canonical baseline (PASS), M1 Guided Mode E2E (PASS, 8/8 tests), M2 First-Run Onboarding (PASS), M3 Context Collection (PASS), M4 Disposable Repository (PASS), M5 Prepared Change E2E (PASS), M6 Change Explanation UX (PASS), M7 Authority Comprehension UX (PASS), M8 Real User Beta (NOT_OBSERVED), M9 Authority Comprehension Gate (NOT_OBSERVED), M10 Expert Mode (PASS), M11 Install Friction (PASS, documented), M12 Safety Regression (PASS), M13 Execution Readiness (NOT_READY). Invariants: unsafe_automation_rate=0.0, mission_traceability=100%, non_actionable_leakage=0, NME_leakage=0, target_repository_mutations=0, mission_executions=0, production_mutations=0, journal_integrity=PASS |
| `validation/EXECUTION_READINESS_ASSESSMENT.md` | Authority model criteria (machine ACTIONABLE impossible, machine NOT_ACTIONABLE impossible, non-ACTIONABLE leakage=0, human adjudication sole authority, Finding ACTIONABLE != mission approval, Mission approval != execution, Execution != deployment, distinct boundaries), Prepared-Change reliability (isolated workspace, no production deployment, no direct target-repo mutation, bounded scope, rollback representation, validation status tracking, human adjudication traceability), Sandbox isolation, Validation quality (journal integrity, mission traceability, prepared-change validation), Mission traceability (Finding→adjudication→mission chain), Permission comprehension (authority level display, enumerated levels, consequence statements), Non-technical user comprehension (Guided Mode UX built, plain-language labels, progressive disclosure, real-user testing NOT_OBSERVED) |
| `CONTROLLED_BETA_GUIDE.md` | Day-to-day operator workflow (add repository, run scan, check readiness, review findings, review evidence, inspect governance decision, perform human review classification, approve/reject findings, generate/approve/reject missions, review execution reports), safe operations, forbidden operations, Evidence & Risk Gate governance model (machine routes findings but never authorizes actionability; every actionability decision requires human adjudication; legacy GOVERNANCE_APPROVED is replay-only and advisory) |
| `validation/usability/USABILITY_BETA_PROTOCOL.md` | M8 test protocol: participant profile (competent computer users without Git/terminal/software architecture knowledge, minimum 5), scenario (operate EVOSIA on real project with pre-loaded fixture), task sequence (connect project, understand summary, identify issue needing attention, answer context question, understand proposed mission, approve preparation, review prepared change, correctly understand change NOT deployed/executed), measurements (task_completion_rate, time_to_first_useful_result, context_question_completion, mission_decision_accuracy, authority_comprehension_rate, accidental_execution_assumption_rate, help_required_rate, abandonment_rate), acceptance question and PASS/FAIL criteria (>=80% task completion, 0% accidental-execution assumption), fixture description (security finding, structural findings, context questions, DRAFT mission) |
| `enterprise/routers/guided.py` | Guided Mode backend router (651 lines): plain-language label mappings (GATE_LABELS, MISSION_STATUS_LABELS, AUTHORITY_LEVEL_LABELS), response models (GuidedSummaryResponse, NeedsAttentionItem, ContextQuestion, GuidedMission, ApprovePreparationRequest, ContextAddRequest, QuestionAnswerRequest, ContextItemRequest, ContextItemResponse), helper functions (_plain_title, _why_it_matters, _build_headline, _human_classification, _cluster_topic, _question_for_topic, _why_ask_for_topic), endpoints (/summary, /needs-attention, /needs-context, /missions, /missions/{id}/approve-preparation, /permission, /context, /context/{id} DELETE, /missions/{id}/prepare, /prepared-changes), authority level 1 (Recommend), permissions object (can_observe, can_recommend, can_prepare=false, can_propose=false, can_execute=false, execution_enabled=false, mutation_enabled=false), safety badge "0 changes made" in headline |
| `enterprise-ui/src/pages/GuidedModePage.tsx` | Guided Mode frontend page (555 lines): GuidedSummary, NeedsAttentionItem, ContextQuestion, GuidedMission TypeScript interfaces, GuidedStep type ('loading'|'summary'|'needs-attention'|'needs-context'|'mission-decision'|'prepared-change'|'no-action-needed'|'evidence-exhausted'|'error'), main page component with step progression, GuidedLayout with header (safety badge "0 changes made", Refresh button), nav chips (Overview, Needs your attention, Needs context, Proposed work with count badges), SummaryView (headline, stats, action buttons, authority info card listing what EVOSIA can/cannot do), NeedsAttentionView (items with plain_title, why_it_matters, category, severity, technical details expandable), NeedsContextView (questions with topic, question, why_asking, affects count, answer options including "I don't know" and "Ask someone else / later", explicit statement that answers don't authorize change, technical details expandable), MissionDecisionView (proposed work with What/Why/Expected benefit/Risk/What could change/How EVOSIA would verify/How to undo, authority consequence statement, approve preparation button, status badges, "Nothing executed yet" confirmation), NoActionNeededView, EvidenceExhaustedView, UsabilityTestEntry (dev-only beta testing tools affordance), PreparedChangeFallback |
| `enterprise-ui/src/lib/api.ts` | API client (89 lines): apiFetch with JWT Bearer auth, getToken/setToken/clearToken (localStorage key: hermes_token — should be renamed to evosia_token in new build), guidedApi wrapper, guidedClient object with summary, needsAttention, needsContext, missions, approvePreparation, prepareChange, preparedChanges, permission, context (list/add/remove) methods |
| `enterprise-ui/src/App.tsx` | React Router app (84 lines): AuthContext with login/logout, ProtectedRoute, routes for /, /repositories, /repositories/:repoId, /scans, /journal, /findings, /missions, /reports, /review, /guided |
| `enterprise-ui/src/components/Layout.tsx` | Layout component with sidebar navigation (Dashboard, Repositories, Scans, Journal, Findings, Missions, Reports, Review, Guided Mode) |
| `enterprise-ui/src/index.css` | Dark theme CSS design system (1008 lines): CSS custom properties (--bg, --bg-card, --bg-hover, --border, --text, --text-muted, --accent, --accent-hover, --green, --red, --yellow, --orange), layout (sidebar, main), cards, stats grid, tables, badges (green/red/yellow/blue/gray/orange), auth container, form elements, guided mode styles (guided-page, guided-loading, guided-spinner, guided-error, guided-layout, guided-header, guided-safety-badge, safety-dot, guided-nav, nav-chip, chip-count, guided-content, guided-summary, summary-hero, summary-subtitle, summary-stats, summary-stat, stat-number, stat-label, summary-actions, all-clear, authority-info, authority-list, needs-attention, attention-card, why-matters, card-meta, technical-details, needs-context, context-card, question, why-asking, affects, answer-options, answer-btn, selected, mission-decision, mission-card, mission-header, mission-body, mission-field, authority-statement, highlight, mission-actions, no-action, evidence-exhausted, usability-test-entry) |
| `enterprise-ui/src/components/FirstRunOnboarding.tsx` | First-run onboarding component (87 lines): 5-step progressive walkthrough, plain-language explanation of what EVOSIA can/cannot do, safety messaging, skip option |
| `enterprise-ui/src/components/ProjectSelection.tsx` | Project selection component (112 lines): "Choose Project / Open Folder" flow, discovers and validates selected project, explains problems in plain language, no raw stack traces |
| `enterprise-ui/src/components/AnalysisProgress.tsx` | Analysis progress component (102 lines): shows what EVOSIA is doing during analysis, read-only indicator, progress/status |
| `enterprise-ui/src/components/PreparedChangeView.tsx` | Prepared change view component (94 lines): shows What will change, Why, Files affected, Expected benefit, Possible risk, How it will be verified, How it can be undone, ordinary language first with technical details expandable |
| `enterprise/models/__init__.py` | SQLAlchemy models including ProjectContext and PreparedChange: ProjectContext (id, repository_id, topic, key, value, source, actor, scope, confidence, is_current, created_at, provenance), PreparedChange (id, mission_id, repository_id, title, description, status, workspace_path, affected_files, validation_status, created_by, created_at, updated_at, provenance, metadata_json), plus Finding, FindingAdjudication, Mission, Repository, User, MissionFinding and other existing models |
| `validation/GUIDED_OPERATIONS_MANIFEST.json` | Program manifest: HERMES_GUIDED_OPERATIONS_AND_CONTROLLED_EXECUTION (note: should be renamed to EVOSIA_GUIDED_OPERATIONS_AND_CONTROLLED_EXECUTION in new build), Hermes v1.3.0 (should be EVOSIA v1.3.0), EVIDENCE_RISK_GATE, baseline_commit 82229d83 |
| `validation/EXECUTION_READINESS_ASSESSMENT.md` | (see above — also referenced in §2) |
| `validation/usability/M9_REAL_USER_TEST_PROTOCOL.md` | M9 real user test protocol (106 lines): participant eligibility, facilitator instructions, no-coaching rule, Tasks 1-10, intervention recording rules, authority-comprehension acceptance criteria, PASS/FAIL rules, privacy guidance, verbatim observation recording instructions |
| `validation/usability/M9_FACILITATOR_QUICK_CARD.md` | M9 facilitator quick card (54 lines): what to say only ("EVOSIA has reviewed this project. Work out whether anything needs your attention and decide what you want EVOSIA to prepare."), what NOT to do (explain interface, explain Git, explain governance, point at buttons, explain what Prepare means, correct misunderstandings unless safety requires), what to record (hesitations, questions, interventions, confusing terminology, exact Task 9 and Task 10 responses), final questions verbatim |
| `validation/usability/M9_PARTICIPANT_TEMPLATE.json` | M9 participant template JSON (94 lines): schema with participant_id, test_timestamp, hermes_version→evosia_version, hermes_commit→evosia_commit, tasks 1-10 each with completed/assistance_required/duration_seconds/observed_behavior/participant_response, time_to_first_analysis_seconds, technical_blockers, operator_interventions, user_confidence, usability_defects, critical_usability_failures, task_9_response_verbatim, task_10_response_verbatim, authority_comprehension (understands_project_not_changed, understands_approval_not_execution, pass), overall_result — all observational values null |
| `validation/usability/M9_RESULTS_SUMMARY_TEMPLATE.json` | M9 results summary template (28 lines): aggregation fields (real_users_tested, task_completion_rate, authority_comprehension_rate, median_time_to_first_analysis, technical_blockers, operator_interventions, usability_defects_found, usability_defects_resolved, critical_usability_failures, confidence_distribution), authority_gate (participants_correct_task_9, participants_correct_task_10, participants_passing_both, total_participants, rate), decision (REAL_USER_USABILITY, EXECUTION_AUTHORITY_COMPREHENSION, READY_FOR_M10) — all null until observed |
| `validation/usability/M9_FACILITATOR_QUICK_CARD.md` | (see above — also referenced in §2) |
| `validation/usability/test_m9_artifact_validator.py` | M9 artifact validator (227 lines): 8 tests validating participant record structure (participant_id present, test_timestamp present, tasks 1-10 present, task_9 and task_10 verbatim responses present, authority_comprehension fields present, no fabricated observations in blank templates, no invalid authority_comprehension values) — validates evidence structure only, never infers human success |
| `validation/usability/participants/` | Directory with README and blank participant records P01–P05 (all containing only participant_id, no fabricated results) |

## Identity Notes for the Build

The following items from the existing codebase use the old "Hermes" naming and must be renamed to "EVOSIA" in the new build:

- localStorage key `hermes_token` → `evosia_token`
- `hermes_version` fields → `evosia_version`
- `hermes_commit` fields → `evosia_commit`
- Program manifest `HERMES_GUIDED_OPERATIONS_AND_CONTROLLED_EXECUTION` → `EVOSIA_GUIDED_OPERATIONS_AND_CONTROLLED_EXECUTION`
- Any internal references to "Hermes" as the system identity → "EVOSIA"

The following items refer to the external Nous Research Hermes Agent technology and must remain as "Hermes Agent" where they appear (though they should not appear in the public-facing product):

- References to the Hermes Agent CLI, package names, or installation instructions
- Attribution to Nous Research for the Hermes Agent technology

In the new EVOSIA application, the public identity is always EVOSIA, under Echoes & Visions, on the EVOS platform. Hermes Agent (the third-party Nous Research technology) should not appear in the user-facing product.
