"""Closed v0.3 known-history comparison. Never reads or resets the v0.2 OOS ledger."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import yaml

from shm.engine.backtest import run_target_weight_backtest
from shm.pipeline import load_pit_history, pit_universe_provider
from shm.report.metrics import average_holding_days
from shm.universe.calendar import xnys_rebalance_dates


CANDIDATE_IDS = ("C0", "C1", "C2", "C3", "C4")
CUTOFF = "2026-09-04"
INITIAL_CASH = 100_000.0


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _source_hash(root: Path) -> str:
    return json_hash({str(path.relative_to(root)): file_hash(path)
                      for path in sorted((root / "src/shm").rglob("*.py"))})


def performance(equity: pd.Series, *, initial_cash: float = INITIAL_CASH,
                weights: pd.DataFrame | None = None,
                transactions: pd.DataFrame | None = None,
                costs: pd.Series | None = None) -> dict:
    """Include the first session's execution cost and initial capital in drawdown."""
    equity = equity.astype(float).sort_index()
    if equity.empty or not np.isfinite(equity).all() or (equity <= 0).any():
        raise ValueError("complete positive equity observations are required")
    previous = equity.shift(1)
    previous.iloc[0] = initial_cash
    returns = equity / previous - 1
    peak = equity.cummax().clip(lower=initial_cash)
    maxdd = float((equity / peak - 1).min())
    cagr = float((equity.iloc[-1] / initial_cash) ** (252 / len(equity)) - 1)
    sigma = float(returns.std()) if len(returns) > 1 else 0.0
    turnover = 0.0
    if transactions is not None and not transactions.empty:
        dates = pd.to_datetime(transactions["execution_date"])
        notionals = pd.to_numeric(transactions["notional"])
        navs = previous.reindex(pd.DatetimeIndex(dates)).to_numpy()
        turnover = float(np.nansum(notionals.to_numpy() / navs) / 2 * 252 / len(equity))
    return {
        "cagr": cagr, "maxdd": maxdd,
        "sharpe": float(returns.mean() / sigma * np.sqrt(252)) if sigma > 0 else 0.0,
        "calmar": cagr / abs(maxdd) if maxdd < 0 else None,
        "net_return": float(equity.iloc[-1] / initial_cash - 1),
        "turnover": turnover,
        "avg_exposure": float(weights.sum(axis=1).mean()) if weights is not None else None,
        "avg_holding_days": average_holding_days(weights),
        "cost_total_usd": float(costs.sum()) if costs is not None else None,
        "sessions": len(equity),
    }


def qualifies(row: dict) -> bool:
    if not all(value == "PASS" for value in row["checks"].values()):
        return False
    return all(
        row[f"metrics_{bps}"]["cagr"] > row[f"benchmark_{bps}"]["cagr"]
        and abs(row[f"metrics_{bps}"]["maxdd"]) < abs(row[f"benchmark_{bps}"]["maxdd"])
        for bps in (10, 25)
    )


def select_winner(rows: list[dict]) -> str | None:
    eligible = [row for row in rows if qualifies(row)]
    if not eligible:
        return None
    eligible.sort(key=lambda row: (
        -(row["metrics_25"]["cagr"] - row["benchmark_25"]["cagr"]),
        abs(row["metrics_25"]["maxdd"]), row["metrics_25"]["turnover"],
        row["module_count"], row["strategy_id"],
    ))
    return eligible[0]["strategy_id"]


def _load_prices(root: Path, tickers: list[str], start: pd.Timestamp,
                 end: pd.Timestamp) -> tuple[dict, dict, list[str]]:
    prices, hashes, missing = {}, {}, []
    for ticker in sorted(set(tickers)):
        path = root / "data/raw/prices" / f"{ticker}.parquet"
        if not path.exists():
            missing.append(ticker)
            continue
        frame = pd.read_parquet(path)
        frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert(None).dt.normalize()
        frame = frame.loc[frame["date"].between(start, end)].sort_values("date")
        frame = frame.drop_duplicates("date", keep="last")
        if frame.empty:
            missing.append(ticker)
            continue
        if "adjusted" not in frame or not frame["adjusted"].eq(True).all():
            raise ValueError(f"{ticker}: adjusted total-return OHLC cache is required")
        columns = ["date", "open", "high", "low", "close", "volume"]
        columns += [key for key in ("as_traded_close", "dollar_volume") if key in frame]
        prices[ticker] = frame[columns].copy()
        hashes[str(path.relative_to(root))] = file_hash(path)
    return prices, hashes, missing


def _spy_buy_hold(frame: pd.DataFrame, evaluation: pd.DatetimeIndex, bps: int) -> pd.Series:
    indexed = frame.set_index("date").reindex(evaluation)
    if indexed[["open", "close"]].isna().any().any():
        raise ValueError("SPY evaluation prices incomplete")
    shares = INITIAL_CASH / (float(indexed.iloc[0]["open"]) * (1 + bps / 10_000))
    return (indexed["close"] * shares).rename("equity")


def _matched_spy(prices: dict, schedule: pd.DatetimeIndex,
                 evaluation: pd.DatetimeIndex, bps: int, candidate: str) -> dict:
    close = prices["SPY"].set_index("date")["close"]
    mean = close.rolling(200).mean()
    vol = close.pct_change(fill_method=None).rolling(20).std() * np.sqrt(252)
    target_vol = .20 if candidate == "C4" else .15
    targets = {}
    for session in close.index[close.index >= schedule[0]]:
        if session in schedule:
            targets[session] = (min(1.0, target_vol / vol[session]) if vol[session] > 0 else 1.0) if close[session] > mean[session] else 0.0
        elif candidate != "C0" and close[session] <= mean[session]:
            targets[session] = 0.0
    result = run_target_weight_backtest(
        {"SPY": prices["SPY"]}, pd.DataFrame({"SPY": pd.Series(targets)}), cost_bps=bps,
    )
    return performance(result.equity.reindex(evaluation),
                       weights=result.weights.reindex(evaluation),
                       transactions=result.transactions, costs=result.costs.reindex(evaluation))


def _return_views(equity: pd.Series, benchmark: pd.Series) -> dict:
    returns = equity.pct_change()
    returns.iloc[0] = equity.iloc[0] / INITIAL_CASH - 1
    spy_returns = benchmark.pct_change()
    spy_returns.iloc[0] = benchmark.iloc[0] / INITIAL_CASH - 1
    years = (1 + returns).groupby(returns.index.year).prod() - 1
    spy_years = (1 + spy_returns).groupby(spy_returns.index.year).prod() - 1
    best = int(years.idxmax())
    selected = returns.index.year != best
    ex_year = INITIAL_CASH * (1 + returns[selected]).cumprod()
    spy_ex_year = INITIAL_CASH * (1 + spy_returns[selected]).cumprod()
    since = returns.index >= pd.Timestamp("2019-01-01")
    return {
        "annual_returns": {str(year): {"strategy": float(value), "spy": float(spy_years[year]),
                                     "partial_year": year == returns.index[-1].year}
                           for year, value in years.items()},
        "since_2019": {
            "strategy": performance(INITIAL_CASH * (1 + returns[since]).cumprod()),
            "spy": performance(INITIAL_CASH * (1 + spy_returns[since]).cumprod()),
        } if since.any() else None,
        "excluding_best_year": {"removed_year": best, "strategy": performance(ex_year),
                                "spy": performance(spy_ex_year)} if selected.any() else None,
    }


def _holding_price_jumps(prepared, backtest, evaluation: pd.DatetimeIndex) -> list[dict]:
    """Flag suspect quotes in actually exposed holdings, not hypothetical picks.

    This is a data-review gate, not a trading rule or an automatic price repair.
    Legitimate corporate events can also exceed 50% and need verification.
    """
    rows = prepared.dates.get_indexer(evaluation)
    if (rows < 0).any():
        raise ValueError("evaluation dates absent from prepared prices")
    returns = prepared.returns[rows]
    weights = backtest.weights.shift(1).reindex(evaluation).reindex(columns=prepared.tickers, fill_value=0).fillna(0).to_numpy()
    hits = np.argwhere(np.isfinite(returns) & (np.abs(returns) > .50) & (weights > 0))
    details = [{"date": str(evaluation[i].date()), "ticker": prepared.tickers[j],
                "return": float(returns[i, j]), "prior_weight": float(weights[i, j])}
               for i, j in hits]
    flagged = {(item["date"], item["ticker"]) for item in details}
    dates = {date: i for i, date in enumerate(evaluation)}
    columns = {ticker: j for j, ticker in enumerate(prepared.tickers)}
    if not backtest.transactions.empty:
        for trade in backtest.transactions.itertuples(index=False):
            date = pd.Timestamp(trade.execution_date).tz_localize(None).normalize()
            key = (str(date.date()), trade.ticker)
            if date not in dates or key in flagged:
                continue
            i, j = dates[date], columns[trade.ticker]
            if trade.side == "buy":
                start, end = float(trade.price), float(prepared.closes[rows[i], j])
                window, quote = "fill_to_close", {"entry_price": start}
            else:
                if rows[i] == 0 or weights[i, j] <= 0:
                    continue
                start, end = float(prepared.closes[rows[i] - 1, j]), float(trade.price)
                window, quote = "close_to_fill", {"previous_close": start, "exit_price": end}
            if not (np.isfinite(start) and np.isfinite(end) and start > 0 and end > 0):
                continue
            # Check only the owned interval: entry-to-close for buys and
            # prior-close-to-fill for exits, even when the exit-day close is normal.
            move = end / start - 1
            if abs(move) > .50:
                details.append({"date": key[0], "ticker": trade.ticker, "return": move,
                                "prior_weight": float(weights[i, j]),
                                "quote_window": window, **quote})
                flagged.add(key)
    return details


def _benchmark_price_jumps(prepared, evaluation: pd.DatetimeIndex) -> list[dict]:
    rows = prepared.dates.get_indexer(evaluation)
    column = prepared.ticker_index["SPY"]
    returns = prepared.returns[rows, column]
    return [{"date": str(evaluation[i].date()), "ticker": "SPY", "return": float(returns[i]), "prior_weight": 1.0}
            for i in np.flatnonzero(np.isfinite(returns) & (np.abs(returns) > .50))]


def _correctness(result, evaluation: pd.DatetimeIndex, *, holding_price_jumps=None,
                 benchmark_price_jumps=None) -> dict:
    bt = result.backtest
    trades = bt.transactions
    timing = trades.empty or bool((pd.to_datetime(trades["execution_date"]) > pd.to_datetime(trades["signal_date"])).all())
    funded = bool((bt.cash >= -1e-6).all() and (bt.weights >= -1e-9).all().all()
                  and (bt.weights.sum(axis=1) <= 1 + 1e-7).all())
    # Missing marks/fills make the path unverified even if carried marks produce a number.
    events = bt.execution_fallbacks
    if not events.empty and "execution_date" in events:
        event_dates = pd.to_datetime(events["execution_date"], errors="coerce")
        events = events.loc[event_dates.isna() | event_dates.ge(evaluation[0])]
    complete = events.empty or bool(events["action"].isin(["adjustment_rescale", "already_processed"]).all())
    prior_sessions = bt.equity.index[bt.equity.index < evaluation[0]]
    first_signal = prior_sessions[-1] if len(prior_sessions) else evaluation[0]
    missing_decisions = [item for item in result.warnings
                         if item["date"] >= str(first_signal.date())
                         and str(item["warning"]).startswith("MISSING_")]
    return {"NEXT_SESSION": "PASS" if timing else "FAIL",
            "FUNDED_LONG_ONLY": "PASS" if funded else "FAIL",
            "EXECUTION_DATA": "PASS" if complete else "INCONCLUSIVE",
            "SIGNAL_DATA": "PASS" if not missing_decisions else "INCONCLUSIVE",
            "HOLDING_PRICE_JUMPS": ("NOT_CHECKED" if holding_price_jumps is None else
                                     "INCONCLUSIVE" if holding_price_jumps else "PASS"),
            "BENCHMARK_PRICE_JUMPS": ("NOT_CHECKED" if benchmark_price_jumps is None else
                                       "INCONCLUSIVE" if benchmark_price_jumps else "PASS"),
            "EVALUATION_COVERAGE": "PASS" if bt.equity.reindex(evaluation).notna().all() else "INCONCLUSIVE"}


def _save_result(directory: Path, candidate: str, bps: int, result, evaluation) -> dict:
    bt = result.backtest
    daily = pd.DataFrame({"equity": bt.equity.reindex(evaluation),
                          "cash": bt.cash.reindex(evaluation), "cost": bt.costs.reindex(evaluation)})
    daily.join(bt.weights.reindex(evaluation).add_prefix("weight_")).to_parquet(directory / f"{candidate}-{bps}.daily.parquet")
    bt.transactions.to_csv(directory / f"{candidate}-{bps}.transactions.csv", index=False)
    bt.execution_fallbacks.to_csv(directory / f"{candidate}-{bps}.execution-events.csv", index=False)
    write_json(directory / f"{candidate}-{bps}.warnings.json", result.warnings)
    write_json(directory / f"{candidate}-{bps}.decisions.json", result.decisions)
    return performance(daily.equity, weights=bt.weights.reindex(evaluation),
                       transactions=bt.transactions, costs=daily.cost)


def _jump_examples(details: list[dict]) -> list[str]:
    unique = {}
    for item in details:
        key = (item["date"], item["ticker"])
        if key not in unique or item["prior_weight"] > unique[key]["prior_weight"]:
            unique[key] = item
    ordered = sorted(unique.values(), key=lambda item: abs(item["return"]) * item["prior_weight"], reverse=True)[:3]
    lines = ["", "| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |", "|---|---|---:|---:|"]
    lines.extend(f"| {item['date']} | {item['ticker']} | {item['return']:.2%} | {item['prior_weight']:.2%} |" for item in ordered)
    return lines


def render_research(payload: dict) -> str:
    lines = ["# SHM v0.3 已知历史研究", "", f"状态：**{payload['status']}**；胜者：**{payload['winner'] or '无'}**。",
             "", f"评价区间：{payload['period']['start']} → {payload['period']['end']}。",
             "这是已观察数据上的复核，不是新的独立样本外，也不是已实现的前向收益。",
             "", "| 候选 | 10bps年化 | 10bps回撤 | 25bps年化 | 25bps回撤 | 晋级 |",
             "|---|---:|---:|---:|---:|---|"]
    for row in payload["candidates"]:
        a, b = row["metrics_10"], row["metrics_25"]
        if row.get("holding_price_jumps_10") or row.get("holding_price_jumps_25"):
            lines.append(f"| {row['strategy_id']} | 报价异常，原始指标无效 | — | 报价异常，原始指标无效 | — | 否 |")
        else:
            lines.append(f"| {row['strategy_id']} | {a['cagr']:.2%} | {a['maxdd']:.2%} | {b['cagr']:.2%} | {b['maxdd']:.2%} | {'是' if row['qualified'] else '否'} |")
    a, b = payload["benchmark_10"], payload["benchmark_25"]
    if payload.get("benchmark_price_jumps"):
        lines.append("| SPY | 报价异常，原始指标无效 | — | 报价异常，原始指标无效 | — | 基准不可用 |")
    else:
        lines.append(f"| SPY | {a['cagr']:.2%} | {a['maxdd']:.2%} | {b['cagr']:.2%} | {b['maxdd']:.2%} | 基准 |")
    lines += ["", "## 判定与证据边界", "", "10%是预警线，不是强制清仓或淘汰条件。成本为模型假设；现金收益0；含分红总回报，末日按收盘估值。",
              "原84只名单的事后选择偏差仍存在。数据覆盖不足、单年依赖及PIT敏感性不能被晋级标记掩盖。"]
    if payload.get("benchmark_price_jumps"):
        lines += ["", "**SPY基准存在超过50%的单日缓存价格跳变；基准及相对收益结论不可用，须核实报价/公司行为。**"]
        lines += _jump_examples(payload["benchmark_price_jumps"])
    for row in payload["candidates"]:
        lines += ["", f"### {row['strategy_id']}", "", f"检查：`{json.dumps(row['checks'], ensure_ascii=False)}`",
                  f"警告：{', '.join(row['warnings']) or '无新增警告'}。",
                  f"平均仓位 {row['metrics_10']['avg_exposure']:.1%}；平均连续持仓 {row['metrics_10']['avg_holding_days']:.1f} 交易日。"]
        owner_jumps = row.get("holding_price_jumps_10", []) + row.get("holding_price_jumps_25", [])
        if owner_jumps:
            lines += ["", "**实际持仓遭遇超过50%的单日缓存价格跳变：以下逐年/区间数值均为受污染的原始诊断，不可用于收益结论。**"]
            lines += _jump_examples(owner_jumps)
        lines += ["", "| 年份 | 策略 | SPY |", "|---|---:|---:|"]
        for year, annual in row["views"]["annual_returns"].items():
            label = year + ("（截至9月4日）" if annual["partial_year"] else "")
            lines.append(f"| {label} | {annual['strategy']:.2%} | {annual['spy']:.2%} |")
        since = row["views"]["since_2019"]
        if since:
            lines.append(f"\n2019年后年化/回撤：{since['strategy']['cagr']:.2%} / {since['strategy']['maxdd']:.2%}；SPY {since['spy']['cagr']:.2%} / {since['spy']['maxdd']:.2%}。")
        ex = row["views"]["excluding_best_year"]
        if ex:
            lines.append(f"\n剔除{ex['removed_year']}：策略年化 {ex['strategy']['cagr']:.2%}，SPY {ex['spy']['cagr']:.2%}。")
        matched = row["risk_matched_spy_10"]
        lines.append(f"\n同大盘风控与波动缩放SPY辅助基准（不含个股SMA/ATR退出）：年化 {matched['cagr']:.2%}、回撤 {matched['maxdd']:.2%}。")
        coverage = row.get("owner_eligibility")
        if coverage:
            lines.append(f"\nOwner时点资格：{coverage['rebalance_count']}次选股中，{coverage['below_30_count']}次少于30只；最少{coverage['minimum_count']}只。不足时暂停新增买入，完整日期见JSON。")
        pit = row.get("pit")
        if pit:
            pit_jumps = pit.get("holding_price_jumps_10", []) + pit.get("holding_price_jumps_25", [])
            if pit_jumps:
                lines.append(f"\n**PIT覆盖 {pit['coverage']:.1%}；状态 INCONCLUSIVE。存在实际持仓报价跳变，原始年化/回撤诊断数不可用，不能据此判断扩池有效。**")
                lines.append("原始数值仅保留在JSON供审计；须先查明证券身份、价格单位及公司行为。影响最大的三个报价异常如下：")
                lines += _jump_examples(pit_jumps)
            else:
                lines.append(f"\nPIT覆盖 {pit['coverage']:.1%}；状态 {pit['status']}；10bps年化 {pit['metrics_10']['cagr']:.2%}、回撤 {pit['metrics_10']['maxdd']:.2%}。仅作敏感性诊断，缺失/退市报价不伪造成交。")
    lines += ["", "## 复现", "", "`uv run shm research-v03 --repo-root .`", "",
              f"run_id: `{payload['run_id']}`；snapshot: `{payload['snapshot_id']}`。",
              "全部逐日净值、权重、交易、执行事件及JSON结果见同一运行目录。", ""]
    return "\n".join(lines)


def _publish_result(root: Path, directory: Path, payload: dict) -> None:
    """Idempotently finish publication after crashes, checking frozen conflicts first."""
    run_id, winner = payload["run_id"], payload["winner"]
    frozen_path = root / "config/v03/winner.json"
    if frozen_path.exists():
        existing = json.loads(frozen_path.read_text())
        if existing.get("research_run_id") != run_id or existing.get("strategy_id") != winner:
            raise ValueError("another v0.3 winner is already frozen; a new strategy version is required")
    frozen = None
    if winner:
        selected = next(row for row in payload["candidates"] if row["strategy_id"] == winner)
        frozen = {"spec_version": "0.3", "strategy_id": winner, "config": selected["config"],
                  "params_hash": json_hash(selected["config"]), "universe_hash": payload["universe_hash"],
                  "research_run_id": run_id, "frozen_at": payload["generated_at"],
                  "cost_bps": [10, 25], "evidence": "known_history"}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.md").write_text(render_research(payload))
    ledger = root / "experiments/v03/log.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    previous_runs = {json.loads(line)["run_id"] for line in ledger.read_text().splitlines() if line.strip()} if ledger.exists() else set()
    if run_id not in previous_runs:
        with ledger.open("a") as stream:
            stream.write(json.dumps({"run_id": run_id, "snapshot_id": payload["snapshot_id"],
                                     "source_hash": payload["source_hash"], "evidence": "known_history",
                                     "candidate_ids": list(CANDIDATE_IDS), "winner": winner,
                                     "status": payload["status"],
                                     "hypothesis": "Closed C0-C4 comparison under approved SPEC-SHM-001 v0.3"}) + "\n")
    if frozen is not None:
        write_json(frozen_path, frozen)
    write_json(directory / "selection.json", payload)
    write_json(root / "reports/v03/selection.json", payload)


def run_research_v03(repo_root: Path | str, *, progress: Callable[[str], None] = print) -> dict:
    from shm.v03.engine import run_simulation
    from shm.v03.strategy import CANDIDATES, prepare_inputs

    root = Path(repo_root).resolve()
    config = yaml.safe_load((root / "config/v03/research.yaml").read_text())
    if tuple(config["candidate_ids"]) != CANDIDATE_IDS or str(config["cutoff"]) != CUTOFF or config["cost_bps"] != [10, 25]:
        raise ValueError("v0.3 is a closed, pre-registered C0-C4 / 10-25bps study through 2026-09-04")
    prereg_hashes = {}
    for candidate in CANDIDATE_IDS:
        path = root / "experiments/prereg/v03" / f"{candidate}.md"
        if "Owner批准" not in path.read_text():
            raise ValueError(f"missing approved preregistration: {candidate}")
        prereg_hashes[str(path.relative_to(root))] = file_hash(path)
    universe_path = root / "config/universe.yaml"
    owner = yaml.safe_load(universe_path.read_text())
    universe = [ticker for ticker in owner["tickers"] if ticker not in owner.get("exclusions", [])]
    end = pd.Timestamp(CUTOFF)
    schedule = xnys_rebalance_dates(config["dev_start"], end, warmup_trading_days=260, every_trading_days=20)
    calendar = xcals.get_calendar("XNYS", start=pd.Timestamp(config["dev_start"]) - pd.Timedelta(days=900), end=end)
    first = calendar.sessions.get_loc(schedule[0])
    sessions = calendar.sessions[first - 260:]
    evaluation = sessions[sessions > schedule[0]]
    prices, hashes, missing = _load_prices(root, universe + ["SPY"], sessions[0], end)
    if "SPY" not in prices:
        raise ValueError("SPY cache is required")
    pit_history = load_pit_history(root / "data/reference/sp500_history.csv")
    provider = pit_universe_provider(pit_history)
    membership = {date: provider(date).tickers for date in schedule}
    pit_union = sorted({ticker for members in membership.values() for ticker in members})
    pit_prices, pit_hashes, pit_missing = _load_prices(root, pit_union + ["SPY"], sessions[0], end)
    all_hashes = {**hashes, **pit_hashes, **prereg_hashes,
                  "config/universe.yaml": file_hash(universe_path),
                  "data/reference/sp500_history.csv": file_hash(root / "data/reference/sp500_history.csv")}
    snapshot_id = json_hash(all_hashes)
    source_hash = _source_hash(root)
    run_id = "v03-" + json_hash({"snapshot": snapshot_id, "source": source_hash, "config": config})[:16]
    directory = root / "reports/v03" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    saved = directory / "selection.json"
    if saved.exists():
        payload = json.loads(saved.read_text())
        _publish_result(root, directory, payload)
        return payload
    write_json(directory / "snapshot.json", {"snapshot_id": snapshot_id, "files": all_hashes,
                                             "source_hash": source_hash, "missing_owner": missing, "missing_pit": pit_missing})
    progress("Preparing owner-universe indicators and historical membership comparison")
    prepared = prepare_inputs(prices, universe, sessions, schedule)
    pit_prepared = prepare_inputs(pit_prices, pit_union, sessions, schedule, membership_by_session=membership)
    coverage_values = []
    available = {ticker: set(frame["date"]) for ticker, frame in pit_prices.items()}
    for date, members in membership.items():
        coverage_values.append(sum(date in available.get(ticker, ()) for ticker in members) / len(members) if members else 0)
    coverage = float(np.mean(coverage_values))
    benchmarks = {bps: _spy_buy_hold(prices["SPY"], evaluation, bps) for bps in (10, 25)}
    benchmark_metrics = {bps: performance(series) for bps, series in benchmarks.items()}
    benchmark_jumps = _benchmark_price_jumps(prepared, evaluation)
    rows = []
    for candidate in CANDIDATE_IDS:
        progress(f"Evaluating {candidate} at 10/25 bps, owner and historical constituent universes")
        row = {"strategy_id": candidate, "config": asdict(CANDIDATES[candidate]),
               "module_count": CANDIDATES[candidate].modules,
               "warnings": ["FIXED_OWNER_UNIVERSE_SELECTION_BIAS"], "checks": {}}
        for bps in (10, 25):
            result = run_simulation(prices, universe, candidate, sessions, schedule, cost_bps=bps, prepared=prepared)
            row[f"metrics_{bps}"] = _save_result(directory, candidate, bps, result, evaluation)
            row[f"benchmark_{bps}"] = benchmark_metrics[bps]
            holding_jumps = _holding_price_jumps(prepared, result.backtest, evaluation)
            row[f"holding_price_jumps_{bps}"] = holding_jumps
            row["checks"].update({f"{key}_{bps}": value for key, value in _correctness(
                result, evaluation, holding_price_jumps=holding_jumps, benchmark_price_jumps=benchmark_jumps).items()})
            if bps == 10:
                selection_days = [d for d in result.decisions if d["diagnostics"].get("rebalance")]
                insufficient = [d["signal_date"] for d in selection_days if d["eligible_count"] < 30]
                row["owner_eligibility"] = {
                    "rebalance_count": len(selection_days), "below_30_count": len(insufficient),
                    "minimum_count": min((d["eligible_count"] for d in selection_days), default=0),
                    "insufficient_dates": insufficient,
                }
                if insufficient:
                    row["warnings"].append("WARN_OWNER_ELIGIBILITY_BELOW_30")
                row["views"] = _return_views(result.backtest.equity.reindex(evaluation), benchmarks[bps])
                ex = row["views"]["excluding_best_year"]
                if ex and ex["strategy"]["cagr"] <= ex["spy"]["cagr"]:
                    row["warnings"].append("WARN_ONE_YEAR_DEPENDENCY")
            row[f"risk_matched_spy_{bps}"] = _matched_spy(prices, schedule, evaluation, bps, candidate)
            pit_result = run_simulation(pit_prices, pit_union, candidate, sessions, schedule,
                                        cost_bps=bps, prepared=pit_prepared)
            pit_metrics = _save_result(directory, f"{candidate}-pit", bps, pit_result, evaluation)
            pit_jumps = _holding_price_jumps(pit_prepared, pit_result.backtest, evaluation)
            pit_checks = _correctness(pit_result, evaluation, holding_price_jumps=pit_jumps,
                                      benchmark_price_jumps=benchmark_jumps)
            pit = row.setdefault("pit", {"coverage": coverage, "status": "DIAGNOSTIC", "checks": {}})
            pit[f"metrics_{bps}"] = pit_metrics
            pit[f"holding_price_jumps_{bps}"] = pit_jumps
            pit["checks"].update({f"{key}_{bps}": value for key, value in pit_checks.items()})
            if coverage < .8 or any(value != "PASS" for value in pit_checks.values()):
                pit["status"] = "INCONCLUSIVE"
        row["checks"]["OWNER_CACHE"] = "PASS" if not missing else "INCONCLUSIVE"
        row["metrics_valid"] = all(value == "PASS" for value in row["checks"].values())
        row["pit"]["metrics_valid"] = row["pit"]["status"] != "INCONCLUSIVE"
        if row["holding_price_jumps_10"] or row["holding_price_jumps_25"]:
            row["warnings"].append("WARN_HOLDING_PRICE_JUMPS")
        if row["pit"]["holding_price_jumps_10"] or row["pit"]["holding_price_jumps_25"]:
            row["warnings"].append("WARN_PIT_PRICE_JUMPS_RAW_METRICS_INVALID")
        if benchmark_jumps:
            row["warnings"].append("WARN_BENCHMARK_PRICE_JUMPS")
        if row["pit"]["status"] == "INCONCLUSIVE":
            row["warnings"].append("WARN_PIT_INCONCLUSIVE")
        if row["metrics_valid"] and row["pit"]["metrics_valid"] and abs(row["metrics_10"]["cagr"] - row["pit"]["metrics_10"]["cagr"]) > .05:
            row["warnings"].append("WARN_UNIVERSE_SENSITIVITY")
        row["qualified"] = qualifies(row)
        rows.append(row)
        write_json(directory / f"{candidate}.json", row)
    winner = select_winner(rows)
    status = "HISTORICAL_SCREEN_PASS" if winner else "NO_QUALIFIED_CANDIDATE"
    if not winner and all(any(v != "PASS" for v in row["checks"].values()) for row in rows):
        status = "INCONCLUSIVE"
    payload = {"spec_version": "0.3", "evidence": "known_history", "run_id": run_id,
               "generated_at": datetime.now(timezone.utc).isoformat(), "snapshot_id": snapshot_id,
               "source_hash": source_hash, "universe_hash": file_hash(universe_path),
               "period": {"start": str(evaluation[0].date()), "end": CUTOFF},
               "winner": winner, "status": status, "candidates": rows,
               "benchmark_10": benchmark_metrics[10], "benchmark_25": benchmark_metrics[25],
               "benchmark_price_jumps": benchmark_jumps,
               "report_path": f"reports/v03/{run_id}/report.md"}
    if _source_hash(root) != source_hash:
        raise RuntimeError("source changed during research; results were not published or frozen")
    _publish_result(root, directory, payload)
    progress(f"{status}; winner={winner}; report={directory / 'report.md'}")
    return payload
