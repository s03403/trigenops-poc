"""Database connection helpers.

Supports real PostgreSQL/Oracle connections and a local SQLite fallback
when USE_SAMPLE_DB=true for testing.
"""

from __future__ import annotations

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator

from observer_advisor.config import get_config

logger = logging.getLogger(__name__)


def _use_sample() -> bool:
    return get_config().use_sample_db


def _use_sample_ascm() -> bool:
    return get_config().use_sample_ascm


def _use_sample_ate() -> bool:
    return get_config().use_sample_ate


def _use_sample_promptopt() -> bool:
    return get_config().use_sample_promptopt


# ── SQLite (testing) ──────────────────────────────────────────────────────────

SAMPLE_ASCM_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_ascm.db")
SAMPLE_ATE_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_ate.db")
SAMPLE_PROMPTOPT_DB_PATH = os.path.join(os.path.dirname(__file__), "sample_promptopt.db")


@contextmanager
def _sample_ascm_connection() -> Generator:
    conn = sqlite3.connect(SAMPLE_ASCM_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _sample_ate_connection() -> Generator:
    conn = sqlite3.connect(SAMPLE_ATE_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _sample_promptopt_connection() -> Generator:
    conn = sqlite3.connect(SAMPLE_PROMPTOPT_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


# ── ASCM (PostgreSQL) ────────────────────────────────────────────────────────

@contextmanager
def get_ascm_connection() -> Generator:
    if _use_sample_ascm():
        with _sample_ascm_connection() as conn:
            yield conn
        return

    import psycopg2
    cfg = get_config().ascm_db
    conn = psycopg2.connect(
        host=cfg.host, database=cfg.database,
        user=cfg.user, password=cfg.password,
        port=cfg.port, options=f"-c search_path={cfg.schema}",
    )
    try:
        yield conn
    finally:
        conn.close()


# ── PromptOpt (PostgreSQL) ───────────────────────────────────────────────────

@contextmanager
def get_promptopt_connection() -> Generator:
    if _use_sample_promptopt():
        with _sample_promptopt_connection() as conn:
            yield conn
        return

    import psycopg2
    cfg = get_config().promptopt_db
    conn = psycopg2.connect(
        host=cfg.host, database=cfg.database,
        user=cfg.user, password=cfg.password,
        port=cfg.port, options=f"-c search_path={cfg.schema}",
    )
    try:
        yield conn
    finally:
        conn.close()


# ── ATE (Oracle) ─────────────────────────────────────────────────────────────

@contextmanager
def get_ate_connection() -> Generator:
    if _use_sample_ate():
        with _sample_ate_connection() as conn:
            yield conn
        return

    import oracledb
    cfg = get_config().ate_db
    dsn = oracledb.makedsn(cfg.host, cfg.port, service_name=cfg.service_name)
    conn = oracledb.connect(user=cfg.user, password=cfg.password, dsn=dsn)
    try:
        yield conn
    finally:
        conn.close()
