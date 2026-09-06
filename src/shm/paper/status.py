"""Read-only P4 progress and Gate-readiness audit."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from shm.paper.option_overlay import _load_paper_config, _yaml_mapping
from shm.paper.core import PaperAccount, read_fill_csv, read_ticket_csv
from shm.universe import xnys_rebalance_dates


_STOCK_TICKET = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")
_MISSED_CYCLE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-fill)?\.json$")
_MONTHLY_REPORT = re.compile(r"^paper-(\d{4}-\d{2})\.md$")


@dataclass(frozen=True)
class PaperProgress:
    forward_start: pd.Timestamp
    completed_cycles: tuple[str, ...]
    pending_cycles: tuple[str, ...]
    missed_cycles: tuple[str, ...]
    monthly_reports: tuple[str, ...]
    next_rebalance_date: pd.Timestamp
    missing_owner_notes: tuple[str, ...]
    p4_evidence_complete: bool
    gate_ready: bool
    gate_blockers: tuple[str, ...]


def _next_session(signal_date: pd.Timestamp) -> pd.Timestamp:
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal_date - pd.Timedelta("7D"),
        end=signal_date + pd.Timedelta("14D"),
    )
    if not calendar.is_session(signal_date):
        raise ValueError(f"paper ticket date is not an XNYS session: {signal_date.date()}")
    return calendar.next_session(signal_date)


def _cycle_status(
    repo_root: Path,
    forward_start: pd.Timestamp,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    completed: list[str] = []
    pending: list[str] = []
    for path in sorted((repo_root / "paper/tickets").glob("*.csv")):
        match = _STOCK_TICKET.fullmatch(path.name)
        if match is None:
            continue
        signal_date = pd.Timestamp(match.group(1)).normalize()
        if signal_date < forward_start:
            continue
        read_ticket_csv(path)
        execution_date = _next_session(signal_date)
        fill_path = repo_root / "paper/fills" / f"{execution_date.date()}.csv"
        account_path = repo_root / "paper/accounts" / f"{execution_date.date()}.json"
        cycle_complete = fill_path.exists() and account_path.exists()
        if cycle_complete:
            read_fill_csv(fill_path)
            payload = json.loads(account_path.read_text(encoding="utf-8"))
            if pd.Timestamp(payload.get("as_of")).normalize() != execution_date:
                raise ValueError(f"account snapshot date does not match {execution_date.date()}")
            PaperAccount(
                cash=payload["cash"],
                positions=payload.get("positions", {}),
                mode=payload.get("mode", "paper"),
            )
        if cycle_complete:
            completed.append(str(signal_date.date()))
        elif not (repo_root / "paper/missed" / f"{signal_date.date()}-fill.json").exists():
            pending.append(str(signal_date.date()))
    return tuple(completed), tuple(pending)


def _monthly_reports(repo_root: Path, forward_start: pd.Timestamp) -> tuple[str, ...]:
    start_month = forward_start.to_period("M")
    months = []
    for path in sorted((repo_root / "reports").glob("paper-*.md")):
        match = _MONTHLY_REPORT.fullmatch(path.name)
        if match is None:
            continue
        month = pd.Period(match.group(1), freq="M")
        if month >= start_month:
            months.append(str(month))
    return tuple(months)


def _missed_cycles(repo_root: Path, forward_start: pd.Timestamp) -> tuple[str, ...]:
    missed: set[str] = set()
    for path in sorted((repo_root / "paper/missed").glob("*.json")):
        match = _MISSED_CYCLE.fullmatch(path.name)
        if match is None:
            continue
        signal_date = pd.Timestamp(match.group(1)).normalize()
        if signal_date >= forward_start:
            missed.add(str(signal_date.date()))
    return tuple(sorted(missed))


def _next_rebalance(
    repo_root: Path,
    forward_start: pd.Timestamp,
    completed: tuple[str, ...],
    pending: tuple[str, ...],
    missed: tuple[str, ...],
) -> pd.Timestamp:
    config = _load_paper_config(repo_root)
    observed = [pd.Timestamp(value) for value in (*completed, *pending, *missed)]
    after = max(observed, default=forward_start - pd.Timedelta("1D"))
    schedule = xnys_rebalance_dates(
        config.dates.dev_start,
        after + pd.Timedelta("365D"),
        warmup_trading_days=config.dates.warmup_trading_days,
        every_trading_days=config.dates.rebalance_every_trading_days,
    )
    future = schedule[(schedule >= forward_start) & (schedule > after)]
    if future.empty:
        raise ValueError("unable to determine the next paper rebalance date")
    return future[0]


def build_paper_progress(repo_root: Path | str) -> PaperProgress:
    """Audit P4 evidence without creating or changing any trading artifact."""
    root = Path(repo_root)
    paper_config = _yaml_mapping(root / "paper/p4.yaml")
    if paper_config.get("mode") != "paper":
        raise PermissionError("P4 status requires mode: paper")
    forward_start = pd.Timestamp(paper_config["forward_test_start"]).normalize()
    completed, pending = _cycle_status(root, forward_start)
    missed = _missed_cycles(root, forward_start)
    monthly_reports = _monthly_reports(root, forward_start)
    missing_notes = tuple(
        f"docs/why/P{phase}.md"
        for phase in range(1, 5)
        if not (root / f"docs/why/P{phase}.md").exists()
    )
    evidence_complete = len(completed) >= 3 and len(monthly_reports) >= 3
    blockers: list[str] = []
    if len(completed) < 3:
        blockers.append(f"paper cycles {len(completed)}/3")
    if len(monthly_reports) < 3:
        blockers.append(f"monthly reports {len(monthly_reports)}/3")
    if missing_notes:
        blockers.append("missing owner phase notes")
    if paper_config.get("provider") == "local_offline_simulator":
        blockers.append("execution cost is simulated, not broker-observed")
    if not (root / "config/live.yaml").exists():
        blockers.append("config/live.yaml is owner-only and absent")
    return PaperProgress(
        forward_start=forward_start,
        completed_cycles=completed,
        pending_cycles=pending,
        missed_cycles=missed,
        monthly_reports=monthly_reports,
        next_rebalance_date=_next_rebalance(root, forward_start, completed, pending, missed),
        missing_owner_notes=missing_notes,
        p4_evidence_complete=evidence_complete,
        gate_ready=evidence_complete and not blockers,
        gate_blockers=tuple(blockers),
    )
