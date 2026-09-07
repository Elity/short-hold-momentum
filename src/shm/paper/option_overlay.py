"""Paper-only option overlay orchestration after stock fills are recorded."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd
import yaml

from shm.config import ConfigBundle
from shm.data import read_price_cache
from shm.experiments import read_jsonl
from shm.options import (
    Candidate,
    Holding,
    OptionChainSource,
    OverlayPlan,
    build_overlay_plan,
    paper_ticket_rows,
    write_paper_ticket_csv,
)
from shm.options.planner import PAPER_TICKET_COLUMNS
from shm.paper.core import (
    PAPER_MODE,
    PaperAccount,
    read_fill_csv,
    read_ticket_csv,
    require_paper_mode,
)
from shm.paper.simulator import _next_completed_session, _session_date
from shm.universe import indexed_prices, xnys_rebalance_dates


@dataclass(frozen=True)
class PaperOptionOverlayResult:
    signal_date: pd.Timestamp
    as_of: pd.Timestamp
    next_rebalance_date: pd.Timestamp
    plan: OverlayPlan
    ticket_path: Path
    audit_path: Path


def _yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _load_paper_config(repo_root: Path) -> ConfigBundle:
    config_dir = repo_root / "config"
    return ConfigBundle.model_validate(
        {
            "dates": _yaml_mapping(config_dir / "dates.yaml"),
            "params": _yaml_mapping(config_dir / "params.frozen.yaml"),
            "costs": _yaml_mapping(config_dir / "costs.yaml"),
        }
    )


def _paper_signal_row(repo_root: Path, signal_date: pd.Timestamp) -> dict[str, Any]:
    rows = [
        row
        for row in read_jsonl(repo_root / "experiments/log.jsonl")
        if row.get("mode") == "paper"
        and row.get("status") == "PAPER_TICKET_READY"
        and pd.Timestamp(row["period"]["end"]).normalize() == signal_date
    ]
    if len(rows) != 1:
        raise ValueError(f"expected one paper signal row for {signal_date.date()}")
    if not rows[0].get("results", {}).get("ranking"):
        raise ValueError("paper signal row is missing the ranked option candidates")
    return rows[0]


def _average_cost_basis(
    repo_root: Path,
    end: pd.Timestamp,
    expected_positions: dict[str, int],
) -> dict[str, float]:
    shares: dict[str, int] = {}
    book_cost: dict[str, float] = {}
    for path in sorted((repo_root / "paper/fills").glob("????-??-??.csv")):
        execution_date = pd.Timestamp(path.stem).normalize()
        if execution_date > end:
            continue
        calendar = xcals.get_calendar(
            "XNYS",
            start=execution_date - pd.Timedelta("7D"),
            end=execution_date + pd.Timedelta("7D"),
        )
        signal_date = calendar.previous_session(execution_date)
        tickets = {
            ticket.ticker: ticket
            for ticket in read_ticket_csv(
                repo_root / "paper/tickets" / f"{signal_date.date()}.csv"
            )
        }
        for fill in read_fill_csv(path):
            ticket = tickets.get(fill.ticker)
            if ticket is None:
                raise ValueError(f"fill has no stock paper ticket: {fill.ticker}")
            quantity = fill.qty
            current_shares = shares.get(fill.ticker, 0)
            current_cost = book_cost.get(fill.ticker, 0.0)
            if ticket.side == "buy":
                shares[fill.ticker] = current_shares + quantity
                book_cost[fill.ticker] = (
                    current_cost + fill.fill_price * quantity + fill.commission
                )
                continue
            if quantity > current_shares:
                raise ValueError(f"sell fill exceeds reconstructed shares for {fill.ticker}")
            average = current_cost / current_shares
            remaining = current_shares - quantity
            if remaining:
                shares[fill.ticker] = remaining
                book_cost[fill.ticker] = current_cost - average * quantity
            else:
                shares.pop(fill.ticker, None)
                book_cost.pop(fill.ticker, None)

    reconstructed = {ticker: qty for ticker, qty in shares.items() if qty}
    if reconstructed != dict(sorted(expected_positions.items())):
        raise ValueError("paper fills do not reconstruct the current account positions")
    return {ticker: book_cost[ticker] / qty for ticker, qty in reconstructed.items()}


def _close_prices(
    repo_root: Path,
    tickers: set[str],
    as_of: pd.Timestamp,
) -> dict[str, float]:
    prices: dict[str, float] = {}
    for ticker in sorted(tickers):
        frame = read_price_cache(
            repo_root / "data/raw/prices" / f"{ticker}.parquet",
            ticker=ticker,
            start=as_of,
            end=as_of,
            mode=PAPER_MODE,
            paper_sessions=1,
        )
        close = indexed_prices(frame)["close"].get(as_of)
        if pd.isna(close):
            raise ValueError(f"{ticker} is missing close on {as_of.date()}")
        prices[ticker] = float(close)
    return prices


def _next_rebalance(config: ConfigBundle, signal_date: pd.Timestamp) -> pd.Timestamp:
    schedule = xnys_rebalance_dates(
        config.dates.dev_start,
        signal_date + pd.Timedelta("90D"),
        warmup_trading_days=config.dates.warmup_trading_days,
        every_trading_days=config.dates.rebalance_every_trading_days,
    )
    future = schedule[schedule > signal_date]
    if future.empty:
        raise ValueError("unable to determine the next rebalance date")
    return future[0]


def _write_idempotent_option_ticket(path: Path, plan: OverlayPlan) -> Path:
    content = pd.DataFrame(
        paper_ticket_rows(plan),
        columns=PAPER_TICKET_COLUMNS,
    ).to_csv(index=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite different option ticket: {path}")
        return path
    return write_paper_ticket_csv(plan, path)


def _write_idempotent_audit(path: Path, payload: dict[str, Any]) -> Path:
    content = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite different option audit: {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def run_paper_option_overlay(
    account: PaperAccount,
    repo_root: Path | str,
    signal_date: object,
    as_of: object,
    *,
    source: OptionChainSource | None = None,
    mode: str = PAPER_MODE,
) -> PaperOptionOverlayResult:
    """Generate a covered CC/CSP paper draft without submitting an order."""
    require_paper_mode(mode)
    require_paper_mode(account.mode)
    root = Path(repo_root)
    signal = _session_date(signal_date)
    account_date = _session_date(as_of)
    execution_date, _ = _next_completed_session(signal)
    if account_date != execution_date:
        raise ValueError("option overlay requires the next-session account snapshot")

    config = _load_paper_config(root)
    row = _paper_signal_row(root, signal)
    ranking = tuple(str(ticker).strip().upper() for ticker in row["results"]["ranking"])
    top_n = config.params.signal.top_n
    candidate_tickers = ranking[top_n : top_n + 5]
    requested = set(account.positions) | set(candidate_tickers)
    spots = _close_prices(root, requested, account_date)
    cost_basis = _average_cost_basis(
        root,
        account_date,
        dict(account.positions),
    )
    holdings = tuple(
        Holding(ticker, shares, spots[ticker], cost_basis[ticker])
        for ticker, shares in sorted(account.positions.items())
    )
    candidates = tuple(Candidate(ticker, spots[ticker]) for ticker in candidate_tickers)
    portfolio_equity = account.equity(
        {ticker: spots[ticker] for ticker in account.positions}
    )
    results = row["results"]
    target_exposure = float(results["target_exposure"])
    # Older V04 rows persist the combined target, which is zero when risk is off.
    trend_exposure = float(results.get("trend_exposure", target_exposure))
    stock_exposure = (portfolio_equity - account.cash) / portfolio_equity
    filled = {}
    for fill in read_fill_csv(root / "paper/fills" / f"{account_date.date()}.csv"):
        filled[fill.ticker] = filled.get(fill.ticker, 0) + fill.qty
    pending_exits = {
        ticket.ticker
        for ticket in read_ticket_csv(root / "paper/tickets" / f"{signal.date()}.csv")
        if ticket.side == "sell" and filled.get(ticket.ticker, 0) < ticket.qty
    }
    allow_new_risk = trend_exposure > 0 and target_exposure > 0
    next_rebalance_date = _next_rebalance(config, signal)
    plan = build_overlay_plan(
        holdings=holdings,
        candidates=candidates,
        portfolio_equity=portfolio_equity,
        available_cash=account.cash,
        as_of=account_date.date(),
        next_rebalance_date=next_rebalance_date.date(),
        source=source,
        allow_new_risk=allow_new_risk,
        pending_exit_symbols=pending_exits,
        stock_exposure=stock_exposure,
        max_total_exposure=target_exposure,
    )
    ticket_path = _write_idempotent_option_ticket(
        root / "paper/tickets" / f"{account_date.date()}-options.csv",
        plan,
    )
    audit_path = _write_idempotent_audit(
        root / "paper/options" / f"{account_date.date()}.json",
        {
            "mode": PAPER_MODE,
            "paper_only": True,
            "signal_date": str(signal.date()),
            "as_of": str(account_date.date()),
            "next_rebalance_date": str(next_rebalance_date.date()),
            "portfolio_equity": portfolio_equity,
            "available_cash": account.cash,
            "risk_gate": {
                "allow_new_risk": allow_new_risk,
                "pending_exit_symbols": sorted(pending_exits),
                "stock_exposure": stock_exposure,
                "max_total_exposure": target_exposure,
                "source": "saved_signal_results",
            },
            "income_recognized": False,
            "orders": [asdict(order) for order in plan.orders],
            "skipped": [asdict(item) for item in plan.skipped],
            "summary": asdict(plan.summary),
            "ticket": ticket_path.relative_to(root).as_posix(),
        },
    )
    return PaperOptionOverlayResult(
        signal,
        account_date,
        next_rebalance_date,
        plan,
        ticket_path,
        audit_path,
    )
