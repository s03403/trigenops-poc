"""
Sample SQLite database for local ASCM testing.

Creates a file-based SQLite database that mimics the ASCM PostgreSQL schema
so the pipeline can be tested end-to-end without real DB credentials.

Usage:
    python -m observer_advisor.tools.sample_db              # stale data (triggers anomaly)
    python -m observer_advisor.tools.sample_db --fresh       # fresh data (no anomaly)
"""

from __future__ import annotations

import os
import sqlite3
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

SAMPLE_ASCM_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_ascm.db")


def create_sample_ascm_db(
    stale: bool = True,
    db_path: str = SAMPLE_ASCM_DB_PATH,
) -> str:
    """Create a sample ASCM SQLite database with test data.

    Args:
        stale: If True, insert yesterday's date → pipeline detects FAIL.
               If False, insert today's date → pipeline sees PASS.
        db_path: Path to the SQLite file.

    Returns:
        Path to the created database file.
    """
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # METADATA table (mimics ascm_web."METADATA")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS METADATA (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            DOCUMENTTYPE TEXT NOT NULL,
            TARGETDATE TEXT NOT NULL,
            CREATED_AT TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    today = date.today()
    target_date = (today - timedelta(days=1)) if stale else today

    rows = [
        ("TGT_FREQUENCY", str(target_date)),
        ("TGT_FREQUENCY", str(target_date - timedelta(days=1))),
        ("TGT_FREQUENCY", str(target_date - timedelta(days=2))),
        ("OTHER_DOC", str(today)),  # different doc type, should be ignored
    ]

    cur.executemany(
        "INSERT INTO METADATA (DOCUMENTTYPE, TARGETDATE) VALUES (?, ?)",
        rows,
    )

    conn.commit()
    conn.close()

    logger.info(f"Sample ASCM DB created at {db_path} ({'STALE' if stale else 'FRESH'}) with {len(rows)} rows")
    return db_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Create sample ASCM SQLite DB")
    parser.add_argument("--fresh", action="store_true", help="Insert today's date (PASS)")
    args = parser.parse_args()

    path = create_sample_ascm_db(stale=not args.fresh)
    print(f"Created: {path}")

    # Verify
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM METADATA")
    for row in cur.fetchall():
        print(row)
    conn.close()
