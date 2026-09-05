import numpy as np
import pandas as pd

from shm.checks import (
    CheckResult,
    check_constraints,
    check_next_session_execution,
    check_spy_annual_returns,
    check_survivorship,
    check_too_good,
    compose_status,
    evaluate_kr2,
)
from shm.report import PerformanceMetrics, calculate_metrics, render_report, yearly_returns


def test_metrics_and_yearly_returns() -> None:
    index = pd.bdate_range("2025-01-02", periods=253)
    equity = pd.Series(np.linspace(100.0, 110.0, len(index)), index=index)
    weights = pd.DataFrame({"AAPL": 0.5, "NVDA": 0.25}, index=index)
    targets = weights.iloc[[0, 20, 40]]
    metrics = calculate_metrics(equity, daily_weights=weights, target_weights=targets)
    assert 0.09 < metrics.cagr < 0.11
    assert metrics.maxdd == 0.0
    assert metrics.avg_exposure == 0.75
    assert list(yearly_returns(equity).index) == [2025]


def test_status_precedence_and_future_peek_like_curve_is_suspect() -> None:
    index = pd.bdate_range("2025-01-02", periods=253)
    unknowable_next_day_returns = pd.Series(
        np.where(np.arange(len(index) - 1) % 2 == 0, 0.01, -0.01), index=index[1:]
    )
    peek_returns = unknowable_next_day_returns.abs()
    equity = pd.concat([pd.Series([100.0], index=index[:1]), 100.0 * (1.0 + peek_returns).cumprod()])
    suspicious = calculate_metrics(equity)
    check = check_too_good({"development": suspicious})
    assert check.status == "SUSPECT"
    assert compose_status({"CHK-03": "WARN_COST_FRAGILE", "CHK-05": check}) == "SUSPECT"
    assert compose_status({"CHK-01": "FAIL", "CHK-05": check}) == "FAIL"


def test_kr2_requires_both_metric_edges_and_an_eligible_status() -> None:
    strategy = PerformanceMetrics(0.10, -0.20, 0.60, 0.50, 1.0, 0.8, 20.0)
    benchmark = PerformanceMetrics(0.08, -0.30, 0.50, 0.27, 1.0, 1.0, 20.0)

    for status in ("PASS", "WARN", "SUSPECT_REVIEWED"):
        assert evaluate_kr2(strategy, benchmark, status).status == "PASS"
    result = evaluate_kr2(strategy, benchmark, "INCONCLUSIVE")
    assert result.status == "FAIL"
    assert not result.run_status_eligible

    equal_sharpe = PerformanceMetrics(0.10, -0.20, 0.50, 0.50, 1.0, 0.8, 20.0)
    assert evaluate_kr2(equal_sharpe, benchmark, "PASS").status == "FAIL"


def test_constraint_check_rejects_same_day_trade() -> None:
    index = pd.bdate_range("2025-01-02", periods=2)
    weights = pd.DataFrame({"AAPL": [0.5, 0.5]}, index=index)
    cash = pd.Series([0.5, 0.5], index=index)
    transactions = pd.DataFrame(
        {"signal_date": [index[0]], "execution_date": [index[0]], "ticker": ["AAPL"]}
    )
    assert check_constraints(weights, cash, transactions).status == "FAIL"


def test_next_session_check_rejects_delayed_execution() -> None:
    transactions = pd.DataFrame(
        {
            "signal_date": ["2025-01-03", "2025-01-03"],
            "execution_date": ["2025-01-06", "2025-01-07"],
        }
    )
    assert check_next_session_execution(transactions.iloc[[0]]).status == "PASS"
    assert check_next_session_execution(transactions.iloc[[1]]).status == "FAIL"


def test_report_contains_required_sections() -> None:
    index = pd.bdate_range("2025-01-02", periods=3)
    equity = pd.Series([100.0, 101.0, 102.0], index=index)
    metrics = calculate_metrics(equity)
    kr2 = evaluate_kr2(
        PerformanceMetrics(0.10, -0.20, 0.60, 0.50, 1.0, 0.8, 20.0),
        PerformanceMetrics(0.08, -0.30, 0.50, 0.27, 1.0, 1.0, 20.0),
        "WARN",
    )
    report = render_report(
        run_id="run-1",
        status="WARN",
        warnings=["WARN_COST_FRAGILE"],
        hypothesis="Baseline records behavior.",
        expected="No directional prediction.",
        verdict="inconclusive",
        metadata={"params_hash": "12345678", "snapshot_id": "snap"},
        params={"signal": {"top_n": 15}},
        strategy=metrics,
        stress=metrics,
        benchmark=metrics,
        strategy_yearly=yearly_returns(equity),
        benchmark_yearly=yearly_returns(equity),
        equity=equity,
        exposure=pd.Series([0.0, 0.5, 0.5], index=index),
        checks={f"CHK-{index:02d}": CheckResult("PASS") for index in range(1, 8)},
        reproduce="uv run shm backtest run --prereg experiments/prereg/V00.md",
        kr2=kr2,
    )
    for heading in (
        "## Metrics",
        "## Calendar-year returns",
        "## KR2 out-of-sample gate",
        "## Automated checks",
        "## Reproduce",
    ):
        assert heading in report
    assert "CHK-07" in report


def test_spy_second_source_check_uses_three_calendar_years() -> None:
    dates = pd.to_datetime(
        ["2008-01-02", "2008-12-31", "2012-01-03", "2012-12-31", "2018-01-02", "2018-12-31"]
    )
    primary = pd.DataFrame({"date": dates, "close": [100, 90, 100, 110, 100, 95]})
    secondary = pd.DataFrame({"date": dates, "close": [100, 90.5, 100, 110.5, 100, 95.5]})
    assert check_spy_annual_returns(primary, secondary).status == "PASS"
    secondary.loc[1, "close"] = 80
    assert check_spy_annual_returns(primary, secondary).status == "INCONCLUSIVE"


def test_survivorship_requires_coverage_before_comparing_metrics() -> None:
    user = PerformanceMetrics(0.15, -0.2, 1.0, 0.75, 1.0, 0.8, 20.0)
    pit = PerformanceMetrics(0.08, -0.2, 0.4, 0.4, 1.0, 0.8, 20.0)
    assert check_survivorship(user, pit, 0.79).status == "INCONCLUSIVE"
    assert check_survivorship(user, pit, 0.90).status == "WARN_SURVIVORSHIP"
