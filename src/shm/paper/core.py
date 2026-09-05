from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite
from numbers import Integral
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

import pandas as pd

from shm.universe import trailing_xnys_sessions


PAPER_MODE = "paper"
PAPER_LOOKBACK_SESSIONS = 260
TICKET_COLUMNS = ("ticker", "side", "qty", "order_type", "time_in_force", "reason")
FILL_COLUMNS = ("ticker", "qty", "fill_price", "fill_time", "official_open")
FILL_OPTIONAL_COLUMNS = ("commission",)

Side = Literal["buy", "sell"]


def require_paper_mode(mode: str) -> None:
    """Reject every execution mode except the isolated paper mode."""
    if mode != PAPER_MODE:
        raise PermissionError("live endpoints are forbidden; mode must be 'paper'")


def paper_xnys_window(as_of: object, *, mode: str = PAPER_MODE) -> pd.DatetimeIndex:
    """Return the only 260 XNYS sessions paper signal code may read."""
    require_paper_mode(mode)
    return trailing_xnys_sessions(pd.Timestamp(as_of), PAPER_LOOKBACK_SESSIONS)


def validate_paper_window(
    dates: Iterable[object],
    *,
    as_of: object,
    mode: str = PAPER_MODE,
) -> pd.DatetimeIndex:
    """Validate that observed dates stay inside the paper-only read window."""
    allowed = paper_xnys_window(as_of, mode=mode)
    observed = pd.DatetimeIndex(dates).tz_localize(None).normalize()
    if observed.has_duplicates:
        raise ValueError("paper window dates must be unique")
    if len(observed) > PAPER_LOOKBACK_SESSIONS or not observed.isin(allowed).all():
        raise ValueError("paper data must be limited to the latest 260 XNYS sessions")
    return observed.sort_values()


def _ticker(value: object) -> str:
    ticker = str(value).strip().upper()
    if not ticker:
        raise ValueError("ticker must not be empty")
    return ticker


def _money(value: object, name: str, *, allow_zero: bool = True) -> float:
    amount = float(value)
    if not isfinite(amount) or amount < 0 or (not allow_zero and amount == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {qualifier}")
    return amount


def _shares(value: object, name: str = "qty") -> int:
    if not isinstance(value, Integral) or isinstance(value, bool) or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


@dataclass(frozen=True)
class PaperAccount:
    cash: float
    positions: Mapping[str, int] = field(default_factory=dict)
    mode: str = PAPER_MODE

    def __post_init__(self) -> None:
        require_paper_mode(self.mode)
        normalized: dict[str, int] = {}
        for raw_ticker, raw_qty in self.positions.items():
            ticker = _ticker(raw_ticker)
            if not isinstance(raw_qty, Integral) or isinstance(raw_qty, bool) or int(raw_qty) < 0:
                raise ValueError("paper positions must be non-negative integer shares")
            if raw_qty:
                normalized[ticker] = int(raw_qty)
        object.__setattr__(self, "cash", _money(self.cash, "cash"))
        object.__setattr__(self, "positions", normalized)

    def equity(self, prices: Mapping[str, float]) -> float:
        normalized_prices = {_ticker(ticker): price for ticker, price in prices.items()}
        value = self.cash
        for ticker, qty in self.positions.items():
            if ticker not in normalized_prices:
                raise ValueError(f"missing price for held ticker {ticker}")
            value += qty * _money(normalized_prices[ticker], f"price for {ticker}", allow_zero=False)
        return float(value)


@dataclass(frozen=True)
class OrderTicket:
    ticker: str
    side: Side
    qty: int
    order_type: str = "market_on_open"
    time_in_force: str = "opg"
    reason: str = "rebalance_to_integer_target"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _ticker(self.ticker))
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        object.__setattr__(self, "qty", _shares(self.qty))
        if not self.order_type.strip() or not self.time_in_force.strip() or not self.reason.strip():
            raise ValueError("order_type, time_in_force, and reason must not be empty")

    def to_record(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "side": self.side,
            "qty": self.qty,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SkippedCandidate:
    ticker: str
    reason: str
    replacement_ticker: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _ticker(self.ticker))
        if not self.reason.strip():
            raise ValueError("skip reason must not be empty")
        if self.replacement_ticker is not None:
            object.__setattr__(self, "replacement_ticker", _ticker(self.replacement_ticker))


@dataclass(frozen=True)
class TicketPlan:
    tickets: tuple[OrderTicket, ...]
    skipped: tuple[SkippedCandidate, ...]
    target_positions: Mapping[str, int]
    projected_cash: float
    rounding_residual_usd: float
    as_of: pd.Timestamp | None = None
    mode: str = PAPER_MODE

    def __post_init__(self) -> None:
        require_paper_mode(self.mode)
        object.__setattr__(self, "projected_cash", _money(self.projected_cash, "projected_cash"))
        object.__setattr__(
            self,
            "rounding_residual_usd",
            _money(self.rounding_residual_usd, "rounding_residual_usd"),
        )
        normalized_positions: dict[str, int] = {}
        for raw_ticker, raw_qty in self.target_positions.items():
            ticker = _ticker(raw_ticker)
            if not isinstance(raw_qty, Integral) or isinstance(raw_qty, bool) or int(raw_qty) < 0:
                raise ValueError("target positions must be non-negative integer shares")
            if raw_qty:
                normalized_positions[ticker] = int(raw_qty)
        object.__setattr__(self, "target_positions", normalized_positions)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", pd.Timestamp(self.as_of).tz_localize(None))

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([ticket.to_record() for ticket in self.tickets], columns=TICKET_COLUMNS)


def tickets_from_frame(frame: pd.DataFrame) -> tuple[OrderTicket, ...]:
    if tuple(frame.columns) != TICKET_COLUMNS:
        raise ValueError(f"ticket columns must be exactly: {', '.join(TICKET_COLUMNS)}")
    return tuple(
        OrderTicket(
            ticker=row.ticker,
            side=row.side,
            qty=row.qty,
            order_type=row.order_type,
            time_in_force=row.time_in_force,
            reason=row.reason,
        )
        for row in frame.itertuples(index=False)
    )


def write_ticket_csv(
    path: Path | str,
    tickets: TicketPlan | Iterable[OrderTicket],
    *,
    mode: str = PAPER_MODE,
) -> Path:
    require_paper_mode(mode)
    if isinstance(tickets, TicketPlan):
        require_paper_mode(tickets.mode)
        frame = tickets.to_frame()
    else:
        frame = pd.DataFrame(
            [ticket.to_record() for ticket in tickets], columns=TICKET_COLUMNS
        )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return destination


def read_ticket_csv(path: Path | str, *, mode: str = PAPER_MODE) -> tuple[OrderTicket, ...]:
    require_paper_mode(mode)
    return tickets_from_frame(pd.read_csv(path))


def generate_integer_share_tickets(
    account: PaperAccount,
    ranked_tickers: Sequence[str],
    previous_closes: Mapping[str, float],
    *,
    target_count: int,
    exposure: float = 1.0,
    estimated_cost_bps: float = 10.0,
    order_type: str = "market_on_open",
    time_in_force: str = "opg",
    as_of: object | None = None,
) -> TicketPlan:
    """Create a deterministic, whole-share rebalance plan without contacting a broker."""
    require_paper_mode(account.mode)
    if not isinstance(target_count, Integral) or isinstance(target_count, bool) or target_count <= 0:
        raise ValueError("target_count must be a positive integer")
    if not isfinite(exposure) or not 0 <= exposure <= 1:
        raise ValueError("exposure must be between 0 and 1")
    if not isfinite(estimated_cost_bps) or estimated_cost_bps < 0:
        raise ValueError("estimated_cost_bps must be finite and non-negative")

    ranking = [_ticker(ticker) for ticker in ranked_tickers]
    if len(ranking) != len(set(ranking)):
        raise ValueError("ranked_tickers must not contain duplicates")
    prices: dict[str, float | None] = {}
    for raw_ticker, raw_price in previous_closes.items():
        ticker = _ticker(raw_ticker)
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            price = float("nan")
        prices[ticker] = price if isfinite(price) and price > 0 else None
    equity = account.equity(
        {
            ticker: price
            for ticker, price in prices.items()
            if price is not None
        }
    )
    target_amount = equity * float(exposure) / int(target_count)

    selected: list[str] = []
    skipped: list[SkippedCandidate] = []
    substitution_sources: dict[str, list[str]] = {}
    pending: list[tuple[str, str]] = []
    if target_amount > 0:
        for ticker in ranking:
            if len(selected) >= target_count:
                break
            price = prices.get(ticker)
            if price is None:
                pending.append((ticker, "missing_or_invalid_previous_close"))
                continue
            if price > target_amount:
                pending.append(
                    (
                        ticker,
                        f"price_exceeds_target_amount:{price:.6f}>{target_amount:.6f}",
                    )
                )
                continue
            selected.append(ticker)
            if pending:
                substitution_sources[ticker] = [source for source, _ in pending]
                skipped.extend(
                    SkippedCandidate(source, reason, replacement_ticker=ticker)
                    for source, reason in pending
                )
                pending = []
        skipped.extend(
            SkippedCandidate(ticker, f"{reason};no_affordable_substitute")
            for ticker, reason in pending
        )

    desired = {ticker: floor(target_amount / float(prices[ticker])) for ticker in selected}
    fee_rate = estimated_cost_bps / 10_000.0
    projected_cash = float(account.cash)
    tickets: list[OrderTicket] = []

    sell_tickers = sorted(set(account.positions) | set(desired))
    for ticker in sell_tickers:
        current_qty = account.positions.get(ticker, 0)
        desired_qty = desired.get(ticker, 0)
        if current_qty <= desired_qty:
            continue
        price = prices.get(ticker)
        if price is None:
            raise ValueError(f"missing price for held ticker {ticker}")
        qty = current_qty - desired_qty
        projected_cash += qty * price * (1.0 - fee_rate)
        reason = "rebalance_exit" if desired_qty == 0 else "rebalance_reduce_to_integer_target"
        tickets.append(OrderTicket(ticker, "sell", qty, order_type, time_in_force, reason))

    final_desired = dict(desired)
    for ticker in selected:
        current_qty = account.positions.get(ticker, 0)
        requested = max(0, desired[ticker] - current_qty)
        if requested == 0:
            continue
        price = float(prices[ticker])
        unit_cost = price * (1.0 + fee_rate)
        affordable = min(requested, floor((projected_cash + 1e-9) / unit_cost))
        if affordable == 0:
            final_desired[ticker] = current_qty
            skipped.append(SkippedCandidate(ticker, "insufficient_cash_after_estimated_costs"))
            continue
        projected_cash -= affordable * unit_cost
        final_desired[ticker] = current_qty + affordable
        reason = "rebalance_to_integer_target"
        if ticker in substitution_sources:
            reason += ";substitutes=" + ",".join(substitution_sources[ticker])
        if affordable < requested:
            reason += f";cash_capped_from={requested}_to={affordable}"
        tickets.append(OrderTicket(ticker, "buy", affordable, order_type, time_in_force, reason))

    final_desired = {ticker: qty for ticker, qty in final_desired.items() if qty > 0}
    actual_target_value = sum(
        final_desired[ticker] * float(prices[ticker]) for ticker in final_desired
    )
    planned_target_value = equity * float(exposure)
    rounding_residual = max(0.0, planned_target_value - actual_target_value)
    if projected_cash < -1e-7:
        raise RuntimeError("paper ticket plan would produce negative cash")

    return TicketPlan(
        tickets=tuple(tickets),
        skipped=tuple(skipped),
        target_positions=final_desired,
        projected_cash=max(0.0, projected_cash),
        rounding_residual_usd=rounding_residual,
        as_of=None if as_of is None else pd.Timestamp(as_of),
    )


@dataclass(frozen=True)
class Fill:
    ticker: str
    qty: int
    fill_price: float
    fill_time: pd.Timestamp
    official_open: float
    commission: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _ticker(self.ticker))
        object.__setattr__(self, "qty", _shares(self.qty))
        object.__setattr__(self, "fill_price", _money(self.fill_price, "fill_price", allow_zero=False))
        object.__setattr__(
            self,
            "official_open",
            _money(self.official_open, "official_open", allow_zero=False),
        )
        object.__setattr__(self, "commission", _money(self.commission, "commission"))
        object.__setattr__(self, "fill_time", pd.Timestamp(self.fill_time).tz_localize(None))

    def to_record(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "qty": self.qty,
            "fill_price": self.fill_price,
            "fill_time": self.fill_time,
            "official_open": self.official_open,
        }


def realized_cost_bps(
    fill_price: float,
    official_open: float,
    *,
    qty: int = 1,
    commission: float = 0.0,
) -> float:
    """Return absolute open slippage plus commission, in basis points."""
    fill = _money(fill_price, "fill_price", allow_zero=False)
    official = _money(official_open, "official_open", allow_zero=False)
    shares = _shares(qty)
    fee = _money(commission, "commission")
    official_notional = official * shares
    return (abs(fill - official) * shares + fee) / official_notional * 10_000.0


@dataclass(frozen=True)
class AppliedFill:
    ticker: str
    side: Side
    qty: int
    fill_price: float
    fill_time: pd.Timestamp
    official_open: float
    commission: float
    realized_cost_bps: float
    execution_price_impact_usd: float


@dataclass(frozen=True)
class FillIngestionResult:
    account: PaperAccount
    applied_fills: tuple[AppliedFill, ...]
    realized_cost_bps: float | None
    traded_official_notional: float
    commissions: float


def fills_from_frame(frame: pd.DataFrame) -> tuple[Fill, ...]:
    columns = tuple(frame.columns)
    if columns not in {FILL_COLUMNS, (*FILL_COLUMNS, *FILL_OPTIONAL_COLUMNS)}:
        raise ValueError(
            "fill columns must be the §4.13 columns with optional trailing commission"
        )
    return tuple(
        Fill(
            ticker=row.ticker,
            qty=row.qty,
            fill_price=row.fill_price,
            fill_time=row.fill_time,
            official_open=row.official_open,
            commission=getattr(row, "commission", 0.0),
        )
        for row in frame.itertuples(index=False)
    )


def fills_to_frame(fills: Iterable[Fill]) -> pd.DataFrame:
    items = tuple(fills)
    include_commission = any(fill.commission != 0 for fill in items)
    records = [
        fill.to_record() | ({"commission": fill.commission} if include_commission else {})
        for fill in items
    ]
    columns = (*FILL_COLUMNS, *FILL_OPTIONAL_COLUMNS) if include_commission else FILL_COLUMNS
    return pd.DataFrame(records, columns=columns)


def write_fill_csv(
    path: Path | str,
    fills: Iterable[Fill],
    *,
    mode: str = PAPER_MODE,
) -> Path:
    require_paper_mode(mode)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fills_to_frame(fills).to_csv(destination, index=False)
    return destination


def read_fill_csv(path: Path | str, *, mode: str = PAPER_MODE) -> tuple[Fill, ...]:
    require_paper_mode(mode)
    return fills_from_frame(pd.read_csv(path))


def ingest_fills(
    account: PaperAccount,
    tickets: TicketPlan | Iterable[OrderTicket],
    fills: Iterable[Fill] | pd.DataFrame,
) -> FillIngestionResult:
    """Apply confirmed paper fills to an account and reject unfunded/unknown fills."""
    require_paper_mode(account.mode)
    if isinstance(tickets, TicketPlan):
        require_paper_mode(tickets.mode)
        ticket_items = tickets.tickets
    else:
        ticket_items = tuple(tickets)
    fill_items = fills_from_frame(fills) if isinstance(fills, pd.DataFrame) else tuple(fills)

    by_ticker: dict[str, OrderTicket] = {}
    for ticket in ticket_items:
        if ticket.ticker in by_ticker:
            raise ValueError(f"multiple tickets for {ticket.ticker} are ambiguous")
        by_ticker[ticket.ticker] = ticket

    matched: list[tuple[OrderTicket, Fill]] = []
    filled_qty: dict[str, int] = {}
    for fill in fill_items:
        ticket = by_ticker.get(fill.ticker)
        if ticket is None:
            raise ValueError(f"fill has no paper ticket: {fill.ticker}")
        filled_qty[fill.ticker] = filled_qty.get(fill.ticker, 0) + fill.qty
        if filled_qty[fill.ticker] > ticket.qty:
            raise ValueError(f"filled quantity exceeds ticket for {fill.ticker}")
        matched.append((ticket, fill))

    matched.sort(key=lambda item: (0 if item[0].side == "sell" else 1, item[1].fill_time, item[1].ticker))
    cash = float(account.cash)
    positions = dict(account.positions)
    applied: list[AppliedFill] = []
    absolute_cost = 0.0
    official_notional = 0.0
    commissions = 0.0

    for ticket, fill in matched:
        notional = fill.fill_price * fill.qty
        if ticket.side == "sell":
            if fill.qty > positions.get(fill.ticker, 0):
                raise ValueError(f"sell fill exceeds position for {fill.ticker}")
            positions[fill.ticker] -= fill.qty
            cash += notional - fill.commission
            if cash < -1e-7:
                raise ValueError("paper fills would produce negative cash")
            price_impact = (fill.official_open - fill.fill_price) * fill.qty + fill.commission
        else:
            cash -= notional + fill.commission
            if cash < -1e-7:
                raise ValueError("paper fills would produce negative cash")
            positions[fill.ticker] = positions.get(fill.ticker, 0) + fill.qty
            price_impact = (fill.fill_price - fill.official_open) * fill.qty + fill.commission
        positions = {ticker: qty for ticker, qty in positions.items() if qty}
        fill_cost = abs(fill.fill_price - fill.official_open) * fill.qty + fill.commission
        reference_notional = fill.official_open * fill.qty
        absolute_cost += fill_cost
        official_notional += reference_notional
        commissions += fill.commission
        applied.append(
            AppliedFill(
                ticker=fill.ticker,
                side=ticket.side,
                qty=fill.qty,
                fill_price=fill.fill_price,
                fill_time=fill.fill_time,
                official_open=fill.official_open,
                commission=fill.commission,
                realized_cost_bps=fill_cost / reference_notional * 10_000.0,
                execution_price_impact_usd=price_impact,
            )
        )

    return FillIngestionResult(
        account=PaperAccount(cash=max(0.0, cash), positions=positions),
        applied_fills=tuple(applied),
        realized_cost_bps=(None if official_notional == 0 else absolute_cost / official_notional * 10_000.0),
        traded_official_notional=official_notional,
        commissions=commissions,
    )


@dataclass(frozen=True)
class MonthlyComparisonInputs:
    month: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    paper_start_equity: float
    paper_end_equity: float
    model_start_equity: float
    model_end_equity: float
    paper_return: float
    model_return: float
    return_gap: float
    fill_count: int
    realized_cost_bps: float | None
    assumed_cost_bps: float
    cost_multiple: float | None
    hc07_triggered: bool | None
    execution_price_impact_usd: float
    integer_rounding_usd: float
    skipped_candidates: tuple[SkippedCandidate, ...]
    option_overlay_pnl_usd: float | None


def _equity_series(values: pd.Series, name: str) -> pd.Series:
    series = values.astype(float).copy()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None)
    series = series.sort_index()
    if series.empty or not series.map(isfinite).all() or (series <= 0).any():
        raise ValueError(f"{name} must contain positive finite equity values")
    return series


def build_monthly_comparison_inputs(
    month: str | pd.Period,
    paper_equity: pd.Series,
    model_equity: pd.Series,
    *,
    applied_fills: Iterable[AppliedFill] = (),
    ticket_plans: Iterable[TicketPlan] = (),
    assumed_cost_bps: float = 10.0,
    option_overlay_pnl_usd: float | None = None,
) -> MonthlyComparisonInputs:
    """Build observed monthly inputs; rendering or forecasting is intentionally out of scope."""
    period = pd.Period(month, freq="M")
    assumed = _money(assumed_cost_bps, "assumed_cost_bps", allow_zero=False)
    paper = _equity_series(paper_equity, "paper_equity")
    model = _equity_series(model_equity, "model_equity")
    common = paper.index.intersection(model.index)
    common = common[common.to_period("M") == period]
    if len(common) < 2:
        raise ValueError("monthly comparison requires at least two observed common equity dates")
    start_date, end_date = common[0], common[-1]
    paper_start, paper_end = float(paper.loc[start_date]), float(paper.loc[end_date])
    model_start, model_end = float(model.loc[start_date]), float(model.loc[end_date])
    paper_return = paper_end / paper_start - 1.0
    model_return = model_end / model_start - 1.0

    monthly_fills = tuple(
        fill for fill in applied_fills if fill.fill_time.to_period("M") == period
    )
    official_notional = sum(fill.official_open * fill.qty for fill in monthly_fills)
    absolute_cost = sum(
        abs(fill.fill_price - fill.official_open) * fill.qty + fill.commission
        for fill in monthly_fills
    )
    measured_bps = None if official_notional == 0 else absolute_cost / official_notional * 10_000.0
    cost_multiple = None if measured_bps is None else measured_bps / assumed

    monthly_plans: list[TicketPlan] = []
    for plan in ticket_plans:
        if plan.as_of is None:
            raise ValueError("monthly attribution requires dated ticket plans")
        if plan.as_of.to_period("M") == period:
            monthly_plans.append(plan)

    if option_overlay_pnl_usd is not None:
        option_overlay_pnl_usd = float(option_overlay_pnl_usd)
        if not isfinite(option_overlay_pnl_usd):
            raise ValueError("option_overlay_pnl_usd must be finite when provided")

    return MonthlyComparisonInputs(
        month=str(period),
        start_date=start_date,
        end_date=end_date,
        paper_start_equity=paper_start,
        paper_end_equity=paper_end,
        model_start_equity=model_start,
        model_end_equity=model_end,
        paper_return=paper_return,
        model_return=model_return,
        return_gap=paper_return - model_return,
        fill_count=len(monthly_fills),
        realized_cost_bps=measured_bps,
        assumed_cost_bps=assumed,
        cost_multiple=cost_multiple,
        hc07_triggered=None if cost_multiple is None else cost_multiple > 2.0,
        execution_price_impact_usd=sum(
            fill.execution_price_impact_usd for fill in monthly_fills
        ),
        integer_rounding_usd=sum(plan.rounding_residual_usd for plan in monthly_plans),
        skipped_candidates=tuple(skip for plan in monthly_plans for skip in plan.skipped),
        option_overlay_pnl_usd=option_overlay_pnl_usd,
    )


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def _dollars(value: float | None) -> str:
    return "not provided" if value is None else f"${value:,.2f}"


def render_monthly_report(inputs: MonthlyComparisonInputs) -> str:
    """Render a report only from observed monthly comparison inputs."""
    if inputs.realized_cost_bps is None:
        measured_cost = cost_multiple = "not observed"
        hc07 = "NOT_EVALUATED"
    else:
        measured_cost = f"{inputs.realized_cost_bps:.2f} bps"
        cost_multiple = f"{inputs.cost_multiple:.2f}x"
        hc07 = "TRIGGERED" if inputs.hc07_triggered else "not triggered"
    skipped = (
        "; ".join(
            f"{item.ticker}: {item.reason}"
            + (f" -> {item.replacement_ticker}" if item.replacement_ticker else "")
            for item in inputs.skipped_candidates
        )
        or "none"
    )
    lines = [
        f"# Paper monthly report — {inputs.month}",
        "",
        "- Mode: `paper`",
        "- Forward test: `true`",
        f"- Observed period: {inputs.start_date.date()} to {inputs.end_date.date()}",
        "",
        "## Paper vs model",
        "",
        "| Measure | Paper | Same-parameter model | Gap |",
        "|---|---:|---:|---:|",
        (
            f"| Return | {_percent(inputs.paper_return)} | {_percent(inputs.model_return)} "
            f"| {_percent(inputs.return_gap)} |"
        ),
        "",
        "## Realized execution cost",
        "",
        f"- Fills: {inputs.fill_count}",
        f"- Realized cost: {measured_cost}",
        f"- Assumed cost: {inputs.assumed_cost_bps:.2f} bps",
        f"- Cost multiple: {cost_multiple}",
        f"- HC-07 (> 2x assumption): {hc07}",
        "",
        "## Attribution inputs",
        "",
        f"- Execution price impact: {_dollars(inputs.execution_price_impact_usd)}",
        f"- Whole-share rounding residual: {_dollars(inputs.integer_rounding_usd)}",
        f"- Skipped/substituted stocks: {skipped}",
        f"- Option overlay P&L: {_dollars(inputs.option_overlay_pnl_usd)}",
        "",
    ]
    return "\n".join(lines)


def write_monthly_report(path: Path | str, inputs: MonthlyComparisonInputs) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_monthly_report(inputs), encoding="utf-8")
    return destination
