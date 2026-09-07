"""One next-open executor shared by the v0.3 research and paper accounts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from shm.engine.backtest import BacktestResult
from shm.v03.corporate_actions import AdjustmentBasis, convert_position
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


def sync_price_basis(prepared: PreparedInputs, state: PortfolioState, *, as_of: object | None = None) -> list[dict]:
    """Rebase persisted units when a refreshed adjusted-history cache changes.

    Compare the *same historical observation*, never adjacent trading dates.
    Quantity changes inversely so this is a unit correction, not a cashflow.
    """
    events = []
    asof = pd.Timestamp(as_of if as_of is not None else prepared.sessions[-1]).date().isoformat()
    previously_unverified = set(state.unverified_price_basis)
    state.unverified_price_basis = []
    participants = {ticker for action in prepared.corporate_actions
                    if action.source_ticker in state.positions
                    and action.effective_session <= asof
                    and state.positions[action.source_ticker].entry_date <= action.last_trading_session
                    and action.action_id not in state.processed_corporate_actions
                    for ticker in (action.source_ticker, action.target_ticker) if ticker}

    def unverified(ticker: str, reference_date: str | None) -> None:
        state.unverified_price_basis.append(ticker)
        events.append({"action": "unverified_price_basis", "ticker": ticker, "reference_date": reference_date})

    for ticker, position in state.positions.items():
        reference_date = state.mark_dates.get(ticker)
        if reference_date is None or ticker not in state.marks:
            if reference_date is not None or ticker in participants or ticker in previously_unverified:
                unverified(ticker, reference_date)
            continue
        row = prepared.date_index.get(pd.Timestamp(reference_date))
        column = prepared.ticker_index.get(ticker)
        if row is None or column is None:
            unverified(ticker, reference_date)
            continue
        old_price, new_price = state.marks[ticker], prepared.closes[row, column]
        if not positive(old_price) or not positive(new_price):
            unverified(ticker, reference_date)
            continue
        factor = float(new_price / old_price)
        if abs(factor - 1) <= 1e-9:
            continue
        position.quantity /= factor
        if ticker in state.blocked_exits and "quantity" in state.blocked_exits[ticker]:
            state.blocked_exits[ticker]["quantity"] /= factor
        position.average_cost *= factor
        position.peak_close *= factor
        if position.trailing_stop is not None:
            position.trailing_stop *= factor
        state.marks[ticker] = float(new_price)
        events.append({"action": "adjustment_rescale", "ticker": ticker, "factor": factor, "reference_date": reference_date})
    return events


def _settle_corporate_receivables(state: PortfolioState, asof: str, result: ExecutionResult) -> None:
    for action_id, item in list(state.corporate_receivables.items()):
        settlement = item.get("cash_settlement_session")
        if settlement is not None and settlement <= asof:
            state.cash += float(item["amount"])
            del state.corporate_receivables[action_id]
            result.events.append({"action": "corporate_cash_settlement", "event_type": "corporate_action",
                                  "action_id": action_id, "execution_date": asof,
                                  "cash_settlement_session": settlement, "amount": item["amount"],
                                  "evidence": item["evidence"], "model_cost": 0.0, "market_fill": False})


def _apply_corporate_actions(prepared: PreparedInputs, date: pd.Timestamp,
                             state: PortfolioState, result: ExecutionResult, integer_shares: bool) -> None:
    asof = date.date().isoformat()
    for action in prepared.corporate_actions:
        receivable = state.corporate_receivables.get(action.action_id)
        if receivable is not None and receivable.get("cash_settlement_session") is None and action.cash_settlement_session:
            receivable["cash_settlement_session"] = action.cash_settlement_session
            receivable["evidence"] = action.evidence
    _settle_corporate_receivables(state, asof, result)
    for action in sorted(prepared.corporate_actions, key=lambda item: (item.effective_session, item.action_id)):
        if action.effective_session > asof or action.action_id in state.processed_corporate_actions:
            continue
        source = action.source_ticker
        if source not in state.positions:
            state.processed_corporate_actions.append(action.action_id)
            continue
        if state.positions[source].entry_date > action.last_trading_session:
            # A subsequently reused ticker is not the old issuer's entitlement.
            state.processed_corporate_actions.append(action.action_id)
            continue
        source_row = prepared.date_index.get(pd.Timestamp(action.last_trading_session))
        source_col = prepared.ticker_index[source]
        target_row = prepared.date_index.get(pd.Timestamp(action.effective_session))
        target_col = prepared.ticker_index.get(action.target_ticker)
        try:
            if any(ticker in state.unverified_price_basis for ticker in (source, action.target_ticker) if ticker):
                raise ValueError("persisted source or existing successor price units could not be verified")
            if source_row is None or prepared.as_traded_closes is None:
                raise ValueError("missing final source adjustment basis")
            continuing = (prepared.dates > pd.Timestamp(action.last_trading_session)) & (prepared.dates <= date)
            if any(np.any(np.isfinite(panel[continuing, source_col]) & (panel[continuing, source_col] > 0))
                   for panel in (prepared.opens, prepared.closes)):
                raise ValueError("source quotes continue after the declared final session; conversion could double count")
            old_adjusted = prepared.closes[source_row, source_col]
            old_nominal = prepared.as_traded_closes[source_row, source_col]
            if not positive(old_adjusted) or not positive(old_nominal):
                raise ValueError("missing final source adjustment basis")
            source_basis = AdjustmentBasis(float(old_adjusted / old_nominal), action.last_trading_session,
                                           f"prepared adjusted/as_traded close; {action.evidence}")
            target_basis, target_mark = None, None
            if action.target_ticker is not None:
                if target_row is None or target_col is None:
                    raise ValueError("missing successor effective-session quotes")
                new_adjusted = prepared.closes[target_row, target_col]
                new_nominal = prepared.as_traded_closes[target_row, target_col]
                target_mark = prepared.opens[target_row, target_col]
                if not all(positive(value) for value in (new_adjusted, new_nominal, target_mark)):
                    raise ValueError("missing successor effective-session adjustment basis or observed open")
                if not positive(prepared.opens[prepared.row(date), target_col]):
                    raise ValueError("missing successor current observed open")
                # This ratio is a unit conversion fixed by corporate actions,
                # including a split on the effective day; it is not a signal.
                target_basis = AdjustmentBasis(float(new_adjusted / new_nominal), action.effective_session,
                                               f"prepared adjusted/as_traded close; {action.evidence}")
            conversion = convert_position(state.positions[source], action, source_basis=source_basis,
                                          target_basis=target_basis, target_mark=target_mark,
                                          integer_actual_shares=integer_shares)
        except ValueError as error:
            result.events.append({"action": "unresolved_corporate_action", "event_type": "corporate_action",
                                  "action_id": action.action_id, "ticker": source,
                                  "effective_session": action.effective_session, "execution_date": asof,
                                  "reason": str(error)})
            continue

        old_position = state.positions.pop(source)
        state.marks.pop(source, None)
        state.mark_dates.pop(source, None)
        source_exit = state.blocked_exits.pop(source, None)
        pending = state.pending
        if pending is not None:
            if source in pending.exits:
                source_exit = {"reason": pending.exits.pop(source), "signal_date": pending.signal_date}
                source_exit["event_type"] = "rebalance" if source_exit["reason"].startswith("rebalance_") else "risk_exit"
                source_exit["not_before"] = pending.execution_date
            if pending.target_weights is not None:
                pending.target_weights.pop(source, None)
        received, target = conversion.target_position, action.target_ticker
        prior_target = asdict(state.positions[target]) if target in state.positions else None
        if received is not None:
            if target in state.positions:
                existing = state.positions[target]
                existing.average_cost = (existing.quantity * existing.average_cost + conversion.target_cost_basis) / (
                    existing.quantity + received.quantity)
                existing.quantity += received.quantity
                # As with an ordinary add, the established target lot's trend
                # state survives. Source-lot bounds remain in the action audit.
            else:
                state.positions[target] = received
                state.marks[target] = float(target_mark)
            if source_exit is not None:
                exit_quantity = received.quantity
                if "quantity" in source_exit:
                    exit_quantity *= min(1.0, float(source_exit["quantity"]) / old_position.quantity)
                elif source_exit.get("target_weight"):
                    current_row = prepared.row(date)
                    current_mark = prepared.opens[current_row, target_col]
                    current_mark = float(current_mark) if positive(current_mark) else float(target_mark)
                    nav = state.cash + state.receivables_value + conversion.cash_delta
                    for ticker, position in state.positions.items():
                        price = prepared.opens[current_row, prepared.ticker_index[ticker]]
                        nav += position.quantity * (float(price) if positive(price) else state.marks.get(ticker, position.average_cost))
                    entitlement_value = conversion.cash_delta + received.quantity * current_mark
                    remaining_fraction = min(1.0, float(source_exit["target_weight"]) * nav / entitlement_value)
                    exit_quantity *= 1.0 - remaining_fraction
                blocked = state.blocked_exits.get(target)
                if exit_quantity > 1e-9:
                    if blocked is None:
                        state.blocked_exits[target] = {key: value for key, value in source_exit.items() if key != "target_weight"}
                        state.blocked_exits[target]["quantity"] = exit_quantity
                    elif "quantity" in blocked:
                        blocked["quantity"] += exit_quantity
                    elif blocked.get("target_weight"):
                        blocked["quantity"] = exit_quantity
                # An existing full target exit takes priority over a transfer.
        if conversion.cash_delta:
            state.corporate_receivables[action.action_id] = {
                "amount": conversion.cash_delta, "effective_session": action.effective_session,
                "cash_settlement_session": action.cash_settlement_session,
                "source_ticker": source, "evidence": action.evidence,
            }
        state.processed_corporate_actions.append(action.action_id)
        result.events.append({**conversion.event, "execution_date": asof,
                              "receivable_added": conversion.cash_delta, "cash_credited": 0.0,
                              "existing_target_before": prior_target,
                              "target_after": asdict(state.positions[target]) if target in state.positions else None,
                              "source_exit": source_exit,
                              "target_exit_after": state.blocked_exits.get(target)})
    _settle_corporate_receivables(state, asof, result)
    for action_id, item in state.corporate_receivables.items():
        if item.get("cash_settlement_session") is None:
            result.events.append({"action": "unresolved_corporate_settlement", "event_type": "corporate_action",
                                  "action_id": action_id, "execution_date": asof, "amount": item["amount"],
                                  "reason": "cash entitlement is known but its availability date is unverified"})


def _exit_maximum(blocked: dict, quantity: float, equity: float, price: float,
                  integer_shares: bool, asof: str) -> float:
    if blocked.get("not_before", asof) > asof:
        return quantity
    if "quantity" in blocked:
        maximum = max(0.0, quantity - float(blocked["quantity"]))
        if blocked.get("target_weight"):
            target = equity * float(blocked["target_weight"]) / price
            maximum = min(maximum, float(np.floor(target)) if integer_shares else target)
        return maximum
    maximum = equity * float(blocked.get("target_weight", 0.0)) / price
    return float(np.floor(maximum)) if integer_shares else maximum


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
    result = ExecutionResult(events=sync_price_basis(prepared, state, as_of=date))
    _apply_corporate_actions(prepared, date, state, result, integer_shares)
    pending = state.pending
    targets = None
    if pending is not None and pending.execution_date <= asof:
        for ticker, reason in pending.exits.items():
            if ticker in state.positions:
                previous = state.blocked_exits.get(ticker)
                if previous is None or "quantity" in previous or (previous.get("target_weight") and reason != previous["reason"]):
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
    unresolved_tickers = {event["ticker"] for event in result.events
                          if event["action"] == "unresolved_corporate_action"}
    unresolved_tickers.update(state.unverified_price_basis)
    valid &= np.array([ticker not in unresolved_tickers for ticker in names], dtype=bool)
    marks = np.array([state.marks.get(t, state.positions[t].average_cost if t in state.positions else 0.0) for t in names])
    valuation_prices = np.where(valid, raw_prices, marks)
    equity_open = float(state.cash + state.receivables_value + np.dot(quantity, valuation_prices))
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
                       and not any(e["action"] in {"unverified_price_basis", "unresolved_corporate_action",
                                                     "unresolved_corporate_settlement"} for e in result.events))
        for i, ticker in enumerate(names):
            if quantity[i] > 0 and not valid[i] and ticker not in state.blocked_exits:
                weight = float(targets.get(ticker, 0.0))
                state.blocked_exits[ticker] = {
                    "signal_date": pending.signal_date, "reason": "rebalance_reduce" if weight else "rebalance_removal",
                    "event_type": "rebalance", "target_weight": weight,
                }
        # Solve post-fee target equity; floors are part of the same calculation.
        def funded_quantities(net_equity: float) -> np.ndarray:
            target_equity = net_equity
            if weights.sum() > 0:
                # An entitlement contributes to NAV but cannot fund purchases.
                # Scale the entire basket before trading so a locked cash leg
                # cannot favor whichever ticker happens to execute first.
                target_equity = min(net_equity, max(0.0, net_equity - state.receivables_value) / weights.sum())
            values = target_equity * weights / safe_prices
            if integer_shares:
                values = np.floor(values + 1e-12)
            if not can_buy:
                values = np.minimum(values, quantity)
            values[~valid] = quantity[~valid]
            for i, ticker in enumerate(names):
                if ticker in state.blocked_exits and valid[i]:
                    maximum = _exit_maximum(state.blocked_exits[ticker], quantity[i], equity_open,
                                            raw_prices[i], integer_shares, asof)
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
        if (ticker in state.blocked_exits and quantity[i] > 0
                and state.blocked_exits[ticker].get("not_before", asof) <= asof):
            if valid[i]:
                blocked = state.blocked_exits[ticker]
                maximum = _exit_maximum(blocked, quantity[i], equity_open, raw_prices[i], integer_shares, asof)
                desired[i] = min(desired[i], maximum)
                if blocked.get("target_weight") and desired[i] >= quantity[i] - 1e-9:
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
                elif blocked and (blocked.get("target_weight") or "quantity" in blocked):
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
            if event["action"] not in {"adjustment_rescale", "already_processed", "corporate_action_conversion",
                                        "corporate_cash_settlement"}:
                warnings.append({"date": date.date().isoformat(), "warning": event["action"], **event})
        # Compact state audit; full serializable state is saved by paper callers.
        state_log.append({"date": date.date().isoformat(), "equity": equity[i], "cash": cash[i],
                          "corporate_receivables": state.receivables_value,
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
