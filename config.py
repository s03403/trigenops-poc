"""
Configuration for Observer-Advisor pipeline.

All DB credentials, thresholds, and LLM settings.
In production, load from Azure Key Vault / env vars.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


# ── Database Configs ──────────────────────────────────────────────────────────

@dataclass
class ASCMDBConfig:
    host: str = field(default=None)
    database: str = field(default=None)
    user: str = field(default=None)
    password: str = field(default=None)
    port: int = field(default=None)
    schema: str = "ascm_web"

    def __post_init__(self):
        if self.host is None:
            self.host = os.getenv("ASCM_DB_HOST", "ulancapppg001.postgres.database.azure.com")
        if self.database is None:
            self.database = os.getenv("ASCM_DB_NAME", "ascm_web")
        if self.user is None:
            self.user = os.getenv("ASCM_DB_USER", "")
        if self.password is None:
            self.password = os.getenv("ASCM_DB_PASSWORD", "")
        if self.port is None:
            self.port = int(os.getenv("ASCM_DB_PORT", "5432"))


@dataclass
class ATEDBConfig:
    host: str = field(default=None)
    service_name: str = field(default=None)
    user: str = field(default=None)
    password: str = field(default=None)
    port: int = field(default=None)

    def __post_init__(self):
        if self.host is None:
            self.host = os.getenv("ATE_DB_HOST", "uktreddbprd001.uniper.onmicrosoft.com")
        if self.service_name is None:
            self.service_name = os.getenv("ATE_DB_SERVICE", "ELATE")
        if self.user is None:
            self.user = os.getenv("ATE_DB_USER", "")
        if self.password is None:
            self.password = os.getenv("ATE_DB_PASSWORD", "")
        if self.port is None:
            self.port = int(os.getenv("ATE_DB_PORT", "1521"))


@dataclass
class PromptOptDBConfig:
    host: str = field(default=None)
    database: str = field(default=None)
    user: str = field(default=None)
    password: str = field(default=None)
    port: int = field(default=None)
    schema: str = "promptopt"

    def __post_init__(self):
        if self.host is None:
            self.host = os.getenv("PROMPTOPT_DB_HOST", "pgpaas-prompt-prd-001.postgres.database.azure.com")
        if self.database is None:
            self.database = os.getenv("PROMPTOPT_DB_NAME", "ulpoptpg001")
        if self.user is None:
            self.user = os.getenv("PROMPTOPT_DB_USER", "")
        if self.password is None:
            self.password = os.getenv("PROMPTOPT_DB_PASSWORD", "")
        if self.port is None:
            self.port = int(os.getenv("PROMPTOPT_DB_PORT", "5432"))


# ── Detection Thresholds ─────────────────────────────────────────────────────

@dataclass
class Thresholds:
    # ASCM
    ascm_stale_hours: float = 4.0

    # ATE
    ate_error_min_count: int = 1
    ate_trade_window_minutes: int = 5
    ate_sync_error_min_count: int = 1

    # PromptOpt
    promptopt_stale_minutes: int = 60
    promptopt_queue_warning: int = 100
    promptopt_queue_critical: int = 500


# ── LLM Config ───────────────────────────────────────────────────────────────

@dataclass
class LLMConfig:
    api_type: str = field(default=None)
    api_base: str = field(default=None)
    api_key: str = field(default=None)
    api_version: str = field(default=None)
    deployment: str = field(default=None)
    temperature: float = 0.1

    def __post_init__(self):
        if self.api_type is None:
            self.api_type = os.getenv("OPENAI_API_TYPE", "azure")
        if self.api_base is None:
            self.api_base = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        if self.api_key is None:
            self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        if self.api_version is None:
            self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        if self.deployment is None:
            self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


# ── Master Config ─────────────────────────────────────────────────────────────

@dataclass
class Config:
    ascm_db: ASCMDBConfig = field(default_factory=ASCMDBConfig)
    ate_db: ATEDBConfig = field(default_factory=ATEDBConfig)
    promptopt_db: PromptOptDBConfig = field(default_factory=PromptOptDBConfig)
    thresholds: Thresholds = field(default_factory=Thresholds)
    llm: LLMConfig = field(default_factory=LLMConfig)
    environment: str = field(default=None)
    use_sample_db: bool = field(default=None)

    # Per-app sample DB overrides (fall back to use_sample_db if not set)
    use_sample_ascm: bool = field(default=None)
    use_sample_ate: bool = field(default=None)
    use_sample_promptopt: bool = field(default=None)

    # Per-application check intervals (seconds)
    ascm_interval: int = field(default=60)
    ate_interval: int = field(default=3000)
    promptopt_interval: int = field(default=3000)

    # Base loop tick (how often the scheduler wakes up)
    loop_tick_seconds: int = field(default=None)

    def __post_init__(self):
        if self.environment is None:
            self.environment = os.getenv("OBSERVER_ENV", "PROD")
        if self.use_sample_db is None:
            self.use_sample_db = os.getenv("USE_SAMPLE_DB", "false").lower() == "true"
        # Per-app overrides: if not set explicitly, fall back to global
        if self.use_sample_ascm is None:
            env = os.getenv("USE_SAMPLE_ASCM")
            self.use_sample_ascm = env.lower() == "true" if env else self.use_sample_db
        if self.use_sample_ate is None:
            env = os.getenv("USE_SAMPLE_ATE")
            self.use_sample_ate = env.lower() == "true" if env else self.use_sample_db
        if self.use_sample_promptopt is None:
            env = os.getenv("USE_SAMPLE_PROMPTOPT")
            self.use_sample_promptopt = env.lower() == "true" if env else self.use_sample_db
        if self.ascm_interval is None:
            self.ascm_interval = int(os.getenv("ASCM_INTERVAL", "300"))
        if self.ate_interval is None:
            self.ate_interval = int(os.getenv("ATE_INTERVAL", "900"))
        if self.promptopt_interval is None:
            self.promptopt_interval = int(os.getenv("PROMPTOPT_INTERVAL", "1800"))
        if self.loop_tick_seconds is None:
            self.loop_tick_seconds = int(os.getenv("LOOP_TICK", "60"))


# Singleton
_cfg: Config | None = None


def get_config() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg
