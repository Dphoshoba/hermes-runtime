# M8-P0 — Facilitator Package for First Genuine Non-Technical Participant

This package defines the minimum facilitator procedures required to conduct
the first genuine non-technical-user M8 session against the verified Railway
deployment.

It reuses the certified M8 protocol (`M9_REAL_USER_TEST_PROTOCOL.md`) and
acceptance criteria. Do NOT invent a new study.

---

## 1. Participant Eligibility Criteria

A genuine non-technical participant MUST meet ALL of the following:

**Include:**
- Comfortable with ordinary software (web browsers, email, documents, social media)
- No professional software-engineering requirement
- Can navigate a web application with a browser
- Fluent enough in the session language to follow written instructions

**Exclude:**
- Current EVOSIA contributors or developers
- People who have seen this protocol before
- Anyone coached on the EVOSIA workflow prior to the session
- Anyone whose professional work involves Git / terminal / software architecture / API design
- Anyone who participated in prior EVOSIA usability testing

The participant must be genuinely non-technical. Do NOT loosen the eligibility
definition merely to obtain participants.

---

## 2. Recruitment Invitation (non-coaching)

Send the following (or equivalent neutral wording). Do NOT describe how EVOSIA works.

---

> You are invited to participate in a usability study of a new software tool.
>
> The study involves using a web application to review a small software project,
> and deciding whether to approve a proposed change. The session takes approximately
> 30–45 minutes and is conducted remotely via screen-sharing.
>
> No prior experience with the tool is required. You will not need to use
> command-line tools, Git, or any software-development tools during the session.
>
> Your participation is voluntary. You may stop at any time. No personally
> identifying information will be recorded — only a participant identifier (e.g. P01).
>
> If you are interested, please reply to arrange a time.

---

## 3. Informed Session Briefing & Consent

Before the session begins, read or share the following:

> This is a usability study of a software tool. I will ask you to complete a
> short task using the tool. I cannot explain how the tool works or answer
> questions about what buttons mean during the task — this is part of the study.
>
> I will record:
> - your screen (with your permission)
> - your task completion and any assistance you request
> - your answers to two short questions
>
> I will NOT record your name or any personally identifying information. You will
> be identified only by a participant number (e.g. P01).
>
> You may stop at any time.
>
> Do you consent to proceed?

Record the consent decision. Do not proceed without it.

---

## 4. Facilitator Pre-Session Procedure

Complete the following BEFORE the participant joins:

### 4.1 Environment preparation

```bash
# Ensure the Railway stack is healthy
docker-compose ps
docker-compose logs --tail=20 backend

# Verify HTTPS endpoint is reachable
curl -k https://<railway-host>/api/health
```

### 4.2 Fixture reset/seed/verify

```bash
# Reset to canonical starting state
docker-compose exec backend python -m enterprise.cli_m8_fixture reset --confirm

# Seed the deterministic fixture
docker-compose exec backend python -m enterprise.cli_m8_fixture seed --confirm

# Verify the fixture contains the required evidence
docker-compose exec backend python -m enterprise.cli_m8_fixture verify --confirm
```

### 4.3 Capture pre-session integrity

```bash
# Record the target repository commit hash — must be identical post-session
docker-compose exec backend git -C /app/validation/m8-disposable-repo rev-parse HEAD
```

### 4.4 Create participant authentication

```bash
# Register the participant with a unique email
docker-compose exec backend python -c "
from enterprise.database import SessionLocal
from enterprise.models import User
from enterprise.services import hash_password
db = SessionLocal()
db.add(User(email='m8-p01-participant@local', name='M8 Participant', hashed_password=hash_password('evosia-m8-p01')))
db.commit()
print('participant ready')
"
```

### 4.5 Prepare the blank participant record

Use `validation/usability/participants/P01.json` — ensure all observational
fields are `null`. Fill ONLY:
- `participant_id`: "P01"
- `evosia_version`: "1.3.0"
- `evosia_commit`: <current git commit of EVOSIA source>
- `test_timestamp`: <ISO timestamp at session start>
- `prior_hermes_experience`: <ask participant: yes/no>
- `technical_experience`: <ask participant: yes/no>

All task fields, verbatim responses, and comprehension classifications MUST
remain `null` until observed.

### 4.6 Prepare facilitator materials

- Print/open the facilitator quick card (`M9_FACILITATOR_QUICK_CARD.md`)
- Open the blank observation sheet (Section 6 below)
- Start screen-recording arrangement (consented)

---

## 5. Participant Access / Login Instructions

Provide the participant ONLY the following:

---

> 1. Open your web browser and go to:
>    `https://<railway-host>`
>
> 2. You will see a login page. Use these credentials:
>    Email: `m8-p01-participant@local`
>    Password: `evosia-m8-p01`
>
> 3. After logging in, click "Guided Mode" in the navigation.
>
> I will now give you your task.

---

Do NOT explain what Guided Mode is, what buttons mean, or what will happen.

---

## 6. Certified M8 Tasks (from the authoritative protocol)

The participant works through the following task sequence. Record completion,
assistance requested, duration, observed behavior, and participant comments.

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

---

## 7. Observation Sheet

Separate evidence into the following categories. Record only what you observe.

### Direct Observation
- Task completed (yes/no/partial)
- Assistance requested (what the participant asked)
- Facilitator intervention (what you did, if anything)
- Duration (seconds)

### Participant Statements
- Verbatim response to Task 9: "Has EVOSIA changed your project?"
- Verbatim response to Task 10: "What would happen if you approved?"
- Any other relevant participant comments

### Facilitator Notes
- Where the participant hesitated
- Technical terminology that confused them
- Usability defects observed
- Critical usability failures

### System Evidence
- Pre-session target repository hash
- Post-session target repository hash
- Fixture verify output

---

## 8. Anti-Coaching Rules

The facilitator MUST NOT:
- explain the interface
- explain Git, repositories, branches, commits
- explain EVOSIA governance (gate states, mission eligibility, journal)
- point at buttons or features
- explain what "Prepare" or "Approve" means
- correct misunderstandings during the task unless safety requires it
- lead the participant toward any answer
- answer Task 9 or Task 10

If the participant asks for assistance, record the request and the intervention
exactly. Do not hide confusion. Confusion is evidence.

---

## 9. Failure / Abort Criteria

### Abort the session if:
- A genuine blocking technical defect occurs (preserve the observation first)
- An authority-safety defect is discovered (participant believes Prepare modified
  the project, approval modified the project, PREPARED means merged/deployed,
  or EVOSIA executed without authority)
- The participant requests to stop

### Record as critical usability failure if:
- The participant cannot complete a task without facilitator explanation of
  EVOSIA itself
- The participant believes EVOSIA has already modified the project
- The participant believes approval would deploy/execute the change

---

## 10. Post-Session Evidence Capture & Reset

### 10.1 Capture evidence

- Complete the participant record from observed evidence only
- Record verbatim Task 9 and Task 10 responses
- Classify authority comprehension per the acceptance criteria
- Capture post-session integrity hash

### 10.2 Post-session integrity

```bash
docker-compose exec backend git -C /app/validation/m8-disposable-repo rev-parse HEAD
```

Must equal pre-session hash. Also verify target config.py unchanged.

### 10.3 Revoke participant access

```bash
docker-compose exec backend python -c "
from enterprise.database import SessionLocal
from enterprise.models import User
db = SessionLocal()
db.query(User).filter(User.email=='m8-p01-participant@local').delete()
db.commit()
print('participant revoked')
"
```

### 10.4 Reset fixture

```bash
docker-compose exec backend python -m enterprise.cli_m8_fixture reset --confirm
```

---

## 11. Acceptance-Gate Evaluation Procedure

After the session, evaluate per the authoritative M8 protocol:

**PASS thresholds:**
- task_completion_rate >= 80%
- authority_comprehension_rate = 100%
- critical_usability_failures = 0

**Overall PASS:** all three thresholds met.
**Overall FAIL:** any threshold not met → remediate and retest.

Do NOT pre-populate any result. Calculate only from completed genuine
participant records.

---

## 12. Evidence Boundaries Checklist

The following evidence MUST come from an actual human participant and MUST
remain blank before the session:

- [ ] Task completion (tasks 1–10)
- [ ] Assistance requested
- [ ] Task durations
- [ ] Observed behavior
- [ ] Participant comments
- [ ] Task 9 verbatim response
- [ ] Task 10 verbatim response
- [ ] Authority comprehension classification
- [ ] Session result

The following MAY be prepared before the session:

- [ ] Participant ID
- [ ] EVOSIA version
- [ ] EVOSIA commit
- [ ] Test timestamp
- [ ] Prior experience (asked at session start)
- [ ] Technical experience (asked at session start)

---

## 13. Acceptance Determination (blank until observed)

| Measure | Result |
|---------|--------|
| task_completion_rate | |
| authority_comprehension_rate | |
| critical_usability_failures | |
| overall_result | |
