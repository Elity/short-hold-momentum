"""Shared, stateful close decisions for SPEC-SHM-001 v0.3.

Inputs are adjusted OHLCV in one consistent price basis. Indicators are computed
once; evaluation only reads the row at the decision date and earlier rows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from shm.universe.core import indexed_prices

if TYPE_CHECKING:
    from shm.v03.corporate_actions import CorporateAction


@dataclass(frozen=True)
class Candidate:
    id: str
    daily_market_exit: bool = False
    stock_exit: str | None = None
    target_vol: float = 0.15
    modules: int = 0


CANDIDATES = {
    "C0": Candidate("C0"),
    "C1": Candidate("C1", True, modules=1),
    "C2": Candidate("C2", True, "sma50", modules=2),
    "C3": Candidate("C3", True, "atr20", modules=2),
    "C4": Candidate("C4", True, target_vol=0.20, modules=1),
}


def _date(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


@dataclass
class PositionState:
    quantity: float
    average_cost: float
    entry_date: str
    peak_close: float
    trailing_stop: float | None = None


@dataclass
class Decision:
    signal_date: str
    execution_date: str
    kind: str = "hold"
    target_weights: dict[str, float] | None = None
    exits: dict[str, str] = field(default_factory=dict)
    selected: list[str] = field(default_factory=list)
    eligible_count: int = 0
    diagnostics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def rebalance(self) -> bool:
        return self.kind == "rebalance"

    @property
    def asof(self) -> str:
        return self.signal_date

    @property
    def execute_session(self) -> str:
        return self.execution_date

    @property
    def allow_new_risk(self) -> bool:
        return bool(self.diagnostics.get("allow_new_risk", False))

    @property
    def exposure_cap(self) -> float:
        return float(self.diagnostics.get("exposure_cap", 0.0))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> Decision:
        return cls(**value)


@dataclass
class PortfolioState:
    cash: float = 100_000.0
    positions: dict[str, PositionState] = field(default_factory=dict)
    equity_high_water: float = 0.0
    marks: dict[str, float] = field(default_factory=dict)
    mark_dates: dict[str, str] = field(default_factory=dict)
    pending: Decision | None = None
    blocked_exits: dict[str, dict] = field(default_factory=dict)
    last_open: str | None = None
    last_close: str | None = None
    latest_decision: dict | None = None
    drawdown_alert_active: bool = False
    processed_corporate_actions: list[str] = field(default_factory=list)
    corporate_receivables: dict[str, dict] = field(default_factory=dict)
    unverified_price_basis: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.equity_high_water:
            self.equity_high_water = self.cash

    @property
    def shares(self) -> dict[str, float]:
        return {ticker: position.quantity for ticker, position in self.positions.items()}

    @property
    def receivables_value(self) -> float:
        return sum(float(item["amount"]) for item in self.corporate_receivables.values())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> PortfolioState:
        value = dict(value)
        value["positions"] = {
            ticker: PositionState(**position) for ticker, position in value.get("positions", {}).items()
        }
        if value.get("pending") is not None:
            value["pending"] = Decision.from_dict(value["pending"])
        return cls(**value)


@dataclass
class PreparedInputs:
    dates: pd.DatetimeIndex
    sessions: pd.DatetimeIndex
    tickers: tuple[str, ...]
    universe: tuple[str, ...]
    rebalance_dates: frozenset[pd.Timestamp]
    opens: np.ndarray
    closes: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    volumes: np.ndarray
    sma50: np.ndarray
    sma200: np.ndarray
    atr20: np.ndarray
    returns: np.ndarray
    scores: np.ndarray
    eligible: np.ndarray
    membership_by_session: dict[pd.Timestamp, frozenset[str]] | None = None
    ticker_index: dict[str, int] = field(init=False)
    date_index: dict[pd.Timestamp, int] = field(init=False)
    next_dates: dict[pd.Timestamp, str] = field(default_factory=dict)
    eligibility_data_known: np.ndarray | None = None
    require_point_in_time_eligibility: bool = False
    as_traded_closes: np.ndarray | None = None
    corporate_actions: tuple[CorporateAction, ...] = ()

    def __post_init__(self) -> None:
        self.ticker_index = {ticker: i for i, ticker in enumerate(self.tickers)}
        self.date_index = {date: i for i, date in enumerate(self.dates)}

    def row(self, session: object) -> int:
        return self.date_index[pd.Timestamp(session).tz_localize(None).normalize()]


def prepare_inputs(
    prices: Mapping[str, pd.DataFrame],
    universe: Iterable[str],
    sessions: Sequence,
    rebalance_dates: Sequence,
    *,
    membership_by_session: Mapping[object, Sequence[str]] | None = None,
    require_point_in_time_eligibility: bool = False,
    corporate_actions: Sequence[CorporateAction] = (),
) -> PreparedInputs:
    """Precompute finite trailing windows, including pre-evaluation warmup.

    Absent owner tickers remain in the pool with unavailable eligibility. Missing
    dates are reindexed on XNYS, never silently compressed into shorter windows.
    Absolute price/liquidity filters prefer dated nominal observations. Strict
    callers require them; legacy callers may fall back to adjusted cache fields.
    """
    sessions = pd.DatetimeIndex(pd.to_datetime(sessions)).tz_localize(None).normalize()
    if sessions.empty or not sessions.is_monotonic_increasing or sessions.has_duplicates:
        raise ValueError("sessions must be nonempty, ascending and unique")
    universe = tuple(sorted(set(universe)))
    corporate_actions = tuple(corporate_actions)
    if len({action.action_id for action in corporate_actions}) != len(corporate_actions):
        raise ValueError("corporate action identifiers must be unique")
    # The caller also supplies held securities that have left the selection
    # universe. Keep their quotes for valuation/exits; ranking still uses only
    # ``universe`` below, so retaining quotes cannot make a removed name a buy.
    action_tickers = {ticker for action in corporate_actions
                      for ticker in (action.source_ticker, action.target_ticker) if ticker}
    tickers = tuple(sorted(set(universe) | set(prices) | {"SPY"} | action_tickers))
    frames = {t: indexed_prices(f) for t, f in prices.items() if t in tickers and not f.empty}
    first = min([sessions[0], *[f.index.min() for f in frames.values()]])
    last = sessions[-1]
    calendar = xcals.get_calendar("XNYS", start=first - pd.Timedelta(days=7), end=last + pd.Timedelta(days=14))
    dates = calendar.sessions_in_range(first, last).tz_localize(None)
    if not sessions.isin(dates).all():
        raise ValueError("sessions must contain only XNYS trading dates")
    panels = {}
    for name in ("open", "close", "high", "low", "volume", "as_traded_close", "dollar_volume"):
        panels[name] = pd.DataFrame(
            {t: frames[t][name] if t in frames and name in frames[t] else pd.Series(dtype=float) for t in tickers},
            index=dates,
            dtype=float,
        )
    close = panels["close"]
    returns = close.pct_change(fill_method=None)
    previous = close.shift(1)
    tr = np.maximum.reduce([
        (panels["high"] - panels["low"]).to_numpy(),
        (panels["high"] - previous).abs().to_numpy(),
        (panels["low"] - previous).abs().to_numpy(),
    ])
    atr = pd.DataFrame(tr, index=dates, columns=tickers).rolling(20, min_periods=20).mean()
    valid = close.gt(0) & np.isfinite(close)
    for name in ("open", "high", "low"):
        valid &= panels[name].gt(0) & np.isfinite(panels[name])
    valid &= panels["volume"].ge(0) & np.isfinite(panels["volume"])
    valid &= panels["high"].ge(panels["low"])
    complete = valid.rolling(260, min_periods=260).sum().eq(260)
    extreme = returns.abs().gt(0.5).rolling(260, min_periods=260).sum().le(3)
    zero_volume = panels["volume"].eq(0).rolling(260, min_periods=260).mean().le(0.05)
    nominal_close = panels["as_traded_close"].where(
        panels["as_traded_close"].gt(0) & np.isfinite(panels["as_traded_close"])
    )
    dollar_volume = panels["dollar_volume"].where(
        panels["dollar_volume"].ge(0) & np.isfinite(panels["dollar_volume"])
    )
    eligibility_known = nominal_close.notna() & dollar_volume.notna().rolling(60, min_periods=60).sum().eq(60)
    if not require_point_in_time_eligibility:
        nominal_close = nominal_close.fillna(close)
        dollar_volume = dollar_volume.fillna(close * panels["volume"])
    adv = dollar_volume.rolling(60, min_periods=60).mean()
    eligible = complete & extreme & zero_volume & nominal_close.ge(5) & adv.ge(10_000_000)
    all_dates = calendar.sessions_in_range(first, last + pd.Timedelta(days=10)).tz_localize(None)
    next_dates = {d: _date(all_dates[i + 1]) for i, d in enumerate(all_dates[:-1]) if d <= last}
    membership = None if membership_by_session is None else {
        pd.Timestamp(d).tz_localize(None).normalize(): frozenset(names)
        for d, names in membership_by_session.items()
    }
    return PreparedInputs(
        dates=dates, sessions=sessions, tickers=tickers, universe=universe,
        rebalance_dates=frozenset(pd.DatetimeIndex(rebalance_dates).tz_localize(None).normalize()),
        opens=panels["open"].to_numpy(), closes=close.to_numpy(),
        highs=panels["high"].to_numpy(), lows=panels["low"].to_numpy(),
        volumes=panels["volume"].to_numpy(),
        sma50=close.rolling(50, min_periods=50).mean().to_numpy(),
        sma200=close.rolling(200, min_periods=200).mean().to_numpy(),
        atr20=atr.to_numpy(), returns=returns.to_numpy(),
        scores=(close.shift(21) / close.shift(126) - 1).to_numpy(),
        eligible=eligible.to_numpy(), membership_by_session=membership, next_dates=next_dates,
        eligibility_data_known=eligibility_known.to_numpy(),
        require_point_in_time_eligibility=require_point_in_time_eligibility,
        as_traded_closes=panels["as_traded_close"].to_numpy(),
        corporate_actions=corporate_actions,
    )


def positive(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0)


def mark_equity(prepared: PreparedInputs, session: object, state: PortfolioState) -> tuple[float, list[str]]:
    row = prepared.row(session)
    missing = []
    equity = state.cash + state.receivables_value
    terminated = {action.source_ticker for action in prepared.corporate_actions
                  if action.effective_session <= _date(session)
                  and action.source_ticker in state.positions
                  and state.positions[action.source_ticker].entry_date <= action.last_trading_session}
    for ticker, position in state.positions.items():
        column = prepared.ticker_index.get(ticker)
        price = (prepared.closes[row, column]
                 if column is not None and ticker not in terminated and ticker not in state.unverified_price_basis
                 else np.nan)
        if positive(price):
            state.marks[ticker] = float(price)
            state.mark_dates[ticker] = _date(session)
        else:
            missing.append(ticker)
        equity += position.quantity * state.marks.get(ticker, position.average_cost)
    return float(equity), missing


def evaluate_close(
    prepared: PreparedInputs, session: object, candidate_id: str, state: PortfolioState,
) -> Decision:
    """Mutate marks/risk state and queue an intent, never execute at this close."""
    candidate = CANDIDATES[candidate_id]
    date = pd.Timestamp(session).tz_localize(None).normalize()
    asof = _date(date)
    if state.last_close == asof and state.latest_decision is not None:
        return Decision.from_dict(state.latest_decision)
    if state.last_close is not None and asof < state.last_close:
        raise ValueError("cannot evaluate a close before the last processed close")
    row = prepared.row(date)
    spy = prepared.ticker_index["SPY"]
    spy_close, spy_sma = prepared.closes[row, spy], prepared.sma200[row, spy]
    market_known = positive(spy_close) and positive(spy_sma)
    risk_off = market_known and spy_close <= spy_sma
    equity, missing = mark_equity(prepared, date, state)
    warnings = [f"MISSING_HOLDING_CLOSE:{ticker}" for ticker in missing]
    unresolved_actions = [action.action_id for action in prepared.corporate_actions
                          if action.effective_session <= asof
                          and action.action_id not in state.processed_corporate_actions
                          and action.source_ticker in state.positions
                          and state.positions[action.source_ticker].entry_date <= action.last_trading_session]
    unresolved_settlements = [key for key, item in state.corporate_receivables.items()
                              if item.get("cash_settlement_session") is None]
    warnings.extend(f"MISSING_CORPORATE_ACTION:{key}" for key in unresolved_actions)
    warnings.extend(f"MISSING_CORPORATE_SETTLEMENT:{key}" for key in unresolved_settlements)
    if not market_known:
        warnings.append("MISSING_SPY_HISTORY")
    exits = {t: str(v["reason"]) for t, v in state.blocked_exits.items()
             if t in state.positions and not v.get("target_weight", 0.0) and "quantity" not in v}
    if candidate.daily_market_exit and risk_off:
        exits.update({t: "market_trend_exit" for t in state.positions})
    for ticker, position in state.positions.items():
        column = prepared.ticker_index.get(ticker)
        if column is None or ticker in missing:
            continue
        close = float(prepared.closes[row, column])
        position.peak_close = max(position.peak_close, close)
        if candidate.daily_market_exit and risk_off:
            exits[ticker] = "market_trend_exit"
        if candidate.stock_exit == "sma50":
            sma = prepared.sma50[row, column]
            if not positive(sma):
                warnings.append(f"MISSING_SMA50:{ticker}")
            elif close <= sma:
                exits.setdefault(ticker, "sma50_exit")
        elif candidate.stock_exit == "atr20":
            atr = prepared.atr20[row, column]
            if not np.isfinite(atr) or atr < 0:
                warnings.append(f"MISSING_ATR20:{ticker}")
            else:
                line = position.peak_close - 3 * float(atr)
                position.trailing_stop = max(position.trailing_stop if position.trailing_stop is not None else line, line)
                if close < position.trailing_stop:
                    exits.setdefault(ticker, "atr_trailing_exit")
    if not missing:
        state.equity_high_water = max(state.equity_high_water, equity)
    drawdown = equity / state.equity_high_water - 1 if state.equity_high_water > 0 else 0.0
    if drawdown <= -0.10 and not state.drawdown_alert_active:
        warnings.append("DRAWDOWN_10_PERCENT_REVIEW")
    state.drawdown_alert_active = drawdown <= -0.10
    rebalance = date in prepared.rebalance_dates
    pool = set(prepared.universe)
    if prepared.membership_by_session is not None:
        pool &= prepared.membership_by_session.get(date, frozenset())
    eligible = [t for t in sorted(pool) if prepared.eligible[row, prepared.ticker_index[t]]
                and np.isfinite(prepared.scores[row, prepared.ticker_index[t]])]
    eligibility_known_count = sum(bool(prepared.eligibility_data_known[row, prepared.ticker_index[t]])
                                  for t in pool) if prepared.eligibility_data_known is not None else 0
    targets = None
    selected: list[str] = []
    exposure = 0.0
    realized_vol = 0.0
    allow_new_risk = (rebalance and len(eligible) >= 30 and market_known and not risk_off and not missing
                      and not unresolved_actions and not unresolved_settlements)
    if rebalance and len(eligible) < 30:
        warnings.append("INSUFFICIENT_ELIGIBLE_UNIVERSE")
    if rebalance and market_known and risk_off:
        # C0's original market gate still acts at the regular rebalance.
        exits.update({t: "market_trend_exit" for t in state.positions})
        targets = {}
    elif rebalance and len(eligible) >= 30 and market_known and not missing:
        selected = sorted(eligible, key=lambda t: (-prepared.scores[row, prepared.ticker_index[t]], t))[:15]
        columns = [prepared.ticker_index[t] for t in selected]
        basket = prepared.returns[row - 19:row + 1, columns].mean(axis=1)
        realized_vol = float(np.std(basket, ddof=1) * np.sqrt(252))
        exposure = min(1.0, candidate.target_vol / realized_vol) if realized_vol > 0 else 1.0
        targets = {t: exposure / 15 for t in selected}
        for ticker in selected:
            column = prepared.ticker_index[ticker]
            if candidate.stock_exit == "sma50" and prepared.closes[row, column] <= prepared.sma50[row, column]:
                targets[ticker] = 0.0
                if ticker in state.positions:
                    exits.setdefault(ticker, "sma50_exit")
        for ticker in exits:
            targets[ticker] = 0.0
    if any(w.startswith("MISSING_") for w in warnings):
        allow_new_risk = False
        # Keep valid risk exits, but do not invent a target on incomplete inputs.
        targets = None
    diagnostics = {
        "rebalance": rebalance, "risk_off": bool(risk_off), "market_known": bool(market_known),
        "allow_new_risk": bool(allow_new_risk), "exposure_cap": float(sum(targets.values())) if targets is not None else 0.0,
        "raw_exposure": exposure, "realized_vol": realized_vol,
        "require_point_in_time_eligibility": prepared.require_point_in_time_eligibility,
        "eligibility_pool_count": len(pool), "eligibility_data_known_count": eligibility_known_count,
        "eligibility_data_unknown_count": len(pool) - eligibility_known_count,
        "equity": equity, "drawdown": float(drawdown), "valuation_complete": not missing,
        "corporate_receivables": state.receivables_value,
        "unresolved_corporate_actions": unresolved_actions,
        "unresolved_corporate_settlements": unresolved_settlements,
        "atr_by_ticker": {t: float(prepared.atr20[row, prepared.ticker_index[t]]) for t in selected
                          if np.isfinite(prepared.atr20[row, prepared.ticker_index[t]]) and prepared.atr20[row, prepared.ticker_index[t]] >= 0},
        "candidate_id": candidate_id,
    }
    kind = "rebalance" if rebalance else "risk_exit" if exits else "hold"
    decision = Decision(asof, prepared.next_dates[date], kind, targets, exits, selected, len(eligible), diagnostics, warnings)
    state.pending = decision if targets is not None or exits else None
    state.last_close = asof
    state.latest_decision = decision.to_dict()
    return decision
