"""LangGraph graph definition for Observer Agent pipeline.

Flow (per-app isolation):
  Step 1: run_tools (all apps at once) → raw results
  For each app with data:
    Step 2: normalize → Step 3: detect → Step 4: correlate → Step 5: route → save
                                          ↓ (no anomalies)
                                        END
"""

from __future__ import annotations

import json
import logging

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from observer_advisor.config import get_config
from observer_advisor.state import ObserverState
from observer_advisor.tools.ascm_tool import check_ascm
from observer_advisor.tools.ate_tool import check_ate
from observer_advisor.tools.promptopt_tool import check_promptopt
from observer_advisor.steps.normalizer import (
    normalize_all, NormalizedSignal, build_enrichment_prompt, apply_enrichment,
)
from observer_advisor.steps.detector import (
    run_detection, build_explanation_prompt,
)
from observer_advisor.steps.correlator import (
    correlate, suppress, build_correlation_prompt, apply_correlation_narrative,
)
from observer_advisor.steps.router import (
    route, build_description_prompt, _compute_severity,
)
from observer_advisor.steps.persistence import (
    save_raw_results, save_signals, save_detections,
    save_incidents, save_final_incidents,
)
from observer_advisor.tools.rag import retrieve_logs
from observer_advisor.logging_config import LLM_LOGGER

logger = logging.getLogger(__name__)
llm_logger = logging.getLogger(LLM_LOGGER)

# ── Tools ─────────────────────────────────────────────────────────────────────

# ── Tools registry ────────────────────────────────────────────────────────────

TOOLS_MAP = {
    "ascm": check_ascm,
    "ate": check_ate,
    "promptopt": check_promptopt,
}


# ── LLM setup ────────────────────────────────────────────────────────────────

def _get_llm():
    cfg = get_config().llm
    return AzureChatOpenAI(
        azure_endpoint=cfg.api_base,
        api_key=cfg.api_key,
        api_version=cfg.api_version,
        azure_deployment=cfg.deployment,
        temperature=cfg.temperature,
    )


# ── Node functions ────────────────────────────────────────────────────────────

def run_tools_node(state: ObserverState) -> dict:
    """Node 1: Call only the DB tools that are due for this cycle."""
    tools_to_run = state.get("tools_to_run", list(TOOLS_MAP.keys()))
    logger.info(f"=== Running DB check tools: {tools_to_run} ===")
    raw_results = []

    for name in tools_to_run:
        tool_fn = TOOLS_MAP.get(name)
        if tool_fn is None:
            logger.warning(f"Unknown tool: {name}")
            continue
        try:
            result = tool_fn.invoke({})
            raw_results.append(result)
            logger.info(f"Tool {name} returned: {result.get('application', 'unknown')}")
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            raw_results.append({
                "application": name.upper(),
                "error": str(e),
            })

    return {"raw_results": raw_results}


def save_raw_node(state: ObserverState) -> dict:
    """Save Step 1 output to JSON."""
    save_raw_results(state.get("raw_results", []))
    return {}


def normalize_node(state: ObserverState) -> dict:
    """Node 2: Normalize & enrich raw results into canonical signals.
    LLM enriches each signal with interpretation & business context."""
    logger.info("=== Step 2: Normalization & Enrichment ===")
    raw_results = state.get("raw_results", [])
    signals = normalize_all(raw_results)

    # LLM enrichment for each signal
    try:
        llm = _get_llm()
        for signal in signals:
            prompt = build_enrichment_prompt(signal)
            llm_logger.info(f"[Step2] [{signal.application.value}] Enrichment prompt for {signal.signal_id}")
            llm_logger.debug(f"[Step2] PROMPT:\n{prompt}")
            response = llm.invoke([HumanMessage(content=prompt)])
            llm_output = response.content
            llm_logger.info(f"[Step2] [{signal.application.value}] Response received for {signal.signal_id}")
            llm_logger.debug(f"[Step2] RESPONSE:\n{llm_output}")
            apply_enrichment(signal, llm_output)
            # Store LLM input/output in evidence for traceability
            signal.evidence["llm_input"] = prompt
            signal.evidence["llm_output"] = llm_output
            logger.info(f"Enriched signal {signal.signal_id}")
    except Exception as e:
        logger.warning(f"LLM enrichment failed (continuing without): {e}")

    return {"signals": [s.model_dump() for s in signals]}


def save_signals_node(state: ObserverState) -> dict:
    """Save Step 2 output to JSON."""
    save_signals(state.get("signals", []))
    return {}


def detect_node(state: ObserverState) -> dict:
    """Node 3: Run detection rules on normalized signals.
    Detection is deterministic. LLM explains each triggered detection."""
    logger.info("=== Step 3: Detection Engine ===")
    signal_dicts = state.get("signals", [])
    signals = [NormalizedSignal(**s) for s in signal_dicts]
    signal_map = {s.signal_id: s for s in signals}
    detections = run_detection(signals)

    # LLM explanation for each triggered detection
    if detections:
        try:
            llm = _get_llm()
            for det in detections:
                signal = signal_map.get(det.signal_id)
                if signal:
                    # RAG: retrieve relevant logs for this application
                    rag_context = retrieve_logs(
                        query=det.evidence,
                        application=det.application.value,
                    )
                    prompt = build_explanation_prompt(det, signal, rag_context=rag_context)
                    llm_logger.info(f"[Step3] [{det.application.value}] Explanation prompt for {det.detection_id}")
                    llm_logger.debug(f"[Step3] PROMPT:\n{prompt}")
                    response = llm.invoke([HumanMessage(content=prompt)])
                    llm_output = response.content.strip()
                    llm_logger.info(f"[Step3] [{det.application.value}] Response received for {det.detection_id}")
                    llm_logger.debug(f"[Step3] RESPONSE:\n{llm_output}")
                    det.evidence += f" | LLM: {llm_output}"
                    # Store rag_context for traceability
                    det._rag_context = rag_context
                    logger.info(f"LLM explained detection {det.detection_id}")
        except Exception as e:
            logger.warning(f"LLM explanation failed (continuing without): {e}")

    # Attach llm_input/llm_output/rag_context to each detection dict
    det_dicts = []
    for det in detections:
        d = det.model_dump()
        signal = signal_map.get(det.signal_id)
        rag_ctx = getattr(det, '_rag_context', '')
        if signal:
            d["llm_input"] = build_explanation_prompt(det, signal, rag_context=rag_ctx)
        # llm_output is already embedded in evidence after "| LLM:"
        d["llm_output"] = det.evidence.split("| LLM: ", 1)[1] if "| LLM: " in det.evidence else None
        d["rag_context"] = rag_ctx
        det_dicts.append(d)

    return {"detections": det_dicts}


def save_detections_node(state: ObserverState) -> dict:
    """Save Step 3 output to JSON."""
    save_detections(state.get("detections", []))
    return {}


def should_continue(state: ObserverState) -> str:
    """Edge: If no anomalies detected, skip to END."""
    detections = state.get("detections", [])
    if not detections:
        logger.info("No anomalies detected — ending pipeline.")
        return "end"
    logger.info(f"{len(detections)} anomalies detected — continuing to correlation.")
    return "correlate"


def correlate_node(state: ObserverState) -> dict:
    """Node 4: Correlate & suppress detections into incident candidates.
    Grouping is deterministic. LLM generates correlation narrative."""
    from observer_advisor.models.signals import Detection as DetectionModel
    logger.info("=== Step 4: Correlation & Suppression ===")
    det_dicts = state.get("detections", [])
    detections = [DetectionModel(**{k: v for k, v in d.items() if k not in ("llm_input", "llm_output")}) for d in det_dicts]
    candidates = correlate(detections)
    candidates = suppress(candidates)

    # LLM correlation narrative for each incident candidate
    llm_traces: dict[str, dict] = {}  # incident_id -> {input, output}
    try:
        llm = _get_llm()
        for candidate in candidates:
            # RAG: retrieve relevant logs for this application
            evidence_query = " ".join(
                d.evidence for d in candidate.contributing_detections
            )
            rag_context = retrieve_logs(
                query=evidence_query,
                application=candidate.application.value,
            )
            prompt = build_correlation_prompt(candidate, rag_context=rag_context)
            llm_logger.info(f"[Step4] [{candidate.application.value}] Correlation prompt for {candidate.incident_id}")
            llm_logger.debug(f"[Step4] PROMPT:\n{prompt}")
            response = llm.invoke([HumanMessage(content=prompt)])
            llm_output = response.content
            llm_logger.info(f"[Step4] [{candidate.application.value}] Response received for {candidate.incident_id}")
            llm_logger.debug(f"[Step4] RESPONSE:\n{llm_output}")
            apply_correlation_narrative(candidate, llm_output)
            llm_traces[candidate.incident_id] = {
                "llm_input": prompt,
                "llm_output": llm_output,
                "rag_context": rag_context,
            }
    except Exception as e:
        logger.warning(f"LLM correlation failed (continuing without): {e}")

    # Attach llm_input/llm_output to each candidate dict
    inc_dicts = []
    for c in candidates:
        d = c.model_dump()
        trace = llm_traces.get(c.incident_id, {})
        d["llm_input"] = trace.get("llm_input")
        d["llm_output"] = trace.get("llm_output")
        d["rag_context"] = trace.get("rag_context")
        inc_dicts.append(d)

    return {"incidents": inc_dicts}


def save_incidents_node(state: ObserverState) -> dict:
    """Save Step 4 output to JSON."""
    save_incidents(state.get("incidents", []))
    return {}


def route_node(state: ObserverState) -> dict:
    """Node 5: Severity scoring & routing.
    Severity is deterministic. LLM generates incident description."""
    from observer_advisor.models.signals import IncidentCandidate, Detection as DetectionModel
    logger.info("=== Step 5: Severity & Routing ===")
    inc_dicts = state.get("incidents", [])

    candidates = []
    for d in inc_dicts:
        # Strip llm_input/llm_output/rag_context before reconstructing model
        clean = {k: v for k, v in d.items() if k not in ("llm_input", "llm_output", "rag_context")}
        dets = [DetectionModel(**{k: v for k, v in det.items() if k not in ("llm_input", "llm_output")})
                for det in clean.get("contributing_detections", [])]
        clean["contributing_detections"] = dets
        candidates.append(IncidentCandidate(**clean))

    incidents = route(candidates)

    # LLM-generated incident description for each incident
    llm_traces: dict[str, dict] = {}  # incident_id -> {input, output}
    try:
        llm = _get_llm()
        for i, incident in enumerate(incidents):
            candidate = candidates[i] if i < len(candidates) else None
            if candidate:
                # RAG: retrieve relevant logs for this application
                evidence_query = " ".join(
                    d.evidence for d in candidate.contributing_detections
                )
                rag_context = retrieve_logs(
                    query=evidence_query,
                    application=candidate.application.value,
                )
                prompt = build_description_prompt(candidate, incident.severity, rag_context=rag_context)
                llm_logger.info(f"[Step5] [{candidate.application.value}] Description prompt for {incident.incident_id}")
                llm_logger.debug(f"[Step5] PROMPT:\n{prompt}")
                response = llm.invoke([HumanMessage(content=prompt)])
                llm_output = response.content.strip()
                llm_logger.info(f"[Step5] [{candidate.application.value}] Response received for {incident.incident_id}")
                llm_logger.debug(f"[Step5] RESPONSE:\n{llm_output}")
                incident.description = llm_output
                llm_traces[incident.incident_id] = {
                    "llm_input": prompt,
                    "llm_output": llm_output,
                    "rag_context": rag_context,
                }

                logger.info(f"LLM described incident {incident.incident_id}")
    except Exception as e:
        logger.warning(f"LLM description failed (keeping default): {e}")

    # Attach llm_input/llm_output to each incident dict
    final_dicts = []
    for inc in incidents:
        d = inc.model_dump()
        trace = llm_traces.get(inc.incident_id, {})
        d["llm_input"] = trace.get("llm_input")
        d["llm_output"] = trace.get("llm_output")
        d["rag_context"] = trace.get("rag_context")
        final_dicts.append(d)

    return {"final_incidents": final_dicts}


def save_node(state: ObserverState) -> dict:
    """Save Step 5 final output to JSON."""
    logger.info("=== Saving final incidents to file ===")
    final_incidents = state.get("final_incidents", [])

    if final_incidents:
        path = save_final_incidents(final_incidents)
        logger.info(f"Final incidents saved to {path}")
    else:
        logger.info("No incidents to save.")

    return {}


# ── Build Graphs ──────────────────────────────────────────────────────────────

def build_check_graph():
    """Build graph for Step 1 only (DB checks for all apps)."""
    graph = StateGraph(ObserverState)
    graph.add_node("run_tools", run_tools_node)
    graph.add_node("save_raw", save_raw_node)
    graph.set_entry_point("run_tools")
    graph.add_edge("run_tools", "save_raw")
    graph.add_edge("save_raw", END)
    return graph.compile()


def build_pipeline_graph():
    """Build graph for Steps 2-5 (single app at a time).
    Save nodes are omitted — combined results are saved by run_pipeline()."""
    graph = StateGraph(ObserverState)

    graph.add_node("normalize", normalize_node)
    graph.add_node("detect", detect_node)
    graph.add_node("correlate", correlate_node)
    graph.add_node("route", route_node)

    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "detect")

    graph.add_conditional_edges(
        "detect",
        should_continue,
        {"correlate": "correlate", "end": END},
    )

    graph.add_edge("correlate", "route")
    graph.add_edge("route", END)

    return graph.compile()


def _get_app_name(raw: dict) -> str:
    """Extract app name from a raw result dict."""
    return raw.get("application", "").upper()


APP_NAMES = {"ASCM": "ascm", "ATE": "ate", "PROMPTOPT": "promptopt"}


def run_pipeline(tools_to_run: list[str] | None = None) -> dict:
    """Run the full pipeline with per-app isolation.

    Step 1: Check all apps (DB queries, no LLM).
    Steps 2-5: Run separately for each app that returned data.

    Returns:
        Combined results from all apps.
    """
    if tools_to_run is None:
        tools_to_run = list(TOOLS_MAP.keys())

    # ── Step 1: Check all apps ──
    logger.info(f"{'='*60}")
    logger.info(f"Step 1: Running DB checks for {tools_to_run}")
    logger.info(f"{'='*60}")

    check_graph = build_check_graph()
    step1_result = check_graph.invoke({
        "messages": [],
        "tools_to_run": tools_to_run,
        "raw_results": [],
        "signals": [],
        "detections": [],
        "incidents": [],
        "final_incidents": [],
    })

    raw_results = step1_result.get("raw_results", [])

    # ── Group raw results by app ──
    app_results: dict[str, list[dict]] = {}
    for raw in raw_results:
        app = _get_app_name(raw)
        app_results.setdefault(app, []).append(raw)

    # ── Steps 2-5: Run per app ──
    pipeline_graph = build_pipeline_graph()
    all_signals = []
    all_detections = []
    all_incidents = []
    all_final_incidents = []

    for app_name, app_raw in app_results.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing app: {app_name}")
        logger.info(f"{'='*60}")

        result = pipeline_graph.invoke({
            "messages": [],
            "tools_to_run": [],
            "raw_results": app_raw,
            "signals": [],
            "detections": [],
            "incidents": [],
            "final_incidents": [],
        })

        all_signals.extend(result.get("signals", []))
        all_detections.extend(result.get("detections", []))
        all_incidents.extend(result.get("incidents", []))
        all_final_incidents.extend(result.get("final_incidents", []))

        if result.get("final_incidents"):
            logger.info(f"{app_name}: {len(result['final_incidents'])} incident(s) created")
        elif result.get("detections"):
            logger.info(f"{app_name}: {len(result['detections'])} detection(s), no incidents")
        else:
            logger.info(f"{app_name}: No anomalies detected")

    # ── Save combined results (all apps in one run entry) ──
    save_signals(all_signals)
    save_detections(all_detections)
    save_incidents(all_incidents)
    if all_final_incidents:
        save_final_incidents(all_final_incidents)

    return {
        "raw_results": raw_results,
        "signals": all_signals,
        "detections": all_detections,
        "incidents": all_incidents,
        "final_incidents": all_final_incidents,
    }


# Keep backward compatibility
def build_graph():
    """Backward-compatible: returns the pipeline graph for Steps 2-5."""
    return build_pipeline_graph()
