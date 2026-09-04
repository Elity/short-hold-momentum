from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

import pandas as pd

from shm.config import EligibilityConfig, UniverseConfig, load_universe_config
from shm.universe.calendar import normalize_session, trailing_xnys_sessions


@dataclass(frozen=True)
class FrozenUniverse:
    frozen_on: date
    rule_text: str
    tickers: tuple[str, ...]
    exclusions: frozenset[str]

    @property
    def active_tickers(self) -> tuple[str, ...]:
        return tuple(ticker for ticker in self.tickers if ticker not in self.exclusions)

    @classmethod
    def from_config(cls, config: UniverseConfig) -> "FrozenUniverse":
        return cls(
            frozen_on=config.frozen_on,
            rule_text=config.rule_text,
            tickers=tuple(config.tickers),
            exclusions=frozenset(config.exclusions),
        )


@dataclass(frozen=True)
class EligibilityResult:
    signal_date: pd.Timestamp
    eligible: tuple[str, ...]
    rejected: Mapping[str, str]
    observations: pd.DataFrame
    below_minimum: bool


def load_frozen_universe(config_dir: Path | str) -> FrozenUniverse:
    return FrozenUniverse.from_config(load_universe_config(config_dir))


def indexed_prices(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a date-indexed view of a price-cache frame."""
    if "date" in frame.columns:
        result = frame.copy().set_index("date")
    else:
        result = frame.copy()
    result.index = pd.DatetimeIndex(pd.to_datetime(result.index)).tz_localize(None).normalize()
    if result.index.has_duplicates:
        raise ValueError("price data contains duplicate dates")
    return result.sort_index()


def filter_eligible_tickers(
    prices: Mapping[str, pd.DataFrame],
    universe: FrozenUniverse,
    signal_date: date | pd.Timestamp | str,
    *,
    config: EligibilityConfig,
    lookback_trading_days: int,
    quarantined: frozenset[str] | set[str] = frozenset(),
) -> EligibilityResult:
    """Apply the frozen-universe and step-1 eligibility rules at ``signal_date``."""
    current_session = normalize_session(signal_date)
    history_sessions = trailing_xnys_sessions(current_session, lookback_trading_days + 1)
    adv_sessions = trailing_xnys_sessions(current_session, config.adv_window_days)
    rejected: dict[str, str] = {}
    observations: dict[str, dict[str, float]] = {}
    eligible: list[str] = []

    for ticker in universe.tickers:
        if ticker in universe.exclusions:
            rejected[ticker] = "excluded"
            continue
        if ticker in quarantined:
            rejected[ticker] = "quarantined"
            continue
        frame = prices.get(ticker)
        if frame is None:
            rejected[ticker] = "missing_data"
            continue

        history = indexed_prices(frame).reindex(history_sessions)
        if not {"close", "volume"}.issubset(history.columns):
            rejected[ticker] = "missing_columns"
            continue
        if config.require_full_history and history[["close", "volume"]].isna().any().any():
            rejected[ticker] = "incomplete_history"
            continue

        close = history.at[current_session, "close"]
        adv_frame = history.reindex(adv_sessions)[["close", "volume"]]
        if pd.isna(close) or adv_frame.isna().any().any():
            rejected[ticker] = "incomplete_adv"
            continue
        adv = float((adv_frame["close"] * adv_frame["volume"]).mean())
        observations[ticker] = {"close": float(close), "adv_usd": adv}
        if float(close) < config.min_price_usd:
            rejected[ticker] = "price_below_minimum"
            continue
        if adv < config.min_adv_usd:
            rejected[ticker] = "adv_below_minimum"
            continue
        eligible.append(ticker)

    observation_frame = pd.DataFrame.from_dict(observations, orient="index")
    observation_frame.index.name = "ticker"
    return EligibilityResult(
        signal_date=current_session,
        eligible=tuple(eligible),
        rejected=rejected,
        observations=observation_frame,
        below_minimum=len(eligible) < config.min_eligible_count,
    )
