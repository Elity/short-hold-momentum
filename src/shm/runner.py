from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd

from shm.checks import (
    CheckResult,
    check_constraints,
    check_cost_fragility,
    check_next_session_execution,
    check_one_year_dependency,
    check_spy_annual_returns,
    check_survivorship,
    check_too_good,
    compose_status,
    download_stooq_spy,
    download_stooq_ticker,
)
from shm.config import ConfigBundle, load_config_bundle
from shm.data import create_snapshot, update_price_caches
from shm.experiments import (
    append_run_log,
    compute_file_hash,
    compute_params_hash,
    load_approved_prereg,
    reserve_variant,
)
from shm.pipeline import (
    SignalPlan,
    build_signal_plan,
    check_plan_no_lookahead,
    load_pit_history,
    pit_price_coverage,
    pit_tickers_for_period,
    pit_universe_provider,
    prepare_cached_data,
    run_cost_scenarios,
)
from shm.report import calculate_metrics, render_report, write_report, yearly_returns
from shm.universe import load_frozen_universe, trailing_xnys_sessions, xnys_rebalance_dates


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    status: str
    report_path: Path
    daily_path: Path


@dataclass(frozen=True)
class DataUpdateSummary:
    core_total: int
    core_failures: int
    pit_total: int
    pit_failures: int


def _git_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("backtests require a git commit so git_sha is reproducible")
    return result.stdout.strip()


def _warmup_start(config: ConfigBundle) -> pd.Timestamp:
    first_signal = xnys_rebalance_dates(
        config.dates.dev_start,
        config.dates.dev_end,
        warmup_trading_days=config.dates.warmup_trading_days,
        every_trading_days=config.dates.rebalance_every_trading_days,
    )[0]
    return trailing_xnys_sessions(first_signal, config.dates.warmup_trading_days + 1)[0]


def _phase_for_prereg(prereg_file: Path) -> str:
    return "P1" if prereg_file.stem == "V00" else "P2"


def _verdict_for_status(status: str) -> str:
    if status == "FAIL":
        return "反驳"
    if status in {"INCONCLUSIVE", "SUSPECT"}:
        return "无法判定"
    return "支持"


def update_development_data(
    *,
    config_dir: Path | str,
    cache_dir: Path | str,
    include_pit: bool = True,
) -> DataUpdateSummary:
    config = load_config_bundle(config_dir)
    universe = load_frozen_universe(config_dir)
    benchmark = config.params.risk.trend_filter.benchmark
    tickers = list(universe.active_tickers)
    if benchmark not in tickers:
        tickers.append(benchmark)
    core_results = update_price_caches(
        tickers,
        cache_dir,
        start=_warmup_start(config).date(),
        end=config.dates.dev_end,
        failures_path=Path(cache_dir).parent / "_failures.jsonl",
    )
    pit_results = {}
    if include_pit:
        history = load_pit_history(Path(config_dir).parent / "data/reference/sp500_history.csv")
        pit_tickers = pit_tickers_for_period(history, config.dates.dev_start, config.dates.dev_end)
        extras = [ticker for ticker in pit_tickers if ticker not in set(tickers)]
        pit_results = update_price_caches(
            extras,
            cache_dir,
            start=_warmup_start(config).date(),
            end=config.dates.dev_end,
            failures_path=Path(cache_dir).parent / "_failures.jsonl",
            retries=1,
        )
    return DataUpdateSummary(
        core_total=len(core_results),
        core_failures=sum(result.failed for result in core_results.values()),
        pit_total=len(pit_results),
        pit_failures=sum(result.failed for result in pit_results.values()),
    )


def _slice_for_engine(
    prices: dict[str, pd.DataFrame], start: object, end: object
) -> dict[str, pd.DataFrame]:
    start_stamp, end_stamp = pd.Timestamp(start), pd.Timestamp(end)
    return {
        ticker: frame.loc[
            pd.to_datetime(frame["date"]).between(start_stamp, end_stamp, inclusive="both")
        ].copy()
        for ticker, frame in prices.items()
    }


def _benchmark_plan(first_signal: pd.Timestamp, ticker: str) -> SignalPlan:
    targets = pd.DataFrame({ticker: [1.0]}, index=[first_signal])
    return SignalPlan(targets, pd.DataFrame(index=[first_signal]), {first_signal: (ticker,)}, False)


def _quality_check(
    prepared_quality: dict[str, object],
    plan: SignalPlan,
    dq05: CheckResult,
) -> CheckResult:
    quarantined = [ticker for ticker, report in prepared_quality.items() if report.quarantine]
    missing = [
        ticker for ticker, report in prepared_quality.items() if report.exclude_for_missing_history
    ]
    zero_volume = [ticker for ticker, report in prepared_quality.items() if report.zero_volume_flag]
    detail = (
        f"quarantine={len(quarantined)}, missing_history={len(missing)}, "
        f"zero_volume_flags={len(zero_volume)}; {dq05.detail}"
    )
    if dq05.status == "INCONCLUSIVE" or plan.inconclusive:
        return CheckResult("INCONCLUSIVE", detail)
    return CheckResult("PASS", detail)


def _realized_trade_pnl(transactions: pd.DataFrame) -> pd.DataFrame:
    positions: dict[str, tuple[float, float]] = {}
    realized: list[dict[str, object]] = []
    for row in transactions.sort_values("execution_date").itertuples(index=False):
        quantity, basis = positions.get(row.ticker, (0.0, 0.0))
        if row.side == "buy":
            positions[row.ticker] = (
                quantity + row.quantity,
                basis + row.notional + row.cost,
            )
            continue
        sold = min(quantity, row.quantity)
        average_basis = basis / quantity if quantity else 0.0
        pnl = row.notional - row.cost - sold * average_basis
        realized.append(
            {
                "ticker": row.ticker,
                "execution_date": row.execution_date,
                "quantity": sold,
                "pnl": pnl,
            }
        )
        remaining = quantity - sold
        positions[row.ticker] = (remaining, average_basis * remaining)
    if not realized:
        return pd.DataFrame(columns=["ticker", "execution_date", "quantity", "pnl"])
    return pd.DataFrame(realized).sort_values("pnl", ascending=False).head(10)


def _write_suspect_checklist(
    *,
    path: Path,
    full_lookahead: CheckResult,
    prices: dict[str, pd.DataFrame],
    universe_tickers: tuple[str, ...],
    start: str,
    end: str,
    ticker_second_source_loader: Callable[[str, str, str], pd.DataFrame],
    execution_check: CheckResult,
    strategy_metrics: object,
    stress_metrics: object,
    survivorship_check: CheckResult,
    one_year_check: CheckResult,
    transactions: pd.DataFrame,
) -> None:
    comparisons: list[str] = []
    candidates = [ticker for ticker in universe_tickers if ticker in prices and not prices[ticker].empty][:10]
    for ticker in candidates:
        try:
            secondary = ticker_second_source_loader(ticker, start, end)
            result = check_spy_annual_returns(prices[ticker], secondary)
            comparisons.append(f"- {ticker}: {result.status} — {result.detail}")
        except Exception as error:
            comparisons.append(f"- {ticker}: UNAVAILABLE — {error}")
    trades = _realized_trade_pnl(transactions)
    trade_lines = ["| Ticker | Exit date | Quantity | Realized P&L | Why it won |", "|---|---|---:|---:|---|"]
    for row in trades.itertuples(index=False):
        trade_lines.append(
            f"| {row.ticker} | {pd.Timestamp(row.execution_date).date()} | {row.quantity:.4f} | "
            f"{row.pnl:.2f} | owner review required |"
        )
    if trades.empty:
        trade_lines.append("| — | — | — | — | no realized trades |")
    content = [
        "# INV-08 suspect checklist",
        "",
        f"- B-01 all-date truncation: {full_lookahead.status} — {full_lookahead.detail}",
        f"- B-03 next-session execution: {execution_check.status} — {execution_check.detail}",
        f"- B-04 25 bps rerun: CAGR {stress_metrics.cagr:.2%} vs default {strategy_metrics.cagr:.2%}",
        f"- B-05 PIT rerun: {survivorship_check.status} — {survivorship_check.detail}",
        f"- B-06 best-year removal: {one_year_check.status} — {one_year_check.detail}",
        "",
        "## B-02 adjusted-price spot checks",
        "",
        *(comparisons or ["- No eligible ticker data available."]),
        "",
        "## B-07 top realized trades",
        "",
        *trade_lines,
        "",
        "Owner must fill the final column and decide at HC-04.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(content), encoding="utf-8")


def run_development_backtest(
    *,
    repo_root: Path | str,
    prereg_path: Path | str,
    second_source_loader: Callable[[str, str], pd.DataFrame] = download_stooq_spy,
    ticker_second_source_loader: Callable[[str, str, str], pd.DataFrame] = download_stooq_ticker,
) -> RunOutcome:
    root = Path(repo_root)
    prereg_file = Path(prereg_path)
    if not prereg_file.is_absolute():
        prereg_file = root / prereg_file
    config_dir = root / "config"
    config = load_config_bundle(config_dir)
    universe = load_frozen_universe(config_dir)
    prereg = load_approved_prereg(prereg_file)
    params = config.params.model_dump(mode="json")
    params_hash = compute_params_hash(params, config.costs.per_side_bps.default)
    phase = _phase_for_prereg(prereg_file)
    variant_index = reserve_variant(
        root / "experiments/log.jsonl", params_hash=params_hash, phase=phase
    )
    git_sha = _git_sha(root)

    history = load_pit_history(root / "data/reference/sp500_history.csv")
    pit_tickers = pit_tickers_for_period(history, config.dates.dev_start, config.dates.dev_end)

    prepared = prepare_cached_data(
        config=config,
        universe=universe,
        cache_dir=root / "data/raw/prices",
        start=_warmup_start(config),
        end=config.dates.dev_end,
        additional_tickers=pit_tickers,
    )
    snapshot = create_snapshot(prepared.paths, root / "data/snapshots/manifest.json")
    plan = build_signal_plan(
        prices=prepared.prices,
        universe=universe,
        config=config,
        quarantined=frozenset(),
    )
    execution_prices = _slice_for_engine(
        prepared.prices, config.dates.dev_start, config.dates.dev_end
    )
    runs = run_cost_scenarios(
        execution_prices,
        plan,
        default_cost_bps=config.costs.per_side_bps.default,
        stress_cost_bps=config.costs.per_side_bps.stress,
    )
    strategy_metrics = calculate_metrics(
        runs.default.equity,
        daily_weights=runs.default.weights,
        target_weights=plan.target_weights,
    )
    stress_metrics = calculate_metrics(
        runs.stress.equity,
        daily_weights=runs.stress.weights,
        target_weights=plan.target_weights,
    )

    benchmark_ticker = config.params.risk.trend_filter.benchmark
    benchmark_plan = _benchmark_plan(plan.target_weights.index[0], benchmark_ticker)
    benchmark_run = run_cost_scenarios(
        {benchmark_ticker: execution_prices[benchmark_ticker]},
        benchmark_plan,
        default_cost_bps=config.costs.per_side_bps.default,
        stress_cost_bps=config.costs.per_side_bps.stress,
    ).default
    benchmark_metrics = calculate_metrics(
        benchmark_run.equity,
        daily_weights=benchmark_run.weights,
        target_weights=benchmark_plan.target_weights,
    )

    pit_provider = pit_universe_provider(history)
    pit_plan = build_signal_plan(
        prices=prepared.prices,
        universe=universe,
        config=config,
        quarantined=frozenset(),
        rebalance_dates=plan.target_weights.index,
        universe_provider=pit_provider,
    )
    pit_run = run_cost_scenarios(
        execution_prices,
        pit_plan,
        default_cost_bps=config.costs.per_side_bps.default,
        stress_cost_bps=config.costs.per_side_bps.stress,
    ).default
    pit_metrics = calculate_metrics(
        pit_run.equity,
        daily_weights=pit_run.weights,
        target_weights=pit_plan.target_weights,
    )
    coverage = pit_price_coverage(history, plan.target_weights.index, prepared.prices)

    try:
        second_spy = second_source_loader(
            str(config.dates.dev_start), str(config.dates.dev_end)
        )
        dq05 = check_spy_annual_returns(prepared.prices[benchmark_ticker], second_spy)
    except Exception as error:
        dq05 = CheckResult("INCONCLUSIVE", f"DQ-05 second source unavailable: {error}")

    default_returns = runs.default.equity.pct_change().dropna()
    benchmark_returns = benchmark_run.equity.pct_change().dropna()
    checks = {
        "CHK-01": check_plan_no_lookahead(
            prices=prepared.prices,
            universe=universe,
            config=config,
            plan=plan,
            quarantined=frozenset(),
        ),
        "CHK-02": check_survivorship(strategy_metrics, pit_metrics, coverage),
        "CHK-03": check_cost_fragility(strategy_metrics.cagr, stress_metrics.cagr),
        "CHK-04": check_one_year_dependency(default_returns, benchmark_returns),
        "CHK-05": check_too_good(
            {"strategy_10bps": strategy_metrics, "strategy_25bps": stress_metrics}
        ),
        "CHK-06": check_constraints(
            runs.default.weights, runs.default.cash, runs.default.transactions
        ),
        "CHK-07": _quality_check(prepared.quality, plan, dq05),
    }
    checks["CHK-02"] = CheckResult(
        checks["CHK-02"].status,
        checks["CHK-02"].detail
        + f"; PIT CAGR={pit_metrics.cagr:.2%}, Sharpe={pit_metrics.sharpe:.3f}, MaxDD={pit_metrics.maxdd:.2%}",
    )
    stamp = datetime.now(ZoneInfo("Asia/Taipei"))
    run_id = f"{stamp:%Y%m%d-%H%M%S}-{params_hash}"
    status = compose_status(checks)
    if status == "SUSPECT":
        full_lookahead = check_plan_no_lookahead(
            prices=prepared.prices,
            universe=universe,
            config=config,
            plan=plan,
            quarantined=frozenset(),
            samples=len(plan.target_weights),
        )
        if full_lookahead.status == "FAIL":
            checks["CHK-01"] = full_lookahead
            status = compose_status(checks)
        _write_suspect_checklist(
            path=root / "experiments/suspect" / f"{run_id}.md",
            full_lookahead=full_lookahead,
            prices=prepared.prices,
            universe_tickers=universe.active_tickers,
            start=str(config.dates.dev_start),
            end=str(config.dates.dev_end),
            ticker_second_source_loader=ticker_second_source_loader,
            execution_check=check_next_session_execution(
                runs.default.transactions, calendar=config.dates.calendar
            ),
            strategy_metrics=strategy_metrics,
            stress_metrics=stress_metrics,
            survivorship_check=checks["CHK-02"],
            one_year_check=checks["CHK-04"],
            transactions=runs.default.transactions,
        )
    report_path = root / "reports" / f"{run_id}.md"
    daily_path = root / "reports" / f"{run_id}.daily.parquet"
    daily = pd.concat(
        [
            runs.default.equity,
            runs.default.cash,
            runs.default.cash_weight,
            runs.default.costs,
            runs.default.weights.add_prefix("weight_"),
        ],
        axis=1,
    )
    daily.to_parquet(daily_path, index=True)
    warnings = sorted(
        result.status for result in checks.values() if result.status.startswith("WARN")
    )
    verdict = _verdict_for_status(status)
    reproduce = f"uv run shm backtest run --prereg {prereg_file.relative_to(root)}"
    report = render_report(
        run_id=run_id,
        status=status,
        warnings=warnings,
        hypothesis=prereg["假设（一句话，可证伪）"],
        expected=prereg.get("预测", ""),
        verdict=verdict,
        metadata={
            "period": f"{config.dates.dev_start}..{config.dates.dev_end}",
            "params_hash": params_hash,
            "universe_hash": compute_file_hash(config_dir / "universe.yaml"),
            "snapshot_id": snapshot.id,
            "git_sha": git_sha,
            "PIT_coverage": f"{coverage:.2%}",
        },
        params=params,
        strategy=strategy_metrics,
        stress=stress_metrics,
        benchmark=benchmark_metrics,
        strategy_yearly=yearly_returns(runs.default.equity),
        benchmark_yearly=yearly_returns(benchmark_run.equity),
        equity=runs.default.equity,
        exposure=runs.default.weights.sum(axis=1),
        checks=checks,
        reproduce=reproduce,
    )
    write_report(report_path, report)
    append_run_log(
        root / "experiments/log.jsonl",
        {
            "run_id": run_id,
            "timestamp": stamp.isoformat(),
            "mode": "backtest",
            "phase": phase,
            "git_sha": git_sha,
            "params_hash": params_hash,
            "params": params,
            "universe_hash": compute_file_hash(config_dir / "universe.yaml"),
            "snapshot_id": snapshot.id,
            "period": {"start": str(config.dates.dev_start), "end": str(config.dates.dev_end)},
            "oos_used": False,
            "variant_index": variant_index,
            "prereg": str(prereg_file.relative_to(root)),
            "hypothesis": prereg["假设（一句话，可证伪）"],
            "expected": prereg.get("预测", ""),
            "results": strategy_metrics.to_dict(),
            "results_stress": stress_metrics.to_dict(),
            "benchmark": benchmark_metrics.to_dict(),
            "checks": {name: result.status for name, result in checks.items()},
            "status": status,
            "verdict": verdict,
            "report": str(report_path.relative_to(root)),
        },
    )
    return RunOutcome(run_id, status, report_path, daily_path)
