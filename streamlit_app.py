"""
Observer Agent - Streamlit Dashboard
=====================================
Visualises every pipeline step with Before-LLM / After-LLM comparison.
Filter by application (ASCM, ATE, PromptOpt) via sidebar radio buttons.

Run:  streamlit run observer_advisor/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# Ensure parent is on sys.path so imports work when run via `streamlit run`
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from observer_advisor.logging_config import setup_logging
setup_logging()

from observer_advisor.scheduler import (
    start_scheduler, stop_scheduler, is_running, get_job_status,
)

# ── Paths ─────────────────────────────────────────────────────────────────────

OUTPUTS = Path(__file__).parent / "outputs"

STEP_FILES = {
    1: OUTPUTS / "step1_raw_results.json",
    2: OUTPUTS / "step2_signals.json",
    3: OUTPUTS / "step3_detections.json",
    4: OUTPUTS / "step4_incidents.json",
    5: OUTPUTS / "step5_final_incidents.json",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_step(step: int) -> list[dict]:
    path = STEP_FILES[step]
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def latest_run(runs: list[dict]) -> dict | None:
    """Merge the latest data per application across all run entries.

    Because the scheduler fires each app on its own timer, the last
    run entry may only contain one app's data.  This walks backwards
    through all runs and collects the most recent record for each app
    so the dashboard always shows every app's latest results.
    """
    if not runs:
        return None

    seen_apps: set[str] = set()
    merged_data: list[dict] = []
    latest_ts: str = runs[-1].get("run_timestamp", "")

    for run in reversed(runs):
        for item in run.get("data", []):
            app = item.get("application", "")
            if app and app not in seen_apps:
                seen_apps.add(app)
                merged_data.append(item)

    return {"run_timestamp": latest_ts, "count": len(merged_data), "data": merged_data}


def filter_by_app(items: list[dict], app_name: str) -> list[dict]:
    """Keep only items whose 'application' matches *app_name* (case-insensitive)."""
    return [i for i in items if i.get("application", "").upper() == app_name.upper()]


def severity_colour(sev: str) -> str:
    return {
        "P1": "#FF4B4B",
        "P2": "#FF8C00",
        "P3": "#FFD700",
        "P4": "#4DA6FF",
    }.get(sev, "#888888")


def severity_emoji(sev: str) -> str:
    return {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🔵"}.get(sev, "⚪")


def result_colour(result: str) -> str:
    return {"FAIL": "#FF4B4B", "WARNING": "#FFD700", "PASS": "#00C853"}.get(result, "#888")


def result_emoji(result: str) -> str:
    return {"FAIL": "🔴", "WARNING": "🟡", "PASS": "🟢"}.get(result, "⚪")


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Observer Agent Dashboard",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem; font-weight: 700; color: #1E88E5;
        border-bottom: 3px solid #1E88E5; padding-bottom: 0.3rem;
        margin-bottom: 1rem;
    }
    .step-header {
        font-size: 1.3rem; font-weight: 600; color: #333;
        border-left: 4px solid #1E88E5; padding-left: 0.8rem;
        margin: 1.5rem 0 0.8rem 0;
    }
    .metric-card {
        background: #f8f9fa; border-radius: 8px; padding: 1rem 1.2rem;
        border: 1px solid #dee2e6; text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #1E88E5; }
    .metric-label { font-size: 0.85rem; color: #666; margin-top: 0.2rem; }
    .llm-box {
        background: #FFF8E1; border: 1px solid #FFD54F; border-radius: 6px;
        padding: 0.8rem 1rem; margin: 0.5rem 0; font-size: 0.85rem;
    }
    .no-llm-box {
        background: #FFEBEE; border: 1px solid #EF9A9A; border-radius: 6px;
        padding: 0.8rem 1rem; margin: 0.5rem 0; font-size: 0.85rem;
        color: #C62828;
    }
    .before-box {
        background: #F3E5F5; border: 1px solid #CE93D8; border-radius: 6px;
        padding: 0.8rem 1rem; font-size: 0.85rem;
    }
    .after-box {
        background: #E8F5E9; border: 1px solid #A5D6A7; border-radius: 6px;
        padding: 0.8rem 1rem; font-size: 0.85rem;
    }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔭 Observer Agent")
    st.divider()

    selected_app = st.radio(
        "Application",
        ["All", "ASCM", "ATE", "PromptOpt"],
        index=0,
        horizontal=True,
    )

    step_view = st.radio(
        "View",
        ["All Steps", "Step 1 - Raw Results", "Step 2 - Signals",
         "Step 3 - Detections", "Step 4 - Correlation",
         "Step 5 - Final Incidents"],
        index=0,
    )

    st.divider()

    # ── Scheduler controls ──
    st.markdown("### ⏱ Scheduler")

    if is_running():
        st.success("Running", icon="✅")
        if st.button("⏹  Stop Scheduler"):
            stop_scheduler()
            st.rerun()

        # Show job schedule
        jobs = get_job_status()
        for job in jobs:
            st.caption(f"**{job['name']}** — next: {job['next_run']}  |  last: {job['last_run']}")
    else:
        st.warning("Stopped", icon="⏸️")
        if st.button("▶  Start Scheduler", type="primary"):
            start_scheduler()
            st.rerun()

    st.divider()

    # ── Run Pipeline button (manual) ──
    st.markdown("### 🔧 Manual")
    if st.button("▶  Run Pipeline Now"):
        with st.spinner("Running Observer pipeline…"):
            import subprocess, sys
            proc = subprocess.run(
                [sys.executable, "-m", "observer_advisor.main"],
                cwd=str(Path(__file__).resolve().parent.parent),
                capture_output=True,
                text=True,
                timeout=120,
            )
        if proc.returncode == 0:
            st.success("Pipeline finished! Refreshing…")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Pipeline failed!")
            st.code(proc.stderr or proc.stdout, language="text")

    if st.button("🔄  Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Auto-refresh toggle (when scheduler is running)
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=is_running())
    if auto_refresh:
        st.caption("Dashboard refreshes every 60 seconds.")

    st.caption("Reads JSON files from `outputs/` folder.")


# ── Auto-refresh (stdlib, no external package) ──────────────────────────────

if auto_refresh:
    # Use Streamlit's built-in auto-rerun via HTML meta refresh
    st.markdown(
        '<meta http-equiv="refresh" content="60">',
        unsafe_allow_html=True,
    )


# ── Load data ─────────────────────────────────────────────────────────────────

all_runs = {s: load_step(s) for s in range(1, 6)}
latest = {s: latest_run(all_runs[s]) for s in range(1, 6)}

run_ts = latest[1].get("run_timestamp", "—") if latest[1] else "—"


# ── Pipeline flow banner ─────────────────────────────────────────────────────

def _count(step: int) -> int:
    run = latest[step]
    if not run:
        return 0
    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)
    return len(data)


st.markdown('<div class="main-header">🔭 Observer Agent Dashboard</div>', unsafe_allow_html=True)
app_label = selected_app if selected_app != "All" else "All Apps"
st.markdown(f"**Last run:** `{run_ts}` &nbsp;&nbsp;|&nbsp;&nbsp; **Showing:** {app_label}")

# Quick stats row
c1, c2, c3, c4, c5 = st.columns(5)
labels = ["Raw Results", "Signals", "Detections", "Correlations", "Incidents"]
for i, (col, label) in enumerate(zip([c1, c2, c3, c4, c5], labels), start=1):
    cnt = _count(i)
    col.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value">{cnt}</div>'
        f'<div class="metric-label">Step {i}: {label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# Flow diagram
st.markdown(
    f"**Pipeline:** &nbsp; Raw ({_count(1)}) &nbsp;→&nbsp; "
    f"Signals ({_count(2)}) &nbsp;→&nbsp; "
    f"Detections ({_count(3)}) &nbsp;→&nbsp; "
    f"Correlation ({_count(4)}) &nbsp;→&nbsp; "
    f"Incidents ({_count(5)})"
)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 - RAW RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_step1():
    st.markdown('<div class="step-header">Step 1 - Raw Results  (DB Queries)</div>', unsafe_allow_html=True)
    st.caption("No LLM involvement — pure SQL query results.")

    run = latest[1]
    if not run:
        st.info("No Step 1 data found.")
        return

    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)

    for item in data:
        app = item.get("application", "?")
        err = item.get("error")
        icon = "🟢" if not err else "🔴"

        with st.expander(f"{icon}  **{app}**", expanded=True):
            if "checks" in item:
                # Multi-check apps (ATE, PromptOpt)
                for cid, cdata in item["checks"].items():
                    status = "✅" if not cdata.get("error") else "❌"
                    st.markdown(f"**{cid}** {status}")
                    col1, col2 = st.columns(2)
                    col1.code(f"Source: {cdata.get('source_table', '—')}")
                    col2.code(f"Value:  {cdata.get('raw_value', 'null')}")
                    if cdata.get("error"):
                        st.error(f"Error: {cdata['error']}")
            else:
                # Single-check app (ASCM)
                col1, col2 = st.columns(2)
                col1.code(f"Source: {item.get('source_table', '—')}")
                col2.code(f"Value:  {item.get('raw_value', 'null')}")
                if err:
                    st.error(f"Error: {err}")

                # Query in collapsible section
                if item.get("query_executed"):
                    with st.expander("🔍 SQL Query", expanded=False):
                        st.code(item["query_executed"], language="sql")

                # Extracted data in collapsible section
                extracted = item.get("extracted_data", [])
                if extracted:
                    with st.expander("📋 Extracted Data from DB", expanded=False):
                        import pandas as pd
                        df = pd.DataFrame(extracted)
                        st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 - SIGNALS (Normalization + LLM Enrichment)
# ═══════════════════════════════════════════════════════════════════════════════

def render_step2():
    st.markdown(
        '<div class="step-header">Step 2 — Normalized Signals  (+ LLM Enrichment)</div>',
        unsafe_allow_html=True,
    )

    run = latest[2]
    if not run:
        st.info("No Step 2 data found.")
        return

    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)

    for sig in data:
        sid = sig.get("signal_id", "?")
        app = sig.get("application", "?")
        check = sig.get("check_id", "?")

        with st.expander(f"📡  **{sid}** — {app} / {check}", expanded=True):
            # ── Before LLM ──
            with st.expander("📋 Input (Deterministic Normalization)", expanded=False):
                cols = st.columns(3)
                cols[0].metric("Signal Type", sig.get("signal_type", "—"))
                cols[1].metric("Observed", str(sig.get("observed_value", "null")))
                cols[2].metric("Expected", str(sig.get("expected_value", "null")))

                st.markdown(f"**Business Date:** {sig.get('business_date', '—')}")

                evidence = sig.get("evidence", {})
                st.markdown(
                    f'<div class="before-box">'
                    f'<b>Evidence (deterministic):</b><br>'
                    f'Source Table: {evidence.get("source_table", "—")}<br>'
                    f'Error: {evidence.get("error") or "None"}<br>'
                    f'Query: {evidence.get("query", "—")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── After LLM ──
            st.markdown("##### After LLM (Enrichment)")
            enrichment = sig.get("enrichment", {})
            llm_in = evidence.get("llm_input")
            llm_out = evidence.get("llm_output")

            interpretation = enrichment.get("interpretation") if isinstance(enrichment, dict) else None
            if interpretation:
                st.markdown(
                    f'<div class="after-box">'
                    f'<b>Interpretation:</b> {interpretation}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="no-llm-box">LLM enrichment: <b>not available</b> (empty or failed)</div>',
                    unsafe_allow_html=True,
                )

            if llm_in:
                with st.popover("🔍 LLM Prompt"):
                    st.text(llm_in)
            if llm_out:
                with st.popover("🔍 LLM Response"):
                    st.text(llm_out)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 - DETECTIONS (Rules + LLM Explanation)
# ═══════════════════════════════════════════════════════════════════════════════

def render_step3():
    st.markdown(
        '<div class="step-header">Step 3 — Detections  (Rules + LLM Explanation)</div>',
        unsafe_allow_html=True,
    )

    run = latest[3]
    if not run:
        st.info("No Step 3 data found.")
        return

    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)

    # Summary bar
    fails = sum(1 for d in data if d.get("result") == "FAIL")
    warns = sum(1 for d in data if d.get("result") == "WARNING")
    st.markdown(f"**Summary:** 🔴 {fails} FAIL &nbsp;&nbsp; 🟡 {warns} WARNING")

    for det in data:
        did = det.get("detection_id", "?")
        rule = det.get("rule_name", "?")
        result = det.get("result", "?")
        sev = det.get("proposed_severity", "—")
        emoji = result_emoji(result)

        with st.expander(f"{emoji}  **{did}** — {rule}  [{result}]", expanded=True):
            cols = st.columns(4)
            cols[0].metric("Rule", rule)
            cols[1].metric("Result", result)
            cols[2].metric("Severity", sev)
            cols[3].metric("Check", det.get("check_id", "—"))

            evidence_raw = det.get("evidence", "")

            # Split evidence into before-LLM and after-LLM parts
            if " | LLM: " in evidence_raw:
                before_part, after_part = evidence_raw.split(" | LLM: ", 1)
            else:
                before_part = evidence_raw
                after_part = None

            # ── Before LLM ──
            with st.expander("📋 Input (Deterministic Rule Result)", expanded=False):
                st.markdown(
                    f'<div class="before-box"><b>Evidence:</b> {before_part}</div>',
                    unsafe_allow_html=True,
                )

            # ── Retrieved Logs (RAG) ──
            rag_ctx = det.get("rag_context")
            if rag_ctx:
                with st.expander("📄 Retrieved Logs (RAG Context)", expanded=False):
                    st.text(rag_ctx)

            # ── After LLM ──
            st.markdown("##### After LLM (Explanation)")
            if after_part:
                st.markdown(
                    f'<div class="after-box"><b>LLM Explanation:</b> {after_part}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="no-llm-box">LLM explanation: <b>not available</b> (null or failed)</div>',
                    unsafe_allow_html=True,
                )

            # LLM I/O trace
            llm_in = det.get("llm_input")
            llm_out = det.get("llm_output")
            if llm_in or llm_out:
                with st.popover("🔍 LLM I/O"):
                    if llm_in:
                        st.markdown("**Prompt sent:**")
                        st.text(llm_in)
                    st.divider()
                    if llm_out:
                        st.markdown("**Response received:**")
                        st.text(llm_out)
                    else:
                        st.warning("LLM output: null")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 - CORRELATION & SUPPRESSION (+ LLM Narrative)
# ═══════════════════════════════════════════════════════════════════════════════

def render_step4():
    st.markdown(
        '<div class="step-header">Step 4 — Correlation & Suppression  (+ LLM Narrative)</div>',
        unsafe_allow_html=True,
    )

    run = latest[4]
    if not run:
        st.info("No Step 4 data found.")
        return

    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)

    for cand in data:
        iid = cand.get("incident_id", "?")
        app = cand.get("application", "?")
        dets = cand.get("contributing_detections", [])

        with st.expander(f"🔗  **{iid}** — {app}  ({len(dets)} detections)", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Application", app)
            cols[1].metric("Detections", len(dets))
            cols[2].metric("Business Date", cand.get("business_date", "—"))

            st.markdown(f"**Dedupe Key:** `{cand.get('dedupe_key', '—')}`")

            # Contributing detections
            st.markdown("**Contributing Detections:**")
            for d in dets:
                emoji = result_emoji(d.get("result", ""))
                st.markdown(
                    f"- {emoji} **{d.get('rule_name', '?')}** "
                    f"[{d.get('result', '?')}] — {d.get('evidence', '—')}"
                )

            # ── Before LLM ──
            with st.expander("📋 Input (Deterministic Grouping)", expanded=False):
                st.markdown(
                    f'<div class="before-box">'
                    f'<b>Grouped by:</b> application + business_date<br>'
                    f'<b>Dedupe key:</b> {cand.get("dedupe_key", "—")}<br>'
                    f'<b>Likely cause:</b> {cand.get("likely_cause") or "null (not yet set)"}<br>'
                    f'<b>Correlation summary:</b> null'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Retrieved Logs (RAG) ──
            rag_ctx = cand.get("rag_context")
            if rag_ctx:
                with st.expander("📄 Retrieved Logs (RAG Context)", expanded=False):
                    st.text(rag_ctx)

            # ── After LLM ──
            st.markdown("##### After LLM (Correlation Narrative)")
            corr = cand.get("correlation_summary")
            if corr:
                st.markdown(
                    f'<div class="after-box"><b>Correlation Narrative:</b><br>{corr}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="no-llm-box">Correlation narrative: <b>not available</b> (null or failed)</div>',
                    unsafe_allow_html=True,
                )

            # LLM I/O
            llm_in = cand.get("llm_input")
            llm_out = cand.get("llm_output")
            if llm_in or llm_out:
                with st.popover("🔍 LLM I/O"):
                    if llm_in:
                        st.markdown("**Prompt sent:**")
                        st.text(llm_in)
                    st.divider()
                    if llm_out:
                        st.markdown("**Response received:**")
                        st.text(llm_out)
                    else:
                        st.warning("LLM output: null")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 - FINAL INCIDENTS (Severity + LLM Description)
# ═══════════════════════════════════════════════════════════════════════════════

def render_step5():
    st.markdown(
        '<div class="step-header">Step 5 — Final Incidents  (Severity & Routing + LLM Description)</div>',
        unsafe_allow_html=True,
    )

    run = latest[5]
    if not run:
        st.info("No Step 5 data found.")
        return

    data = run.get("data", [])
    if selected_app != "All":
        data = filter_by_app(data, selected_app)

    for inc in data:
        iid = inc.get("incident_id", "?")
        sev = inc.get("severity", "—")
        app = inc.get("application", "?")
        emoji = severity_emoji(sev)
        colour = severity_colour(sev)

        with st.expander(f"{emoji}  **{iid}** — {app}  |  {sev}", expanded=True):
            # Header metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(
                f'<div style="text-align:center">'
                f'<span style="font-size:1.8rem;color:{colour};font-weight:700">{sev}</span>'
                f'<br><small>Severity</small></div>',
                unsafe_allow_html=True,
            )
            c2.metric("Application", app)
            c3.metric("Environment", inc.get("environment", "—"))
            c4.metric("Assignment", inc.get("assignment_group", "—"))

            st.markdown(f"**Title:** {inc.get('title', '—')}")

            # ── Before LLM ──
            with st.expander("📋 Input (Deterministic Description)", expanded=False):
                # Build deterministic fallback
                ev_summary = inc.get("evidence_summary", {})
                det_list = ev_summary.get("detections", [])
                fallback_lines = [
                    f"Application: {app}",
                    f"Severity: {sev}",
                    f"Business Date: {ev_summary.get('business_date', '—')}",
                    f"Detections: {len(det_list)}",
                    "",
                ]
                for d in det_list:
                    fallback_lines.append(
                        f"- [{d.get('result', '?')}] {d.get('rule', '?')}: {d.get('evidence', '—')}"
                    )
                fallback_text = "\n".join(fallback_lines)

                st.markdown(
                    f'<div class="before-box"><pre>{fallback_text}</pre></div>',
                    unsafe_allow_html=True,
                )

            # ── Retrieved Logs (RAG) ──
            rag_ctx = inc.get("rag_context")
            if rag_ctx:
                with st.expander("📄 Retrieved Logs (RAG Context)", expanded=False):
                    st.text(rag_ctx)

            # ── After LLM ──
            st.markdown("##### After LLM (ITSM Incident Description)")
            llm_out = inc.get("llm_output")
            description = inc.get("description", "")

            if llm_out:
                st.markdown(
                    f'<div class="after-box"><b>LLM-Generated Description:</b><br><br>{llm_out}</div>',
                    unsafe_allow_html=True,
                )
            elif description and not description.startswith("Application:"):
                # LLM description exists but llm_output field missing (older run)
                st.markdown(
                    f'<div class="after-box"><b>Description:</b><br><br>{description}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="no-llm-box">LLM description: <b>not available</b> — using deterministic fallback above</div>',
                    unsafe_allow_html=True,
                )

            # Evidence & Correlation expandables
            with st.popover("📋 Evidence Summary"):
                st.json(ev_summary)

            corr = inc.get("correlation_summary")
            if corr:
                with st.popover("🔗 Correlation Summary"):
                    st.text(corr)

            # LLM I/O
            llm_in = inc.get("llm_input")
            if llm_in or llm_out:
                with st.popover("🔍 LLM I/O"):
                    if llm_in:
                        st.markdown("**Prompt sent:**")
                        st.text(llm_in)
                    st.divider()
                    if llm_out:
                        st.markdown("**Response received:**")
                        st.text(llm_out)
                    else:
                        st.warning("LLM output: null")

            st.caption(f"Created: {inc.get('created_at', '—')}")


# ═══════════════════════════════════════════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════════════════════════════════════════

STEP_MAP = {
    "All Steps": None,
    "Step 1 - Raw Results": 1,
    "Step 2 - Signals": 2,
    "Step 3 - Detections": 3,
    "Step 4 - Correlation": 4,
    "Step 5 - Final Incidents": 5,
}

renderers = {1: render_step1, 2: render_step2, 3: render_step3, 4: render_step4, 5: render_step5}

selected = STEP_MAP[step_view]

if selected is None:
    for s in range(1, 6):
        renderers[s]()
        st.divider()
else:
    renderers[selected]()
