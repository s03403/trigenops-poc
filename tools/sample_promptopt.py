"""
Sample SQLite database for local PromptOpt testing.

Creates a file-based SQLite database that mimics the PromptOpt PostgreSQL schema
so the pipeline can be tested end-to-end without real DB credentials.

Usage:
    python -m observer_advisor.tools.sample_promptopt              # anomaly data
    python -m observer_advisor.tools.sample_promptopt --fresh       # normal data
"""

from __future__ import annotations

import os
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SAMPLE_PROMPTOPT_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_promptopt.db")


def create_sample_promptopt_db(stale: bool = True, db_path: str = SAMPLE_PROMPTOPT_DB_PATH) -> str:
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS popt_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            last_active TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS popt_xml_queue_tab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_name TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            enqueued_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS popt_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_level TEXT NOT NULL,
            message TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL
        )
    """)

    now = datetime.now(timezone.utc)

    if stale:
        # Anomaly: old activity, large queue, recent errors
        stale_activity = [
            ("OPTIMIZATION", "COMPLETED", "Batch optimisation run", (now - timedelta(hours=2, minutes=10)).isoformat()),
            ("HEALTH_CHECK", "COMPLETED", "Scheduled ping", (now - timedelta(hours=2)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO popt_activity (activity_type, status, details, last_active) VALUES (?, ?, ?, ?)",
            stale_activity,
        )

        # Queue buildup: 150 pending items
        queue_rows = []
        for i in range(150):
            queue_rows.append((
                "PROMPT_QUEUE",
                f"<prompt id=\"{i+1}\"><text>optimise schedule delta-{i+1}</text></prompt>",
                "PENDING",
                (now - timedelta(minutes=30 + i)).isoformat(),
            ))
        cur.executemany(
            "INSERT INTO popt_xml_queue_tab (queue_name, payload, status, enqueued_at) VALUES (?, ?, ?, ?)",
            queue_rows,
        )

        # Recent errors
        error_logs = [
            ("ERROR", "Connection to solver engine refused: ECONNREFUSED 10.0.5.22:9090", "SOLVER_CONN_ERR", (now - timedelta(minutes=5)).isoformat()),
            ("ERROR", "Memory limit exceeded during optimisation batch #42", "OOM_ERR", (now - timedelta(minutes=8)).isoformat()),
            ("ERROR", "Timeout waiting for solver response (>120 s)", "SOLVER_TIMEOUT", (now - timedelta(minutes=12)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO popt_log (log_level, message, error_code, created_at) VALUES (?, ?, ?, ?)",
            error_logs,
        )
    else:
        # Normal: recent activity, small queue, no errors
        recent_activity = [
            ("OPTIMIZATION", "COMPLETED", "Batch optimisation run", (now - timedelta(minutes=3)).isoformat()),
            ("HEALTH_CHECK", "COMPLETED", "Scheduled ping", (now - timedelta(minutes=1)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO popt_activity (activity_type, status, details, last_active) VALUES (?, ?, ?, ?)",
            recent_activity,
        )

        # Small queue
        small_queue = [
            ("PROMPT_QUEUE", "<prompt id=\"1\"><text>optimise</text></prompt>", "PENDING", (now - timedelta(minutes=1)).isoformat()),
            ("PROMPT_QUEUE", "<prompt id=\"2\"><text>optimise</text></prompt>", "PENDING", (now - timedelta(minutes=2)).isoformat()),
            ("PROMPT_QUEUE", "<prompt id=\"3\"><text>optimise</text></prompt>", "PENDING", (now - timedelta(minutes=3)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO popt_xml_queue_tab (queue_name, payload, status, enqueued_at) VALUES (?, ?, ?, ?)",
            small_queue,
        )

        # Info-level logs only
        info_logs = [
            ("INFO", "Optimisation batch #50 completed successfully", None, (now - timedelta(minutes=2)).isoformat()),
            ("INFO", "Health check passed", None, (now - timedelta(minutes=5)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO popt_log (log_level, message, error_code, created_at) VALUES (?, ?, ?, ?)",
            info_logs,
        )

    conn.commit()
    conn.close()
    logger.info(f"Sample PromptOpt DB created at {db_path} ({'STALE' if stale else 'FRESH'})")
    return db_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Create sample PromptOpt SQLite DB")
    parser.add_argument("--fresh", action="store_true", help="Insert normal data (PASS)")
    args = parser.parse_args()

    path = create_sample_promptopt_db(stale=not args.fresh)
    print(f"Created: {path}")

    conn = sqlite3.connect(path)
    cur = conn.cursor()
    print("\n── popt_activity ──")
    cur.execute("SELECT * FROM popt_activity")
    for row in cur.fetchall():
        print(row)
    print(f"\n── popt_xml_queue_tab ({cur.execute('SELECT COUNT(*) FROM popt_xml_queue_tab').fetchone()[0]} rows) ──")
    cur.execute("SELECT * FROM popt_xml_queue_tab LIMIT 5")
    for row in cur.fetchall():
        print(row)
    print("\n── popt_log ──")
    cur.execute("SELECT * FROM popt_log")
    for row in cur.fetchall():
        print(row)
    conn.close()
