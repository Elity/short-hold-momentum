"""Pure mandatory cash/stock conversion in the engine's adjusted price units.

For an adjusted price ``A = nominal_price * f``, a held quantity ``q`` represents
``q * f`` nominal shares. Thus cash is ``q * f_source * cash_per_share`` and new
adjusted units are ``q * f_source * exchange_ratio / f_target``. The conversion
does not create a market fill, charge model trading costs, or reinvest cash.

Only a source series terminating before the action may use this path. A series
already extended with the merger's total-return payoff must not also receive
cash or successor shares: that would count the same entitlement twice. Ordinary
dividends/splits already embedded in adjusted OHLC are not additional cashflows.
The caller verifies the terminal-series declaration against the actual data.

Basis factors describe dated units, not a future closing-price signal. Callers
must supply verified factors and their evidence; no last-price or unit fallback
is inferred here. Peak/stop levels inherit the old lot's economic bound after
distributed cash is removed. The caller owns application timing, idempotency,
pending exits and separate lots when the successor is already held.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import floor, isfinite

from shm.v03.strategy import PositionState


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    source_ticker: str
    announced_date: str
    known_date: str
    last_trading_session: str
    effective_session: str
    cash_per_share: float
    evidence: str
    source_price_treatment: str
    target_ticker: str | None = None
    exchange_ratio: float = 0.0
    cash_in_lieu_price: float | None = None
    cash_settlement_session: str | None = None

    def __post_init__(self) -> None:
        announced, known, last, effective = [date.fromisoformat(value) for value in (
            self.announced_date, self.known_date, self.last_trading_session, self.effective_session,
        )]
        if not announced <= known <= effective or not last < effective:
            raise ValueError("action dates must be known by the effective session and follow the final trading session")
        if self.cash_settlement_session is not None and date.fromisoformat(self.cash_settlement_session) < effective:
            raise ValueError("cash settlement cannot precede the effective session")
        if not self.action_id or not self.source_ticker or not self.evidence.strip():
            raise ValueError("action identity and evidence are required")
        if self.source_price_treatment != "terminal_before_action":
            raise ValueError("corporate action requires a terminal source series; total-return continuation would double count")
        if not all(isfinite(value) and value >= 0 for value in (self.cash_per_share, self.exchange_ratio)):
            raise ValueError("cash and stock consideration must be finite and nonnegative")
        if not self.cash_per_share and not self.exchange_ratio:
            raise ValueError("action has no consideration")
        if bool(self.target_ticker) != bool(self.exchange_ratio) or self.target_ticker == self.source_ticker:
            raise ValueError("stock consideration requires a distinct successor ticker")
        if self.cash_in_lieu_price is not None and not (
            isfinite(self.cash_in_lieu_price) and self.cash_in_lieu_price > 0
        ):
            raise ValueError("cash-in-lieu price must be finite and positive")


@dataclass(frozen=True)
class AdjustmentBasis:
    factor: float
    reference_date: str
    evidence: str

    def __post_init__(self) -> None:
        date.fromisoformat(self.reference_date)
        if not isfinite(self.factor) or self.factor <= 0 or not self.evidence.strip():
            raise ValueError("a positive adjustment factor with dated evidence is required")


@dataclass(frozen=True)
class CorporateActionConversion:
    target_position: PositionState | None
    cash_delta: float
    source_cost_basis: float
    cash_cost_basis: float
    target_cost_basis: float
    realized_cash_pnl: float
    event: dict


def convert_position(
    position: PositionState,
    action: CorporateAction,
    *,
    source_basis: AdjustmentBasis,
    target_basis: AdjustmentBasis | None = None,
    target_mark: float | None = None,
    integer_actual_shares: bool = False,
) -> CorporateActionConversion:
    """Return the legal entitlement and its audit record without mutating inputs.

    ``target_mark`` is the successor's observed adjusted open for valuation and
    economic cost-basis allocation, not an assumed sale. Integer mode rounds
    successor *nominal* shares; a fractional remainder requires the documented
    cash-in-lieu price. Research may retain fractional entitlement shares.
    """
    if source_basis.reference_date != action.last_trading_session:
        raise ValueError("source basis must describe the final trading session")
    if not all(isfinite(value) and value > 0 for value in (
        position.quantity, position.average_cost,
    )) or not isfinite(position.peak_close):
        raise ValueError("source position must have valid quantity, cost and peak")
    if position.trailing_stop is not None and not isfinite(position.trailing_stop):
        raise ValueError("source trailing stop must be finite")
    if action.target_ticker is not None:
        if target_basis is None or target_mark is None or not isfinite(target_mark) or target_mark <= 0:
            raise ValueError("stock consideration requires a verified target basis and observed positive mark")
        if target_basis.reference_date > action.effective_session:
            raise ValueError("target basis cannot refer to a later session")
    elif target_basis is not None or target_mark is not None:
        raise ValueError("cash-only conversion has no target price basis")

    source_actual_shares = position.quantity * source_basis.factor
    entitled_shares = source_actual_shares * action.exchange_ratio
    target_actual_shares, fractional_shares = entitled_shares, 0.0
    if integer_actual_shares and entitled_shares:
        target_actual_shares = float(floor(entitled_shares + 1e-10))
        fractional_shares = max(0.0, entitled_shares - target_actual_shares)
        if fractional_shares > 0 and action.cash_in_lieu_price is None:
            raise ValueError("fractional successor shares require a documented cash-in-lieu price")
    cash_consideration = source_actual_shares * action.cash_per_share
    fractional_cash = fractional_shares * (action.cash_in_lieu_price or 0.0)
    cash_delta = cash_consideration + fractional_cash
    target_quantity = target_actual_shares / target_basis.factor if target_basis is not None else 0.0
    target_value = target_quantity * target_mark if target_mark is not None else 0.0
    total_consideration = cash_delta + target_value
    source_cost_basis = position.quantity * position.average_cost
    cash_cost_basis = source_cost_basis * cash_delta / total_consideration
    target_cost_basis = source_cost_basis - cash_cost_basis
    realized_cash_pnl = cash_delta - cash_cost_basis
    target_position = None
    if target_quantity:
        # Preserve the whole old lot's economic peak/stop, allowing cash already
        # distributed to satisfy part or all of that bound. Negative inherited
        # stops are valid; the usual ATR update will subsequently raise them.
        def transfer_level(value: float) -> float:
            return (position.quantity * value - cash_delta) / target_quantity

        target_position = PositionState(
            quantity=target_quantity,
            average_cost=target_cost_basis / target_quantity,
            entry_date=position.entry_date,
            peak_close=transfer_level(position.peak_close),
            trailing_stop=transfer_level(position.trailing_stop) if position.trailing_stop is not None else None,
        )
    event = {
        "action": "corporate_action_conversion", "event_type": "corporate_action",
        "action_id": action.action_id, "effective_session": action.effective_session,
        "announced_date": action.announced_date, "known_date": action.known_date,
        "last_trading_session": action.last_trading_session,
        "cash_settlement_session": action.cash_settlement_session,
        "cash_delivery": "receivable_entitlement_until_settlement",
        "stock_delivery": "economic_entitlement_not_broker_confirmation",
        "source_ticker": action.source_ticker, "target_ticker": action.target_ticker,
        "evidence": action.evidence, "source_price_treatment": action.source_price_treatment,
        "source_basis": asdict(source_basis),
        "target_basis": asdict(target_basis) if target_basis is not None else None,
        "source_actual_shares": source_actual_shares,
        "exchange_ratio": action.exchange_ratio, "cash_per_share": action.cash_per_share,
        "entitled_successor_shares": entitled_shares,
        "target_actual_shares": target_actual_shares, "target_quantity": target_quantity,
        "cash_consideration": cash_consideration, "cash_in_lieu": fractional_cash,
        "cash_in_lieu_price": action.cash_in_lieu_price,
        "fractional_successor_shares": fractional_shares,
        "cash_delta": cash_delta, "target_mark": target_mark, "target_value": target_value,
        "total_consideration": total_consideration,
        "source_cost_basis": source_cost_basis, "cash_cost_basis": cash_cost_basis,
        "target_cost_basis": target_cost_basis, "realized_cash_pnl": realized_cash_pnl,
        "cost_basis_method": "relative_fair_value_economic_allocation_not_tax_accounting",
        "source_position": asdict(position),
        "target_position": asdict(target_position) if target_position is not None else None,
        "integer_actual_shares": integer_actual_shares,
        "model_cost": 0.0, "market_fill": False,
    }
    return CorporateActionConversion(target_position, cash_delta, source_cost_basis, cash_cost_basis,
                                     target_cost_basis, realized_cash_pnl, event)
