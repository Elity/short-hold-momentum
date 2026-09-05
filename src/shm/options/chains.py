"""Delayed yfinance option-chain access and contract selection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from math import erf, exp, isfinite, log, sqrt
from typing import Literal, Protocol

import pandas as pd


OptionKind = Literal["call", "put"]


@dataclass(frozen=True)
class OptionChainSnapshot:
    ticker: str
    expiration: date
    calls: pd.DataFrame
    puts: pd.DataFrame


@dataclass(frozen=True)
class SelectedOption:
    underlying: str
    contract_symbol: str
    expiration: date
    strike: float
    bid: float
    ask: float
    delta: float | None
    delta_source: Literal["chain", "black_scholes", "otm_fallback"]


class OptionChainSource(Protocol):
    def load(
        self, ticker: str, *, not_before: date
    ) -> OptionChainSnapshot | None: ...


def _as_date(value: date | str | pd.Timestamp) -> date:
    return pd.Timestamp(value).date()


def _is_standard_expiration(value: date) -> bool:
    return value.weekday() == 4 and 15 <= value.day <= 21


def first_standard_expiration(
    expirations: Iterable[date | str | pd.Timestamp],
    *,
    not_before: date | str | pd.Timestamp,
) -> date | None:
    threshold = _as_date(not_before)
    available = sorted(
        value
        for value in (_as_date(expiration) for expiration in expirations)
        if value >= threshold and _is_standard_expiration(value)
    )
    return available[0] if available else None


class YFinanceOptionChainSource:
    """Load the first standard expiration on/after the next rebalance date."""

    def __init__(self, ticker_factory: Callable[[str], object] | None = None) -> None:
        if ticker_factory is None:
            import yfinance as yf

            ticker_factory = yf.Ticker
        self._ticker_factory = ticker_factory

    def load(
        self, ticker: str, *, not_before: date
    ) -> OptionChainSnapshot | None:
        symbol = ticker.upper().replace(".", "-")
        remote = self._ticker_factory(symbol)
        expiration = first_standard_expiration(
            remote.options,
            not_before=not_before,
        )
        if expiration is None:
            return None
        chain = remote.option_chain(expiration.isoformat())
        calls = chain.calls if chain.calls is not None else pd.DataFrame()
        puts = chain.puts if chain.puts is not None else pd.DataFrame()
        return OptionChainSnapshot(
            ticker=ticker.upper(),
            expiration=expiration,
            calls=calls.copy(),
            puts=puts.copy(),
        )


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def black_scholes_delta(
    *,
    option_kind: OptionKind,
    spot: float,
    strike: float,
    volatility: float,
    expiration: date | str | pd.Timestamp,
    as_of: date | str | pd.Timestamp,
    risk_free_rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> float:
    """Estimate European delta using calendar time and explicit rates."""

    spot = float(spot)
    strike = float(strike)
    volatility = float(volatility)
    days = (_as_date(expiration) - _as_date(as_of)).days
    if spot <= 0 or strike <= 0 or volatility <= 0 or days <= 0:
        raise ValueError("Black-Scholes inputs must be positive and unexpired")
    years = days / 365.0
    d1 = (
        log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * years
    ) / (volatility * sqrt(years))
    discounted = exp(-dividend_yield * years)
    call_delta = discounted * _normal_cdf(d1)
    if option_kind == "call":
        return call_delta
    if option_kind == "put":
        return call_delta - discounted
    raise ValueError(f"unsupported option kind: {option_kind}")


def _number(row: pd.Series, column: str) -> float | None:
    value = pd.to_numeric(row.get(column), errors="coerce")
    if pd.isna(value) or not isfinite(float(value)):
        return None
    return float(value)


def _contract_delta(
    row: pd.Series,
    *,
    option_kind: OptionKind,
    snapshot: OptionChainSnapshot,
    spot: float,
    as_of: date,
    risk_free_rate: float,
    dividend_yield: float,
) -> tuple[float | None, Literal["chain", "black_scholes"] | None]:
    chain_delta = _number(row, "delta")
    if chain_delta is not None:
        return chain_delta, "chain"
    volatility = _number(row, "impliedVolatility")
    strike = _number(row, "strike")
    if volatility is None or volatility <= 0 or strike is None:
        return None, None
    return (
        black_scholes_delta(
            option_kind=option_kind,
            spot=spot,
            strike=strike,
            volatility=volatility,
            expiration=snapshot.expiration,
            as_of=as_of,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        ),
        "black_scholes",
    )


def _selected(
    snapshot: OptionChainSnapshot,
    row: pd.Series,
    *,
    delta: float | None,
    delta_source: Literal["chain", "black_scholes", "otm_fallback"],
) -> SelectedOption:
    return SelectedOption(
        underlying=snapshot.ticker,
        contract_symbol=str(row["contractSymbol"]),
        expiration=snapshot.expiration,
        strike=float(row["strike"]),
        bid=float(row["bid"]),
        ask=float(row["ask"]),
        delta=delta,
        delta_source=delta_source,
    )


def select_covered_call(
    snapshot: OptionChainSnapshot,
    *,
    spot: float,
    as_of: date,
    max_delta: float = 0.30,
    minimum_otm: float = 0.05,
    minimum_bid: float = 0.10,
    maximum_relative_spread: float = 0.20,
    risk_free_rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> SelectedOption | None:
    """Select the lowest qualifying call strike from one standard expiry."""

    choices: list[SelectedOption] = []
    for _, row in snapshot.calls.iterrows():
        strike = _number(row, "strike")
        bid = _number(row, "bid")
        ask = _number(row, "ask")
        if strike is None or bid is None or ask is None or bid < minimum_bid:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or ask < bid or (ask - bid) / mid > maximum_relative_spread:
            continue
        delta, source = _contract_delta(
            row,
            option_kind="call",
            snapshot=snapshot,
            spot=spot,
            as_of=as_of,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        if delta is not None:
            if not 0 <= delta <= max_delta:
                continue
            choices.append(_selected(snapshot, row, delta=delta, delta_source=source))
        elif strike >= spot * (1.0 + minimum_otm):
            choices.append(
                _selected(snapshot, row, delta=None, delta_source="otm_fallback")
            )
    return min(choices, key=lambda option: option.strike) if choices else None


def select_cash_secured_put(
    snapshot: OptionChainSnapshot,
    *,
    spot: float,
    as_of: date,
    available_cash: float,
    max_abs_delta: float = 0.25,
    minimum_bid: float = 0.10,
    maximum_relative_spread: float = 0.20,
    risk_free_rate: float = 0.0,
    dividend_yield: float = 0.0,
) -> SelectedOption | None:
    """Select the highest liquid qualifying put affordable with secured cash."""

    choices: list[SelectedOption] = []
    for _, row in snapshot.puts.iterrows():
        strike = _number(row, "strike")
        bid = _number(row, "bid")
        ask = _number(row, "ask")
        if strike is None or bid is None or ask is None or bid < minimum_bid:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or ask < bid or (ask - bid) / mid > maximum_relative_spread:
            continue
        if strike * 100 > available_cash:
            continue
        delta, source = _contract_delta(
            row,
            option_kind="put",
            snapshot=snapshot,
            spot=spot,
            as_of=as_of,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        if delta is None or abs(delta) > max_abs_delta:
            continue
        choices.append(_selected(snapshot, row, delta=delta, delta_source=source))
    return max(choices, key=lambda option: option.strike) if choices else None
