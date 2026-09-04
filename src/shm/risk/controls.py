from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

import numpy as np
import pandas as pd

from shm.config import RiskConfig, TrendFilterConfig, VolTargetConfig
from shm.universe import indexed_prices, normalize_session, trailing_xnys_sessions


@dataclass(frozen=True)
class RiskAdjustedTarget:
    signal_date: pd.Timestamp
    weights: pd.Series
    cash: float
    exposure: float
    trend_exposure: float
    realized_vol: float
    vol_scale: float


def trend_exposure(
    benchmark_prices: pd.DataFrame,
    signal_date: date | pd.Timestamp | str,
    *,
    config: TrendFilterConfig,
) -> float:
    if not config.enabled:
        return 1.0
    current_session = normalize_session(signal_date)
    sessions = trailing_xnys_sessions(current_session, config.sma_days)
    closes = indexed_prices(benchmark_prices).reindex(sessions)["close"]
    if closes.isna().any():
        raise ValueError("benchmark lacks the full trend-filter window")
    return 1.0 if float(closes.iloc[-1]) > float(closes.mean()) else config.off_exposure


def basket_realized_vol(
    prices: Mapping[str, pd.DataFrame],
    selected: tuple[str, ...] | list[str],
    signal_date: date | pd.Timestamp | str,
    *,
    window_days: int,
) -> float:
    """Annualized volatility of 20 equal-weight returns in ``(t-20, t]``."""
    if not selected:
        return 0.0
    current_session = normalize_session(signal_date)
    sessions = trailing_xnys_sessions(current_session, window_days + 1)
    closes = pd.DataFrame(
        {
            ticker: indexed_prices(prices[ticker]).reindex(sessions)["close"]
            for ticker in selected
        }
    )
    if closes.isna().any().any():
        raise ValueError("selected basket lacks the full volatility window")
    basket_returns = closes.pct_change(fill_method=None).iloc[1:].mean(axis=1)
    return float(basket_returns.std(ddof=1) * np.sqrt(252.0))


def volatility_scale(realized_vol: float, *, config: VolTargetConfig) -> float:
    if not config.enabled:
        return 1.0
    if realized_vol < 0 or not np.isfinite(realized_vol):
        raise ValueError("realized_vol must be finite and non-negative")
    if realized_vol == 0:
        return config.max_exposure
    return min(config.max_exposure, config.target_annual_vol / realized_vol)


def assert_long_only_weights(
    weights: pd.Series | Mapping[str, float],
    *,
    cash: float | None = None,
    tolerance: float = 1e-9,
) -> None:
    values = pd.Series(weights, dtype=float)
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError("weights must be finite")
    if (values < -tolerance).any():
        raise ValueError("negative weights are forbidden")
    total = float(values.sum())
    if total > 1.0 + tolerance:
        raise ValueError("weight sum cannot exceed 1")
    if cash is not None:
        if not np.isfinite(cash) or cash < -tolerance:
            raise ValueError("cash cannot be negative")
        if abs((total + cash) - 1.0) > tolerance:
            raise ValueError("cash must equal 1 minus total weight")


def build_risk_adjusted_target(
    raw_weights: pd.Series,
    prices: Mapping[str, pd.DataFrame],
    signal_date: date | pd.Timestamp | str,
    *,
    config: RiskConfig,
) -> RiskAdjustedTarget:
    assert_long_only_weights(raw_weights)
    if config.trend_filter.enabled:
        benchmark = prices[config.trend_filter.benchmark]
    else:
        benchmark = pd.DataFrame()
    trend = trend_exposure(benchmark, signal_date, config=config.trend_filter)
    realized_vol = basket_realized_vol(
        prices,
        list(raw_weights.index),
        signal_date,
        window_days=config.vol_target.window_days,
    )
    scale = volatility_scale(realized_vol, config=config.vol_target)
    requested_exposure = float(np.clip(trend * scale, 0.0, 1.0))
    weights = raw_weights.astype(float) * requested_exposure
    exposure = float(weights.sum())
    cash = max(0.0, 1.0 - exposure)
    assert_long_only_weights(weights, cash=cash)
    return RiskAdjustedTarget(
        signal_date=normalize_session(signal_date),
        weights=weights,
        cash=cash,
        exposure=exposure,
        trend_exposure=trend,
        realized_vol=realized_vol,
        vol_scale=scale,
    )
