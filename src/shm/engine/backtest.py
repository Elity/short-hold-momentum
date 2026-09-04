from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


HARD_COST_FLOOR_BPS = 5.0


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    cash: pd.Series
    cash_weight: pd.Series
    weights: pd.DataFrame
    costs: pd.Series
    transactions: pd.DataFrame


def validate_target_weights(target_weights: pd.DataFrame) -> None:
    weights = target_weights.fillna(0.0).astype(float)
    if not np.isfinite(weights.to_numpy()).all():
        raise ValueError("target weights must be finite")
    if (weights < -1e-12).any().any():
        raise ValueError("target weights must be non-negative")
    if (weights.sum(axis=1) > 1.0 + 1e-9).any():
        raise ValueError("target weights must sum to at most 1.0")


def _price_panel(prices: Mapping[str, pd.DataFrame], column: str) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for ticker, frame in sorted(prices.items()):
        values = frame.copy()
        if "date" in values.columns:
            values["date"] = pd.to_datetime(values["date"]).dt.tz_localize(None)
            values = values.set_index("date")
        series[ticker] = values[column.lower()].astype(float)
    panel = pd.DataFrame(series)
    panel.index = pd.DatetimeIndex(panel.index).tz_localize(None)
    return panel.sort_index()


def _funded_target(
    current_shares: pd.Series,
    cash: float,
    open_prices: pd.Series,
    target_weights: pd.Series,
    equity_open: float,
    fee_rate: float,
) -> tuple[pd.Series, float, float]:
    def outcome(scale: float) -> tuple[pd.Series, float, float]:
        desired = target_weights * equity_open * scale / open_prices
        delta = desired - current_shares
        fees = float((delta.abs() * open_prices).sum() * fee_rate)
        cash_after = float(cash - (delta * open_prices).sum() - fees)
        return desired, cash_after, fees

    desired, cash_after, fees = outcome(1.0)
    if cash_after >= -1e-9:
        return desired, max(0.0, cash_after), fees
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2.0
        _, candidate_cash, _ = outcome(middle)
        if candidate_cash >= 0:
            low = middle
        else:
            high = middle
    desired, cash_after, fees = outcome(low)
    return desired, max(0.0, cash_after), fees


def run_target_weight_backtest(
    prices: Mapping[str, pd.DataFrame],
    target_weights: pd.DataFrame,
    *,
    cost_bps: float,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    if cost_bps < HARD_COST_FLOOR_BPS:
        raise ValueError(f"cost_bps must be at least {HARD_COST_FLOOR_BPS:g}")
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    if not prices:
        raise ValueError("prices must not be empty")
    validate_target_weights(target_weights)

    opens = _price_panel(prices, "open")
    closes = _price_panel(prices, "close").reindex(opens.index)
    sessions = opens.index
    tickers = opens.columns
    targets = target_weights.copy()
    targets.index = pd.DatetimeIndex(targets.index).tz_localize(None)
    targets = targets.reindex(columns=tickers, fill_value=0.0).sort_index()

    executions: dict[pd.Timestamp, tuple[pd.Timestamp, pd.Series]] = {}
    for signal_date, weights in targets.iterrows():
        position = sessions.searchsorted(signal_date, side="right")
        if position >= len(sessions):
            continue
        executions[sessions[position]] = (signal_date, weights.fillna(0.0))

    holdings = pd.Series(0.0, index=tickers)
    cash_amount = float(initial_cash)
    equity_values: dict[pd.Timestamp, float] = {}
    cash_values: dict[pd.Timestamp, float] = {}
    cash_weights: dict[pd.Timestamp, float] = {}
    daily_weights: dict[pd.Timestamp, pd.Series] = {}
    daily_costs: dict[pd.Timestamp, float] = {}
    transaction_rows: list[dict[str, object]] = []
    fee_rate = cost_bps / 10_000.0

    for session in sessions:
        session_cost = 0.0
        if session in executions:
            signal_date, desired_weights = executions[session]
            required = (holdings.ne(0.0)) | desired_weights.ne(0.0)
            execution_prices = opens.loc[session]
            if execution_prices[required].isna().any() or (execution_prices[required] <= 0).any():
                raise ValueError(f"missing or invalid open price on {session.date()}")
            safe_prices = execution_prices.where(required, 1.0)
            equity_open = float(cash_amount + (holdings * safe_prices).sum())
            new_holdings, new_cash, session_cost = _funded_target(
                holdings,
                cash_amount,
                safe_prices,
                desired_weights,
                equity_open,
                fee_rate,
            )
            delta = new_holdings - holdings
            for ticker in tickers[delta.abs() > 1e-12]:
                quantity = float(abs(delta[ticker]))
                price = float(execution_prices[ticker])
                transaction_rows.append(
                    {
                        "signal_date": signal_date,
                        "execution_date": session,
                        "ticker": ticker,
                        "side": "buy" if delta[ticker] > 0 else "sell",
                        "quantity": quantity,
                        "price": price,
                        "notional": quantity * price,
                        "cost": quantity * price * fee_rate,
                    }
                )
            holdings, cash_amount = new_holdings, new_cash

        close_prices = closes.loc[session]
        required_close = holdings.ne(0.0)
        if close_prices[required_close].isna().any() or (close_prices[required_close] <= 0).any():
            raise ValueError(f"missing or invalid close price on {session.date()}")
        safe_close = close_prices.where(required_close, 0.0)
        market_values = holdings * safe_close
        equity = float(cash_amount + market_values.sum())
        if equity <= 0:
            raise RuntimeError("portfolio equity became non-positive")
        equity_values[session] = equity
        cash_values[session] = cash_amount
        cash_weights[session] = cash_amount / equity
        daily_weights[session] = market_values / equity
        daily_costs[session] = session_cost

    transactions = pd.DataFrame(
        transaction_rows,
        columns=["signal_date", "execution_date", "ticker", "side", "quantity", "price", "notional", "cost"],
    )
    return BacktestResult(
        equity=pd.Series(equity_values, name="equity"),
        cash=pd.Series(cash_values, name="cash"),
        cash_weight=pd.Series(cash_weights, name="cash_weight"),
        weights=pd.DataFrame.from_dict(daily_weights, orient="index").reindex(columns=tickers).fillna(0.0),
        costs=pd.Series(daily_costs, name="cost"),
        transactions=transactions,
    )
