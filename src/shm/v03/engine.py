"""One next-open executor shared by the v0.3 research and paper accounts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from shm.engine.backtest import BacktestResult
from shm.v03.strategy import (
    Decision, PortfolioState, PositionState, PreparedInputs, evaluate_close,
    mark_equity, positive, prepare_inputs,
)


@dataclass
class ExecutionResult:
    transactions: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    cost: float = 0.0
    equity: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def sync_price_basis(prepared: PreparedInputs, state: PortfolioState) -> list[dict]:
    """Rebase persisted units when a refreshed adjusted-history cache changes.

    Compare the *same historical observation*, never adjacent trading dates.
    Quantity changes inversely so this is a unit correction, not a cashflow.
    """
    events = []
    for ticker, position in state.positions.items():
        reference_date = state.mark_dates.get(ticker)
        if reference_date is None or ticker not in state.marks:
            continue
        row = prepared.date_index.get(pd.Timestamp(reference_date))
        column = prepared.ticker_index.get(ticker)
        if row is None or column is None:
            events.append({"action": "unverified_price_basis", "ticker": ticker, "reference_date": reference_date})
            continue
        old_price, new_price = state.marks[ticker], prepared.closes[row, column]
        if not positive(old_price) or not positive(new_price):
            continue
        factor = float(new_price / old_price)
        if abs(factor - 1) <= 1e-9:
            continue
        position.quantity /= factor
        position.average_cost *= factor
        position.peak_close *= factor
        if position.trailing_stop is not None:
            position.trailing_stop *= factor
        state.marks[ticker] = float(new_price)
        events.append({"action": "adjustment_rescale", "ticker": ticker, "factor": factor, "reference_date": reference_date})
    return events


def advance_open(
    prepared: PreparedInputs, session: object, state: PortfolioState, *,
    cost_bps: float, integer_shares: bool = False,
) -> ExecutionResult:
    """Execute only already-created intents, mutating ``state`` exactly once.

    Missing opens never become transactions. Sell intentions persist; missing
    buys expire. No target is reallocated after a skipped entry or risk exit.
    """
    if not np.isfinite(cost_bps) or cost_bps < 5:
        raise ValueError("cost_bps must be finite and at least 5")
    date = pd.Timestamp(session).tz_localize(None).normalize()
    asof = date.date().isoformat()
    if state.last_open == asof:
        return ExecutionResult(events=[{"action": "already_processed", "execution_date": asof}])
    if state.last_open is not None and asof < state.last_open:
        raise ValueError("cannot execute an open before the last processed open")
    row = prepared.row(date)
    result = ExecutionResult(events=sync_price_basis(prepared, state))
    pending = state.pending
    targets = None
    if pending is not None and pending.execution_date <= asof:
        for ticker, reason in pending.exits.items():
            if ticker in state.positions:
                previous = state.blocked_exits.get(ticker)
                if previous is None or (previous.get("target_weight") and reason != previous["reason"]):
                    state.blocked_exits[ticker] = {"signal_date": pending.signal_date, "reason": reason,
                                                  "event_type": "rebalance" if reason.startswith("rebalance_") else "risk_exit"}
        if pending.execution_date == asof:
            targets = pending.target_weights
        else:
            result.events.append({"action": "missed_execution", "signal_date": pending.signal_date,
                                  "execution_date": asof, "scheduled_date": pending.execution_date})
        state.pending = None
    elif pending is not None:
        pending = None
    names = sorted(set(state.positions) | set(targets or {}) | set(state.blocked_exits))
    quantity = np.array([state.positions[t].quantity if t in state.positions else 0.0 for t in names])
    raw_prices = np.array([prepared.opens[row, prepared.ticker_index[t]] if t in prepared.ticker_index else np.nan for t in names])
    valid = np.isfinite(raw_prices) & (raw_prices > 0)
    marks = np.array([state.marks.get(t, state.positions[t].average_cost if t in state.positions else 0.0) for t in names])
    valuation_prices = np.where(valid, raw_prices, marks)
    equity_open = float(state.cash + np.dot(quantity, valuation_prices))
    result.equity = equity_open
    unpriced_holding = bool(np.any((quantity > 0) & ~valid))
    missing_benchmark = not positive(prepared.opens[row, prepared.ticker_index["SPY"]])
    if unpriced_holding or missing_benchmark:
        result.events.append({"action": "incomplete_open_valuation", "execution_date": asof,
                              "tickers": sorted(set([t for i, t in enumerate(names) if quantity[i] > 0 and not valid[i]]
                                                    + (["SPY"] if missing_benchmark else [])))})
    desired = quantity.copy()
    fee_rate = cost_bps / 10_000
    if targets is not None:
        weights = np.array([max(0.0, float(targets.get(t, 0.0))) for t in names])
        if weights.sum() > 1 + 1e-9:
            raise ValueError("target exposure exceeds 100 percent")
        safe_prices = np.where(valid, raw_prices, 1.0)
        weights[~valid] = 0
        can_buy = bool(pending and pending.allow_new_risk and not unpriced_holding and not missing_benchmark
                       and not any(e["action"] == "unverified_price_basis" for e in result.events))
        for i, ticker in enumerate(names):
            if quantity[i] > 0 and not valid[i] and ticker not in state.blocked_exits:
                weight = float(targets.get(ticker, 0.0))
                state.blocked_exits[ticker] = {
                    "signal_date": pending.signal_date, "reason": "rebalance_reduce" if weight else "rebalance_removal",
                    "event_type": "rebalance", "target_weight": weight,
                }
        # Solve post-fee target equity; floors are part of the same calculation.
        def funded_quantities(net_equity: float) -> np.ndarray:
            values = net_equity * weights / safe_prices
            if integer_shares:
                values = np.floor(values + 1e-12)
            if not can_buy:
                values = np.minimum(values, quantity)
            values[~valid] = quantity[~valid]
            for i, ticker in enumerate(names):
                if ticker in state.blocked_exits and valid[i]:
                    limit = float(state.blocked_exits[ticker].get("target_weight", 0.0))
                    maximum = equity_open * limit / raw_prices[i]
                    if integer_shares:
                        maximum = float(np.floor(maximum))
                    values[i] = min(values[i], maximum)
            return values
        low, high = 0.0, equity_open
        for _ in range(40):
            middle = (low + high) / 2
            trial = funded_quantities(middle)
            fees = float(np.sum(np.abs(trial - quantity) * np.where(valid, raw_prices, 0.0)) * fee_rate)
            if middle + fees <= equity_open:
                low = middle
            else:
                high = middle
        desired = funded_quantities(low)
        for i, ticker in enumerate(names):
            if not valid[i] and targets.get(ticker, 0.0) > 0:
                result.events.append({"action": "unfilled_entry", "ticker": ticker,
                                      "signal_date": pending.signal_date, "execution_date": asof, "reason": "missing_open"})
    for i, ticker in enumerate(names):
        if ticker in state.blocked_exits and quantity[i] > 0:
            if valid[i]:
                limit = float(state.blocked_exits[ticker].get("target_weight", 0.0))
                maximum = equity_open * limit / raw_prices[i]
                if integer_shares:
                    maximum = float(np.floor(maximum))
                desired[i] = min(desired[i], maximum)
                if limit and desired[i] >= quantity[i] - 1e-9:
                    state.blocked_exits.pop(ticker)
            else:
                result.events.append({"action": "pending_exit", "ticker": ticker,
                                      "signal_date": state.blocked_exits[ticker]["signal_date"],
                                      "execution_date": asof, "reason": "missing_open"})
    delta = desired - quantity
    # Sales fund purchases; fees are charged on real executed notional only.
    for side in ("sell", "buy"):
        for i, ticker in enumerate(names):
            change = float(delta[i])
            if not valid[i] or (side == "sell" and change >= -1e-9) or (side == "buy" and change <= 1e-9):
                continue
            amount, price = abs(change), float(raw_prices[i])
            if side == "buy":
                affordable = state.cash / (price * (1 + fee_rate))
                if amount > affordable + 1e-8:
                    amount = max(0.0, float(np.floor(affordable) if integer_shares else affordable))
                if amount <= 1e-9:
                    continue
            fee = amount * price * fee_rate
            blocked = state.blocked_exits.get(ticker)
            reason = blocked["reason"] if blocked else "rebalance"
            signal_date = blocked["signal_date"] if blocked else pending.signal_date
            realized_pnl = 0.0
            if side == "sell":
                position = state.positions[ticker]
                realized_pnl = amount * (price - position.average_cost) - fee
                state.cash += amount * price - fee
                position.quantity -= amount
                if position.quantity <= 1e-9:
                    del state.positions[ticker]
                    state.marks.pop(ticker, None)
                    state.mark_dates.pop(ticker, None)
                    state.blocked_exits.pop(ticker, None)
                elif blocked and blocked.get("target_weight"):
                    state.blocked_exits.pop(ticker, None)
            else:
                state.cash -= amount * price + fee
                if ticker in state.positions:
                    position = state.positions[ticker]
                    position.average_cost = (position.quantity * position.average_cost + amount * price + fee) / (position.quantity + amount)
                    position.quantity += amount
                else:
                    signal_row = prepared.date_index.get(pd.Timestamp(pending.signal_date))
                    atr = (prepared.atr20[signal_row, prepared.ticker_index[ticker]] if signal_row is not None else
                           pending.diagnostics.get("atr_by_ticker", {}).get(ticker))
                    if atr is not None and not np.isfinite(atr):
                        atr = None
                    state.positions[ticker] = PositionState(amount, price * (1 + fee_rate), asof, price,
                                                          price - 3 * atr if atr is not None else None)
                    state.marks[ticker] = price
            result.cost += fee
            result.transactions.append({"signal_date": signal_date, "execution_date": asof,
                                        "ticker": ticker, "side": side, "quantity": amount, "price": price,
                                        "notional": amount * price, "cost": fee, "reason": reason,
                                        "event_type": blocked.get("event_type", "risk_exit") if blocked else "rebalance", "realized_pnl": realized_pnl})
    if state.cash < -1e-7:
        raise RuntimeError("execution produced negative cash")
    state.cash = max(0.0, state.cash)
    state.last_open = asof
    return result


@dataclass
class SimulationResult:
    backtest: BacktestResult
    decisions: list[dict]
    state_log: list[dict]
    warnings: list[dict]
    final_state: PortfolioState


def run_simulation(
    prices: Mapping[str, pd.DataFrame], universe: Iterable[str], candidate_id: str,
    sessions: Sequence, rebalance_dates: Sequence, *, cost_bps: float,
    initial_cash: float = 100_000.0, integer_shares: bool = False,
    prepared: PreparedInputs | None = None,
    membership_by_session: Mapping[object, Sequence[str]] | None = None,
) -> SimulationResult:
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    prepared = prepared or prepare_inputs(prices, universe, sessions, rebalance_dates,
                                          membership_by_session=membership_by_session)
    state = PortfolioState(cash=initial_cash)
    dates = prepared.sessions
    equity, cash, costs = np.zeros(len(dates)), np.zeros(len(dates)), np.zeros(len(dates))
    weights = np.zeros((len(dates), len(prepared.tickers)))
    transactions, events, decisions, state_log, warnings = [], [], [], [], []
    for i, date in enumerate(dates):
        execution = advance_open(prepared, date, state, cost_bps=cost_bps, integer_shares=integer_shares)
        decision = evaluate_close(prepared, date, candidate_id, state)
        equity[i], cash[i], costs[i] = decision.diagnostics["equity"], state.cash, execution.cost
        for ticker, position in state.positions.items():
            weights[i, prepared.ticker_index[ticker]] = position.quantity * state.marks[ticker] / equity[i]
        transactions.extend(execution.transactions)
        events.extend(execution.events)
        decisions.append(decision.to_dict())
        warnings.extend({"date": date.date().isoformat(), "warning": warning} for warning in decision.warnings)
        for event in execution.events:
            if event["action"] not in {"adjustment_rescale", "already_processed"}:
                warnings.append({"date": date.date().isoformat(), "warning": event["action"], **event})
        # Compact state audit; full serializable state is saved by paper callers.
        state_log.append({"date": date.date().isoformat(), "equity": equity[i], "cash": cash[i],
                          "drawdown": decision.diagnostics["drawdown"],
                          "positions": {t: {"quantity": p.quantity, "peak_close": p.peak_close, "trailing_stop": p.trailing_stop}
                                        for t, p in state.positions.items()}})
    tx_columns = ["signal_date", "execution_date", "ticker", "side", "quantity", "price", "notional", "cost", "reason", "event_type", "realized_pnl"]
    frame = pd.DataFrame(transactions, columns=tx_columns)
    for name in ("signal_date", "execution_date"):
        frame[name] = pd.to_datetime(frame[name])
    backtest = BacktestResult(
        equity=pd.Series(equity, index=dates, name="equity"),
        cash=pd.Series(cash, index=dates, name="cash"),
        cash_weight=pd.Series(cash / equity, index=dates, name="cash_weight"),
        weights=pd.DataFrame(weights, index=dates, columns=prepared.tickers),
        costs=pd.Series(costs, index=dates, name="cost"), transactions=frame,
        execution_fallbacks=pd.DataFrame(events),
    )
    return SimulationResult(backtest, decisions, state_log, warnings, state)
