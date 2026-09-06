from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from shm.config import load_config_bundle
from shm.paper.status import build_paper_progress
from shm.universe import load_frozen_universe


StepReporter = Callable[[str, str, str, datetime, datetime], None]
CommandRunner = Callable[[Sequence[str], Path], str]


class MissedForwardWindow(RuntimeError):
    """Raised when a forward-only artifact can no longer be created honestly."""


@dataclass(frozen=True)
class WorkflowResult:
    market_session: str
    actions: tuple[str, ...]

    @property
    def summary(self) -> str:
        if not self.actions:
            return f"{self.market_session}: no actionable P4 change"
        return f"{self.market_session}: " + "; ".join(self.actions)


def latest_completed_session(now: datetime | pd.Timestamp | None = None) -> pd.Timestamp:
    stamp = pd.Timestamp(now or datetime.now(UTC))
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    day = stamp.normalize().tz_localize(None)
    calendar = xcals.get_calendar(
        "XNYS",
        start=day - pd.Timedelta(days=14),
        end=day + pd.Timedelta(days=2),
    )
    sessions = calendar.sessions
    completed = [session for session in sessions if calendar.session_close(session) <= stamp]
    if not completed:
        raise RuntimeError("unable to determine the latest completed XNYS session")
    return pd.Timestamp(completed[-1]).normalize()


def next_session(signal_date: str | pd.Timestamp) -> pd.Timestamp:
    signal = pd.Timestamp(signal_date).normalize()
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal - pd.Timedelta("1D"),
        end=signal + pd.Timedelta("10D"),
    )
    return pd.Timestamp(calendar.next_session(signal)).normalize()


def _default_command_runner(command: Sequence[str], cwd: Path) -> str:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode != 0:
        raise RuntimeError(output or f"command failed with exit code {result.returncode}")
    return output


def _latest_account(repo_root: Path, on_or_before: pd.Timestamp) -> Path:
    candidates: list[tuple[pd.Timestamp, Path]] = []
    for path in (repo_root / "paper/accounts").glob("*.json"):
        try:
            date = pd.Timestamp(path.stem).normalize()
        except ValueError:
            continue
        if date <= on_or_before:
            candidates.append((date, path))
    if not candidates:
        raise FileNotFoundError(f"no paper account exists on or before {on_or_before.date()}")
    return max(candidates, key=lambda item: item[0])[1]


def _forward_start(repo_root: Path) -> pd.Timestamp:
    import yaml

    payload = yaml.safe_load((repo_root / "paper/p4.yaml").read_text(encoding="utf-8"))
    return pd.Timestamp(payload["forward_test_start"]).normalize()


def _has_paper_log(repo_root: Path, signal_date: pd.Timestamp) -> bool:
    log_path = repo_root / "experiments/log.jsonl"
    if not log_path.exists():
        return False
    expected = str(signal_date.date())
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (
            record.get("mode") == "paper"
            and record.get("status") == "PAPER_TICKET_READY"
            and record.get("period", {}).get("end") == expected
        ):
            return True
    return False


def _account_matches(path: Path, execution_date: pd.Timestamp) -> bool:
    if not path.exists():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return pd.Timestamp(payload.get("as_of")).normalize() == execution_date


def _completed_report_months(repo_root: Path, market_session: pd.Timestamp) -> tuple[str, ...]:
    start = _forward_start(repo_root).to_period("M")
    end = market_session.to_period("M")
    completed: list[str] = []
    for period in pd.period_range(start, end, freq="M"):
        month_start = period.start_time.normalize()
        month_end = period.end_time.normalize()
        calendar = xcals.get_calendar(
            "XNYS",
            start=month_start - pd.Timedelta("7D"),
            end=month_end + pd.Timedelta("7D"),
        )
        sessions = calendar.sessions_in_range(month_start, month_end)
        if len(sessions) >= 2 and pd.Timestamp(sessions[-1]).normalize() <= market_session:
            completed.append(str(period))
    return tuple(completed)


def validate_required_price_caches(repo_root: Path) -> str:
    config = load_config_bundle(repo_root / "config")
    universe = load_frozen_universe(repo_root / "config")
    required = set(universe.active_tickers) | {config.params.risk.trend_filter.benchmark}
    cache_dir = repo_root / "data/raw/prices"
    missing = sorted(
        ticker
        for ticker in required
        if not (cache_dir / f"{ticker}.parquet").is_file()
        or (cache_dir / f"{ticker}.parquet").stat().st_size == 0
    )
    if missing:
        for ticker in missing:
            (cache_dir / f"{ticker}.coverage.json").unlink(missing_ok=True)
        raise RuntimeError("required price caches missing after update: " + ", ".join(missing))
    return f"required price caches available: {len(required)}"


def run_daily_workflow(
    repo_root: Path | str,
    *,
    now: datetime | pd.Timestamp | None = None,
    reporter: StepReporter | None = None,
    command_runner: CommandRunner = _default_command_runner,
) -> WorkflowResult:
    root = Path(repo_root).resolve()
    market_session = latest_completed_session(now)
    actions: list[str] = []

    def run_step(name: str, args: Sequence[str]) -> str:
        started = datetime.now(UTC)
        try:
            output = command_runner([sys.executable, "-m", "shm", *args], root)
        except Exception as exc:
            finished = datetime.now(UTC)
            if reporter:
                reporter(name, "failed", str(exc), started, finished)
            raise
        finished = datetime.now(UTC)
        if reporter:
            reporter(name, "success", output, started, finished)
        return output

    def write_marker(name: str, path: Path, payload: dict[str, str]) -> None:
        started = datetime.now(UTC)
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                temporary = path.with_suffix(path.suffix + ".tmp")
                temporary.write_text(rendered, encoding="utf-8")
                temporary.replace(path)
        except Exception as exc:
            finished = datetime.now(UTC)
            if reporter:
                reporter(name, "failed", str(exc), started, finished)
            raise
        finished = datetime.now(UTC)
        if reporter:
            reporter(name, "success", str(path.relative_to(root)), started, finished)

    def run_local_step(name: str, operation: Callable[[], str]) -> str:
        started = datetime.now(UTC)
        try:
            output = operation()
        except Exception as exc:
            finished = datetime.now(UTC)
            if reporter:
                reporter(name, "failed", str(exc), started, finished)
            raise
        finished = datetime.now(UTC)
        if reporter:
            reporter(name, "success", output, started, finished)
        return output

    run_step("data-update", ["data", "update", "--through-oos", "--skip-pit"])
    run_local_step("validate-price-cache", lambda: validate_required_price_caches(root))

    forward_start = _forward_start(root)
    for ticket in sorted((root / "paper/tickets").glob("????-??-??.csv")):
        signal = pd.Timestamp(ticket.stem).normalize()
        if signal < forward_start or _has_paper_log(root, signal):
            continue
        account = _latest_account(root, signal)
        run_step(
            f"recover-rebalance-audit-{signal.date()}",
            [
                "paper",
                "rebalance",
                "--repo-root",
                str(root),
                "--account",
                str(account),
                "--as-of",
                str(signal.date()),
            ],
        )
        actions.append(f"recovered ticket audit {signal.date()}")

    progress = build_paper_progress(root)
    next_rebalance = progress.next_rebalance_date.normalize()
    while next_rebalance < market_session:
        write_marker(
            f"missed-rebalance-{next_rebalance.date()}",
            root / "paper/missed" / f"{next_rebalance.date()}.json",
            {
                "event": "rebalance",
                "signal_date": str(next_rebalance.date()),
                "detected_market_session": str(market_session.date()),
                "detected_at": datetime.now(UTC).isoformat(),
                "reason": "signal session was no longer the latest completed XNYS session",
            },
        )
        actions.append(f"missed rebalance {next_rebalance.date()}")
        progress = build_paper_progress(root)
        next_rebalance = progress.next_rebalance_date.normalize()
    if next_rebalance == market_session:
        account = _latest_account(root, next_rebalance)
        run_step(
            f"rebalance-{next_rebalance.date()}",
            [
                "paper",
                "rebalance",
                "--repo-root",
                str(root),
                "--account",
                str(account),
                "--as-of",
                str(next_rebalance.date()),
            ],
        )
        actions.append(f"ticket {next_rebalance.date()}")

    progress = build_paper_progress(root)
    for signal_text in progress.pending_cycles:
        signal = pd.Timestamp(signal_text).normalize()
        execution = next_session(signal)
        fill_path = root / "paper/fills" / f"{execution.date()}.csv"
        output_account = root / "paper/accounts" / f"{execution.date()}.json"
        recover_account = fill_path.exists() and not output_account.exists()
        if execution < market_session and not recover_account:
            marker = root / "paper/missed" / f"{signal.date()}-fill.json"
            write_marker(
                f"missed-fill-{signal.date()}",
                marker,
                {
                    "event": "fill",
                    "signal_date": str(signal.date()),
                    "execution_date": str(execution.date()),
                    "detected_market_session": str(market_session.date()),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "reason": "execution session was no longer the latest completed XNYS session",
                },
            )
            actions.append(f"missed fill {execution.date()}")
            continue
        if execution != market_session and not recover_account:
            continue
        account = _latest_account(root, signal)
        run_step(
            f"simulate-fills-{signal.date()}",
            [
                "paper",
                "simulate-fills",
                "--repo-root",
                str(root),
                "--account",
                str(account),
                "--signal-date",
                str(signal.date()),
                "--output-account",
                str(output_account),
            ],
        )
        action = "recovered account" if recover_account else "fills"
        actions.append(f"{action} {execution.date()}")

    for ticket in sorted((root / "paper/tickets").glob("????-??-??.csv")):
        signal = pd.Timestamp(ticket.stem).normalize()
        if signal < forward_start:
            continue
        execution = next_session(signal)
        fill = root / "paper/fills" / f"{execution.date()}.csv"
        account = root / "paper/accounts" / f"{execution.date()}.json"
        option_audit = root / "paper/options" / f"{execution.date()}.json"
        option_missed = root / "paper/missed" / f"{signal.date()}-option.json"
        if not fill.exists() or not account.exists() or option_audit.exists() or option_missed.exists():
            continue
        if not _account_matches(account, execution):
            raise ValueError(f"account snapshot date does not match {execution.date()}")
        if execution < market_session:
            write_marker(
                f"missed-option-overlay-{signal.date()}",
                option_missed,
                {
                    "event": "option-overlay",
                    "signal_date": str(signal.date()),
                    "execution_date": str(execution.date()),
                    "detected_market_session": str(market_session.date()),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "reason": "optional overlay was not created in its execution-session window",
                },
            )
            actions.append(f"skipped stale option overlay {execution.date()}")
            continue
        if execution != market_session:
            continue
        run_step(
            f"option-overlay-{signal.date()}",
            [
                "paper",
                "option-overlay",
                "--repo-root",
                str(root),
                "--account",
                str(account),
                "--signal-date",
                str(signal.date()),
            ],
        )
        actions.append(f"option overlay {execution.date()}")

    for month in _completed_report_months(root, market_session):
        report = root / "reports" / f"paper-{month}.md"
        if report.exists():
            continue
        run_step(
            f"monthly-report-{month}",
            ["paper", "monthly-report", "--repo-root", str(root), "--month", month],
        )
        actions.append(f"monthly report {month}")

    status = run_step("paper-status", ["paper", "status", "--repo-root", str(root)])
    if status:
        actions.append(status.splitlines()[-1])
    return WorkflowResult(str(market_session.date()), tuple(actions))
