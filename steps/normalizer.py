"""Step 2: Normalization & Enrichment.

Converts raw tool outputs into canonical NormalizedSignal objects.
Optionally uses LLM for enrichment context.

Input:  raw tool results (list of dicts)
Output: list of NormalizedSignal
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date

from observer_advisor.models.enums import Application, SignalType
from observer_advisor.models.signals import NormalizedSignal
from observer_advisor.prompts.normalizer_prompts import ENRICHMENT_PROMPT

logger = logging.getLogger(__name__)


# ── Deterministic normalization ───────────────────────────────────────────────

def _normalize_ascm(raw: dict) -> list[NormalizedSignal]:
    """Normalize ASCM raw check result."""
    
    today = date.today()
    observed = raw.get("raw_value")

    return [NormalizedSignal(
        check_id="Target Frequency",
        application=Application.ASCM,
        signal_type=SignalType.DATA_AVAILABILITY,
        observed_value=observed,
        expected_value=today.isoformat(),
        business_date=today,
        evidence={
            "source_table": raw.get("source_table", ""),
            "query": raw.get("query_executed", ""),
            "error": raw.get("error"),
        },
    )]


def _normalize_ate(raw: dict) -> list[NormalizedSignal]:
    """Normalize ATE raw check results (multiple sub-checks)."""
    signals = []
    today = date.today()
    checks = raw.get("checks", {})

    type_map = {
        "ate_trade_errors": SignalType.ERROR_COUNT,
        "ate_trade_count": SignalType.TRADE_FLOW,
        "ate_exchsync_errors": SignalType.SYNC_ERROR,
    }

    for check_id, check_data in checks.items():
        signals.append(NormalizedSignal(
            check_id=check_id,
            application=Application.ATE,
            signal_type=type_map.get(check_id, SignalType.ERROR_COUNT),
            observed_value=check_data.get("raw_value"),
            expected_value=0 if "error" in check_id else None,
            business_date=today,
            evidence={
                "source_table": check_data.get("source_table", ""),
                "error": check_data.get("error"),
            },
        ))

    return signals


def _normalize_promptopt(raw: dict) -> list[NormalizedSignal]:
    """Normalize PromptOpt raw check results (multiple sub-checks)."""
    signals = []
    today = date.today()
    checks = raw.get("checks", {})

    type_map = {
        "promptopt_activity": SignalType.EXECUTION_CYCLE,
        "promptopt_queue_depth": SignalType.QUEUE_DEPTH,
        "promptopt_errors": SignalType.ERROR_COUNT,
    }

    for check_id, check_data in checks.items():
        signals.append(NormalizedSignal(
            check_id=check_id,
            application=Application.PROMPTOPT,
            signal_type=type_map.get(check_id, SignalType.ERROR_COUNT),
            observed_value=check_data.get("raw_value"),
            business_date=today,
            evidence={
                "source_table": check_data.get("source_table", ""),
                "error": check_data.get("error"),
            },
        ))

    return signals


def normalize_all(raw_results: list[dict]) -> list[NormalizedSignal]:
    """Normalize all raw tool results into canonical signals.

    Args:
        raw_results: List of dicts returned by the 3 DB tools.

    Returns:
        List of NormalizedSignal objects.
    """
    signals = []

    for raw in raw_results:
        app = raw.get("application", "")

        if app == "ASCM":
            signals.extend(_normalize_ascm(raw))
        elif app == "ATE":
            signals.extend(_normalize_ate(raw))
        elif app == "PromptOpt":
            signals.extend(_normalize_promptopt(raw))
        else:
            logger.warning(f"Unknown application in raw result: {app}")

    logger.info(f"Normalized {len(signals)} signals from {len(raw_results)} raw results")
    return signals


# ── LLM enrichment (optional) ────────────────────────────────────────────────

def build_enrichment_prompt(signal: NormalizedSignal) -> str:
    """Build the LLM enrichment prompt for a signal."""
    return ENRICHMENT_PROMPT.format(
        application=signal.application.value,
        check_id=signal.check_id,
        source_table=signal.evidence.get("source_table", "unknown"),
        observed_value=signal.observed_value,
        expected_value=signal.expected_value,
        business_date=signal.business_date.isoformat(),
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences from LLM output."""
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def apply_enrichment(signal: NormalizedSignal, llm_response: str) -> NormalizedSignal:
    """Apply LLM enrichment response to a signal, validated via Pydantic."""
    from observer_advisor.models.signals import Enrichment
    try:
        cleaned = _strip_markdown_fences(llm_response)
        parsed = json.loads(cleaned)
        enrichment = Enrichment(**parsed)
        signal.enrichment = enrichment.model_dump()
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Enrichment parsing failed: {e}")
        signal.enrichment = Enrichment().model_dump()
    return signal
