from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from shm.config import SignalConfig
from shm.universe import indexed_prices, normalize_session, trailing_xnys_sessions


@dataclass(frozen=True)
class MomentumSelection:
    signal_date: pd.Timestamp
    eligible: tuple[str, ...]
    scores: pd.Series
    selected: tuple[str, ...]
    raw_weights: pd.Series
    selected_all_eligible: bool
    top_n_shortfall: bool


def momentum_scores(
    prices: Mapping[str, pd.DataFrame],
    tickers: Iterable[str],
    signal_date: date | pd.Timestamp | str,
    *,
    lookback_trading_days: int,
    skip_trading_days: int,
) -> pd.Series:
    """Calculate exact 12-1 scores using only closes at or before ``signal_date``."""
    if skip_trading_days >= lookback_trading_days:
        raise ValueError("skip_trading_days must be below lookback_trading_days")

    current_session = normalize_session(signal_date)
    sessions = trailing_xnys_sessions(current_session, lookback_trading_days + 1)
    start_session = sessions[0]
    end_session = sessions[-skip_trading_days - 1]
    values: dict[str, float] = {}
    for ticker in tickers:
        frame = indexed_prices(prices[ticker])
        start_close = frame["close"].get(start_session, np.nan)
        end_close = frame["close"].get(end_session, np.nan)
        if pd.isna(start_close) or pd.isna(end_close):
            continue
        values[ticker] = float(end_close / start_close - 1.0)
    return pd.Series(values, name="momentum", dtype=float)


def rank_momentum(scores: pd.Series, top_n: int) -> tuple[str, ...]:
    if top_n < 1:
        raise ValueError("top_n must be positive")
    finite = ((str(ticker), float(score)) for ticker, score in scores.items() if np.isfinite(score))
    ranked = sorted(finite, key=lambda item: (-item[1], item[0]))
    return tuple(ticker for ticker, _ in ranked[:top_n])


def equal_weights(tickers: Iterable[str]) -> pd.Series:
    selected = tuple(tickers)
    if not selected:
        return pd.Series(dtype=float, name="weight")
    return pd.Series(1.0 / len(selected), index=selected, name="weight", dtype=float)


def select_momentum(
    prices: Mapping[str, pd.DataFrame],
    eligible: Iterable[str],
    signal_date: date | pd.Timestamp | str,
    *,
    config: SignalConfig,
) -> MomentumSelection:
    eligible_tickers = tuple(eligible)
    scores = momentum_scores(
        prices,
        eligible_tickers,
        signal_date,
        lookback_trading_days=config.lookback_trading_days,
        skip_trading_days=config.skip_trading_days,
    )
    selected = rank_momentum(scores, config.top_n)
    return MomentumSelection(
        signal_date=normalize_session(signal_date),
        eligible=eligible_tickers,
        scores=scores,
        selected=selected,
        raw_weights=equal_weights(selected),
        selected_all_eligible=len(selected) == len(eligible_tickers),
        top_n_shortfall=len(eligible_tickers) < config.top_n,
    )
