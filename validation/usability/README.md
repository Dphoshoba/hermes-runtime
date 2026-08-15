# Usability Testing

This directory contains protocols, templates, and results for EVOSIA
usability testing.

## Structure

| Path | Purpose |
|------|---------|
| `M9_REAL_USER_TEST_PROTOCOL.md` | Full test protocol for real-user beta |
| `M9_FACILITATOR_QUICK_CARD.md` | Printable facilitator quick card |
| `M9_PARTICIPANT_TEMPLATE.json` | Participant record template (JSON schema) |
| `M9_RESULTS_SUMMARY_TEMPLATE.json` | Results aggregation template |
| `participants/` | Anonymized participant records (P01–P05) |

## Running the M9 Test

1. Print `M9_FACILITATOR_QUICK_CARD.md`.
2. Invite a non-technical participant.
3. Read only the facilitator script.
4. Record observations in a copy of `M9_PARTICIPANT_TEMPLATE.json`.
5. Store completed records in `participants/`.
6. Aggregate into `M9_RESULTS_SUMMARY_TEMPLATE.json`.

## Rules

- **Do not fabricate observations.**
- Use participant IDs only (no names or emails).
- All result fields start `null` until genuine participant data exists.
- See `M9_REAL_USER_TEST_PROTOCOL.md` for full rules.

## Validation

Run the artifact validator to ensure structure is correct:

```bash
pytest tests/test_m9_artifact_validator.py -v
```

This validates evidence structure only — it never infers human success.
