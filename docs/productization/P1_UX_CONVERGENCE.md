# P1 — Google AI Studio / Production UX Convergence

**Date:** 2026-08-30
**P1 Baseline:** `39e015937c8ec5f78114bcbd00a6198bb52876e4`
**EVOSIA Version:** 1.3.0
**Purpose:** Reconcile current production EVOSIA, the Google AI Studio build specification, and the actual Google AI Studio generated application into a canonical product experience for later implementation milestones.

---

## 1. EVIDENCE SOURCES

| Source | Type | Role |
|--------|------|------|
| Current production `enterprise-ui/` source | Repository-verified | Authoritative production implementation |
| `docs/google-ai-studio/EVOSIA_GOOGLE_AI_STUDIO_BUILD_PROMPT.md` | Repository-verified | Build specification for AI Studio prototype |
| Human visual inspection of 8 AI Studio screens | Operator-observed | Actual generated application evidence |
| `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md` | Repository-verified | P0 gap inventory and concept classification |

**Canonical rule:** The EVOSIA backend remains authoritative. The AI Studio prototype is UX/product-design reference. It is NOT an independent authority implementation, a replacement backend, or a second source of truth.

---

## 2. GOVERNING AUTHORITY BOUNDARY

P1 preserves all LA0–LA6 authority invariants:

| Invariant | Status |
|-----------|--------|
| DeviceProject authority | REVIEW_ONLY |
| ALLOWED_OPERATION_TYPES | `frozenset({"PROJECT_SCAN"})` |

For the currently certified connected-PC workflow:

| Capability | Status |
|------------|--------|
| Review | AVAILABLE |
| Understand | AVAILABLE |
| Ask Context | AVAILABLE (product concept subject to existing contracts) |
| Recommend | AVAILABLE (governed recommendation layer) |
| Prepare | NOT GRANTED through Local Agent Productization |
| Execute | NOT GRANTED |

P1 MUST NOT turn attractive prototype UI into new authority.

### Authority Equivalences Preserved

- context answer != approval
- conversation != approval
- recommendation != preparation
- approval != execution
- finding != permission to modify
- PROJECT_SCAN != preparation
- PROJECT_SCAN != execution

---

## 3. AI STUDIO SURFACE-BY-SURFACE CLASSIFICATION

### Screen 1 — Welcome / First-Run Onboarding

**Observed:**
- "Welcome to EVOSIA"
- "Autonomous Intelligence for Safe, Governed Execution"
- Explanation that EVOSIA reviews projects, explains improvements, prepares changes in isolated workspace
- Workflow: Review → Understand → Prepare → Approve → Execute (Execute visually unavailable/crossed)
- "Each step is a strict authority boundary. You are always in control."

**Production equivalent:** `FirstRunOnboarding.tsx` (5-step wizard: Welcome, What EVOSIA does, Needs your attention, Needs context, Proposed work & approval, Let's begin)

**Classification: ADAPT**

**Preserve:**
- First-run onboarding concept
- Plain-language product explanation
- Authority education ("each step is a strict authority boundary")
- Human-control emphasis
- Guided onboarding flow
- Workflow visualization

**Adapt:**
- "Autonomous Intelligence" — replace with product-appropriate descriptor that does not imply autonomous action
- "Governed Execution" — replace with language matching current authority (REVIEW_ONLY for connected-PC)
- "Prepare" in workflow — make visually clear this is a higher authority level not available for all project types
- Wording must not imply that REVIEW_ONLY connected projects possess preparation or execution authority

**Production source reference:** `FirstRunOnboarding.tsx` already implements 5-step onboarding. AI Studio adds workflow visualization and authority education. Adopt the education pattern; adapt the wording.

---

### Screen 2 — Guided Overview

**Observed:**
- Header: "DEMO PROJECT — Sample data only", "Right now: 0 changes made", "Level 1 — Recommend"
- Navigation: Overview, Needs your attention, Needs context, Proposed work, Prepared changes
- Plain-language summary: "I reviewed your project. 14 things examined. 3 worth discussing. 2 questions need your help. 1 important issue. 1 proposed change. 0 changes made."
- Metrics: Examined, Worth Discussing, Need Your Help, Important Issues, Proposed Changes, Changes Made
- Authority explanation: "Current Authority Level: Level 1 — Recommend" with "What EVOSIA Can Do Now" / "What EVOSIA Will NOT Do"
- Actions: "Analyze Project (Read-Only)", "Ask EVOSIA", "Technical View"

**Production equivalent:** `GuidedModePage.tsx` (SummaryView with headline, stats grid, authority info card, DemoModeToggle, ProvenanceBadge)

**Classification: ADOPT / ADAPT**

**Adopt:**
- Plain-language review summary format ("I reviewed your project. N things examined. M worth discussing.")
- "Right now: 0 changes made" persistent safety badge
- Explicit current authority display ("Level 1 — Recommend")
- "What EVOSIA Can Do Now" / "What EVOSIA Will NOT Do"
- Read-only analysis language
- Guided / Technical split
- Visible demo provenance ("DEMO PROJECT — Sample data only")
- Count badges on navigation chips

**Adapt:**
- Authority level naming — reconcile "Level 1 — Recommend" with production authority model
- "Analyze Project" — reconcile with production "Review project" terminology
- Navigation item "Proposed work" — reconcile with production "MissionDecisionView"
- "Prepared changes" — lock behind authority for REVIEW_ONLY projects
- Metrics must derive from actual backend data, not prototype sample data

**Production source reference:** `GuidedModePage.tsx` SummaryView already has headline, stats, authority info. AI Studio adds count badges, Can Do/Will Not Do split, and more prominent authority display. Adopt patterns; adapt terminology.

---

### Screen 3 — Needs Your Attention

**Observed:**
- "Needs Your Attention" with "Sample Findings (Demo)"
- Per finding: priority badge, category badge, plain-language title, "Why this matters", file/location, optional "Show technical details", stable finding identifier
- Examples: HIGH PRIORITY / Security, MODERATE / Reliability, MINOR / Architecture

**Production equivalent:** `GuidedModePage.tsx` NeedsAttentionView with finding cards, severity/category badges, "Why it matters" section, "Review recommended fix" button, expandable technical details

**Classification: ADOPT / ADAPT**

**Adopt:**
- "Do not hide technical truth from non-technical users. Translate it." — canonical principle
- Guided Mode explains authoritative findings
- Technical details remain progressively available ("Show technical details")
- Severity/classification must remain authoritative EVOSIA data
- Stable finding identifiers

**Adapt:**
- Gemini must NOT manufacture or alter authoritative severity/classification
- "Why this matters" must be derived from backend evidence, not generated independently
- Category naming must reconcile with production finding categories

**Production source reference:** `NeedsAttentionView` already implements finding cards with badges and progressive disclosure. AI Studio adds "Why this matters" as a more prominent plain-language field. Adopt the pattern.

---

### Screen 4 — Needs Context

**Observed:**
- "Needs Context" with "open questions" and "Sample Questions (Demo)"
- Purpose: "Questions EVOSIA asks to better understand user intentions and reduce false positives."
- Safety Guarantee: "EVOSIA will never treat answers as a decision to change code."
- Per question: topic, question, "Why EVOSIA is asking", affected finding count, suggested answers, "I don't know", "Ask someone else / later", custom clarification, Submit Answer

**Production equivalent:** `GuidedModePage.tsx` NeedsContextView with ContextQuestion cards, answer options, "I don't know" option

**Classification: ADOPT / ADAPT**

**Adopt:**
- "EVOSIA will never treat answers as a decision to change code" — canonical invariant
- "Why EVOSIA is asking" explanation
- Affected finding count
- "I don't know" and "Ask someone else / later" options
- Safety guarantee prominently displayed

**Adapt:**
- Human context MUST NOT become approval, preparation authority, or execution authority
- Human context MUST NOT become permission to modify files
- Where supported by existing architecture, human context should retain traceable provenance
- Do not invent a new persistence contract during P1

**Production source reference:** `NeedsContextView` already implements context questions with answer options. AI Studio adds safety guarantee and "Why EVOSIA is asking" as more prominent elements. Adopt the safety language.

---

### Screen 5 — Proposed Work & Mission Decisions

**Observed:**
- "Proposed Work & Mission Decisions" with "Sample Missions (Demo)" and "PROPOSED WORK (DRAFT)"
- Per proposal: What will be prepared, Why EVOSIA proposes this, Expected Benefit, Potential Risk & Impact, Scope & Affected Files, How EVOSIA verifies in sandbox, Undo / Rollback method
- Mandatory authority consequence statement: "Approving permits EVOSIA to PREPARE a candidate patch in an isolated sandbox workspace. It will NOT merge, deploy, or change live repository files. Approving does not modify the repository."

**Production equivalent:** `GuidedModePage.tsx` MissionDecisionView with What/Why/Benefit/Risk/Scope/Validation/Rollback fields, authority statement, preparation outcome panel

**Classification: ADAPT — AUTHORITY SENSITIVE**

**Preserve:**
- Decision-information architecture (What/Why/Scope/Benefit/Risk/Validation/Rollback)
- Mandatory authority consequence statement
- "What approval authorizes" / "What approval does NOT authorize"

**Adapt:**
- P0–P8 must NOT activate preparation authority for REVIEW_ONLY Local Agent projects merely because this prototype contains the UI
- For REVIEW_ONLY projects: "Approving" should be "Approving for future preparation" not "Approving preparation now"
- The distinction between preparation authority levels must be clear
- For REVIEW_ONLY: no Prepare action should be available

**Authority note:** This screen is the most authority-sensitive surface. The prototype implies preparation authority exists. For REVIEW_ONLY Local Agent product, Prepare remains LOCKED. The information architecture is valuable; the authority activation must be gated.

**Production source reference:** `MissionDecisionView` already implements the decision fields and authority statement. AI Studio makes the authority consequence statement more prominent and structured. Adopt the prominence; preserve the authority gate.

---

### Screen 6 — Prepared Changes

**Observed:**
- Empty state: "No prepared changes yet."
- Explanation that after approving a proposed mission and selecting "Prepare in isolated Workspace", EVOSIA can generate/test a candidate patch in safe isolation.

**Production equivalent:** `GuidedModePage.tsx` PreparedChangeReview and `PreparedChangeView.tsx` with diff, validation, rollback info

**Classification: PRESERVE_LOCKED**

**Preserve concept:**
- Valid broader EVOSIA concept
- Explains what would happen if preparation authority were granted

**Lock behind authority:**
- Do NOT activate through Productization merely because the concept exists
- For REVIEW_ONLY connected-project product: Prepare is LOCKED
- The UI may explain what preparation means; it must NOT present it as immediately available

**Production source reference:** `PreparedChangeView` already implements the prepared change display. AI Studio shows empty state with explanation. Both preserve the concept. Lock the activation.

---

### Screen 7 — Technical View

**Observed:**
- "Technical & Governance Explorer" with "PROGRESSIVE DISCLOSURE" label
- "DEMO PROJECT — Sample data only"
- Governance indicator: "Governance Invariant: PASS (0.0% Unsafe Automation)"
- Sections: Technical Findings, Mission Traceability, Audit Journal, Governance Report, M8/M9 Authority Gate Validator
- Technical finding table: Rule ID, Severity, Category, Location, Evidence Hash, Adjudication

**Production equivalent:** Separate pages — `FindingsPage.tsx`, `JournalPage.tsx`, `ScansPage.tsx`, `MissionsPage.tsx`, `ReportsPage.tsx`

**Classification: ADOPT / ADAPT**

**Adopt:**
- "Technical View" as a unified progressive disclosure surface
- Technical findings table with structured columns
- Governance invariant display
- Audit journal exposure
- Evidence hash visibility

**Adapt:**
- Guided Mode and Technical View MUST consume the SAME authoritative backend state
- No duplicated state machine
- No parallel authority model
- Guided Mode translates; Technical View exposes
- Neither becomes a second authority layer
- Do not expose internal engineering milestone terminology (M8/M9) as permanent customer-facing terminology — translate durable product concepts appropriately

**Production source reference:** Production has 5 separate pages for findings/journal/scans/missions/reports. AI Studio consolidates into a single "Technical View." Adopt the consolidation concept; ensure same backend consumption.

---

### Screen 8 — Ask EVOSIA

**Observed:**
- "Conversational EVOSIA" with "Plain-language reasoning & project Q&A"
- "Right now: 0 changes made" safety state
- Introduction: EVOSIA can answer questions about findings, why they matter, candidate patches
- Suggested questions: "Has EVOSIA changed my project?", "What will happen if I approve?", "Why does the token expiration issue matter?", "What is the difference between Prepared and Executed?"
- Safety statement: "EVOSIA conversations are read-only and never trigger execution."

**Production equivalent:** `/api/guided/explain/*` endpoints (finding, question, mission, prepared-change explanations via Gemini)

**Classification: ADOPT / ADAPT**

**Adopt:**
- Conversational explanation interface concept
- "EVOSIA conversations are read-only and never trigger execution" — canonical invariant
- Suggested questions reflecting actual authority
- Plain-language reasoning

**Adapt:**
- Converge with EXISTING governed Gemini explanation layer (`enterprise/services/gemini_explain.py`)
- Do NOT create an unrestricted repository chatbot
- Conversation MUST NOT trigger: PROJECT_SCAN, authority change, approval, preparation, execution, repository mutation
- For REVIEW_ONLY projects, suggested questions should reflect actual current authority:
  - What did EVOSIA find?
  - Which issue matters most?
  - Explain this without technical language.
  - Why is EVOSIA asking this?
  - Has EVOSIA changed anything?
  - What can EVOSIA do with this project right now?
- Provenance: GEMINI_EXPLANATION label must be clear

**Production source reference:** `/api/guided/explain/*` endpoints exist but no conversational UI. AI Studio adds chat interface. Adopt the concept; bind to existing governed explanation endpoints.

---

## 4. P0 ABSENT/PARTIAL CONCEPT RECONCILIATION

### P0 Absent Concepts (12)

| # | Concept | Disposition | Rationale |
|---|---------|-------------|-----------|
| 1 | Native installer / Connector | ADAPT | AI Studio does not address installation. P2 specification required. |
| 2 | Automatic background startup | ADAPT | AI Studio does not address runtime lifecycle. P2 specification required. |
| 3 | Native folder picker | ADAPT | AI Studio shows project selection concept. Adopt the concept; implement native OS picker in P3–P5. |
| 4 | In-app pairing flow | ADAPT | AI Studio does not address device pairing. P2 specification required. |
| 5 | Connection status visual | KEEP PRODUCTION | Production `DevicesPage.tsx` already shows online/offline/revoked. Adopt as-is. |
| 6 | Update mechanism | ADAPT | AI Studio does not address updates. P2 specification required. |
| 7 | Uninstall mechanism | ADAPT | AI Studio does not address uninstall. P2 specification required. |
| 8 | OS keychain integration | ADAPT | AI Studio does not address credential storage. P2 specification required. |
| 9 | System tray integration | ADAPT | AI Studio does not address background operation. P2 specification required. |
| 10 | First-run wizard for Connector | PRESERVE_LOCKED | Valid concept for P3–P4. Not addressed by AI Studio. |
| 11 | Chat/conversation interface | ADOPT | AI Studio Screen 8 demonstrates this. Bind to existing governed explanation endpoints. |
| 12 | In-app authorization explanation | ADOPT | AI Studio Screen 1 and Screen 5 demonstrate authority education. Adopt the pattern. |

### P0 Partial Concepts (5)

| # | Concept | Disposition | Rationale |
|---|---------|-------------|-----------|
| 1 | Non-technical primary user | ADOPT | AI Studio fully targets this audience. Adopt the language and interaction patterns. |
| 2 | Project selection | ADOPT | AI Studio Screen 2 shows "Analyze Project (Read-Only)". Adopt concept; adapt to native folder picker. |
| 3 | Conversational intelligence (Gemini) | ADOPT | AI Studio Screen 8 demonstrates conversational interface. Bind to existing governed endpoints. |
| 4 | Expert/technical views | ADOPT | AI Studio Screen 7 demonstrates consolidated Technical View. Adopt consolidation concept. |
| 5 | Authority consequence statement | ADOPT | AI Studio Screen 5 demonstrates mandatory authority statement. Adopt prominence and structure. |

### P0 Visual Comparison Concepts (5)

| # | Concept | Disposition | Rationale |
|---|---------|-------------|-----------|
| 1 | Google AI Studio generated app visual design | ADAPT | Visual design is reference. Adopt calm/premium aesthetic. Adapt to production CSS design system. |
| 2 | Dark theme color palette alignment | ADAPT | AI Studio uses specified colors. Production has its own dark theme. Align accent colors; preserve production foundation. |
| 3 | Typography and spacing | ADAPT | AI Studio specifies "premium, calm, trustworthy." Production has its own type scale. Adopt spacing principles. |
| 4 | Badge system visual states | ADOPT | AI Studio specifies DRAFT/APPROVED/PREPARED colors. Adopt the state labels and color mapping. |
| 5 | Card component styling | ADAPT | AI Studio specifies elevated cards with subtle borders. Production has card styling. Adopt elevation pattern. |

---

## 5. CANONICAL GUIDED MODE

### Role

Guided Mode is the primary EVOSIA product experience for non-technical users. It translates authoritative backend data into plain language while preserving progressive access to technical detail.

### Canonical Questions Answered

| Question | Guided Mode Answer |
|----------|-------------------|
| What did EVOSIA find? | Plain-language summary with count badges |
| Why does it matter? | Per-finding "Why this matters" explanation |
| What does EVOSIA need from me? | Context questions with safety guarantee |
| What does EVOSIA recommend? | Proposed work with full decision architecture |
| Has anything changed? | Persistent safety badge: "0 changes made" |
| What is EVOSIA allowed to do right now? | Authority level display with Can Do / Will Not Do |

### Canonical Structure

```
Guided Mode
├── Overview
│   ├── Plain-language review summary
│   ├── Stats grid (Examined, Worth Discussing, Need Your Help, etc.)
│   ├── Safety badge ("0 changes made")
│   ├── Authority level display
│   └── Demo/Live provenance indicator
├── Needs Your Attention
│   ├── Finding cards with severity/category
│   ├── "Why this matters" per finding
│   ├── Progressive technical details
│   └── Stable finding identifiers
├── Needs Context
│   ├── Context questions with safety guarantee
│   ├── "Why EVOSIA is asking"
│   ├── Affected finding count
│   ├── Answer options + "I don't know"
│   └── "Answers never authorize code changes"
├── Proposed Work
│   ├── What/Why/Benefit/Risk/Scope/Validation/Rollback
│   ├── Authority consequence statement
│   ├── "Approved for preparation" (not "Approved")
│   └── Preparation status
└── Ask EVOSIA
    ├── Conversational explanation interface
    ├── Suggested questions
    ├── "Read-only, never triggers execution"
    └── GEMINI_EXPLANATION provenance
```

### Design Principles

1. **Translate, don't hide** — Technical truth is presented in plain language, not suppressed
2. **Progressive disclosure** — Technical details available on demand, not by default
3. **Same authoritative state** — Guided Mode consumes the same backend as Technical View
4. **Authority-aware** — UI capabilities derive from actual granted authority
5. **Safety visible** — "0 changes made" always present; authority level always visible

---

## 6. CANONICAL TECHNICAL VIEW

### Role

Technical View is a progressive disclosure surface for users who want deeper technical detail. It uses the SAME authoritative backend state as Guided Mode.

### Canonical Structure

```
Technical View
├── Technical Findings
│   ├── Rule ID, Severity, Category, Location
│   ├── Evidence Hash, Adjudication
│   └── Classification, Module, File Context
├── Mission Traceability
│   ├── Finding → Mission → Change chain
│   └── Evidence lineage
├── Audit Journal
│   ├── Event type, timestamp, stage, actor
│   └── Append-only log
├── Governance Report
│   ├── Governance invariant status
│   ├── Unsafe automation rate
│   └── Authority boundary verification
└── Provenance
    ├── LIVE_EVOSIA_EVIDENCE
    ├── GEMINI_EXPLANATION
    └── DEMO / SAMPLE
```

### Design Principles

1. **Same backend** — No duplicated state machine, no parallel authority model
2. **Expose, don't translate** — Technical View shows raw data; Guided Mode translates it
3. **No authority layer** — Technical View is a view, not an authority mechanism
4. **Progressive from Guided** — Users can move from Guided to Technical for any item
5. **No internal terminology** — M8/M9 and other engineering milestones not exposed as customer terminology

---

## 7. CANONICAL ASK EVOSIA

### Role

Ask EVOSIA is a conversational explanation interface bound to the existing governed Gemini explanation layer. It is NOT an unrestricted repository chatbot.

### Canonical Architecture

```
User question
    ↓
Conversational EVOSIA interface
    ↓
EVOSIA backend selects permitted evidence
    ↓
Governed Gemini explanation service (enterprise/services/gemini_explain.py)
    ↓
Plain-language explanation
    ↓
GEMINI_EXPLANATION provenance label
```

### Authority Invariants

| Constraint | Status |
|------------|--------|
| Conversation is read-only | ENFORCED |
| Conversation cannot trigger PROJECT_SCAN | ENFORCED |
| Conversation cannot grant authority | ENFORCED |
| Conversation cannot approve preparation | ENFORCED |
| Conversation cannot execute changes | ENFORCED |
| Conversation cannot mutate repository | ENFORCED |

### Suggested Questions (REVIEW_ONLY projects)

- What did EVOSIA find?
- Which issue matters most?
- Explain this without technical language.
- Why is EVOSIA asking this question?
- Has EVOSIA changed anything?
- What can EVOSIA do with this project right now?
- What is the difference between a finding and a recommendation?
- Why does this finding matter?

### Provenance

All explanations carry `GEMINI_EXPLANATION` provenance. This MUST be visually distinct from `LIVE_EVOSIA_EVIDENCE`. Users must never confuse AI-generated explanation with authoritative scan evidence.

---

## 8. PROVENANCE PRESENTATION

### Supported Provenance Classes

| Provenance | Source | Visual Treatment |
|------------|--------|-----------------|
| `DEMO / SAMPLE` | Prototype data | Prominent banner: "Sample data only — not from your project" |
| `LIVE_EVOSIA_EVIDENCE` | Agent PROJECT_SCAN | Authoritative badge: "Live EVOSIA evidence" |
| `GEMINI_EXPLANATION` | Governed Gemini service | Explanation badge: "AI explanation" |
| Human context | User-provided answers | Context badge: "Your context" |

### Canonical Rules

1. **UI presentation must never make simulated evidence look live.** Demo/sample data is always labeled.
2. **Gemini explanation must never look like authoritative EVOSIA evidence.** Explanation provenance is always distinct from scan evidence.
3. **Provenance is additive.** An item can have multiple provenance labels (e.g., LIVE_EVOSIA_EVIDENCE + GEMINI_EXPLANATION).
4. **Provenance is immutable.** Once assigned, provenance does not change.

---

## 9. AUTHORITY-AWARE UI

### Current REVIEW_ONLY Connected-Project Authority

| Capability | UI Status |
|------------|----------|
| Review | AVAILABLE — "Review project" button active |
| Understand | AVAILABLE — Guided Mode summary, findings |
| Explain | AVAILABLE — Ask EVOSIA, guided explanations |
| Ask Context | AVAILABLE — Context questions with safety guarantee |
| Recommend | AVAILABLE — Proposed work displayed |
| Prepare | LOCKED — Not available for REVIEW_ONLY projects |
| Execute | LOCKED — Not available |
| Merge | LOCKED — Not available |
| Deploy | LOCKED — Not available |

### UI Authority Presentation

The UI may explain unavailable higher authority. It must NOT present locked actions as immediately executable.

Conceptual presentation:

```
✓ Review
✓ Understand
✓ Recommend

🔒 Prepare
🔒 Execute
```

### Authority Consequence Statement (Mandatory)

When presenting proposed work, the following statement must always be present:

> Approving permits EVOSIA to prepare a candidate patch in an isolated sandbox workspace.
> It will NOT merge, deploy, or change live repository files.
> Approving does not modify the repository.

For REVIEW_ONLY projects, add:

> Preparation is not available for this project. Review only.

---

## 10. TERMINOLOGY RECONCILIATION

| AI Studio Wording | Production Wording | Canonical Concept | Disposition |
|-------------------|-------------------|-------------------|-------------|
| Autonomous Intelligence | (not in production) | (not used) | REJECT — implies autonomous action |
| Governed Execution | (not in production) | (not used) | REJECT — implies execution authority |
| Analyze Project | Review project | Review Project | ADAPT — use "Review" |
| Review Project | Review project | Review Project | KEEP PRODUCTION — same term |
| Needs Your Attention | Needs attention (in Guided) | Needs Your Attention | ADOPT — AI Studio capitalization more prominent |
| Findings | Findings | Findings | KEEP PRODUCTION — same term |
| Needs Context | (in Guided backend) | Needs Context | KEEP PRODUCTION — same concept |
| Proposed Work | Missions (backend) | Proposed Work | ADAPT — "Proposed Work" is user-friendlier than "Missions" |
| Mission | Mission (backend) | Mission (internal) / Proposed Work (UI) | ADAPT — user-facing: "Proposed Work"; internal: "Mission" |
| Prepared Changes | Prepared Changes | Prepared Changes | KEEP PRODUCTION — same term |
| Guided Mode | Guided Mode | Guided Mode | KEEP PRODUCTION — same term |
| Technical View | (separate pages) | Technical View | ADOPT — consolidate concept from AI Studio |
| Ask EVOSIA | (API endpoints exist, no UI) | Ask EVOSIA | ADOPT — name and concept from AI Studio |
| Level 1 — Recommend | (authority info card) | Authority Level | ADAPT — adopt level naming, bind to actual authority |
| Right now: 0 changes made | "0 changes made" (safety badge) | Safety Badge | KEEP PRODUCTION — same concept |

---

## 11. CONVERGENCE INVENTORIES

### ADOPT (implement substantially as observed, bind to production contracts)

| # | Concept | Source Screen |
|---|---------|--------------|
| 1 | Plain-language review summary ("I reviewed your project. N things examined...") | Screen 2 |
| 2 | "Right now: 0 changes made" persistent safety badge | Screen 2 |
| 3 | Explicit current authority display ("Level 1 — Recommend") | Screen 2 |
| 4 | "What EVOSIA Can Do Now" / "What EVOSIA Will NOT Do" | Screen 2 |
| 5 | "Do not hide technical truth. Translate it." — Needs Your Attention principle | Screen 3 |
| 6 | "Why EVOSIA is asking" per context question | Screen 4 |
| 7 | "EVOSIA will never treat answers as a decision to change code" | Screen 4 |
| 8 | Mandatory authority consequence statement on proposed work | Screen 5 |
| 9 | Conversational explanation interface (Ask EVOSIA) | Screen 8 |
| 10 | "EVOSIA conversations are read-only and never trigger execution" | Screen 8 |
| 11 | Suggested questions reflecting actual authority | Screen 8 |
| 12 | Consolidated Technical View concept | Screen 7 |
| 13 | Count badges on navigation chips | Screen 2 |
| 14 | Stable finding identifiers | Screen 3 |
| 15 | "I don't know" / "Ask someone else / later" options | Screen 4 |

### ADAPT (valuable concept, wording/behavior/data binding must change)

| # | Concept | Source Screen | Adaptation Required |
|---|---------|--------------|-------------------|
| 1 | "Autonomous Intelligence" descriptor | Screen 1 | Replace with product-appropriate descriptor |
| 2 | "Governed Execution" descriptor | Screen 1 | Replace with language matching current authority |
| 3 | "Prepare" in workflow visualization | Screen 1 | Visually gate behind authority level |
| 4 | "Analyze Project" terminology | Screen 2 | Adopt "Review" to match production |
| 5 | Authority level naming | Screen 2 | Bind to actual production authority model |
| 6 | Navigation "Proposed work" label | Screen 2 | Adopt user-friendly label for "Missions" |
| 7 | Dark theme color palette | Screen 2 | Align accent colors; preserve production foundation |
| 8 | Card component styling | Screen 2 | Adopt elevation pattern; preserve production CSS |
| 9 | Technical View consolidation | Screen 7 | Adopt concept; ensure same backend consumption |
| 10 | Native folder picker concept | Screen 2 | Adopt concept; implement OS-native in P3–P5 |
| 11 | In-app pairing concept | (not shown) | Adopt concept; specify in P2 |
| 12 | Update mechanism concept | (not shown) | Adopt concept; specify in P2 |

### KEEP PRODUCTION (existing production implementation is stronger or more authoritative)

| # | Concept | Production Source |
|---|---------|------------------|
| 1 | Review project button and lifecycle | `DevicesPage.tsx` |
| 2 | Online/offline/revoked device state | `DevicesPage.tsx` |
| 3 | Device management (register, revoke) | `DevicesPage.tsx` |
| 4 | Project authorization token flow | `DevicesPage.tsx` |
| 5 | Review history display | `DevicesPage.tsx` |
| 6 | Truncation disclosure | `DevicesPage.tsx` |
| 7 | Demo/Live toggle | `DemoModeToggle.tsx` |
| 8 | ProvenanceBadge component | `ProvenanceBadge.tsx` |
| 9 | GuidedModePage structure | `GuidedModePage.tsx` |
| 10 | NeedsAttentionView | `GuidedModePage.tsx` |
| 11 | NeedsContextView | `GuidedModePage.tsx` |
| 12 | MissionDecisionView | `GuidedModePage.tsx` |
| 13 | PreparedChangeView | `PreparedChangeView.tsx` |
| 14 | FirstRunOnboarding | `FirstRunOnboarding.tsx` |
| 15 | JWT authentication flow | `App.tsx` AuthContext |

### PRESERVE_LOCKED (valid broader EVOSIA concept, unavailable under current product authority)

| # | Concept | Lock Reason |
|---|---------|------------|
| 1 | Prepared Changes activation | REVIEW_ONLY — Prepare not granted |
| 2 | Execute action | Not granted |
| 3 | Merge action | Not granted |
| 4 | Deploy action | Not granted |
| 5 | Autonomous PROJECT_SCAN creation | Not granted |
| 6 | First-run wizard for Connector | Requires P3–P4 implementation |

### REJECT (conflicts with product direction, certified evidence, or authority boundaries)

| # | Concept | Rejection Reason |
|---|---------|-----------------|
| 1 | "Autonomous Intelligence" descriptor | Implies autonomous action; conflicts with human-authority model |
| 2 | "Governed Execution" descriptor | Implies execution authority; not granted for connected-PC |
| 3 | M8/M9 Authority Gate Validator as customer-facing terminology | Internal engineering milestone; not product terminology |
| 4 | Unrestricted repository chatbot | Must be bound to governed Gemini explanation layer |
| 5 | Conversation triggering PROJECT_SCAN | Authority violation |
| 6 | Conversation granting authority | Authority violation |

---

## 12. UNRESOLVED EVIDENCE

| # | Item | Required for P2 |
|---|------|----------------|
| 1 | Exact AI Studio visual design comparison against production CSS | P2 Connector specification needs visual target |
| 2 | AI Studio app responsiveness/mobile behavior | P2 may need to specify desktop-only |
| 3 | AI Studio error handling patterns | P2 Connector error handling specification |
| 4 | AI Studio authentication flow details | P2 pairing flow specification |
| 5 | Exact Gemini conversation model parameters | P2 Ask EVOSIA binding to production endpoints |

All unresolved items are non-blocking for P2 specification. P2 can proceed with the canonical models defined in this document.

---

## 13. P2 INPUTS

P1 provides the following inputs to P2 Connector Specification:

| Input | P1 Section | P2 Use |
|-------|-----------|--------|
| Canonical Guided Mode structure | Section 5 | Connector UI structure |
| Canonical Technical View structure | Section 6 | Connector progressive disclosure |
| Canonical Ask EVOSIA architecture | Section 7 | Connector conversational interface |
| Provenance model | Section 8 | Connector provenance display |
| Authority-aware UI rules | Section 9 | Connector authority gating |
| Terminology reconciliation | Section 10 | Connector label/copy decisions |
| ADOPT inventory | Section 11 | Connector features to implement |
| ADAPT inventory | Section 11 | Connector features requiring production binding |
| PRESERVE_LOCKED inventory | Section 11 | Connector features to explain but not activate |
| REJECT inventory | Section 11 | Connector features to avoid |

---

## 14. P1 DISPOSITION

| Gate | Status |
|------|--------|
| A. All eight observed surfaces recorded | PASS |
| B. Each surface has convergence disposition | PASS |
| C. P0 absent/partial concepts reconciled | PASS |
| D. Canonical Guided Mode defined | PASS |
| E. Canonical Technical View defined | PASS |
| F. Canonical Ask EVOSIA defined | PASS |
| G. Provenance presentation rules defined | PASS |
| H. Authority-aware UI rules defined | PASS |
| I. Prepare remains locked for REVIEW_ONLY | PASS |
| J. Execute remains locked | PASS |
| K. Conversation remains read-only/non-authoritative | PASS |
| L. Demo/live provenance cannot be confused | PASS |
| M. No application code changed | PASS |
| N. No authority expansion occurred | PASS |
| O. P2 receives enough UX requirements | PASS |

**P1 DISPOSITION: PASS**

---

## 15. SOURCE DOCUMENTS

| Document | Path |
|----------|------|
| P1 Convergence (this document) | `docs/productization/P1_UX_CONVERGENCE.md` |
| Productization Programme | `docs/productization/EVOSIA_PRODUCTIZATION_PROGRAMME.md` |
| P0 Evidence | `docs/productization/P0_PRODUCT_SURFACE_INVENTORY.md` |
| Google AI Studio Build Prompt | `docs/google-ai-studio/EVOSIA_GOOGLE_AI_STUDIO_BUILD_PROMPT.md` |
| Local Agent Certification | `validation/LOCAL_AGENT_PRODUCTION_CERTIFICATION.md` |

---

**STOP. No production mutations performed. No execution authority granted. No new programme started beyond P1.**
