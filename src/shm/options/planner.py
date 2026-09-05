"""Build a paper-only option overlay from positions and ranked candidates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

from shm.options.calculator import (
    OptionOrder,
    OverlayRejectedError,
    OverlaySummary,
    make_cash_secured_put_order,
    make_covered_call_order,
    validate_overlay,
)
from shm.options.chains import (
    OptionChainSource,
    YFinanceOptionChainSource,
    select_cash_secured_put,
    select_covered_call,
)


PAPER_TICKET_COLUMNS = (
    "ticker",
    "side",
    "qty",
    "order_type",
    "time_in_force",
    "reason",
)


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: int
    spot: float
    cost_basis_per_share: float


@dataclass(frozen=True)
class Candidate:
    ticker: str
    spot: float


@dataclass(frozen=True)
class SkippedOverlay:
    ticker: str
    strategy: str
    reason: str


@dataclass(frozen=True)
class OverlayPlan:
    orders: tuple[OptionOrder, ...]
    skipped: tuple[SkippedOverlay, ...]
    summary: OverlaySummary


def build_overlay_plan(
    *,
    holdings: Sequence[Holding],
    candidates: Sequence[Candidate],
    portfolio_equity: float,
    available_cash: float,
    as_of: date,
    next_rebalance_date: date,
    source: OptionChainSource | None = None,
    risk_free_rate: float = 0.0,
    dividend_yields: Mapping[str, float] | None = None,
) -> OverlayPlan:
    """Create a constrained CC/CSP proposal without submitting any orders."""

    source = source or YFinanceOptionChainSource()
    dividend_yields = dividend_yields or {}
    orders: list[OptionOrder] = []
    skipped: list[SkippedOverlay] = []
    held = {holding.ticker.upper() for holding in holdings}

    for holding in holdings:
        ticker = holding.ticker.upper()
        if holding.shares < 100:
            skipped.append(
                SkippedOverlay(ticker, "covered_call", "fewer than 100 shares")
            )
            continue
        snapshot = source.load(ticker, not_before=next_rebalance_date)
        if snapshot is None:
            skipped.append(
                SkippedOverlay(ticker, "covered_call", "no standard expiration")
            )
            continue
        selected = select_covered_call(
            snapshot,
            spot=holding.spot,
            as_of=as_of,
            risk_free_rate=risk_free_rate,
            dividend_yield=float(dividend_yields.get(ticker, 0.0)),
        )
        if selected is None:
            skipped.append(
                SkippedOverlay(ticker, "covered_call", "no qualifying liquid call")
            )
            continue
        orders.append(
            make_covered_call_order(
                underlying=ticker,
                contract_symbol=selected.contract_symbol,
                expiration=selected.expiration,
                strike=selected.strike,
                bid=selected.bid,
                ask=selected.ask,
                delta=selected.delta,
                delta_source=selected.delta_source,
                shares=holding.shares,
                stock_cost_basis=holding.cost_basis_per_share,
            )
        )

    validate_overlay(
        orders,
        portfolio_equity=portfolio_equity,
        available_cash=available_cash,
    )

    seen_candidates: set[str] = set()
    for candidate in candidates[:5]:
        ticker = candidate.ticker.upper()
        if ticker in held:
            skipped.append(
                SkippedOverlay(ticker, "cash_secured_put", "candidate is already held")
            )
            continue
        if ticker in seen_candidates:
            continue
        seen_candidates.add(ticker)
        current = validate_overlay(
            orders,
            portfolio_equity=portfolio_equity,
            available_cash=available_cash,
        )
        remaining_cash = min(
            available_cash - current.cash_usage,
            portfolio_equity * 0.20 - current.csp_notional,
        )
        if remaining_cash <= 0:
            skipped.append(
                SkippedOverlay(ticker, "cash_secured_put", "cash or 20% CSP cap exhausted")
            )
            continue
        snapshot = source.load(ticker, not_before=next_rebalance_date)
        if snapshot is None:
            skipped.append(
                SkippedOverlay(ticker, "cash_secured_put", "no standard expiration")
            )
            continue
        selected = select_cash_secured_put(
            snapshot,
            spot=candidate.spot,
            as_of=as_of,
            available_cash=remaining_cash,
            risk_free_rate=risk_free_rate,
            dividend_yield=float(dividend_yields.get(ticker, 0.0)),
        )
        if selected is None:
            skipped.append(
                SkippedOverlay(ticker, "cash_secured_put", "no qualifying affordable put")
            )
            continue
        proposed = make_cash_secured_put_order(
            underlying=ticker,
            contract_symbol=selected.contract_symbol,
            expiration=selected.expiration,
            strike=selected.strike,
            bid=selected.bid,
            ask=selected.ask,
            delta=selected.delta,
            delta_source=selected.delta_source,
        )
        try:
            validate_overlay(
                [*orders, proposed],
                portfolio_equity=portfolio_equity,
                available_cash=available_cash,
            )
        except OverlayRejectedError as error:
            skipped.append(
                SkippedOverlay(ticker, "cash_secured_put", str(error))
            )
            continue
        orders.append(proposed)

    summary = validate_overlay(
        orders,
        portfolio_equity=portfolio_equity,
        available_cash=available_cash,
    )
    return OverlayPlan(tuple(orders), tuple(skipped), summary)


def paper_ticket_rows(plan: OverlayPlan) -> list[dict[str, str | int]]:
    """Render §4.13-compatible rows; this function never submits orders."""

    rows: list[dict[str, str | int]] = []
    for order in plan.orders:
        rows.append(
            {
                "ticker": order.contract_symbol,
                "side": "sell",
                "qty": order.contracts,
                "order_type": "limit",
                "time_in_force": "day",
                "reason": (
                    f"paper_only {order.strategy} underlying={order.underlying} "
                    f"expiry={order.expiration.isoformat()} strike={order.strike:g} "
                    f"limit_bid={order.bid:g} delta_source={order.delta_source}"
                ),
            }
        )
    return rows


def write_paper_ticket_csv(plan: OverlayPlan, path: Path | str) -> Path:
    """Write a paper ticket draft using the stock-ticket column contract."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PAPER_TICKET_COLUMNS)
        writer.writeheader()
        writer.writerows(paper_ticket_rows(plan))
    return output
