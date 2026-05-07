"""Background scheduler for Observer-Advisor pipeline.

Uses Python stdlib threading.Timer to run per-app DB checks at independent intervals:
  ASCM: every 5 min | ATE: every 15 min | PromptOpt: every 30 min

Designed to run inside the Streamlit process so a single
`streamlit run` command starts both the UI and the scheduler.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, "_RepeatingJob"] = {}
_running = False


class _RepeatingJob:
    """A simple repeating timer that re-schedules itself after each run."""

    def __init__(self, job_id: str, name: str, interval: int, target, args):
        self.job_id = job_id
        self.name = name
        self.interval = interval
        self._target = target
        self._args = args
        self._timer: threading.Timer | None = None
        self.last_run: str | None = None
        self.next_run: str | None = None

    def _run(self):
        self.last_run = datetime.now().strftime("%H:%M:%S")
        try:
            self._target(*self._args)
        except Exception as e:
            logger.error(f"[Scheduler] Job {self.name} failed: {e}")
        # Re-schedule
        self._schedule()

    def _schedule(self):
        self._timer = threading.Timer(self.interval, self._run)
        self._timer.daemon = True
        self._timer.start()
        now = datetime.now()
        from datetime import timedelta
        self.next_run = (now + timedelta(seconds=self.interval)).strftime("%H:%M:%S")

    def start(self):
        self._schedule()

    def stop(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def _run_app_check(tools: list[str]) -> None:
    """Run the pipeline for a specific set of tools."""
    from observer_advisor.graph import run_pipeline

    label = ", ".join(tools)
    logger.info(f"[Scheduler] Starting check for: {label}")
    try:
        run_pipeline(tools_to_run=tools)
        logger.info(f"[Scheduler] Completed check for: {label}")
    except Exception as e:
        logger.error(f"[Scheduler] Check failed for {label}: {e}")


def start_scheduler() -> None:
    """Start the background scheduler (idempotent — safe to call multiple times)."""
    global _running

    with _lock:
        if _running:
            return

        from observer_advisor.config import get_config
        cfg = get_config()

        _jobs["ascm_check"] = _RepeatingJob(
            "ascm_check", "ASCM DB Check", cfg.ascm_interval,
            _run_app_check, (["ascm"],),
        )
        _jobs["ate_check"] = _RepeatingJob(
            "ate_check", "ATE DB Check", cfg.ate_interval,
            _run_app_check, (["ate"],),
        )
        _jobs["promptopt_check"] = _RepeatingJob(
            "promptopt_check", "PromptOpt DB Check", cfg.promptopt_interval,
            _run_app_check, (["promptopt"],),
        )

        for job in _jobs.values():
            job.start()

        _running = True
        logger.info(
            f"[Scheduler] Started — ASCM: {cfg.ascm_interval}s, "
            f"ATE: {cfg.ate_interval}s, PromptOpt: {cfg.promptopt_interval}s"
        )


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _running

    with _lock:
        for job in _jobs.values():
            job.stop()
        _jobs.clear()
        _running = False
        logger.info("[Scheduler] Stopped")


def is_running() -> bool:
    """Check if the scheduler is currently running."""
    return _running


def get_job_status() -> list[dict]:
    """Get status of all scheduled jobs."""
    if not _running:
        return []
    result = []
    for job in _jobs.values():
        result.append({
            "id": job.job_id,
            "name": job.name,
            "next_run": job.next_run or "—",
            "interval": f"{job.interval}s",
            "last_run": job.last_run or "—",
        })
    return result
