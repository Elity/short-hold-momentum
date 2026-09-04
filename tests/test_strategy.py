from __future__ import annotations

from datetime import date

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from shm.config import (
    EligibilityConfig,
    RiskConfig,
    SignalConfig,
    TrendFilterConfig,
    VolTargetConfig,
)
from shm.risk import (
    assert_long_only_weights,
    basket_realized_vol,
    build_risk_adjusted_target,
)
from shm.signals import select_momentum, xnys_rebalance_dates
from shm.universe import filter_eligible_tickers, load_frozen_universe


def price_frame(
    sessions: pd.DatetimeIndex,
    closes: np.ndarray | list[float],
    *,
    volume: float = 1_000_000,
) -> pd.DataFrame:
    close = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "date": sessions,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": volume,
        }
    )


def test_frozen_universe_exclusions_and_eligibility(tmp_path) -> None:
    (tmp_path / "universe.yaml").write_text(
        """\
frozen_on: 2026-09-04
rule_text: owner supplied technology universe
exclusions: [MSFT]
tickers: [GOOD, MSFT, CHEAP, ILLQ, MISS, QUAR]
""",
        encoding="utf-8",
    )
    universe = load_frozen_universe(tmp_path)
    assert universe.active_tickers == ("GOOD", "CHEAP", "ILLQ", "MISS", "QUAR")

    sessions = xcals.get_calendar(
        "XNYS", start="2022-01-01", end="2024-01-31"
    ).sessions_in_range("2023-01-03", "2024-01-31")[-253:]
    prices = {
        "GOOD": price_frame(sessions, np.full(len(sessions), 100.0)),
        "MSFT": price_frame(sessions, np.full(len(sessions), 100.0)),
        "CHEAP": price_frame(sessions, np.full(len(sessions), 4.0)),
        "ILLQ": price_frame(sessions, np.full(len(sessions), 100.0), volume=10_000),
        "MISS": price_frame(sessions.delete(10), np.full(len(sessions) - 1, 100.0)),
        "QUAR": price_frame(sessions, np.full(len(sessions), 100.0)),
    }
    result = filter_eligible_tickers(
        prices,
        universe,
        sessions[-1],
        config=EligibilityConfig(
            min_price_usd=5,
            min_adv_usd=10_000_000,
            adv_window_days=60,
            require_full_history=True,
            min_eligible_count=2,
        ),
        lookback_trading_days=252,
        quarantined={"QUAR"},
    )

    assert result.eligible == ("GOOD",)
    assert result.below_minimum
    assert result.rejected == {
        "MSFT": "excluded",
        "CHEAP": "price_below_minimum",
        "ILLQ": "adv_below_minimum",
        "MISS": "incomplete_history",
        "QUAR": "quarantined",
    }


def test_exact_momentum_tie_break_and_truncation_consistency() -> None:
    sessions = xcals.get_calendar(
        "XNYS", start="2024-01-01", end="2024-02-29"
    ).sessions_in_range("2024-01-02", "2024-01-12")[:8]
    signal_date = sessions[-2]
    # lookback=4 and skip=1: score uses close[t-1] / close[t-4] - 1.
    prices = {
        "BBB": price_frame(sessions, [10, 10, 10, 10, 10, 20, 999, 1]),
        "AAA": price_frame(sessions, [5, 5, 5, 5, 5, 10, 999, 1]),
        "CCC": price_frame(sessions, [10, 10, 10, 10, 10, 15, 999, 1]),
    }
    config = SignalConfig(
        name="xs_momentum_12_1",
        lookback_trading_days=4,
        skip_trading_days=1,
        top_n=2,
        weighting="equal",
        tie_break="ticker_asc",
    )

    full = select_momentum(prices, ("BBB", "AAA", "CCC"), signal_date, config=config)
    truncated_prices = {
        ticker: frame.loc[frame["date"] <= signal_date].copy()
        for ticker, frame in prices.items()
    }
    truncated = select_momentum(
        truncated_prices, ("BBB", "AAA", "CCC"), signal_date, config=config
    )

    pd.testing.assert_series_equal(full.scores.sort_index(), truncated.scores.sort_index())
    assert full.selected == truncated.selected == ("AAA", "BBB")
    assert full.scores.to_dict() == pytest.approx({"BBB": 1.0, "AAA": 1.0, "CCC": 0.5})
    assert full.raw_weights.to_dict() == {"AAA": 0.5, "BBB": 0.5}


def test_rebalance_dates_are_every_twentieth_xnys_session() -> None:
    dates = xnys_rebalance_dates(
        date(2024, 1, 1),
        date(2024, 6, 30),
        warmup_trading_days=260,
        every_trading_days=20,
    )
    calendar = xcals.get_calendar("XNYS", start="2022-01-01", end="2024-06-30")
    all_sessions = calendar.sessions_in_range(dates[0], dates[-1])

    assert dates[0] == pd.Timestamp("2024-01-02")
    positions = all_sessions.get_indexer(dates)
    assert np.diff(positions).tolist() == [20] * (len(dates) - 1)
    assert all(calendar.is_session(session) for session in dates)


def test_risk_controls_use_trend_and_equal_weight_basket_vol() -> None:
    sessions = xcals.get_calendar(
        "XNYS", start="2024-01-01", end="2024-02-29"
    ).sessions_in_range("2024-01-02", "2024-01-12")[:8]
    signal_date = sessions[-1]
    a_close = np.array([100, 102, 101, 104, 103, 107, 108, 110], dtype=float)
    b_close = np.array([100, 99, 101, 100, 103, 102, 106, 105], dtype=float)
    prices = {
        "AAA": price_frame(sessions, a_close),
        "BBB": price_frame(sessions, b_close),
        "SPY": price_frame(sessions, np.arange(100, 108, dtype=float)),
    }
    vol_config = VolTargetConfig(
        enabled=True,
        window_days=4,
        target_annual_vol=0.15,
        max_exposure=1.0,
    )
    risk_config = RiskConfig(
        trend_filter=TrendFilterConfig(
            enabled=True,
            benchmark="SPY",
            sma_days=3,
            off_exposure=0.0,
        ),
        vol_target=vol_config,
    )
    raw_weights = pd.Series({"AAA": 0.5, "BBB": 0.5}, dtype=float)

    expected_returns = pd.DataFrame({"AAA": a_close[-5:], "BBB": b_close[-5:]})
    expected_vol = float(
        expected_returns.pct_change(fill_method=None).iloc[1:].mean(axis=1).std(ddof=1)
        * np.sqrt(252)
    )
    assert basket_realized_vol(
        prices, ["AAA", "BBB"], signal_date, window_days=4
    ) == pytest.approx(expected_vol)

    target = build_risk_adjusted_target(
        raw_weights, prices, signal_date, config=risk_config
    )
    expected_exposure = min(1.0, 0.15 / expected_vol)
    assert target.trend_exposure == 1.0
    assert target.realized_vol == pytest.approx(expected_vol)
    assert target.exposure == pytest.approx(expected_exposure)
    assert target.weights.sum() + target.cash == pytest.approx(1.0)
    assert (target.weights >= 0).all()


def test_trend_off_is_all_cash_and_invalid_long_only_targets_are_rejected() -> None:
    sessions = xcals.get_calendar(
        "XNYS", start="2024-01-01", end="2024-02-29"
    ).sessions_in_range("2024-01-02", "2024-01-12")
    prices = {
        "AAA": price_frame(sessions, np.linspace(100, 110, len(sessions))),
        "SPY": price_frame(sessions, np.linspace(110, 100, len(sessions))),
    }
    config = RiskConfig(
        trend_filter=TrendFilterConfig(
            enabled=True,
            benchmark="SPY",
            sma_days=3,
            off_exposure=0.0,
        ),
        vol_target=VolTargetConfig(
            enabled=True,
            window_days=4,
            target_annual_vol=0.15,
            max_exposure=1.0,
        ),
    )
    target = build_risk_adjusted_target(
        pd.Series({"AAA": 1.0}), prices, sessions[-1], config=config
    )
    assert target.exposure == 0.0
    assert target.weights["AAA"] == 0.0
    assert target.cash == 1.0

    with pytest.raises(ValueError, match="negative weights"):
        assert_long_only_weights({"AAA": -0.01})
    with pytest.raises(ValueError, match="sum"):
        assert_long_only_weights({"AAA": 0.6, "BBB": 0.5})
    with pytest.raises(ValueError, match="cash"):
        assert_long_only_weights({"AAA": 0.5}, cash=-0.1)
