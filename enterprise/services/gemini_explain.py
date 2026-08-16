"""Governed Gemini explanation layer.

Gemini may explain. EVOSIA decides.

This module is a non-authoritative explanation service. It accepts only
explicitly-permitted authoritative evidence supplied by the EVOSIA backend
and returns plain-language explanations. It NEVER creates, infers, or
overrides authoritative EVOSIA state.

Security:
  - Credentials read from environment only (EVOSIA_GEMINI_API_KEY)
  - API key never logged or returned to client
  - Only explicitly-permitted evidence fields reach the model
  - Failure is non-fatal: callers receive an insufficient-evidence /
    unavailable response

Gemini may EXPLAIN:
  - EVOSIA findings in plain language
  - why something needs attention
  - context questions
  - proposed missions
  - what approval for preparation means
  - prepared-change state

Gemini may NOT generate or determine ANY of:
  - finding existence/severity/classification
  - evidence authenticity/hashes
  - authority level / permission state
  - mission state / approval
  - whether preparation is authorized or completed
  - PREPARED status
  - workspace paths / affected files / patches
  - validation status/results / test results
  - mutation / execution / deployment state
  - governance decisions
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — server-side only
# ---------------------------------------------------------------------------

_gemini_api_key = os.environ.get("EVOSIA_GEMINI_API_KEY")
_gemini_model = os.environ.get("EVOSIA_GEMINI_MODEL", "gemini-1.5-flash")
_gemini_enabled = bool(_gemini_api_key)

# ---------------------------------------------------------------------------
# Authoritative evidence allow-lists
# ---------------------------------------------------------------------------

# Only these Finding fields may reach Gemini — always presentation-layer only.
_FINDING_ALLOWED_FIELDS = frozenset({"title", "category", "plain_title", "why_it_matters"})

# Only these Mission fields may reach Gemini.
_MISSION_ALLOWED_FIELDS = frozenset({
    "mission_id", "title", "plain_title", "what", "why", "benefit",
    "risk", "scope", "validation", "rollback",
})

# Only these ContextQuestion fields may reach Gemini.
_CONTEXT_ALLOWED_FIELDS = frozenset({"topic", "question", "why_asking"})

# Only these PreparedChange fields may reach Gemini.
_PREPARED_ALLOWED_FIELDS = frozenset({"title", "description"})


def _filter_allowed(source: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    """Return only allow-listed fields. All other data is excluded."""
    return {k: source[k] for k in allowed if k in source}


def _call_gemini(prompt: str) -> str:
    """Minimal Gemini call. Returns text or raises on failure.

    Never logs the API key. Swallows the response metadata — only the
    text content is surfaced, and only as GEMINI_EXPLANATION provenance.
    """
    if not _gemini_enabled:
        raise RuntimeError("Gemini integration not configured")
    try:
        from google import genai  # local import — not a hard dependency
    except ImportError as exc:
        raise RuntimeError(f"Gemini client unavailable: {exc}") from exc

    client = genai.Client(api_key=_gemini_api_key)
    response = client.models.generate_content(model=_gemini_model, contents=prompt)
    return response.text


def explain_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Explain an EVOSIA finding in plain language.

    Finding evidence is authoritative (EVOSIA). Gemini only translates.
    The returned text carries 'GEMINI_EXPLANATION' provenance only.
    """
    safe = _filter_allowed(finding, _FINDING_ALLOWED_FIELDS)
    if not safe:
        return _insufficient("No explainable finding evidence supplied")
    prompt = (
        "EVOSIA has reviewed a project and produced this finding. "
        "Explain it in plain, non-technical language that a project stakeholder "
        "can understand. Do NOT claim this is your own analysis. "
        "Do NOT fabricate severity, evidence, or findings. "
        f"Finding: {safe}\n\nPlain-language explanation:"
    )
    return _explain(prompt)


def explain_context_question(question: dict[str, Any]) -> dict[str, Any]:
    """Explain why EVOSIA needs this context."""
    safe = _filter_allowed(question, _CONTEXT_ALLOWED_FIELDS)
    if not safe:
        return _insufficient("No explainable context evidence supplied")
    prompt = (
        "EVOSIA has a question about a project that needs a human's help. "
        "Explain in plain language WHO might answer it and WHY it matters, "
        "without claiming your own analysis authority. "
        f"Context question: {safe}\n\nPlain-language explanation:"
    )
    return _explain(prompt)


def explain_mission(mission: dict[str, Any]) -> dict[str, Any]:
    """Explain an existing proposed mission from EVOSIA."""
    safe = _filter_allowed(mission, _MISSION_ALLOWED_FIELDS)
    if not safe:
        return _insufficient("No explainable mission evidence supplied")
    prompt = (
        "EVOSIA has proposed this work item. Explain it in plain language "
        "to a project stakeholder: what it is, why it matters, and what "
        "approving preparation means — without fabricating findings, evidence, "
        "workspace paths, patches, or execution. "
        "Approval for preparation does NOT mean the change has been executed, merged, or deployed. "
        f"Mission: {safe}\n\nPlain-language explanation:"
    )
    return _explain(prompt)


def explain_prepared_change(prepared: dict[str, Any]) -> dict[str, Any]:
    """Explain an existing prepared-change state from EVOSIA.

    Only title/description are sent — never workspace_path, affected_files,
    diff_content, or validation results. Those are authoritative EVOSIA state
    that Gemini must neither see nor restate.
    """
    safe = _filter_allowed(prepared, _PREPARED_ALLOWED_FIELDS)
    if not safe:
        return _insufficient("No explainable prepared-change evidence supplied")
    prompt = (
        "EVOSIA has prepared a change in an isolated workspace. "
        "Explain what 'prepared change' means to a project stakeholder in plain "
        "language — what approval enabled it, what environment it is in, and "
        "that it has NOT been merged, deployed, or applied to production. "
        "Do NOT state or infer workspace paths, file lists, patches, or validation "
        "results — those are authoritative EVOSIA details. "
        f"Prepared change: {safe}\n\nPlain-language explanation:"
    )
    return _explain(prompt)


def explain_approval() -> dict[str, Any]:
    """Static explanation: what approval for preparation means."""
    prompt = (
        "EVOSIA has an authority boundary called 'approval for preparation'. "
        "Explain in plain language what this permits and what it does NOT permit: "
        "it allows EVOSIA to create a candidate change in an isolated workspace, "
        "but does NOT execute, merge, deploy, or modify production. "
        "Do NOT fabricate workspace paths, patches, or validation results."
    )
    return _explain(prompt)


# ---------------------------------------------------------------------------
# Response helpers — all carry explicit GEMINI_EXPLANATION provenance
# ---------------------------------------------------------------------------

_PROVENANCE = "GEMINI_EXPLANATION"


def _explain(prompt: str) -> dict[str, Any]:
    """Call Gemini and wrap result with provenance. Failure is non-fatal."""
    try:
        text = _call_gemini(prompt)
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        logger.warning("Gemini explanation unavailable: %s", exc)
        return {
            "explanation": (
                "EVOSIA cannot provide a plain-language explanation for this "
                "item at the moment. The authoritative data above is still "
                "valid and complete."
            ),
            "provenance": _PROVENANCE + "_UNAVAILABLE",
            "available": False,
        }
    return {
        "explanation": text,
        "provenance": _PROVENANCE,
        "available": True,
    }


def _insufficient(reason: str) -> dict[str, Any]:
    return {
        "explanation": (
            "EVOSIA has insufficient evidence to generate an explanation "
            f"for this request. Reason: {reason}"
        ),
        "provenance": _PROVENANCE + "_INSUFFICIENT_EVIDENCE",
        "available": False,
    }


# Re-export for dependency injection / testing
__all__ = [
    "explain_finding",
    "explain_context_question",
    "explain_mission",
    "explain_prepared_change",
    "explain_approval",
    "gemini_enabled",
]

# Module-level flag for tests
gemini_enabled = _gemini_enabled
