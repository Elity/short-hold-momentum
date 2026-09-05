"""Automated research validity checks."""

from shm.checks.core import (
    CheckResult,
    KR2Result,
    check_constraints,
    check_cost_fragility,
    check_one_year_dependency,
    check_next_session_execution,
    check_survivorship,
    check_too_good,
    check_truncated_signal,
    compose_status,
    evaluate_kr2,
)
from shm.checks.data_quality import (
    check_spy_annual_returns,
    download_stooq_spy,
    download_stooq_ticker,
)

__all__ = [
    "CheckResult",
    "KR2Result",
    "check_constraints",
    "check_cost_fragility",
    "check_one_year_dependency",
    "check_next_session_execution",
    "check_survivorship",
    "check_too_good",
    "check_truncated_signal",
    "check_spy_annual_returns",
    "compose_status",
    "evaluate_kr2",
    "download_stooq_spy",
    "download_stooq_ticker",
]
