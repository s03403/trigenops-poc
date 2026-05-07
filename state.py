"""LangGraph state definition for Observer Agent pipeline."""

from __future__ import annotations

from typing import Any, Annotated
from langgraph.graph import MessagesState


class ObserverState(MessagesState):
    """State flowing through the Observer graph.

    Attributes:
        tools_to_run:    Which tools to invoke this cycle (e.g. ["ascm", "ate"])
        raw_results:     Output from DB tools (step 1 / tools)
        signals:         Normalized signals (step 2)
        detections:      Triggered detections (step 3)
        incidents:       Correlated incident candidates (step 4)
        final_incidents: Routed incidents with severity (step 5)
    """
    tools_to_run: list[str] = []
    raw_results: list[dict] = []
    signals: list[dict] = []
    detections: list[dict] = []
    incidents: list[dict] = []
    final_incidents: list[dict] = []
