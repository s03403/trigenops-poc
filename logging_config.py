"""Centralized logging configuration for Observer-Advisor pipeline.

Log files (all under observer_advisor/logs/):
  pipeline.log  — Full execution trace, all steps, all apps (DEBUG+)
  errors.log    — ERROR and WARNING only, all apps
  llm.log       — LLM prompts & responses (Steps 2-5)
  rag.log       — RAG retrieval queries & results
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

# ── Log directory ─────────────────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── Formatters ────────────────────────────────────────────────────────────────

_DETAILED_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_COMPACT_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Max file size: 10 MB, keep 3 backups ──────────────────────────────────────

_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 3

# ── Logger names for dedicated log files ──────────────────────────────────────

LLM_LOGGER = "observer_advisor.llm"
RAG_LOGGER = "observer_advisor.rag"


def setup_logging(console_level: int = logging.INFO) -> None:
    """Configure the 4-file logging setup. Call once at startup."""

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls (e.g. in tests)
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    # 1. pipeline.log — everything at DEBUG+
    pipeline_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "pipeline.log"),
        maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
    )
    pipeline_handler.setLevel(logging.DEBUG)
    pipeline_handler.setFormatter(_DETAILED_FMT)
    root.addHandler(pipeline_handler)

    # 2. errors.log — WARNING+ only
    error_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "errors.log"),
        maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(_DETAILED_FMT)
    root.addHandler(error_handler)

    # 3. llm.log — dedicated LLM logger
    llm_logger = logging.getLogger(LLM_LOGGER)
    llm_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "llm.log"),
        maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
    )
    llm_handler.setLevel(logging.DEBUG)
    llm_handler.setFormatter(_COMPACT_FMT)
    llm_logger.addHandler(llm_handler)

    # 4. rag.log — dedicated RAG logger
    rag_logger = logging.getLogger(RAG_LOGGER)
    rag_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "rag.log"),
        maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
    )
    rag_handler.setLevel(logging.DEBUG)
    rag_handler.setFormatter(_COMPACT_FMT)
    rag_logger.addHandler(rag_handler)

    # 5. Console — configurable level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(_DETAILED_FMT)
    root.addHandler(console_handler)
