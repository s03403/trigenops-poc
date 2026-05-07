"""PromptOpt database check tool for LangGraph.

Queries the PromptOpt PostgreSQL database for activity freshness,
queue depth, and recent errors.
"""

from __future__ import annotations

import logging
from datetime import datetime

from langchain_core.tools import tool

from observer_advisor.tools.db_connections import get_promptopt_connection
from observer_advisor.config import get_config

logger = logging.getLogger(__name__)


@tool
def check_promptopt() -> dict:
    """Check PromptOpt database for activity, queue depth, and errors.

    Runs multiple checks:
    - Latest activity timestamp from popt_activity
    - Pending queue depth from POPT_XML_QUEUE_TAB
    - Recent error count from popt_log (last 30 min)
    Returns all results in a single dict.
    """
    from datetime import timedelta, timezone

    use_sample = get_config().use_sample_promptopt
    results = {}

    if use_sample:
        cutoff_str = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        checks = [
            {
                "check_id": "promptopt_activity",
                "table": "popt_activity",
                "query": "SELECT MAX(last_active) FROM popt_activity",
                "params": (),
            },
            {
                "check_id": "promptopt_queue_depth",
                "table": "popt_xml_queue_tab",
                "query": "SELECT COUNT(*) FROM popt_xml_queue_tab WHERE status = 'PENDING'",
                "params": (),
            },
            {
                "check_id": "promptopt_errors",
                "table": "popt_log",
                "query": "SELECT COUNT(*) FROM popt_log WHERE log_level = 'ERROR' AND created_at >= ?",
                "params": (cutoff_str,),
            },
        ]
    else:
        checks = [
            {
                "check_id": "promptopt_activity",
                "table": "promptopt.popt_activity",
                "query": "SELECT MAX(created_at) FROM promptopt.popt_activity",
                "params": (),
            },
            {
                "check_id": "promptopt_queue_depth",
                "table": "promptopt.POPT_XML_QUEUE_TAB",
                "query": """
                    SELECT COUNT(*)
                    FROM promptopt."POPT_XML_QUEUE_TAB"
                    WHERE status = 'PENDING'
                """,
                "params": (),
            },
            {
                "check_id": "promptopt_errors",
                "table": "promptopt.popt_log",
                "query": """
                    SELECT COUNT(*)
                    FROM promptopt.popt_log
                    WHERE level = 'ERROR'
                      AND created_at >= NOW() - INTERVAL '30 minutes'
                """,
                "params": (),
            },
        ]

    for chk in checks:
        try:
            with get_promptopt_connection() as conn:
                cur = conn.cursor()
                cur.execute(chk["query"], chk["params"])
                row = cur.fetchone()
                value = row[0] if row else None

                if isinstance(value, datetime):
                    value = value.isoformat()

                results[chk["check_id"]] = {
                    "application": "PromptOpt",
                    "source_table": chk["table"],
                    "raw_value": value if value is not None else str(value),
                    "error": None,
                }
        except Exception as e:
            logger.error(f"PromptOpt check {chk['check_id']} failed: {e}")
            results[chk["check_id"]] = {
                "application": "PromptOpt",
                "source_table": chk["table"],
                "raw_value": None,
                "error": str(e),
            }

    return {
        "application": "PromptOpt",
        "checks": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
