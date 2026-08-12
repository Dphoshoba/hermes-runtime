# CYCLE 8 VALIDATION PROTOCOL

**Status:** DESIGN ONLY — NOT EXECUTED

**Purpose:** Unseen holdout validation for governance candidate

---

## Requirements

- Minimum findings: 60
- Target findings: 75-100

### Required Representation

- Useful: >=15 naturally occurring
- Needs More Evidence: >=15
- Not Actionable: >=10
- Configuration: >=5 if available
- High Severity: >=5 if available
- High Extreme Exceedance: >=5 if available
- Test And Production: both
- Multiple Repositories: True
- Multiple Languages: True

---

## Protocol

Step 1: Scan expanded repository cohort

Step 2: Extract evidence for all findings

Step 3: Create blind review queue

Step 4: Operator classifies findings without seeing governance decisions

Step 5: Freeze validation dataset

Step 6: Evaluate governance candidate against frozen dataset

Step 7: Calculate metrics

Step 8: Compare with Cycle 7 calibration data

Step 9: Determine promotion readiness

---

## Success Gates

### Safety

- over_approval: materially below Production
- autonomous_execution: False
- repository_mutation: False

### Useful Recognition

- primary_gate: USEFUL approval recall >= 70%
- stretch_target: >= 80%

### Over Approval

- target: <= 20%

### Not Actionable

- target_accuracy: >= 70%

### Nme

- target_accuracy: >= 70%

### Generalization

- max_exact_agreement_delta: <= 15 percentage points

### Explainability

- requirement: Every decision must include machine-readable reason codes

---

## Anti-Overfitting Requirements

The following are FORBIDDEN in governance rules:

- Repository names in rules
- Specific file names in rules
- Finding IDs in rules
- Rules created solely to capture one Cycle 7 example
- Human classifications as runtime inputs
- Mission priority as governance evidence
- Existing governance decisions as features
- Post-review metadata
- Changing another global default
- Approving based only on severity
- Approving based only on a single arbitrary threshold

---

## Calibration Data Usage

- **Cycle7 Frozen Review Set:** CALIBRATION_ONLY_AFTER_THIS_ANALYSIS
- **Usage:** Feature discovery and hypothesis generation only
- **Validation:** Must use NEW unseen holdout for final validation

---

**DO NOT execute this plan without operator authorization.**
