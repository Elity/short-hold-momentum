"""Risk calculations and hard constraints for the P3 option overlay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isclose, isfinite
from typing import Literal, Sequence


OptionStrategy = Literal["covered_call", "cash_secured_put"]


class OverlayRejectedError(ValueError):
    """Raised when an option overlay violates an INV-04 constraint."""


@dataclass(frozen=True)
class PositionRisk:
    strategy: OptionStrategy
    contracts: int
    max_loss: float
    upside_cap: float | None
    cash_usage: float
    covered_shares: int


@dataclass(frozen=True)
class OptionOrder:
    underlying: str
    strategy: OptionStrategy
    contract_symbol: str
    expiration: date
    strike: float
    contracts: int
    bid: float
    ask: float
    delta: float | None
    delta_source: str
    max_loss: float
    upside_cap: float | None
    cash_usage: float
    covered_shares: int = 0


@dataclass(frozen=True)
class OverlaySummary:
    max_loss: float
    cash_usage: float
    csp_notional: float


def _positive_money(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _premium(value: float) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError("premium_per_share must be finite and non-negative")
    return value


def covered_call_risk(
    *,
    shares: int,
    stock_cost_basis: float,
    strike: float,
    premium_per_share: float,
) -> PositionRisk:
    """Calculate risk for one call sold per complete 100-share lot."""

    if shares < 100:
        raise OverlayRejectedError("covered call requires at least 100 shares")
    basis = _positive_money(stock_cost_basis, "stock_cost_basis")
    strike = _positive_money(strike, "strike")
    premium = _premium(premium_per_share)
    contracts = shares // 100
    covered_shares = contracts * 100
    return PositionRisk(
        strategy="covered_call",
        contracts=contracts,
        max_loss=max(0.0, (basis - premium) * covered_shares),
        upside_cap=strike,
        cash_usage=0.0,
        covered_shares=covered_shares,
    )


def cash_secured_put_risk(
    *, strike: float, premium_per_share: float
) -> PositionRisk:
    """Calculate risk and required collateral for one cash-secured put."""

    strike = _positive_money(strike, "strike")
    premium = _premium(premium_per_share)
    return PositionRisk(
        strategy="cash_secured_put",
        contracts=1,
        max_loss=max(0.0, (strike - premium) * 100),
        upside_cap=None,
        cash_usage=strike * 100,
        covered_shares=0,
    )


def make_covered_call_order(
    *,
    underlying: str,
    contract_symbol: str,
    expiration: date,
    strike: float,
    bid: float,
    ask: float,
    delta: float | None,
    delta_source: str,
    shares: int,
    stock_cost_basis: float,
) -> OptionOrder:
    risk = covered_call_risk(
        shares=shares,
        stock_cost_basis=stock_cost_basis,
        strike=strike,
        premium_per_share=bid,
    )
    return OptionOrder(
        underlying=underlying.upper(),
        strategy=risk.strategy,
        contract_symbol=contract_symbol,
        expiration=expiration,
        strike=float(strike),
        contracts=risk.contracts,
        bid=float(bid),
        ask=float(ask),
        delta=delta,
        delta_source=delta_source,
        max_loss=risk.max_loss,
        upside_cap=risk.upside_cap,
        cash_usage=risk.cash_usage,
        covered_shares=risk.covered_shares,
    )


def make_cash_secured_put_order(
    *,
    underlying: str,
    contract_symbol: str,
    expiration: date,
    strike: float,
    bid: float,
    ask: float,
    delta: float | None,
    delta_source: str,
) -> OptionOrder:
    risk = cash_secured_put_risk(strike=strike, premium_per_share=bid)
    return OptionOrder(
        underlying=underlying.upper(),
        strategy=risk.strategy,
        contract_symbol=contract_symbol,
        expiration=expiration,
        strike=float(strike),
        contracts=risk.contracts,
        bid=float(bid),
        ask=float(ask),
        delta=delta,
        delta_source=delta_source,
        max_loss=risk.max_loss,
        upside_cap=risk.upside_cap,
        cash_usage=risk.cash_usage,
        covered_shares=risk.covered_shares,
    )


def validate_overlay(
    orders: Sequence[OptionOrder],
    *,
    portfolio_equity: float,
    available_cash: float,
    csp_notional_limit: float = 0.20,
) -> OverlaySummary:
    """Enforce stock coverage, cash coverage, and aggregate loss limits."""

    equity = _positive_money(portfolio_equity, "portfolio_equity")
    cash = float(available_cash)
    if not isfinite(cash) or cash < 0:
        raise ValueError("available_cash must be finite and non-negative")
    if not 0 <= csp_notional_limit <= 1:
        raise ValueError("csp_notional_limit must be between 0 and 1")

    for order in orders:
        if order.strategy == "covered_call":
            if order.covered_shares < order.contracts * 100:
                raise OverlayRejectedError(
                    f"{order.underlying} covered call lacks 100 shares per contract"
                )
            if not isclose(order.cash_usage, 0.0, abs_tol=1e-9):
                raise OverlayRejectedError("covered calls cannot consume secured cash")
        elif order.strategy == "cash_secured_put":
            required = order.strike * 100 * order.contracts
            if not isclose(order.cash_usage, required, rel_tol=1e-9, abs_tol=1e-9):
                raise OverlayRejectedError(
                    f"{order.underlying} put is not 100% cash secured"
                )
        else:
            raise OverlayRejectedError(f"unsupported option strategy: {order.strategy}")

    total_max_loss = sum(order.max_loss for order in orders)
    total_cash_usage = sum(order.cash_usage for order in orders)
    csp_notional = sum(
        order.cash_usage for order in orders if order.strategy == "cash_secured_put"
    )
    if total_max_loss > equity + 1e-9:
        raise OverlayRejectedError("aggregate maximum loss exceeds portfolio equity")
    if total_cash_usage > cash + 1e-9:
        raise OverlayRejectedError("cash-secured put usage exceeds available cash")
    if csp_notional > equity * csp_notional_limit + 1e-9:
        raise OverlayRejectedError("cash-secured put notional exceeds 20% of equity")
    return OverlaySummary(
        max_loss=total_max_loss,
        cash_usage=total_cash_usage,
        csp_notional=csp_notional,
    )
