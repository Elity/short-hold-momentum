"""Forward-only paper and model equity reconstruction for P4 monthly reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import yaml

from shm.data import read_price_cache
from shm.engine import run_target_weight_backtest
from shm.experiments import read_jsonl
from shm.paper.core import (
    AppliedFill,
    MonthlyComparisonInputs,
    PaperAccount,
    SkippedCandidate,
    TicketPlan,
    build_monthly_comparison_inputs,
    read_fill_csv,
    read_ticket_csv,
    realized_cost_bps,
    write_monthly_report,
)
from shm.universe import indexed_prices


@dataclass(frozen=True)
class MonthlyReportResult:
    inputs: MonthlyComparisonInputs
    paper_equity: pd.Series
    model_equity: pd.Series
    report_path: Path


def _yaml_mapping(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _paper_settings(repo_root: Path) -> tuple[pd.Timestamp, float, float]:
    payload = _yaml_mapping(repo_root / "paper/p4.yaml")
    if payload.get("mode") != "paper":
        raise PermissionError("P4 reporting requires mode: paper")
    start = pd.Timestamp(payload["forward_test_start"]).normalize()
    initial = float(payload["initial_equity_usd"])
    assumed_cost = float(
        _yaml_mapping(repo_root / "config/costs.yaml")["per_side_bps"]["default"]
    )
    if initial <= 0:
        raise ValueError("initial_equity_usd must be positive")
    return start, initial, assumed_cost


def _utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _completed_month_sessions(month: pd.Period, forward_start: pd.Timestamp) -> pd.DatetimeIndex:
    start = max(forward_start, month.start_time.normalize())
    end = month.end_time.normalize()
    if end < forward_start:
        raise ValueError(f"{month} precedes forward_test_start")
    calendar = xcals.get_calendar(
        "XNYS",
        start=start - pd.Timedelta("7D"),
        end=end + pd.Timedelta("7D"),
    )
    sessions = calendar.sessions_in_range(start, end)
    if len(sessions) < 2:
        raise ValueError("monthly report requires at least two forward XNYS sessions")
    if calendar.session_close(sessions[-1]) > _utc_now():
        raise ValueError(f"{month} is not a completed paper month")
    return sessions


def _account_snapshots(
    repo_root: Path,
    forward_start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[tuple[pd.Timestamp, PaperAccount]]:
    snapshots: list[tuple[pd.Timestamp, PaperAccount]] = []
    for path in sorted((repo_root / "paper/accounts").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        as_of = pd.Timestamp(payload.get("as_of", path.stem)).normalize()
        if as_of < forward_start or as_of > end:
            continue
        snapshots.append(
            (
                as_of,
                PaperAccount(
                    cash=payload["cash"],
                    positions=payload.get("positions", {}),
                    mode=payload.get("mode", "paper"),
                ),
            )
        )
    snapshots.sort(key=lambda item: item[0])
    if not snapshots:
        raise ValueError("paper reporting requires at least one account snapshot")
    return snapshots


def _paper_equity_curve(
    repo_root: Path,
    sessions: pd.DatetimeIndex,
    *,
    forward_start: pd.Timestamp,
) -> pd.Series:
    snapshots = _account_snapshots(repo_root, forward_start, sessions[-1])
    tickers = sorted({ticker for _, account in snapshots for ticker in account.positions})
    prices: dict[str, pd.Series] = {}
    for ticker in tickers:
        frame = read_price_cache(
            repo_root / "data/raw/prices" / f"{ticker}.parquet",
            ticker=ticker,
            start=sessions[0],
            end=sessions[-1],
            mode="paper",
            paper_sessions=260,
        )
        prices[ticker] = indexed_prices(frame)["close"]

    values: dict[pd.Timestamp, float] = {}
    for session in sessions:
        eligible = [item for item in snapshots if item[0] <= session]
        if not eligible:
            raise ValueError(f"missing account snapshot on or before {session.date()}")
        account = eligible[-1][1]
        marks: dict[str, float] = {}
        for ticker in account.positions:
            close = prices[ticker].get(session)
            if pd.isna(close):
                raise ValueError(f"{ticker} is missing close on {session.date()}")
            marks[ticker] = float(close)
        values[session] = account.equity(marks)
    return pd.Series(values, name="paper_equity")


def _paper_run_rows(
    repo_root: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, object]]:
    rows = []
    for row in read_jsonl(repo_root / "experiments/log.jsonl"):
        if row.get("mode") != "paper" or row.get("status") != "PAPER_TICKET_READY":
            continue
        signal_date = pd.Timestamp(row["period"]["end"]).normalize()
        if start <= signal_date <= end:
            rows.append(row)
    return sorted(rows, key=lambda row: row["period"]["end"])


def _model_equity_curve(
    repo_root: Path,
    sessions: pd.DatetimeIndex,
    *,
    initial_equity: float,
    cost_bps: float,
) -> pd.Series:
    rows = _paper_run_rows(repo_root, sessions[0], sessions[-1])
    targets: dict[pd.Timestamp, pd.Series] = {}
    tickers: set[str] = set()
    for row in rows:
        signal_date = pd.Timestamp(row["period"]["end"]).normalize()
        selected = tuple(row["results"]["selected"])
        exposure = float(row["results"]["target_exposure"])
        weight = exposure / len(selected) if selected else 0.0
        targets[signal_date] = pd.Series({ticker: weight for ticker in selected})
        tickers.update(selected)
    if not targets or not tickers:
        return pd.Series(initial_equity, index=sessions, name="model_equity")

    prices: dict[str, pd.DataFrame] = {}
    for ticker in sorted(tickers):
        prices[ticker] = read_price_cache(
            repo_root / "data/raw/prices" / f"{ticker}.parquet",
            ticker=ticker,
            start=sessions[0],
            end=sessions[-1],
            mode="paper",
            paper_sessions=260,
        )
    target_weights = pd.DataFrame.from_dict(targets, orient="index").fillna(0.0)
    result = run_target_weight_backtest(
        prices,
        target_weights,
        cost_bps=cost_bps,
        initial_cash=initial_equity,
    )
    equity = result.equity.reindex(sessions)
    if equity.isna().any():
        raise ValueError("model equity is missing one or more forward sessions")
    return equity.rename("model_equity")


def _monthly_applied_fills(
    repo_root: Path,
    month: pd.Period,
    forward_start: pd.Timestamp,
) -> tuple[AppliedFill, ...]:
    calendar = xcals.get_calendar(
        "XNYS",
        start=month.start_time.normalize() - pd.Timedelta("7D"),
        end=month.end_time.normalize() + pd.Timedelta("7D"),
    )
    applied: list[AppliedFill] = []
    for path in sorted((repo_root / "paper/fills").glob("????-??-??.csv")):
        execution_date = pd.Timestamp(path.stem).normalize()
        if execution_date < forward_start or execution_date.to_period("M") != month:
            continue
        signal_date = calendar.previous_session(execution_date)
        tickets = {
            ticket.ticker: ticket
            for ticket in read_ticket_csv(
                repo_root / "paper/tickets" / f"{signal_date.date()}.csv"
            )
        }
        filled: dict[str, int] = {}
        for fill in read_fill_csv(path):
            ticket = tickets.get(fill.ticker)
            if ticket is None:
                raise ValueError(f"fill has no paper ticket: {fill.ticker}")
            filled[fill.ticker] = filled.get(fill.ticker, 0) + fill.qty
            if filled[fill.ticker] > ticket.qty:
                raise ValueError(f"filled quantity exceeds ticket for {fill.ticker}")
            impact = (
                (fill.fill_price - fill.official_open) * fill.qty + fill.commission
                if ticket.side == "buy"
                else (fill.official_open - fill.fill_price) * fill.qty + fill.commission
            )
            applied.append(
                AppliedFill(
                    ticker=fill.ticker,
                    side=ticket.side,
                    qty=fill.qty,
                    fill_price=fill.fill_price,
                    fill_time=fill.fill_time,
                    official_open=fill.official_open,
                    commission=fill.commission,
                    realized_cost_bps=realized_cost_bps(
                        fill.fill_price,
                        fill.official_open,
                        qty=fill.qty,
                        commission=fill.commission,
                    ),
                    execution_price_impact_usd=impact,
                )
            )
    return tuple(applied)


def _monthly_ticket_plans(
    repo_root: Path,
    month: pd.Period,
    forward_start: pd.Timestamp,
) -> tuple[TicketPlan, ...]:
    plans: list[TicketPlan] = []
    for row in _paper_run_rows(repo_root, forward_start, month.end_time.normalize()):
        as_of = pd.Timestamp(row["period"]["end"]).normalize()
        if as_of.to_period("M") != month:
            continue
        results = row["results"]
        skipped = tuple(
            SkippedCandidate(
                item["ticker"],
                item["reason"],
                item.get("replacement_ticker"),
            )
            for item in results.get("skipped_candidates", ())
        )
        plans.append(
            TicketPlan(
                tickets=(),
                skipped=skipped,
                target_positions=results.get("target_positions", {}),
                projected_cash=float(results["projected_cash"]),
                rounding_residual_usd=float(results.get("rounding_residual_usd", 0.0)),
                as_of=as_of,
            )
        )
    return tuple(plans)


def generate_monthly_report(
    repo_root: Path | str,
    month: str | pd.Period,
) -> MonthlyReportResult:
    """Generate one observed, forward-only P4 monthly report from repository ledgers."""
    root = Path(repo_root)
    period = pd.Period(month, freq="M")
    forward_start, initial_equity, assumed_cost = _paper_settings(root)
    monthly_sessions = _completed_month_sessions(period, forward_start)
    calendar = xcals.get_calendar(
        "XNYS",
        start=forward_start - pd.Timedelta("7D"),
        end=monthly_sessions[-1] + pd.Timedelta("7D"),
    )
    forward_sessions = calendar.sessions_in_range(forward_start, monthly_sessions[-1])
    paper_equity = _paper_equity_curve(
        root,
        monthly_sessions,
        forward_start=forward_start,
    )
    model_equity = _model_equity_curve(
        root,
        forward_sessions,
        initial_equity=initial_equity,
        cost_bps=assumed_cost,
    ).reindex(monthly_sessions)
    inputs = build_monthly_comparison_inputs(
        period,
        paper_equity,
        model_equity,
        applied_fills=_monthly_applied_fills(root, period, forward_start),
        ticket_plans=_monthly_ticket_plans(root, period, forward_start),
        assumed_cost_bps=assumed_cost,
    )
    report_path = write_monthly_report(
        root / "reports" / f"paper-{period}.md",
        inputs,
    )
    return MonthlyReportResult(inputs, paper_equity, model_equity, report_path)
