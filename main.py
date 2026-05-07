"""Entry point for Observer Agent pipeline.

Runs each DB check on its own schedule:
  ASCM: every 5 min | ATE: every 15 min | PromptOpt: every 30 min

Usage:
    cd observer_advisor
    python main.py              # run once (all tools)
    python main.py --loop       # run on per-app schedules
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running as `python main.py` from inside observer_advisor/
_this_dir = Path(__file__).resolve().parent
_parent_dir = _this_dir.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from dotenv import load_dotenv

# Load .env from the observer_advisor folder
_env_path = _this_dir / ".env"
load_dotenv(dotenv_path=_env_path)

from observer_advisor.config import get_config
from observer_advisor.graph import run_pipeline
from observer_advisor.steps.correlator import clear_suppression_cache
from observer_advisor.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def run_once(tools_to_run: list[str] | None = None) -> dict:
    """Execute the Observer pipeline once (per-app isolation).

    Args:
        tools_to_run: List of tool names to run (e.g. ["ascm", "ate"]).
                      If None, runs all tools.
    """
    if tools_to_run is None:
        tools_to_run = ["ascm", "ate", "promptopt"]

    logger.info(f"{'='*60}")
    logger.info(f"Observer pipeline started at {datetime.utcnow().isoformat()}")
    logger.info(f"Tools to run: {tools_to_run}")
    logger.info(f"{'='*60}")

    result = run_pipeline(tools_to_run=tools_to_run)

    # Print summary
    detections = result.get("detections", [])
    final_incidents = result.get("final_incidents", [])

    logger.info(f"\n{'='*60}")
    logger.info(f"PIPELINE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Tools checked:      {tools_to_run}")
    logger.info(f"Signals normalized: {len(result.get('signals', []))}")
    logger.info(f"Anomalies detected: {len(detections)}")
    logger.info(f"Incidents created:  {len(final_incidents)}")

    if final_incidents:
        logger.info(f"\n--- Incidents ---")
        for inc in final_incidents:
            logger.info(f"  [{inc.get('severity')}] {inc.get('title')}")
            logger.info(f"    Assigned to: {inc.get('assignment_group')}")

    logger.info(f"{'='*60}\n")
    return result


# Check interval in seconds
CHECK_INTERVAL = get_config().loop_tick_seconds  # default 60s


def run_loop():
    """Run the pipeline on a fixed interval, like a simple polling loop."""
    print(f"[{datetime.now()}] Starting Observer loop (interval={CHECK_INTERVAL}s)")

    while True:
        try:
            clear_suppression_cache()
            run_once()
            print(f"[{datetime.now()}] Check completed successfully.")
        except Exception as e:
            print(f"[{datetime.now()}] Error:", e)

        time.sleep(CHECK_INTERVAL)


def main():
    parser = argparse.ArgumentParser(description="Observer-Advisor Pipeline")
    parser.add_argument("--loop", action="store_true", help="Run continuously on interval")
    args = parser.parse_args()

    if args.loop:
        run_loop()
    else:
        run_once()


if __name__ == "__main__":
    main()
