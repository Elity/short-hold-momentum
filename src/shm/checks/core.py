from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import exchange_calendars as xcals
import pandas as pd

from shm.report.metrics import PerformanceMetrics, annualized_sharpe


@dataclass(frozen=True)
class CheckResult:
    status: str
    detail: str = ""


@dataclass(frozen=True)
class KR2Result:
    status: str
    sharpe_beats_spy: bool
    maxdd_beats_spy: bool
    run_status_eligible: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "sharpe_beats_spy": self.sharpe_beats_spy,
            "maxdd_beats_spy": self.maxdd_beats_spy,
            "run_status_eligible": self.run_status_eligible,
            "detail": self.detail,
        }


def compose_status(checks: Mapping[str, CheckResult | str]) -> str:
    statuses = [value.status if isinstance(value, CheckResult) else value for value in checks.values()]
    if "FAIL" in statuses:
        return "FAIL"
    if "SUSPECT" in statuses:
        return "SUSPECT"
    if "INCONCLUSIVE" in statuses:
        return "INCONCLUSIVE"
    if any(status.startswith("WARN") for status in statuses):
        return "WARN"
    return "PASS"


def evaluate_kr2(
    strategy: PerformanceMetrics,
    benchmark: PerformanceMetrics,
    run_status: str,
) -> KR2Result:
    sharpe_beats_spy = strategy.sharpe > benchmark.sharpe
    maxdd_beats_spy = abs(strategy.maxdd) < abs(benchmark.maxdd)
    run_status_eligible = run_status in {"PASS", "WARN", "SUSPECT_REVIEWED"}
    passed = sharpe_beats_spy and maxdd_beats_spy and run_status_eligible
    return KR2Result(
        status="PASS" if passed else "FAIL",
        sharpe_beats_spy=sharpe_beats_spy,
        maxdd_beats_spy=maxdd_beats_spy,
        run_status_eligible=run_status_eligible,
        detail=(
            f"Sharpe {strategy.sharpe:.3f} {'>' if sharpe_beats_spy else '<='} "
            f"SPY {benchmark.sharpe:.3f}; |MaxDD| {abs(strategy.maxdd):.2%} "
            f"{'<' if maxdd_beats_spy else '>='} SPY {abs(benchmark.maxdd):.2%}; "
            f"run status {run_status} is "
            f"{'eligible' if run_status_eligible else 'ineligible'}"
        ),
    )


def check_truncated_signal(
    full_selection: Mapping[str, float], truncated_selection: Mapping[str, float]
) -> CheckResult:
    if dict(full_selection) != dict(truncated_selection):
        return CheckResult("FAIL", "selection or weights changed after future rows were removed")
    return CheckResult("PASS")


def check_cost_fragility(cagr_default: float, cagr_stress: float) -> CheckResult:
    if cagr_default > 0 and cagr_stress < 0.5 * cagr_default:
        return CheckResult("WARN_COST_FRAGILE", "25 bps CAGR is below half of 10 bps CAGR")
    return CheckResult("PASS")


def check_survivorship(
    user_metrics: PerformanceMetrics,
    pit_metrics: PerformanceMetrics,
    coverage: float,
) -> CheckResult:
    if coverage < 0.80:
        return CheckResult("INCONCLUSIVE", f"PIT price coverage {coverage:.1%} is below 80%")
    sharpe_gap = user_metrics.sharpe - pit_metrics.sharpe
    cagr_gap = user_metrics.cagr - pit_metrics.cagr
    if sharpe_gap > 0.5 or cagr_gap > 0.05:
        return CheckResult(
            "WARN_SURVIVORSHIP",
            f"user-minus-PIT Sharpe={sharpe_gap:.3f}, CAGR={cagr_gap:.2%}, coverage={coverage:.1%}",
        )
    return CheckResult("PASS", f"PIT coverage={coverage:.1%}")


def check_one_year_dependency(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> CheckResult:
    aligned = pd.concat(
        [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")], axis=1, join="inner"
    ).dropna()
    if aligned.empty:
        return CheckResult("INCONCLUSIVE", "no overlapping daily returns")
    annual = (1.0 + aligned["strategy"]).groupby(aligned.index.year).prod() - 1.0
    best_year = int(annual.idxmax())
    reduced = aligned[aligned.index.year != best_year]
    strategy_sharpe = annualized_sharpe(reduced["strategy"])
    benchmark_sharpe = annualized_sharpe(reduced["benchmark"])
    if strategy_sharpe <= benchmark_sharpe:
        return CheckResult(
            "WARN_ONE_YEAR_WONDER",
            f"after removing {best_year}, strategy Sharpe {strategy_sharpe:.3f} <= SPY {benchmark_sharpe:.3f}",
        )
    return CheckResult("PASS", f"removed best year {best_year}")


def check_too_good(intervals: Mapping[str, PerformanceMetrics]) -> CheckResult:
    triggers = [
        name
        for name, metrics in intervals.items()
        if metrics.cagr > 0.30 or abs(metrics.maxdd) < 0.08
    ]
    if triggers:
        return CheckResult("SUSPECT", f"INV-08 triggered for: {', '.join(triggers)}")
    return CheckResult("PASS")


def check_constraints(
    daily_weights: pd.DataFrame,
    cash: pd.Series,
    transactions: pd.DataFrame,
) -> CheckResult:
    weights = daily_weights.fillna(0.0).astype(float)
    if (weights < -1e-12).any().any():
        return CheckResult("FAIL", "negative portfolio weight")
    if (weights.sum(axis=1) > 1.0 + 1e-9).any():
        return CheckResult("FAIL", "portfolio weights exceed 1.0")
    if (cash.astype(float) < -1e-9).any():
        return CheckResult("FAIL", "negative cash")
    if not transactions.empty:
        signal_dates = pd.to_datetime(transactions["signal_date"])
        execution_dates = pd.to_datetime(transactions["execution_date"])
        if (execution_dates <= signal_dates).any():
            return CheckResult("FAIL", "trade occurred on or before its signal date")
    return CheckResult("PASS")


def check_next_session_execution(
    transactions: pd.DataFrame, *, calendar: str = "XNYS"
) -> CheckResult:
    if transactions.empty:
        return CheckResult("PASS", "no transactions")
    signal_dates = pd.DatetimeIndex(pd.to_datetime(transactions["signal_date"])).tz_localize(None)
    execution_dates = pd.DatetimeIndex(pd.to_datetime(transactions["execution_date"])).tz_localize(None)
    exchange = xcals.get_calendar(
        calendar,
        start=signal_dates.min() - pd.Timedelta(days=10),
        end=execution_dates.max() + pd.Timedelta(days=10),
    )
    sessions = exchange.sessions.tz_localize(None)
    for signal_date, execution_date in zip(signal_dates, execution_dates, strict=True):
        position = sessions.searchsorted(signal_date, side="right")
        if position >= len(sessions) or execution_date != sessions[position]:
            return CheckResult(
                "FAIL",
                f"{signal_date.date()} executed {execution_date.date()}, expected next XNYS session",
            )
    return CheckResult("PASS", "all trades executed on the next XNYS session")
