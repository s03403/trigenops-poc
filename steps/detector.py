"""Step 3: Detection Engine.

Applies deterministic rules to normalized signals to decide:
  PASS / WARNING / FAIL

LLM is used ONLY to explain triggered detections (not to decide).

Input:  list of NormalizedSignal
Output: list of Detection
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from observer_advisor.config import get_config
from observer_advisor.models.enums import (
    Application, DetectionResult, Severity, SignalType,
)
from observer_advisor.models.signals import NormalizedSignal, Detection
from observer_advisor.prompts.detector_prompts import DETECTION_EXPLANATION_PROMPT

logger = logging.getLogger(__name__)


# ── Rule functions ────────────────────────────────────────────────────────────

def _detect_ascm(signal: NormalizedSignal) -> Detection | None:
    """ASCM: Target Frequency freshness check."""
    if signal.check_id != "Target Frequency":
        return None

    today = date.today()
    observed = signal.observed_value

    # Error in query
    if signal.evidence.get("error"):
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ASCM,
            result=DetectionResult.FAIL,
            rule_name="ASCM Daily Data Check",
            evidence=f"Query failed: {signal.evidence['error']}",
            proposed_severity=Severity.P2,
        )

    # No data at all
    if observed is None:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ASCM,
            result=DetectionResult.FAIL,
            rule_name="ASCM Daily Data Check",
            evidence="No TARGETDATE found in METADATA table",
            proposed_severity=Severity.P2,
        )

    # Date comparison
    try:
        observed_date = date.fromisoformat(str(observed))
    except (ValueError, TypeError):
        observed_date = None

    if observed_date is None:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ASCM,
            result=DetectionResult.WARNING,
            rule_name="ASCM Daily Data Check",
            evidence=f"Cannot parse TARGETDATE: {observed}",
            proposed_severity=Severity.P3,
        )

    if observed_date < today:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ASCM,
            result=DetectionResult.FAIL,
            rule_name="ASCM Daily Data Check",
            evidence=f"TARGETDATE={observed_date} is behind today={today}",
            proposed_severity=Severity.P2,
        )

    # All good
    return Detection(
        signal_id=signal.signal_id,
        check_id=signal.check_id,
        application=Application.ASCM,
        result=DetectionResult.PASS,
        rule_name="ASCM Daily Data Check",
        evidence=f"TARGETDATE={observed_date} matches today={today}",
    )


def _detect_ate(signal: NormalizedSignal) -> Detection | None:
    """ATE: Error count & trade flow checks."""
    cfg = get_config().thresholds
    value = signal.observed_value

    # Query error
    if signal.evidence.get("error"):
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ATE,
            result=DetectionResult.FAIL,
            rule_name="ate_query_error",
            evidence=f"Query failed: {signal.evidence['error']}",
            proposed_severity=Severity.P2,
        )

    if value is None:
        return None

    # Trade errors
    if signal.check_id == "ate_trade_errors" and int(value) >= cfg.ate_error_min_count:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ATE,
            result=DetectionResult.FAIL,
            rule_name="ate_trade_errors_detected",
            evidence=f"Found {value} trade errors in last {5} minutes",
            proposed_severity=Severity.P2,
        )

    # Sync errors
    if signal.check_id == "ate_exchsync_errors" and int(value) >= cfg.ate_sync_error_min_count:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ATE,
            result=DetectionResult.FAIL,
            rule_name="ate_sync_errors_detected",
            evidence=f"Found {value} EXCHSYNC errors in last {5} minutes",
            proposed_severity=Severity.P2,
        )

    # Trade count = 0 during expected activity
    if signal.check_id == "ate_trade_count" and int(value) == 0:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.ATE,
            result=DetectionResult.WARNING,
            rule_name="ate_no_recent_trades",
            evidence=f"Zero trades in last {5} minutes",
            proposed_severity=Severity.P3,
        )

    # Pass
    return Detection(
        signal_id=signal.signal_id,
        check_id=signal.check_id,
        application=Application.ATE,
        result=DetectionResult.PASS,
        rule_name=f"{signal.check_id}_ok",
        evidence=f"Value={value} within acceptable range",
    )


def _detect_promptopt(signal: NormalizedSignal) -> Detection | None:
    """PromptOpt: Activity staleness, queue depth, error count."""
    cfg = get_config().thresholds
    value = signal.observed_value

    # Query error
    if signal.evidence.get("error"):
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.PROMPTOPT,
            result=DetectionResult.FAIL,
            rule_name="promptopt_query_error",
            evidence=f"Query failed: {signal.evidence['error']}",
            proposed_severity=Severity.P2,
        )

    if value is None:
        return None

    # Queue depth
    if signal.check_id == "promptopt_queue_depth":
        depth = int(value)
        if depth >= cfg.promptopt_queue_critical:
            return Detection(
                signal_id=signal.signal_id,
                check_id=signal.check_id,
                application=Application.PROMPTOPT,
                result=DetectionResult.FAIL,
                rule_name="promptopt_queue_critical",
                evidence=f"Queue depth={depth} exceeds critical threshold={cfg.promptopt_queue_critical}",
                proposed_severity=Severity.P1,
            )
        if depth >= cfg.promptopt_queue_warning:
            return Detection(
                signal_id=signal.signal_id,
                check_id=signal.check_id,
                application=Application.PROMPTOPT,
                result=DetectionResult.WARNING,
                rule_name="promptopt_queue_warning",
                evidence=f"Queue depth={depth} exceeds warning threshold={cfg.promptopt_queue_warning}",
                proposed_severity=Severity.P3,
            )

    # Error count
    if signal.check_id == "promptopt_errors" and int(value) > 0:
        return Detection(
            signal_id=signal.signal_id,
            check_id=signal.check_id,
            application=Application.PROMPTOPT,
            result=DetectionResult.FAIL,
            rule_name="promptopt_recent_errors",
            evidence=f"Found {value} errors in last 30 minutes",
            proposed_severity=Severity.P3,
        )

    # Pass
    return Detection(
        signal_id=signal.signal_id,
        check_id=signal.check_id,
        application=Application.PROMPTOPT,
        result=DetectionResult.PASS,
        rule_name=f"{signal.check_id}_ok",
        evidence=f"Value={value} within acceptable range",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def run_detection(signals: list[NormalizedSignal]) -> list[Detection]:
    """Run detection rules on all normalized signals.

    Returns only triggered detections (FAIL or WARNING).
    """
    detections: list[Detection] = []

    dispatch = {
        Application.ASCM: _detect_ascm,
        Application.ATE: _detect_ate,
        Application.PROMPTOPT: _detect_promptopt,
    }

    for signal in signals:
        fn = dispatch.get(signal.application)
        if fn is None:
            continue

        det = fn(signal)
        if det and det.result != DetectionResult.PASS:
            detections.append(det)
            logger.info(f"Detection triggered: {det.rule_name} -> {det.result}")

    logger.info(f"Detection complete: {len(detections)} anomalies from {len(signals)} signals")
    return detections


# ── LLM helper ───────────────────────────────────────────────────────────────

def build_explanation_prompt(det: Detection, signal: NormalizedSignal, rag_context: str = "") -> str:
    """Build prompt for LLM to explain a detection."""
    return DETECTION_EXPLANATION_PROMPT.format(
        application=det.application.value,
        rule_name=det.rule_name,
        observed_value=signal.observed_value,
        expected_value=signal.expected_value,
        result=det.result.value,
        rag_context=rag_context if rag_context else "No relevant application logs available.",
    )
