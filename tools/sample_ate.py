"""
Sample SQLite database for local ATE testing.

Creates a file-based SQLite database that mimics the ATE Oracle schema
so the pipeline can be tested end-to-end without real DB credentials.

Usage:
    python -m observer_advisor.tools.sample_ate              # anomaly data
    python -m observer_advisor.tools.sample_ate --fresh       # normal data
"""

from __future__ import annotations

import os
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

SAMPLE_ATE_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_ate.db")


def create_sample_ate_db(stale: bool = True, db_path: str = SAMPLE_ATE_DB_PATH) -> str:
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS POWER_TRADE_ERROR (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ERROR_TYPE TEXT NOT NULL,
            FAILED_REASON TEXT,
            CREATED_DATE TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS POWER_TRADE (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            TRADE_ID TEXT NOT NULL,
            INSTRUMENT TEXT,
            QUANTITY REAL,
            PRICE REAL,
            STATUS TEXT DEFAULT 'COMPLETED',
            CREATED_DATE TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS EXCHSYNC_MESSAGE (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            MESSAGE_TYPE TEXT NOT NULL,
            STATUS TEXT NOT NULL,
            DETAILS TEXT,
            CREATED_DATE TEXT NOT NULL
        )
    """)

    now = datetime.now(timezone.utc)

    if stale:
        # Anomaly: trade errors, zero recent trades, exchsync errors
        ate_errors = [
            ("VALIDATION", "Price out of bounds for POWER_DE_BASE_2026Q3", (now - timedelta(minutes=2)).isoformat()),
            ("CONNECTIVITY", "TCP reset from exchange server mktdata-prod.exchange.net:8443", (now - timedelta(minutes=3)).isoformat()),
            ("VALIDATION", "Duplicate trade ID detected: T-20260427-1142", (now - timedelta(minutes=4)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO POWER_TRADE_ERROR (ERROR_TYPE, FAILED_REASON, CREATED_DATE) VALUES (?, ?, ?)",
            ate_errors,
        )

        # Only old trades — no recent ones (anomaly)
        old_trades = [
            ("T-20260427-0901", "POWER_DE_BASE", 50.0, 85.20, "COMPLETED", (now - timedelta(hours=2)).isoformat()),
            ("T-20260427-0902", "POWER_FR_PEAK", 25.0, 92.10, "COMPLETED", (now - timedelta(hours=2)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO POWER_TRADE (TRADE_ID, INSTRUMENT, QUANTITY, PRICE, STATUS, CREATED_DATE) VALUES (?, ?, ?, ?, ?, ?)",
            old_trades,
        )

        # EXCHSYNC errors
        exchsync_rows = [
            ("MARKET_DATA", "ERROR", "TCP reset from exchange server", (now - timedelta(minutes=1)).isoformat()),
            ("MARKET_DATA", "ERROR", "Connection refused to mktdata-prod.exchange.net:8443", (now - timedelta(minutes=2)).isoformat()),
            ("MARKET_DATA", "ERROR", "Timeout waiting for exchange response", (now - timedelta(minutes=3)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO EXCHSYNC_MESSAGE (MESSAGE_TYPE, STATUS, DETAILS, CREATED_DATE) VALUES (?, ?, ?, ?)",
            exchsync_rows,
        )
    else:
        # Normal: no errors, recent trades, exchsync OK
        recent_trades = [
            ("T-20260427-1001", "POWER_DE_BASE", 50.0, 85.20, "COMPLETED", (now - timedelta(minutes=1)).isoformat()),
            ("T-20260427-1002", "POWER_FR_PEAK", 25.0, 92.10, "COMPLETED", (now - timedelta(minutes=2)).isoformat()),
            ("T-20260427-1003", "GAS_TTF_CAL27", 100.0, 32.45, "COMPLETED", (now - timedelta(minutes=3)).isoformat()),
            ("T-20260427-1004", "POWER_NL_OFF", 75.0, 78.60, "COMPLETED", (now - timedelta(minutes=4)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO POWER_TRADE (TRADE_ID, INSTRUMENT, QUANTITY, PRICE, STATUS, CREATED_DATE) VALUES (?, ?, ?, ?, ?, ?)",
            recent_trades,
        )

        exchsync_ok = [
            ("MARKET_DATA", "OK", "Price update received", (now - timedelta(minutes=1)).isoformat()),
            ("MARKET_DATA", "OK", "Price update received", (now - timedelta(minutes=2)).isoformat()),
        ]
        cur.executemany(
            "INSERT INTO EXCHSYNC_MESSAGE (MESSAGE_TYPE, STATUS, DETAILS, CREATED_DATE) VALUES (?, ?, ?, ?)",
            exchsync_ok,
        )

    conn.commit()
    conn.close()
    logger.info(f"Sample ATE DB created at {db_path} ({'STALE' if stale else 'FRESH'})")
    return db_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Create sample ATE SQLite DB")
    parser.add_argument("--fresh", action="store_true", help="Insert normal data (PASS)")
    args = parser.parse_args()

    path = create_sample_ate_db(stale=not args.fresh)
    print(f"Created: {path}")

    conn = sqlite3.connect(path)
    cur = conn.cursor()
    print("\n── POWER_TRADE_ERROR ──")
    cur.execute("SELECT * FROM POWER_TRADE_ERROR")
    for row in cur.fetchall():
        print(row)
    print("\n── POWER_TRADE ──")
    cur.execute("SELECT * FROM POWER_TRADE")
    for row in cur.fetchall():
        print(row)
    print("\n── EXCHSYNC_MESSAGE ──")
    cur.execute("SELECT * FROM EXCHSYNC_MESSAGE")
    for row in cur.fetchall():
        print(row)
    conn.close()
