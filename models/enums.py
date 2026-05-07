"""Enumerations used across Observer-Advisor pipeline."""

from enum import Enum


class Application(str, Enum):
    ASCM = "ASCM"
    ATE = "ATE"
    PROMPTOPT = "PromptOpt"


class Environment(str, Enum):
    PROD = "PROD"
    UAT = "UAT"


class SignalType(str, Enum):
    DATA_AVAILABILITY = "data_availability"
    STALENESS = "staleness"
    ERROR_COUNT = "error_count"
    TRADE_FLOW = "trade_flow"
    SYNC_ERROR = "sync_error"
    QUEUE_DEPTH = "queue_depth"
    EXECUTION_CYCLE = "execution_cycle"
    OBSERVABILITY_GAP = "observability_gap"


class DetectionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    NONE = "NONE"
