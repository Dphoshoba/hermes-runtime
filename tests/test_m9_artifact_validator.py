"""M9 Usability Artifact Validator.

Validates the structure of M9 usability test artifacts WITHOUT inferring
human success. It checks evidence structure only — never fabricates results.

Usage:
    python -m pytest tests/test_m9_artifact_validator.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
USABILITY_DIR = REPO / "validation" / "usability"
PARTICIPANTS_DIR = USABILITY_DIR / "participants"

REQUIRED_TASKS = [f"task_{i}" for i in range(1, 11)]


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


class ValidationError:
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def __str__(self):
        return f"{self.path}: {self.message}"


def validate_participant_record(path: Path) -> list[ValidationError]:
    """Validate a single participant record's structure."""
    errors = []
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [ValidationError(str(path), f"invalid JSON: {e}")]

    # participant_id must be present
    if not data.get("participant_id"):
        errors.append(ValidationError(str(path), "missing participant_id"))

    # Tasks 1-10 must exist
    tasks = data.get("tasks", {})
    for task_name in REQUIRED_TASKS:
        if task_name not in tasks:
            errors.append(ValidationError(str(path), f"missing {task_name}"))
        else:
            task = tasks[task_name]
            # Each task must have the required fields
            for field in ["completed", "assistance_required", "duration_seconds",
                          "observed_behavior", "participant_response"]:
                if field not in task:
                    errors.append(ValidationError(str(path), f"{task_name} missing {field}"))

    # Authority comprehension must be present
    ac = data.get("authority_comprehension", {})
    for field in ["understands_project_not_changed",
                  "understands_approval_not_execution", "pass"]:
        if field not in ac:
            errors.append(ValidationError(str(path), f"authority_comprehension missing {field}"))

    # Verbatim responses must be present as fields (but may be null for blank templates)
    if "task_9_response_verbatim" not in data:
        errors.append(ValidationError(str(path), "missing task_9_response_verbatim"))
    if "task_10_response_verbatim" not in data:
        errors.append(ValidationError(str(path), "missing task_10_response_verbatim"))

    return errors


def validate_results_summary(path: Path) -> list[ValidationError]:
    """Validate the results summary template."""
    errors = []
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [ValidationError(str(path), f"invalid JSON: {e}")]

    # Required top-level fields
    for field in ["real_users_tested", "task_completion_rate",
                  "authority_comprehension_rate", "median_time_to_first_analysis",
                  "technical_blockers", "operator_interventions",
                  "usability_defects_found", "usability_defects_resolved",
                  "critical_usability_failures", "confidence_distribution",
                  "authority_gate", "decision"]:
        if field not in data:
            errors.append(ValidationError(str(path), f"missing {field}"))

    # Authority gate
    ag = data.get("authority_gate", {})
    for field in ["participants_correct_task_9", "participants_correct_task_10",
                  "participants_passing_both", "total_participants", "rate"]:
        if field not in ag:
            errors.append(ValidationError(str(path), f"authority_gate missing {field}"))

    # Decision
    d = data.get("decision", {})
    for field in ["REAL_USER_USABILITY", "EXECUTION_AUTHORITY_COMPREHENSION",
                  "READY_FOR_M10"]:
        if field not in d:
            errors.append(ValidationError(str(path), f"decision missing {field}"))

    return errors


def validate_blank_template_is_unpopulated(path: Path) -> list[ValidationError]:
    """Ensure blank participant templates have NOT been pre-populated with
    fabricated observations. participant_id may be non-null (it identifies
    the template), but all other observational fields must be null."""
    errors = []
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [ValidationError(str(path), f"invalid JSON: {e}")]

    # All observational fields must be null in a blank template
    observational_fields = [
        "test_timestamp", "evosia_commit", "prior_hermes_experience",
        "technical_experience", "time_to_first_analysis_seconds",
        "technical_blockers", "operator_interventions", "user_confidence",
        "usability_defects", "critical_usability_failures",
        "task_9_response_verbatim", "task_10_response_verbatim",
        "overall_result",
    ]
    for field in observational_fields:
        if data.get(field) is not None:
            errors.append(ValidationError(
                str(path),
                f"blank template has pre-populated {field} — possible fabrication"
            ))

    # Tasks must all be null
    tasks = data.get("tasks", {})
    for task_name in REQUIRED_TASKS:
        task = tasks.get(task_name, {})
        for field in ["completed", "assistance_required", "duration_seconds",
                      "observed_behavior", "participant_response"]:
            if task.get(field) is not None:
                errors.append(ValidationError(
                    str(path),
                    f"blank template has pre-populated {task_name}.{field} — possible fabrication"
                ))

    # Authority comprehension must be null
    ac = data.get("authority_comprehension", {})
    for field in ["understands_project_not_changed",
                  "understands_approval_not_execution", "pass"]:
        if ac.get(field) is not None:
            errors.append(ValidationError(
                str(path),
                f"blank template has pre-populated authority_comprehension.{field} — possible fabrication"
            ))

    return errors


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_participant_template_structure():
    """The template must have all required fields (except participant_id,
    which is null in the template)."""
    template_path = USABILITY_DIR / "M9_PARTICIPANT_TEMPLATE.json"
    assert template_path.exists(), f"missing {template_path}"
    errors = validate_participant_record(template_path)
    # Filter out participant_id requirement for the template itself
    errors = [e for e in errors if "participant_id" not in e.message]
    assert not errors, f"template errors: {[str(e) for e in errors]}"


def test_blank_participant_records_exist():
    """P01-P05 must exist."""
    for i in range(1, 6):
        path = PARTICIPANTS_DIR / f"P{i:02d}.json"
        assert path.exists(), f"missing {path}"


def test_blank_records_are_unpopulated():
    """Blank participant records must NOT contain fabricated observations."""
    for i in range(1, 6):
        path = PARTICIPANTS_DIR / f"P{i:02d}.json"
        errors = validate_blank_template_is_unpopulated(path)
        assert not errors, f"fabrication detected: {[str(e) for e in errors]}"


def test_results_summary_template_structure():
    """The results summary template must have all required fields."""
    path = USABILITY_DIR / "M9_RESULTS_SUMMARY_TEMPLATE.json"
    assert path.exists(), f"missing {path}"
    errors = validate_results_summary(path)
    assert not errors, f"summary errors: {[str(e) for e in errors]}"


def test_results_summary_is_unpopulated():
    """Results summary must NOT be pre-populated."""
    path = USABILITY_DIR / "M9_RESULTS_SUMMARY_TEMPLATE.json"
    data = load_json(path)
    # All result fields must be null
    for field in ["real_users_tested", "task_completion_rate",
                  "authority_comprehension_rate", "median_time_to_first_analysis",
                  "technical_blockers", "operator_interventions",
                  "usability_defects_found", "usability_defects_resolved",
                  "critical_usability_failures"]:
        assert data.get(field) is None, f"pre-populated {field} — possible fabrication"


def test_protocol_document_exists():
    """The test protocol must exist."""
    path = USABILITY_DIR / "M9_REAL_USER_TEST_PROTOCOL.md"
    assert path.exists(), f"missing {path}"


def test_facilitator_quick_card_exists():
    """The facilitator quick card must exist."""
    path = USABILITY_DIR / "M9_FACILITATOR_QUICK_CARD.md"
    assert path.exists(), f"missing {path}"


def test_participants_readme_exists():
    """The participants directory README must exist."""
    path = PARTICIPANTS_DIR / "README.md"
    assert path.exists(), f"missing {path}"
