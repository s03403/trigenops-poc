"""ASCM database check tool for LangGraph.

Queries the ASCM PostgreSQL database for Target Frequency freshness.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta

from langchain_core.tools import tool

from observer_advisor.tools.db_connections import get_ascm_connection
from observer_advisor.config import get_config

logger = logging.getLogger(__name__)


@tool
def check_ascm() -> dict:
    """Check ASCM database for Target Frequency freshness.

    Checks whether today's TARGETDATE exists in METADATA for TGT_FREQUENCY.
    Returns the count of matching rows to determine if data is current.
    """
    # use_sample = get_config().use_sample_db
    use_sample = get_config().use_sample_ascm
    today = date.today()
    today_start = f"{today} 00:00:00"
    tomorrow_start = f"{today + timedelta(days=1)} 00:00:00"

    if use_sample:
        query = """
            SELECT COUNT(*) AS row_count
            FROM METADATA
            WHERE DOCUMENTTYPE = 'TGT_FREQUENCY'
            AND "targetdate" >= %s
            AND "targetdate" < %s?
        """
        params = (today_start, tomorrow_start)
    else:
        query = """
            SELECT COUNT(*) AS row_count
            FROM METADATA
            WHERE DOCUMENTTYPE = 'TGT_FREQUENCY'
            AND "targetdate" >= %s
            AND "targetdate" < %s
        """
        params = (today_start, tomorrow_start)

    try:
        with get_ascm_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            count = row[0] if row else 0

            # raw_value = today's date if rows exist, else None
            value = today.isoformat() if count > 0 else None

            return {
                "check_id": "Target Frequency",
                "application": "ASCM",
                "source_table": "ascm_web.METADATA",
                "query_executed": query.strip(),
                "raw_value": value,
                "row_count": count,
                "checked_date": today.isoformat(),
                "error": None,
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        logger.error(f"ASCM check failed: {e}")
        return {
            "check_id": "Target Frequency",
            "application": "ASCM",
            "source_table": "ascm_web.METADATA",
            "query_executed": query.strip(),
            "raw_value": None,
            "row_count": None,
            "checked_date": today.isoformat(),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
