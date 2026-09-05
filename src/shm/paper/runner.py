"""Local-only orchestration for one paper rebalance date."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd
import yaml

from shm.config import ConfigBundle
from shm.data import create_snapshot, read_price_cache
from shm.experiments import (
    append_run_log,
    compute_file_hash,
    compute_params_hash,
    read_jsonl,
)
from shm.paper.core import (
    PAPER_MODE,
    PaperAccount,
    TicketPlan,
    generate_integer_share_tickets,
    paper_xnys_window,
    require_paper_mode,
    validate_paper_window,
    write_ticket_csv,
)
from shm.risk import build_risk_adjusted_target
from shm.signals import equal_weights, momentum_scores, rank_momentum
from shm.universe import (
    EligibilityResult,
    FrozenUniverse,
    filter_eligible_tickers,
    indexed_prices,
    load_frozen_universe,
    trailing_xnys_sessions,
    xnys_rebalance_dates,
)


@dataclass(frozen=True)
class PaperRebalanceResult:
    run_id: str
    as_of: pd.Timestamp
    params_hash: str
    universe_hash: str
    snapshot_id: str
    eligibility: EligibilityResult
    ranking: pd.Series
    selected: tuple[str, ...]
    exposure: float
    trend_exposure: float
    realized_vol: float
    vol_scale: float
    ticket_plan: TicketPlan
    ticket_path: Path
    log_path: Path


@dataclass(frozen=True)
class FrozenEligibleUniverse:
    params_hash: str
    universe_hash: str
    tickers: tuple[str, ...]


def _yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
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


def _load_frozen_eligible_universe(
    repo_root: Path,
    config: ConfigBundle,
    universe: FrozenUniverse,
) -> FrozenEligibleUniverse:
    payload = _yaml_mapping(repo_root / "config/p2_eligible.frozen.yaml")
    params_hash = compute_params_hash(
        config.params.model_dump(mode="json"),
        config.costs.per_side_bps.default,
    )
    universe_hash = compute_file_hash(repo_root / "config/universe.yaml")
    if payload.get("params_hash") != params_hash:
        raise ValueError("p2 eligible list params_hash does not match params.frozen.yaml")
    if payload.get("universe_hash") != universe_hash:
        raise ValueError("p2 eligible list universe_hash does not match universe.yaml")
    tickers = tuple(str(ticker).strip().upper() for ticker in payload.get("tickers", ()))
    if not tickers or len(tickers) != len(set(tickers)):
        raise ValueError("p2 eligible list must contain unique tickers")
    active = set(universe.active_tickers)
    if not set(tickers).issubset(active):
        raise ValueError("p2 eligible list contains tickers outside the active universe")
    if payload.get("eligible_count") != len(tickers):
        raise ValueError("p2 eligible list count does not match its tickers")
    if payload.get("excluded_count") != len(active) - len(tickers):
        raise ValueError("p2 excluded count does not match the active universe")
    return FrozenEligibleUniverse(params_hash, universe_hash, tickers)


def _paper_prices(
    repo_root: Path,
    tickers: set[str],
    as_of: pd.Timestamp,
) -> tuple[dict[str, pd.DataFrame], dict[str, Path]]:
    window = paper_xnys_window(as_of)
    cache_dir = repo_root / "data/raw/prices"
    prices: dict[str, pd.DataFrame] = {}
    paths: dict[str, Path] = {}
    for ticker in sorted(tickers):
        path = cache_dir / f"{ticker}.parquet"
        frame = read_price_cache(
            path,
            ticker=ticker,
            start=window[0],
            end=as_of,
            mode=PAPER_MODE,
            paper_sessions=len(window),
        )
        validate_paper_window(frame["date"], as_of=as_of)
        prices[ticker] = frame
        paths[ticker] = path
    return prices, paths


def _require_completed_session(signal_date: pd.Timestamp) -> None:
    calendar = xcals.get_calendar(
        "XNYS",
        start=signal_date - pd.Timedelta(days=1),
        end=signal_date + pd.Timedelta(days=1),
    )
    close = calendar.session_close(signal_date)
    if close > pd.Timestamp.now(tz="UTC"):
        raise ValueError(f"{signal_date.date()} is not a completed XNYS session")


def _requested_session(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("America/New_York").tz_localize(None)
    return timestamp.normalize()


def _require_benchmark_history(
    frame: pd.DataFrame,
    signal_date: pd.Timestamp,
    *,
    benchmark: str,
    sma_days: int,
) -> None:
    sessions = trailing_xnys_sessions(signal_date, sma_days)
    closes = indexed_prices(frame).reindex(sessions)["close"]
    if pd.isna(closes.iloc[-1]):
        raise ValueError(f"{benchmark} is missing close on {signal_date.date()}")
    if closes.isna().any():
        raise ValueError(f"{benchmark} lacks the frozen {sma_days}-session SMA window")


def _write_idempotent_ticket(path: Path, plan: TicketPlan) -> Path:
    content = plan.to_frame().to_csv(index=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite different paper ticket: {path}")
        return path
    return write_ticket_csv(path, plan)


def _git_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("paper runs require a git commit so git_sha is reproducible")
    return result.stdout.strip()


def _account_hash(account: PaperAccount) -> str:
    payload = {
        "cash": account.cash,
        "mode": account.mode,
        "positions": dict(sorted(account.positions.items())),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _append_paper_log(log_path: Path, record: dict[str, Any]) -> None:
    matches = [row for row in read_jsonl(log_path) if row.get("run_id") == record["run_id"]]
    if matches:
        stable_fields = (
            "git_sha",
            "params_hash",
            "universe_hash",
            "snapshot_id",
            "period",
            "results",
            "checks",
            "report",
        )
        if all(matches[-1].get(key) == record.get(key) for key in stable_fields):
            return
        raise ValueError(f"conflicting paper run record for run_id {record['run_id']}")
    append_run_log(log_path, record)


def run_paper_rebalance(
    account: PaperAccount,
    repo_root: Path | str,
    as_of: object,
    *,
    mode: str = PAPER_MODE,
) -> PaperRebalanceResult:
    """Build and persist one stock ticket file; no broker or backtest path is used."""
    require_paper_mode(mode)
    require_paper_mode(account.mode)
    root = Path(repo_root)
    config = _load_paper_config(root)
    signal_date = _requested_session(as_of)
    try:
        paper_xnys_window(signal_date, mode=mode)
    except ValueError:
        raise ValueError(f"{signal_date.date()} is not an XNYS session") from None
    _require_completed_session(signal_date)
    schedule = xnys_rebalance_dates(
        config.dates.dev_start,
        signal_date,
        warmup_trading_days=config.dates.warmup_trading_days,
        every_trading_days=config.dates.rebalance_every_trading_days,
    )
    if signal_date not in schedule:
        raise ValueError(f"{signal_date.date()} is not a configured 20-session rebalance date")

    universe = load_frozen_universe(root / "config")
    frozen = _load_frozen_eligible_universe(root, config, universe)
    paper_universe = FrozenUniverse(
        frozen_on=universe.frozen_on,
        rule_text=universe.rule_text,
        tickers=frozen.tickers,
        exclusions=frozenset(),
    )
    benchmark = config.params.risk.trend_filter.benchmark
    requested = set(paper_universe.active_tickers) | set(account.positions) | {benchmark}
    prices, price_paths = _paper_prices(root, requested, signal_date)
    _require_benchmark_history(
        prices[benchmark],
        signal_date,
        benchmark=benchmark,
        sma_days=config.params.risk.trend_filter.sma_days,
    )
    eligibility = filter_eligible_tickers(
        prices,
        paper_universe,
        signal_date,
        config=config.params.eligibility,
        lookback_trading_days=config.params.signal.lookback_trading_days,
    )
    if eligibility.below_minimum:
        raise ValueError(
            f"paper eligibility below minimum: {len(eligibility.eligible)} "
            f"< {config.params.eligibility.min_eligible_count}"
        )
    scores = momentum_scores(
        prices,
        eligibility.eligible,
        signal_date,
        lookback_trading_days=config.params.signal.lookback_trading_days,
        skip_trading_days=config.params.signal.skip_trading_days,
    )
    ranked_tickers = rank_momentum(scores, max(1, len(scores)))
    ranking = scores.reindex(ranked_tickers)
    selected = ranked_tickers[: config.params.signal.top_n]

    if selected:
        risk = build_risk_adjusted_target(
            equal_weights(selected),
            prices,
            signal_date,
            config=config.params.risk,
        )
        exposure = risk.exposure
        trend = risk.trend_exposure
        realized_vol = risk.realized_vol
        vol_scale = risk.vol_scale
    else:
        exposure = trend = realized_vol = vol_scale = 0.0

    prior_closes: dict[str, float] = {}
    for ticker in set(ranked_tickers) | set(account.positions):
        close = indexed_prices(prices[ticker])["close"].get(signal_date)
        if pd.notna(close):
            prior_closes[ticker] = float(close)
    target_count = max(1, len(selected))
    ticket_plan = generate_integer_share_tickets(
        account,
        ranked_tickers,
        prior_closes,
        target_count=target_count,
        exposure=exposure,
        estimated_cost_bps=config.costs.per_side_bps.default,
        as_of=signal_date,
    )
    git_sha = _git_sha(root)
    ticket_path = _write_idempotent_ticket(
        root / "paper/tickets" / f"{signal_date.date().isoformat()}.csv",
        ticket_plan,
    )
    snapshot = create_snapshot(
        price_paths,
        root / "data/snapshots/manifest.json",
    )
    run_id = f"paper-{signal_date:%Y%m%d}-{frozen.params_hash}"
    log_path = root / "experiments/log.jsonl"
    paper_window = paper_xnys_window(signal_date)
    account_hash = _account_hash(account)
    relative_ticket = ticket_path.relative_to(root).as_posix()
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": "paper",
        "phase": "P4",
        "git_sha": git_sha,
        "params_hash": frozen.params_hash,
        "params": config.params.model_dump(mode="json"),
        "universe_hash": frozen.universe_hash,
        "snapshot_id": snapshot.id,
        "period": {
            "start": paper_window[0].date().isoformat(),
            "end": signal_date.date().isoformat(),
        },
        "oos_used": False,
        "variant_index": 4,
        "prereg": "experiments/prereg/V04.md",
        "hypothesis": "Forward paper execution of frozen V04 remains operationally feasible.",
        "expected": "Generate a funded whole-share paper ticket without historical performance metrics.",
        "results": {
            "account_hash": account_hash,
            "eligible_count": len(eligibility.eligible),
            "selected": list(selected),
            "target_exposure": exposure,
            "ticket_count": len(ticket_plan.tickets),
            "projected_cash": ticket_plan.projected_cash,
        },
        "results_stress": {},
        "benchmark": {},
        "checks": {
            "PAPER_MODE": "PASS",
            "PAPER_WINDOW_260": "PASS",
            "FROZEN_IDENTITY": "PASS",
            "COMPLETED_REBALANCE_DATE": "PASS",
            "NO_LIVE_ENDPOINT": "PASS",
        },
        "status": "PAPER_TICKET_READY",
        "verdict": "PENDING_FORWARD_EVIDENCE",
        "report": relative_ticket,
    }
    _append_paper_log(log_path, record)
    return PaperRebalanceResult(
        run_id=run_id,
        as_of=signal_date,
        params_hash=frozen.params_hash,
        universe_hash=frozen.universe_hash,
        snapshot_id=snapshot.id,
        eligibility=eligibility,
        ranking=ranking,
        selected=selected,
        exposure=exposure,
        trend_exposure=trend,
        realized_vol=realized_vol,
        vol_scale=vol_scale,
        ticket_plan=ticket_plan,
        ticket_path=ticket_path,
        log_path=log_path,
    )
