import exchange_calendars as xcals
import numpy as np
import pandas as pd

from shm.config import load_config_bundle
from shm.experiments import read_jsonl, record_oos_unlock
from shm.pipeline import (
    build_signal_plan,
    check_plan_no_lookahead,
    load_pit_history,
    pit_price_coverage,
    pit_tickers_for_period,
    prepare_cached_data,
)
from shm.universe import FrozenUniverse


def _frame(sessions: pd.DatetimeIndex, start: float, slope: float) -> pd.DataFrame:
    close = start + np.arange(len(sessions)) * slope
    return pd.DataFrame(
        {
            "date": sessions,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000_000,
        }
    )


def test_signal_plan_is_long_only_and_truncation_stable() -> None:
    calendar = xcals.get_calendar("XNYS", start="2003-01-01", end="2006-12-31")
    sessions = calendar.sessions
    prices = {
        "AAA": _frame(sessions, 20, 0.10),
        "BBB": _frame(sessions, 20, 0.08),
        "CCC": _frame(sessions, 20, 0.06),
        "SPY": _frame(sessions, 100, 0.05),
    }
    config = load_config_bundle("config")
    eligibility = config.params.eligibility.model_copy(
        update={"min_adv_usd": 1, "min_eligible_count": 2}
    )
    signal = config.params.signal.model_copy(update={"top_n": 2})
    config = config.model_copy(
        update={"params": config.params.model_copy(update={"eligibility": eligibility, "signal": signal})}
    )
    universe = FrozenUniverse(pd.Timestamp("2026-09-04").date(), "test", ("AAA", "BBB", "CCC"), frozenset())
    rebalance_dates = sessions[-6:]
    plan = build_signal_plan(
        prices=prices,
        universe=universe,
        config=config,
        rebalance_dates=rebalance_dates,
    )
    assert (plan.target_weights >= 0).all().all()
    assert (plan.target_weights.sum(axis=1) <= 1.0 + 1e-9).all()
    assert check_plan_no_lookahead(
        prices=prices,
        universe=universe,
        config=config,
        plan=plan,
        samples=5,
    ).status == "PASS"


def test_pit_ticker_union_includes_start_snapshot_and_period_changes(tmp_path) -> None:
    path = tmp_path / "history.csv"
    pd.DataFrame(
        {
            "date": ["2004-12-01", "2005-06-01", "2019-01-01"],
            "tickers": ["AAA,BBB", "BBB,CCC", "ZZZ"],
        }
    ).to_csv(path, index=False)
    history = load_pit_history(path)
    assert pit_tickers_for_period(history, "2005-01-01", "2018-12-31") == ("AAA", "BBB", "CCC")


def test_pit_coverage_requires_data_on_each_signal_date(tmp_path) -> None:
    path = tmp_path / "history.csv"
    pd.DataFrame({"date": ["2024-01-02"], "tickers": ["AAA,BBB"]}).to_csv(path, index=False)
    history = load_pit_history(path)
    dates = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    prices = {
        "AAA": _frame(dates, 20, 0.1),
        "BBB": _frame(pd.DatetimeIndex([dates[1]]), 20, 0.1),
    }
    assert pit_price_coverage(history, dates, prices) == 0.75


def test_batch_oos_read_records_one_unlock(tmp_path) -> None:
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    dates = pd.DatetimeIndex(["2018-12-31", "2019-01-02"])
    for ticker in ("AAA", "BBB", "SPY"):
        _frame(dates, 20, 0.1).to_parquet(cache_dir / f"{ticker}.parquet", index=False)
    config = load_config_bundle("config")
    universe = FrozenUniverse(
        pd.Timestamp("2026-09-04").date(), "test", ("AAA", "BBB"), frozenset()
    )
    audit_path = tmp_path / "oos_unlocks.jsonl"
    record_oos_unlock(
        audit_path,
        run_id="run-1",
        variant_index=1,
        reason="owner-approved OOS run",
        predicted="The candidate should retain its edge.",
        approved_by="owner",
    )

    prepared = prepare_cached_data(
        config=config,
        universe=universe,
        cache_dir=cache_dir,
        start=dates[0],
        end=dates[-1],
        unlock_oos=True,
        reason="owner-approved OOS run",
        oos_audit_path=audit_path,
        oos_run_id="run-1",
    )
    assert len(read_jsonl(audit_path)) == 1
    assert all(len(frame) == 2 for frame in prepared.prices.values())


def test_future_extreme_returns_do_not_quarantine_an_earlier_signal() -> None:
    calendar = xcals.get_calendar("XNYS", start="2023-01-01", end="2025-12-31")
    sessions = calendar.sessions
    prices = {
        "AAA": _frame(sessions, 20, 0.10),
        "BBB": _frame(sessions, 20, 0.05),
        "SPY": _frame(sessions, 100, 0.04),
    }
    signal_date = sessions[300]
    future_mask = prices["AAA"]["date"] > signal_date
    future_rows = prices["AAA"].index[future_mask][-5:]
    prices["AAA"].loc[future_rows, "close"] *= [2, 0.4, 2, 0.4, 2]
    config = load_config_bundle("config")
    dates = config.dates.model_copy(update={"dev_start": sessions[0].date()})
    eligibility = config.params.eligibility.model_copy(
        update={"min_adv_usd": 1, "min_eligible_count": 2}
    )
    signal = config.params.signal.model_copy(update={"top_n": 1})
    config = config.model_copy(
        update={
            "dates": dates,
            "params": config.params.model_copy(update={"eligibility": eligibility, "signal": signal}),
        }
    )
    universe = FrozenUniverse(pd.Timestamp("2026-09-04").date(), "test", ("AAA", "BBB"), frozenset())
    plan = build_signal_plan(
        prices=prices,
        universe=universe,
        config=config,
        rebalance_dates=pd.DatetimeIndex([signal_date]),
    )
    assert "AAA" in plan.selections[signal_date]
