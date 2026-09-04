from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping
from collections.abc import Iterable

import numpy as np
import pandas as pd

from shm.checks import CheckResult, check_truncated_signal
from shm.config import ConfigBundle
from shm.data import DataQualityReport, read_price_cache, run_data_quality
from shm.engine import BacktestResult, run_target_weight_backtest
from shm.risk import build_risk_adjusted_target
from shm.signals import select_momentum
from shm.universe import FrozenUniverse, filter_eligible_tickers, xnys_rebalance_dates


@dataclass(frozen=True)
class PreparedData:
    prices: dict[str, pd.DataFrame]
    quality: dict[str, DataQualityReport]
    paths: dict[str, Path]
    quarantined: frozenset[str]


@dataclass(frozen=True)
class SignalPlan:
    target_weights: pd.DataFrame
    diagnostics: pd.DataFrame
    selections: dict[pd.Timestamp, tuple[str, ...]]
    inconclusive: bool


@dataclass(frozen=True)
class CostRuns:
    default: BacktestResult
    stress: BacktestResult


UniverseProvider = Callable[[pd.Timestamp], FrozenUniverse]


def _asof_quarantined(
    prices: Mapping[str, pd.DataFrame],
    tickers: tuple[str, ...],
    signal_date: pd.Timestamp,
    *,
    dev_start: object,
    calendar: str,
) -> set[str]:
    quarantined: set[str] = set()
    for ticker in tickers:
        frame = prices.get(ticker)
        if frame is None or frame.empty:
            continue
        history = frame.loc[pd.to_datetime(frame["date"]) <= signal_date].copy()
        quality = run_data_quality(
            ticker,
            history,
            dev_start=dev_start,
            dev_end=signal_date,
            calendar=calendar,
        )
        if not quality.report.eligible:
            quarantined.add(ticker)
    return quarantined


def prepare_cached_data(
    *,
    config: ConfigBundle,
    universe: FrozenUniverse,
    cache_dir: Path | str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    mode: str = "backtest",
    unlock_oos: bool = False,
    reason: str | None = None,
    oos_audit_path: Path | str | None = None,
    oos_run_id: str | None = None,
    additional_tickers: Iterable[str] = (),
) -> PreparedData:
    cache_root = Path(cache_dir)
    tickers = list(universe.active_tickers)
    benchmark = config.params.risk.trend_filter.benchmark
    if benchmark not in tickers:
        tickers.append(benchmark)
    tickers.extend(ticker for ticker in additional_tickers if ticker not in set(tickers))
    prices: dict[str, pd.DataFrame] = {}
    quality: dict[str, DataQualityReport] = {}
    paths: dict[str, Path] = {}
    quarantined: set[str] = set()
    for ticker in tickers:
        path = cache_root / f"{ticker}.parquet"
        frame = read_price_cache(
            path,
            ticker=ticker,
            start=start,
            end=end,
            mode=mode,
            oos_start=config.dates.oos_start,
            unlock_oos=unlock_oos,
            reason=reason,
            oos_audit_path=oos_audit_path,
            oos_run_id=oos_run_id,
        )
        result = run_data_quality(
            ticker,
            frame,
            dev_start=config.dates.dev_start,
            dev_end=config.dates.dev_end,
            calendar=config.dates.calendar,
        )
        prices[ticker] = result.frame
        quality[ticker] = result.report
        if path.exists():
            paths[ticker] = path
        if not result.report.eligible:
            quarantined.add(ticker)
    return PreparedData(prices, quality, paths, frozenset(quarantined))


def _one_target(
    *,
    prices: Mapping[str, pd.DataFrame],
    universe: FrozenUniverse,
    signal_date: pd.Timestamp,
    config: ConfigBundle,
    quarantined: frozenset[str] | set[str],
) -> tuple[pd.Series, dict[str, object], tuple[str, ...]]:
    effective_quarantine = set(quarantined) | _asof_quarantined(
        prices,
        universe.tickers,
        signal_date,
        dev_start=config.dates.dev_start,
        calendar=config.dates.calendar,
    )
    eligibility = filter_eligible_tickers(
        prices,
        universe,
        signal_date,
        config=config.params.eligibility,
        lookback_trading_days=config.params.signal.lookback_trading_days,
        quarantined=effective_quarantine,
    )
    selection = select_momentum(
        prices,
        eligibility.eligible,
        signal_date,
        config=config.params.signal,
    )
    if selection.raw_weights.empty:
        weights = pd.Series(dtype=float)
        exposure = 0.0
        trend = 0.0
        realized_vol = 0.0
        vol_scale = 0.0
    else:
        target = build_risk_adjusted_target(
            selection.raw_weights,
            prices,
            signal_date,
            config=config.params.risk,
        )
        weights = target.weights
        exposure = target.exposure
        trend = target.trend_exposure
        realized_vol = target.realized_vol
        vol_scale = target.vol_scale
    diagnostics = {
        "eligible_count": len(eligibility.eligible),
        "below_minimum": eligibility.below_minimum,
        "selected_count": len(selection.selected),
        "top_n_shortfall": selection.top_n_shortfall,
        "selected": ",".join(selection.selected),
        "exposure": exposure,
        "trend_exposure": trend,
        "realized_vol": realized_vol,
        "vol_scale": vol_scale,
    }
    return weights, diagnostics, selection.selected


def build_signal_plan(
    *,
    prices: Mapping[str, pd.DataFrame],
    universe: FrozenUniverse,
    config: ConfigBundle,
    quarantined: frozenset[str] | set[str] = frozenset(),
    rebalance_dates: pd.DatetimeIndex | None = None,
    universe_provider: UniverseProvider | None = None,
) -> SignalPlan:
    dates = rebalance_dates
    if dates is None:
        dates = xnys_rebalance_dates(
            config.dates.dev_start,
            config.dates.dev_end,
            warmup_trading_days=config.dates.warmup_trading_days,
            every_trading_days=config.dates.rebalance_every_trading_days,
        )
    rows: dict[pd.Timestamp, pd.Series] = {}
    diagnostics: dict[pd.Timestamp, dict[str, object]] = {}
    selections: dict[pd.Timestamp, tuple[str, ...]] = {}
    for signal_date in dates:
        current_universe = universe_provider(signal_date) if universe_provider else universe
        weights, detail, selected = _one_target(
            prices=prices,
            universe=current_universe,
            signal_date=signal_date,
            config=config,
            quarantined=quarantined,
        )
        rows[signal_date] = weights
        diagnostics[signal_date] = detail
        selections[signal_date] = selected
    target_weights = pd.DataFrame.from_dict(rows, orient="index").fillna(0.0).sort_index()
    detail_frame = pd.DataFrame.from_dict(diagnostics, orient="index").sort_index()
    inconclusive = bool(detail_frame["below_minimum"].any()) if not detail_frame.empty else True
    return SignalPlan(target_weights, detail_frame, selections, inconclusive)


def run_cost_scenarios(
    prices: Mapping[str, pd.DataFrame],
    plan: SignalPlan,
    *,
    default_cost_bps: float,
    stress_cost_bps: float,
    initial_cash: float = 100_000.0,
) -> CostRuns:
    return CostRuns(
        default=run_target_weight_backtest(
            prices, plan.target_weights, cost_bps=default_cost_bps, initial_cash=initial_cash
        ),
        stress=run_target_weight_backtest(
            prices, plan.target_weights, cost_bps=stress_cost_bps, initial_cash=initial_cash
        ),
    )


def check_plan_no_lookahead(
    *,
    prices: Mapping[str, pd.DataFrame],
    universe: FrozenUniverse,
    config: ConfigBundle,
    plan: SignalPlan,
    quarantined: frozenset[str] | set[str] = frozenset(),
    samples: int = 5,
    seed: int = 0,
) -> CheckResult:
    dates = plan.target_weights.index
    if len(dates) < samples:
        return CheckResult("INCONCLUSIVE", f"only {len(dates)} rebalance dates available")
    rng = np.random.default_rng(seed)
    chosen = sorted(rng.choice(len(dates), size=samples, replace=False))
    for position in chosen:
        signal_date = dates[position]
        truncated = {
            ticker: frame.loc[pd.to_datetime(frame["date"]) <= signal_date].copy()
            for ticker, frame in prices.items()
        }
        weights, _, _ = _one_target(
            prices=truncated,
            universe=universe,
            signal_date=signal_date,
            config=config,
            quarantined=quarantined,
        )
        full = plan.target_weights.loc[signal_date]
        truncated_aligned = weights.reindex(full.index, fill_value=0.0)
        result = check_truncated_signal(full.to_dict(), truncated_aligned.to_dict())
        if result.status != "PASS":
            return CheckResult("FAIL", f"{signal_date.date()}: {result.detail}")
    return CheckResult("PASS", f"{samples} deterministic random rebalance dates matched")


def load_pit_history(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if not {"date", "tickers"}.issubset(frame.columns):
        raise ValueError("PIT history requires date,tickers columns")
    frame["date"] = pd.to_datetime(frame["date"])
    frame["members"] = frame["tickers"].fillna("").map(
        lambda value: tuple(ticker for ticker in str(value).split(",") if ticker)
    )
    return frame.sort_values("date").reset_index(drop=True)


def pit_universe_provider(history: pd.DataFrame) -> UniverseProvider:
    dates = pd.DatetimeIndex(history["date"])

    def provider(signal_date: pd.Timestamp) -> FrozenUniverse:
        position = dates.searchsorted(signal_date, side="right") - 1
        if position < 0:
            return FrozenUniverse(signal_date.date(), "PIT S&P 500", (), frozenset())
        members = tuple(history.iloc[position]["members"])
        return FrozenUniverse(signal_date.date(), "PIT S&P 500", members, frozenset())

    return provider


def pit_price_coverage(
    history: pd.DataFrame,
    dates: pd.DatetimeIndex,
    prices: Mapping[str, pd.DataFrame],
) -> float:
    provider = pit_universe_provider(history)
    available_dates = {
        ticker: set(
            pd.to_datetime(frame["date"], utc=True).dt.tz_convert(None).dt.normalize()
        )
        for ticker, frame in prices.items()
        if not frame.empty
    }
    coverage: list[float] = []
    for signal_date in dates:
        members = set(provider(signal_date).tickers)
        session = pd.Timestamp(signal_date).tz_localize(None).normalize()
        covered = sum(session in available_dates.get(ticker, set()) for ticker in members)
        coverage.append(covered / len(members) if members else 0.0)
    return float(np.mean(coverage)) if coverage else 0.0


def pit_tickers_for_period(
    history: pd.DataFrame,
    start: object,
    end: object,
) -> tuple[str, ...]:
    start_stamp, end_stamp = pd.Timestamp(start), pd.Timestamp(end)
    before = history.loc[history["date"] <= start_stamp]
    during = history.loc[history["date"].between(start_stamp, end_stamp, inclusive="both")]
    rows = []
    if not before.empty:
        rows.append(before.iloc[-1])
    rows.extend(row for _, row in during.iterrows())
    tickers = {ticker for row in rows for ticker in row["members"]}
    return tuple(sorted(tickers))
