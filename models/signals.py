"""Data models for each pipeline step."""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import Application, Environment, SignalType, DetectionResult, Severity


# ── Tool output (raw DB result) ───────────────────────────────────────────────

class RawCheckResult(BaseModel):
    """Raw result returned by a DB-check tool."""
    check_id: str
    application: Application
    source_table: str
    query_executed: str
    raw_value: Any = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Step 2: LLM Enrichment (validated) ────────────────────────────────────────

class Enrichment(BaseModel):
    """Validated LLM enrichment output for a signal."""
    interpretation: str = ""
    business_context: str = ""


# ── Step 2 output: Normalized Signal ──────────────────────────────────────────

class NormalizedSignal(BaseModel):
    """Canonical signal after normalization & enrichment."""
    signal_id: str = Field(default_factory=lambda: f"SIG-{uuid.uuid4().hex[:8]}")
    check_id: str
    application: Application
    environment: Environment = Environment.PROD
    signal_type: SignalType
    observed_value: Any = None
    expected_value: Any = None
    business_date: date = Field(default_factory=date.today)
    collection_time: datetime = Field(default_factory=datetime.utcnow)
    evidence: dict[str, Any] = Field(default_factory=dict)
    enrichment: dict[str, Any] = Field(default_factory=dict)


# ── Step 3 output: Detection ─────────────────────────────────────────────────

class Detection(BaseModel):
    """Result of a detection rule evaluation."""
    detection_id: str = Field(default_factory=lambda: f"DET-{uuid.uuid4().hex[:8]}")
    signal_id: str
    check_id: str
    application: Application
    result: DetectionResult
    rule_name: str
    confidence: str = "high"
    evidence: str = ""
    proposed_severity: Optional[Severity] = None


# ── Step 4 output: Correlated Incident ────────────────────────────────────────

class IncidentCandidate(BaseModel):
    """Grouped detections forming one incident."""
    incident_id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:8]}")
    application: Application
    environment: Environment = Environment.PROD
    dedupe_key: str
    likely_cause: Optional[str] = None
    contributing_detections: list[Detection] = Field(default_factory=list)
    correlation_summary: Optional[str] = None
    business_date: date = Field(default_factory=date.today)


# ── Step 5 output: Routed Incident ───────────────────────────────────────────

class Incident(BaseModel):
    """Final incident ready for Advisor handoff."""
    incident_id: str
    severity: Severity
    application: Application
    environment: Environment
    assignment_group: str
    title: str
    description: str
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    correlation_summary: Optional[str] = None
    advisor_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
