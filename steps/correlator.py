"""Step 4: Correlation & Suppression.

Groups related detections into single incident candidates.
Uses deterministic key-based + temporal grouping.
LLM generates the correlation narrative.

Input:  list of Detection
Output: list of IncidentCandidate
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date

from observer_advisor.models.enums import Application, DetectionResult
from observer_advisor.models.signals import Detection, IncidentCandidate
from observer_advisor.prompts.correlator_prompts import CORRELATION_PROMPT

logger = logging.getLogger(__name__)


# ── Deterministic grouping ────────────────────────────────────────────────────

def _build_dedupe_key(det: Detection) -> str:
    """Build a deduplication key: application + date."""
    return f"{det.application.value}_{date.today().isoformat()}"


def correlate(detections: list[Detection]) -> list[IncidentCandidate]:
    """Group detections into correlated incident candidates.

    Grouping strategy: by application + business date.
    All detections from the same app on the same day form one incident.
    """
    if not detections:
        return []

    # Group by dedupe key
    groups: dict[str, list[Detection]] = defaultdict(list)
    for det in detections:
        key = _build_dedupe_key(det)
        groups[key].append(det)

    # Build incident candidates
    candidates = []
    for key, dets in groups.items():
        app = dets[0].application

        candidate = IncidentCandidate(
            application=app,
            dedupe_key=key,
            contributing_detections=dets,
            business_date=date.today(),
        )
        candidates.append(candidate)
        logger.info(
            f"Correlated incident {candidate.incident_id}: "
            f"{len(dets)} detections for {app.value}"
        )

    logger.info(f"Correlation complete: {len(candidates)} incidents from {len(detections)} detections")
    return candidates


# ── Suppression ───────────────────────────────────────────────────────────────

# In-memory store of active incident keys (reset on restart).
# In production, use Redis or a DB table.
_active_incidents: dict[str, str] = {}


def suppress(candidates: list[IncidentCandidate]) -> list[IncidentCandidate]:
    """Filter out already-reported incidents (same dedupe key).

    Returns only new or updated candidates.
    """
    new_candidates = []
    for c in candidates:
        if c.dedupe_key in _active_incidents:
            logger.info(f"Suppressed duplicate incident: {c.dedupe_key}")
            continue
        _active_incidents[c.dedupe_key] = c.incident_id
        new_candidates.append(c)

    return new_candidates


def clear_suppression_cache():
    """Clear the suppression cache (useful for testing or daily reset)."""
    _active_incidents.clear()


# ── LLM helper ───────────────────────────────────────────────────────────────

def build_correlation_prompt(candidate: IncidentCandidate, rag_context: str = "") -> str:
    """Build prompt for LLM to generate correlation narrative."""
    detections_data = [
        {
            "check_id": d.check_id,
            "rule_name": d.rule_name,
            "result": d.result.value,
            "evidence": d.evidence,
            "application": d.application.value,
        }
        for d in candidate.contributing_detections
    ]
    return CORRELATION_PROMPT.format(
        detections_json=json.dumps(detections_data, indent=2),
        rag_context=rag_context or "No logs available.",
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences from LLM output."""
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def apply_correlation_narrative(
    candidate: IncidentCandidate, llm_response: str
) -> IncidentCandidate:
    """Apply LLM correlation narrative to a candidate."""
    try:
        cleaned = _strip_markdown_fences(llm_response)
        parsed = json.loads(cleaned)
        candidate.likely_cause = parsed.get("likely_cause")
        candidate.correlation_summary = parsed.get("correlation_narrative", cleaned)
    except (json.JSONDecodeError, Exception):
        candidate.correlation_summary = llm_response
    return candidate
