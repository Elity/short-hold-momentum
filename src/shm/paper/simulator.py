"""Deterministic local fill simulation for paper stock tickets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from shm.data import read_price_cache
from shm.paper.core import (
    PAPER_MODE,
    Fill,
    FillIngestionResult,
    PaperAccount,
    fills_to_frame,
    ingest_fills,
    read_ticket_csv,
    require_paper_mode,
    write_fill_csv,
)
from shm.universe import indexed_prices


@dataclass(frozen=True)
class SimulatedFillResult:
    signal_date: pd.Timestamp
    execution_date: pd.Timestamp
    fill_path: Path
    ingestion: FillIngestionResult


def _session_date(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("America/New_York").tz_localize(None)
    return timestamp.normalize()


def _next_completed_session(signal_date: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal_date - pd.Timedelta(days=1),
        end=signal_date + pd.Timedelta(days=10),
    )
    if not calendar.is_session(signal_date):
        raise ValueError(f"{signal_date.date()} is not an XNYS session")
    execution_date = calendar.next_session(signal_date)
    if calendar.session_close(execution_date) > pd.Timestamp.now(tz="UTC"):
        raise ValueError(f"{execution_date.date()} is not a completed XNYS session")
    execution_open = calendar.session_open(execution_date)
    local_open = execution_open.tz_convert("America/New_York").tz_localize(None)
    return execution_date, local_open


def _write_idempotent_fills(path: Path, fills: tuple[Fill, ...]) -> Path:
    content = fills_to_frame(fills).to_csv(index=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite different paper fills: {path}")
        return path
    return write_fill_csv(path, fills)


def simulate_next_open_fills(
    account: PaperAccount,
    repo_root: Path | str,
    signal_date: object,
    *,
    ticket_path: Path | str | None = None,
    mode: str = PAPER_MODE,
) -> SimulatedFillResult:
    """Fill stock MOO paper tickets at the next official open, locally only."""
    require_paper_mode(mode)
    require_paper_mode(account.mode)
    root = Path(repo_root)
    signal = _session_date(signal_date)
    execution_date, execution_open = _next_completed_session(signal)
    source = (
        root / "paper/tickets" / f"{signal.date().isoformat()}.csv"
        if ticket_path is None
        else Path(ticket_path)
    )
    if not source.is_absolute():
        source = root / source
    tickets = read_ticket_csv(source)
    if any(
        ticket.order_type != "market_on_open" or ticket.time_in_force != "opg"
        for ticket in tickets
    ):
        raise ValueError("local fill simulation accepts stock MOO/OPG tickets only")

    fills: list[Fill] = []
    for ticket in tickets:
        frame = read_price_cache(
            root / "data/raw/prices" / f"{ticket.ticker}.parquet",
            ticker=ticket.ticker,
            start=execution_date,
            end=execution_date,
            mode=PAPER_MODE,
            paper_sessions=1,
        )
        open_price = indexed_prices(frame)["open"].get(execution_date)
        if pd.isna(open_price):
            raise ValueError(
                f"{ticket.ticker} is missing official open on {execution_date.date()}"
            )
        fills.append(
            Fill(
                ticket.ticker,
                ticket.qty,
                float(open_price),
                execution_open,
                float(open_price),
            )
        )

    fill_items = tuple(fills)
    ingestion = ingest_fills(account, tickets, fill_items)
    fill_path = _write_idempotent_fills(
        root / "paper/fills" / f"{execution_date.date().isoformat()}.csv",
        fill_items,
    )
    return SimulatedFillResult(signal, execution_date, fill_path, ingestion)
