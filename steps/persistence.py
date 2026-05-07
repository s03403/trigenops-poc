"""Local JSON persistence for each pipeline step.

Saves output of each step into a separate JSON file under observer_advisor/outputs/.
Each run overwrites with the latest data (append-friendly per run_timestamp).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Output directory: observer_advisor/outputs/
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")


def _ensure_output_dir():
    """Create the outputs directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _save_step(step_name: str, data: list[dict]) -> str:
    """Save a step's output to its own JSON file.

    Args:
        step_name: Name of the step (used as filename).
        data: List of dicts to save.

    Returns:
        Path to the saved file.
    """
    _ensure_output_dir()
    filepath = os.path.join(OUTPUT_DIR, f"{step_name}.json")

    # Load existing runs
    existing: list[dict] = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, Exception):
            existing = []

    # Append new run entry
    entry = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "count": len(data),
        "data": data,
    }
    existing.append(entry)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, default=str)

    logger.info(f"Step '{step_name}': saved {len(data)} item(s) to {filepath}")
    return filepath


def save_raw_results(data: list[dict]) -> str:
    """Save Step 1 (Tools) output → outputs/step1_raw_results.json"""
    return _save_step("step1_raw_results", data)


def save_signals(data: list[dict]) -> str:
    """Save Step 2 (Normalize) output → outputs/step2_signals.json"""
    return _save_step("step2_signals", data)


def save_detections(data: list[dict]) -> str:
    """Save Step 3 (Detect) output → outputs/step3_detections.json"""
    return _save_step("step3_detections", data)


def save_incidents(data: list[dict]) -> str:
    """Save Step 4 (Correlate) output → outputs/step4_incidents.json"""
    return _save_step("step4_incidents", data)


def save_final_incidents(data: list[dict]) -> str:
    """Save Step 5 (Route) output → outputs/step5_final_incidents.json"""
    return _save_step("step5_final_incidents", data)
