"""Step 5: Severity & Routing.

Computes final severity, determines assignment group, and builds
the Incident object for ServiceNow / Advisor handoff.

Detection severity rules are deterministic.
LLM generates the human-readable incident description.

Input:  list of IncidentCandidate
Output: list of Incident
"""

from __future__ import annotations

import json
import logging
from datetime import date

from observer_advisor.config import get_config
from observer_advisor.models.enums import Application, Severity, DetectionResult, Environment
from observer_advisor.models.signals import Detection, IncidentCandidate, Incident
from observer_advisor.prompts.router_prompts import (
    INCIDENT_DESCRIPTION_PROMPT,
    ROUTING_PROMPT,
)

logger = logging.getLogger(__name__)


# ── Deterministic severity ────────────────────────────────────────────────────

ASSIGNMENT_GROUPS = {
    Application.ASCM: "ASCM App Support",
    Application.ATE: "ATE Trading Support",
    Application.PROMPTOPT: "PromptOpt Data Ops",
}


def _compute_severity(candidate: IncidentCandidate) -> Severity:
    """Deterministic severity from contributing detections.

    Takes the highest (most critical) proposed severity.
    P1 > P2 > P3 > P4 > NONE.
    """
    severity_order = {Severity.P1: 1, Severity.P2: 2, Severity.P3: 3, Severity.P4: 4, Severity.NONE: 5}
    best = Severity.NONE

    for det in candidate.contributing_detections:
        if det.proposed_severity and severity_order.get(det.proposed_severity, 5) < severity_order.get(best, 5):
            best = det.proposed_severity

    # Env modifier: UAT downgrades by 1 level
    env = get_config().environment
    if env == "UAT" and best in (Severity.P1, Severity.P2):
        best = Severity.P3

    return best


def _build_title(candidate: IncidentCandidate) -> str:
    """Build a concise incident title."""
    rules = [d.rule_name for d in candidate.contributing_detections]
    return f"[{candidate.application.value}] Anomaly detected: {', '.join(rules[:3])}"


def _build_evidence_summary(candidate: IncidentCandidate) -> dict:
    """Compile evidence from all detections."""
    return {
        "detections": [
            {
                "check_id": d.check_id,
                "rule": d.rule_name,
                "result": d.result.value,
                "evidence": d.evidence,
            }
            for d in candidate.contributing_detections
        ],
        "business_date": candidate.business_date.isoformat(),
        "correlation_summary": candidate.correlation_summary,
    }


def _build_default_description(candidate: IncidentCandidate, severity: Severity) -> str:
    """Fallback description if LLM is not used."""
    lines = [
        f"Application: {candidate.application.value}",
        f"Severity: {severity.value}",
        f"Business Date: {candidate.business_date.isoformat()}",
        f"Detections: {len(candidate.contributing_detections)}",
        "",
    ]
    for d in candidate.contributing_detections:
        lines.append(f"- [{d.result.value}] {d.rule_name}: {d.evidence}")

    if candidate.correlation_summary:
        lines.append(f"\nCorrelation: {candidate.correlation_summary}")

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def route(candidates: list[IncidentCandidate]) -> list[Incident]:
    """Convert incident candidates into final Incident objects.

    Computes severity, assigns group, builds description.
    """
    incidents = []

    for candidate in candidates:
        severity = _compute_severity(candidate)
        assignment = ASSIGNMENT_GROUPS.get(candidate.application, "Infrastructure Ops")
        env = Environment(get_config().environment)

        incident = Incident(
            incident_id=candidate.incident_id,
            severity=severity,
            application=candidate.application,
            environment=env,
            assignment_group=assignment,
            title=_build_title(candidate),
            description=_build_default_description(candidate, severity),
            evidence_summary=_build_evidence_summary(candidate),
            correlation_summary=candidate.correlation_summary,
            advisor_payload={
                "incident_id": candidate.incident_id,
                "severity": severity.value,
                "application": candidate.application.value,
                "detections": [d.model_dump() for d in candidate.contributing_detections],
                "correlation_summary": candidate.correlation_summary,
                "business_date": candidate.business_date.isoformat(),
            },
        )
        incidents.append(incident)
        logger.info(
            f"Routed incident {incident.incident_id}: "
            f"{severity.value} -> {assignment}"
        )

    return incidents


# ── LLM helpers ──────────────────────────────────────────────────────────────

def build_description_prompt(candidate: IncidentCandidate, severity: Severity, rag_context: str = "") -> str:
    """Build prompt for LLM to generate incident description."""
    detections_summary = "; ".join(
        f"{d.rule_name}: {d.evidence}" for d in candidate.contributing_detections
    )
    return INCIDENT_DESCRIPTION_PROMPT.format(
        application=candidate.application.value,
        environment=get_config().environment,
        severity=severity.value,
        detections_summary=detections_summary,
        correlation_summary=candidate.correlation_summary or "N/A",
        business_date=candidate.business_date.isoformat(),
        rag_context=rag_context or "No logs available.",
    )


def build_routing_prompt(candidate: IncidentCandidate) -> str:
    """Build prompt for LLM to recommend assignment group."""
    detections_summary = "; ".join(
        f"{d.rule_name}: {d.evidence}" for d in candidate.contributing_detections
    )
    return ROUTING_PROMPT.format(
        application=candidate.application.value,
        environment=get_config().environment,
        incident_type=candidate.contributing_detections[0].rule_name if candidate.contributing_detections else "unknown",
        detections_summary=detections_summary,
    )
