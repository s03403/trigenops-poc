"""ATE database check tool for LangGraph.

Queries the ATE Oracle database for trade errors, trade counts,
exchange sync errors, and position management errors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from langchain_core.tools import tool

from observer_advisor.tools.db_connections import get_ate_connection
from observer_advisor.config import get_config

logger = logging.getLogger(__name__)

LOOKBACK_MINUTES = 5


@tool
def check_ate() -> dict:
    """Check ATE database for trade errors and sync issues.

    Runs multiple checks:
    - Count of recent rows in POWER_TRADE_ERROR
    - Count of recent trades in POWER_TRADE
    - Count of EXCHSYNC errors
    Returns all results in a single dict.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    use_sample = get_config().use_sample_ate
    results = {}

    cutoff_str = cutoff.isoformat()

    if use_sample:
        checks = [
            {
                "check_id": "ate_trade_errors",
                "table": "POWER_TRADE_ERROR",
                "query": "SELECT COUNT(*) FROM POWER_TRADE_ERROR WHERE CREATED_DATE >= ?",
                "params": (cutoff_str,),
            },
            {
                "check_id": "ate_trade_count",
                "table": "POWER_TRADE",
                "query": "SELECT COUNT(*) FROM POWER_TRADE WHERE CREATED_DATE >= ?",
                "params": (cutoff_str,),
            },
            {
                "check_id": "ate_exchsync_errors",
                "table": "EXCHSYNC_MESSAGE",
                "query": "SELECT COUNT(*) FROM EXCHSYNC_MESSAGE WHERE STATUS = 'ERROR' AND CREATED_DATE >= ?",
                "params": (cutoff_str,),
            },
        ]
    else:
        checks = [
            {
                "check_id": "ate_trade_errors",
                "table": "AUTOTRADE.POWER_TRADE_ERROR",
                "query": """
                    SELECT COUNT(*)
                    FROM AUTOTRADE.POWER_TRADE_ERROR
                    WHERE CREATED_DATE >= :cutoff
                """,
                "params": {"cutoff": cutoff},
            },
            {
                "check_id": "ate_trade_count",
                "table": "AUTOTRADE.POWER_TRADE",
                "query": """
                    SELECT COUNT(*)
                    FROM AUTOTRADE.POWER_TRADE
                    WHERE CREATED_DATE >= :cutoff
                """,
                "params": {"cutoff": cutoff},
            },
            {
                "check_id": "ate_exchsync_errors",
                "table": "EXCHSYNC.MESSAGE",
                "query": """
                    SELECT COUNT(*)
                    FROM EXCHSYNC.MESSAGE
                    WHERE STATUS = 'ERROR'
                      AND CREATED_DATE >= :cutoff
                """,
                "params": {"cutoff": cutoff},
            },
        ]

    for chk in checks:
        try:
            with get_ate_connection() as conn:
                cur = conn.cursor()
                cur.execute(chk["query"], chk["params"])
                count = cur.fetchone()[0]
                results[chk["check_id"]] = {
                    "application": "ATE",
                    "source_table": chk["table"],
                    "raw_value": count,
                    "error": None,
                }
        except Exception as e:
            logger.error(f"ATE check {chk['check_id']} failed: {e}")
            results[chk["check_id"]] = {
                "application": "ATE",
                "source_table": chk["table"],
                "raw_value": None,
                "error": str(e),
            }

    return {
        "application": "ATE",
        "checks": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
