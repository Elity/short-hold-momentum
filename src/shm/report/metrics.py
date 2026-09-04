from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    cagr: float
    maxdd: float
    sharpe: float
    calmar: float
    turnover: float
    avg_exposure: float
    avg_holding_days: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def daily_returns(equity: pd.Series) -> pd.Series:
    return equity.astype(float).sort_index().pct_change().dropna()


def yearly_returns(equity: pd.Series) -> pd.Series:
    returns = daily_returns(equity)
    if returns.empty:
        return pd.Series(dtype=float)
    return (1.0 + returns).groupby(returns.index.year).prod() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    values = equity.astype(float).sort_index()
    if values.empty:
        return 0.0
    return float((values / values.cummax() - 1.0).min())


def annualized_sharpe(returns: pd.Series) -> float:
    values = returns.dropna().astype(float)
    if len(values) < 2:
        return 0.0
    volatility = float(values.std(ddof=1))
    return 0.0 if volatility == 0.0 else float(values.mean() / volatility * sqrt(252))


def annual_turnover(target_weights: pd.DataFrame | None, sessions: int) -> float:
    if target_weights is None or target_weights.empty or sessions <= 0:
        return 0.0
    weights = target_weights.fillna(0.0).astype(float)
    changes = weights.diff().fillna(weights.iloc[0]).abs().sum(axis=1).sum() / 2.0
    return float(changes * 252.0 / sessions)


def average_holding_days(daily_weights: pd.DataFrame | None) -> float:
    if daily_weights is None or daily_weights.empty:
        return 0.0
    durations: list[int] = []
    for ticker in daily_weights.columns:
        held = daily_weights[ticker].fillna(0.0).gt(0.0)
        groups = held.ne(held.shift(fill_value=False)).cumsum()
        durations.extend(int(group.sum()) for _, group in held[held].groupby(groups[held]))
    return float(np.mean(durations)) if durations else 0.0


def calculate_metrics(
    equity: pd.Series,
    *,
    daily_weights: pd.DataFrame | None = None,
    target_weights: pd.DataFrame | None = None,
) -> PerformanceMetrics:
    values = equity.astype(float).sort_index()
    returns = daily_returns(values)
    sessions = len(returns)
    if sessions == 0 or values.iloc[0] <= 0:
        cagr = 0.0
    else:
        cagr = float((values.iloc[-1] / values.iloc[0]) ** (252.0 / sessions) - 1.0)
    drawdown = max_drawdown(values)
    sharpe = annualized_sharpe(returns)
    calmar = float("inf") if drawdown == 0 and cagr > 0 else (0.0 if drawdown == 0 else cagr / abs(drawdown))
    exposure = (
        0.0
        if daily_weights is None or daily_weights.empty
        else float(daily_weights.fillna(0.0).sum(axis=1).mean())
    )
    return PerformanceMetrics(
        cagr=cagr,
        maxdd=drawdown,
        sharpe=sharpe,
        calmar=calmar,
        turnover=annual_turnover(target_weights, sessions),
        avg_exposure=exposure,
        avg_holding_days=average_holding_days(daily_weights),
    )

