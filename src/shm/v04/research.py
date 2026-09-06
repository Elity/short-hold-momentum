"""Fixed S500-C0..C4 comparison using historical constituent membership only."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import yaml

from shm.pipeline import load_pit_history, pit_universe_provider
from shm.universe.calendar import xnys_rebalance_dates
from shm.v03.engine import run_simulation
from shm.v03.strategy import CANDIDATES, prepare_inputs
from shm.v03.research import (
    CUTOFF, _benchmark_price_jumps, _correctness, _holding_price_jumps,
    _jump_examples, _load_prices, _matched_spy, _return_views, _save_result,
    _source_hash, _spy_buy_hold, file_hash, json_hash, performance,
    qualifies, select_winner, write_json,
)
from shm.v04.profiles import SP500_IDS, base_candidate, candidate_config
from shm.v04.history import load_membership, apply_price_repairs


def historical_membership(history: pd.DataFrame, schedule: pd.DatetimeIndex,
                          evaluation: pd.DatetimeIndex) -> tuple[dict, dict]:
    """Do not extend the last published historical list beyond its coverage."""
    first, last = history["date"].min(), history["date"].max()
    provider = pit_universe_provider(history)
    membership = {date: provider(date).tickers if first <= date <= last else () for date in schedule}
    missing = [str(date.date()) for date, members in membership.items() if not members]
    complete = bool(first <= evaluation[0] and last >= evaluation[-1] and not missing)
    return membership, {
        "source_first_date": str(first.date()), "source_last_date": str(last.date()),
        "required_start": str(evaluation[0].date()), "required_end": str(evaluation[-1].date()),
        "missing_rebalance_dates": missing,
        "status": "PASS" if complete else "INCONCLUSIVE",
        "outside_coverage_behavior": "membership_unknown_no_new_ranking_buys",
    }


def price_coverage(prices: dict, membership: dict) -> dict:
    available = {}
    for ticker, frame in prices.items():
        columns = frame[["open", "high", "low", "close"]]
        valid = np.isfinite(columns).all(axis=1) & columns.gt(0).all(axis=1)
        valid &= frame["volume"].ge(0) & np.isfinite(frame["volume"])
        valid &= frame["high"].ge(frame["low"])
        available[ticker] = set(frame.loc[valid, "date"])
    rows = []
    for date, members in membership.items():
        if not members:
            continue
        covered = sum(date in available.get(ticker, ()) for ticker in members)
        rows.append({"date": str(date.date()), "expected": len(members), "available": covered,
                     "coverage": covered / len(members)})
    return {"coverage": float(np.mean([row["coverage"] for row in rows])) if rows else 0.0,
            "rebalance_dates": rows,
            "denominator": "members on selection dates with published PIT membership"}


def sector_concentration(weights: pd.DataFrame, current: dict | None) -> dict:
    """Descriptive current sector labels; they never select historical members."""
    labels = {row["symbol"]: row.get("sector") or "Unknown" for row in (current or {}).get("members", [])}
    sectors = {}
    for ticker in weights.columns:
        label = labels.get(ticker, "Unknown")
        sectors[label] = sectors.get(label, pd.Series(0.0, index=weights.index)) + weights[ticker]
    panel = pd.DataFrame(sectors, index=weights.index)
    return {"classification_as_of": (current or {}).get("source_as_of"),
            "classification": "current_metadata_not_historical_sector_classification",
            "average_weights": {sector: float(value) for sector, value in panel.mean().items()},
            "peak_weights": {sector: float(value) for sector, value in panel.max().items()},
            "unknown_peak_weight": float(panel.get("Unknown", pd.Series([0.0])).max())}


def eligibility_basis_coverage(prepared, membership: dict) -> dict:
    rows = []
    for date, members in membership.items():
        if not members:
            continue
        known = sum(bool(prepared.eligibility_data_known[prepared.row(date), prepared.ticker_index[t]])
                    for t in members)
        rows.append({"date": str(date.date()), "expected": len(members), "known": known,
                     "coverage": known / len(members)})
    return {"coverage": float(np.mean([row["coverage"] for row in rows])) if rows else 0.0,
            "rebalance_dates": rows, "basis": "as_traded_close_and_unadjusted_dollar_volume"}


def render_research_v04(payload: dict) -> str:
    membership = payload["membership_history"]
    coverage = payload["price_coverage"]
    lines = ["# SHM v0.4 历史时点标普500研究", "",
             f"状态：**{payload['status']}**；胜者：**{payload['winner'] or '无'}**。", "",
             f"共同评价区间：{payload['period']['start']} → {payload['period']['end']}。",
             "本轮只更换股票池，C0–C4规则与10/25bps模型成本保持。全部属于已知历史，不是新样本外。", "",
             f"历史成分来源覆盖至 {membership['source_last_date']}；所需截止 {membership['required_end']}；"
             f"成分覆盖检查：{membership['status']}；已知成分日价格覆盖：{coverage['coverage']:.1%}。",
             "当前503证券名单未用于回填历史。成分未知区间仍保留原评价日期，暂停新增排名买入；这些区间的结果不能作为有效策略成绩。", "",
             "| 候选 | 10bps年化/回撤 | 25bps年化/回撤 | 晋级 |", "|---|---:|---:|---|"]
    for row in payload["candidates"]:
        if row["metrics_valid"]:
            a, b = row["metrics_10"], row["metrics_25"]
            lines.append(f"| {row['strategy_id']} | {a['cagr']:.2%} / {a['maxdd']:.2%} | "
                         f"{b['cagr']:.2%} / {b['maxdd']:.2%} | {'是' if row['qualified'] else '否'} |")
        else:
            lines.append(f"| {row['strategy_id']} | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |")
    lines.extend(["", "原始数字及逐日路径只保留作数据审计，不以异常CAGR宣称扩池有效。",
                  "10%为预警目标，不是本轮淘汰线。官方开盘价与模型成本不构成券商执行证据。"])
    if "eligibility_basis" in payload:
        lines.extend(["", f"当时报价与成交额的资格数据覆盖：{payload['eligibility_basis']['coverage']:.1%}。"
                      "5美元门槛使用当时实际报价，ADV60使用当时成交额；动量和收益仍用含分红复权价。"])
    repairs = payload.get("data_repairs", {})
    if repairs:
        lines.append(f"\n补入 {repairs.get('price_override_count', 0)} 只归档价格序列（不代表已通过质量验收），隔离 {repairs.get('quarantined_count', 0)} 只；隔离证券仍保留在历史成分和覆盖率分母中。")
        for issue in repairs.get("unresolved", []):
            lines.append(f"- 未解决：{issue.get('reason', issue)}")
    for row in payload["candidates"]:
        lines.extend(["", f"## {row['strategy_id']}", "",
                      "检查：" + json.dumps(row["checks"], ensure_ascii=False),
                      "警告：" + (", ".join(row["warnings"]) or "无")])
        jumps = row["holding_price_jumps_10"] + row["holding_price_jumps_25"]
        if jumps:
            lines.extend(["", "持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。"])
            lines.extend(_jump_examples(jumps))
        if row["metrics_valid"]:
            for bps in (10, 25):
                views = row[f"views_{bps}"]
                lines.extend(["", f"### {bps} bps", "", "| 年份 | 策略 | SPY |", "|---|---:|---:|"])
                for year, annual in views["annual_returns"].items():
                    label = year + ("（未完年）" if annual["partial_year"] else "")
                    lines.append(f"| {label} | {annual['strategy']:.2%} | {annual['spy']:.2%} |")
                since, excluding = views["since_2019"], views["excluding_best_year"]
                if since:
                    lines.append(f"\n2019年后年化：策略 {since['strategy']['cagr']:.2%}，SPY {since['spy']['cagr']:.2%}。")
                if excluding:
                    lines.append(f"\n剔除最佳年{excluding['removed_year']}：策略年化 {excluding['strategy']['cagr']:.2%}，SPY {excluding['spy']['cagr']:.2%}。")
        else:
            lines.append("\n逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。")
        matched = row["risk_matched_spy_10"]
        if not payload["benchmark_price_jumps"]:
            lines.append(f"\n同大盘趋势与波动预算SPY辅助对照：年化 {matched['cagr']:.2%}、回撤 {matched['maxdd']:.2%}；不含个股退出。")
        sector = row["sector_concentration_10"]
        lines.extend(["", "行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。",
                      "行业峰值权重：" + json.dumps(sector["peak_weights"], ensure_ascii=False)])
    previous = payload.get("previous_v03")
    if previous:
        previous_link = "../../" + previous["report_path"].removeprefix("reports/")
        lines.extend(["", f"原v0.3结果：[{previous['run_id']}]({previous_link})；"
                      f"旧快照 {previous['snapshot_id']}，本轮未重新运行owner股票池，不混作同快照比较。"])
    lines.extend(["", f"run_id: `{payload['run_id']}`；snapshot: `{payload['snapshot_id']}`。",
                  "复现：`uv run --no-sync shm research-v04 --repo-root .`。", ""])
    return "\n".join(lines)


def _publish_result(root: Path, directory: Path, payload: dict) -> None:
    winner, run_id = payload["winner"], payload["run_id"]
    frozen_path = root / "config/v04/winner.json"
    if frozen_path.exists():
        existing = json.loads(frozen_path.read_text())
        if existing.get("research_run_id") != run_id or existing.get("strategy_id") != winner:
            raise ValueError("another v0.4 winner is already frozen; do not overwrite it")
    frozen = None
    if winner:
        selected = next(row for row in payload["candidates"] if row["strategy_id"] == winner)
        if not selected["metrics_valid"] or not qualifies(selected):
            raise ValueError("cannot freeze an unqualified v0.4 candidate")
        frozen = {"spec_version": "0.4", "strategy_id": winner, "config": selected["config"],
                  "params_hash": json_hash(selected["config"]), "universe_hash": payload["universe_hash"],
                  "research_run_id": run_id, "frozen_at": payload["generated_at"],
                  "cost_bps": [10, 25], "evidence": "known_history"}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.md").write_text(render_research_v04(payload), encoding="utf-8")
    ledger = root / "experiments/v04/log.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    previous = {json.loads(line)["run_id"] for line in ledger.read_text().splitlines() if line.strip()} if ledger.exists() else set()
    if run_id not in previous:
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"run_id": run_id, "snapshot_id": payload["snapshot_id"],
                                     "source_hash": payload["source_hash"], "evidence": "known_history",
                                     "candidate_ids": list(SP500_IDS), "winner": winner,
                                     "status": payload["status"], "universe_policy": "historical_sp500_constituents"}) + "\n")
    if frozen is not None:
        write_json(frozen_path, frozen)
    write_json(directory / "selection.json", payload)
    write_json(root / "reports/v04/selection.json", payload)


def run_research_v04(repo_root: Path | str, *, progress: Callable[[str], None] = print) -> dict:
    root = Path(repo_root).resolve()
    config_path = root / "config/v04/research.yaml"
    config = yaml.safe_load(config_path.read_text())
    if (tuple(config["candidate_ids"]) != SP500_IDS or str(config["cutoff"]) != CUTOFF
            or str(config["dev_start"]) != "2005-01-01" or str(config["spec_version"]) != "0.4"
            or config["universe"] != "historical_sp500_constituents"
            or config["cost_bps"] != [10, 25] or float(config["minimum_pit_coverage"]) != .80):
        raise ValueError("v0.4 is the fixed S500-C0..C4 / 10-25bps / 0.80 PIT coverage study")
    prereg_hashes = {}
    for strategy_id in SP500_IDS:
        path = root / "experiments/prereg/v04" / f"{strategy_id}.md"
        if "Owner批准" not in path.read_text():
            raise ValueError(f"missing approved preregistration: {strategy_id}")
        prereg_hashes[str(path.relative_to(root))] = file_hash(path)
    end = pd.Timestamp(CUTOFF)
    schedule = xnys_rebalance_dates(config["dev_start"], end, warmup_trading_days=260, every_trading_days=20)
    calendar = xcals.get_calendar("XNYS", start=pd.Timestamp(config["dev_start"]) - pd.Timedelta(days=900), end=end)
    first = calendar.sessions.get_loc(schedule[0])
    sessions = calendar.sessions[first - 260:]
    evaluation = sessions[sessions > schedule[0]]
    history, membership_hashes, membership_repairs = load_membership(root)
    membership, history_evidence = historical_membership(history, schedule, evaluation)
    universe = sorted({ticker for members in membership.values() for ticker in members})
    if not universe:
        raise ValueError("historical PIT membership contains no securities for the fixed evaluation period")
    prices, hashes, missing = _load_prices(root, universe + ["SPY"], sessions[0], end)
    prices, hashes, missing, data_repairs = apply_price_repairs(root, prices, hashes, missing, sessions[0], end)
    if "SPY" not in prices:
        raise ValueError("SPY cache is required")
    current_path = root / "data/reference/sp500/current.json"
    current = json.loads(current_path.read_text()) if current_path.exists() else None
    all_hashes = {**hashes, **prereg_hashes, **membership_hashes,
                  str(config_path.relative_to(root)): file_hash(config_path)}
    if current is not None:
        all_hashes[str(current_path.relative_to(root))] = file_hash(current_path)
    snapshot_id = json_hash(all_hashes)
    source_hash = _source_hash(root)
    run_id = "v04-" + json_hash({"snapshot": snapshot_id, "source": source_hash, "config": config})[:16]
    directory = root / "reports/v04" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "selection.json").exists():
        payload = json.loads((directory / "selection.json").read_text())
        _publish_result(root, directory, payload)
        return payload
    write_json(directory / "snapshot.json", {"snapshot_id": snapshot_id, "files": all_hashes,
                                             "source_hash": source_hash, "missing_pit": missing,
                                             "membership_history": history_evidence})
    progress(f"Preparing historical PIT universe ({len(universe)} securities); membership through {history_evidence['source_last_date']}")
    prepared = prepare_inputs(prices, universe, sessions, schedule, membership_by_session=membership,
                              require_point_in_time_eligibility=True)
    coverage = price_coverage(prices, membership)
    basis_coverage = eligibility_basis_coverage(prepared, membership)
    benchmarks = {bps: _spy_buy_hold(prices["SPY"], evaluation, bps) for bps in (10, 25)}
    benchmark_metrics = {bps: performance(series) for bps, series in benchmarks.items()}
    benchmark_jumps = _benchmark_price_jumps(prepared, evaluation)
    rows = []
    for strategy_id in SP500_IDS:
        candidate = base_candidate(strategy_id)
        progress(f"Evaluating {strategy_id} at 10/25 bps on historical constituents")
        row = {"strategy_id": strategy_id, "config": candidate_config(strategy_id),
               "module_count": CANDIDATES[candidate].modules, "pit": None,
               "warnings": [], "checks": {
                   "MEMBERSHIP_HISTORY_COVERAGE": history_evidence["status"],
                   "PIT_PRICE_COVERAGE": "PASS" if coverage["coverage"] >= .80 else "INCONCLUSIVE",
                   "PIT_ELIGIBILITY_BASIS": "PASS" if basis_coverage["coverage"] >= .80 else "INCONCLUSIVE",
                   "PRICE_REPAIR_EVIDENCE": data_repairs["status"],
               }}
        for bps in (10, 25):
            result = run_simulation(prices, universe, candidate, sessions, schedule,
                                    cost_bps=bps, prepared=prepared)
            row[f"metrics_{bps}"] = _save_result(directory, strategy_id, bps, result, evaluation)
            row[f"benchmark_{bps}"] = benchmark_metrics[bps]
            jumps = _holding_price_jumps(prepared, result.backtest, evaluation)
            row[f"holding_price_jumps_{bps}"] = jumps
            row["checks"].update({f"{key}_{bps}": value for key, value in _correctness(
                result, evaluation, holding_price_jumps=jumps, benchmark_price_jumps=benchmark_jumps).items()})
            row[f"views_{bps}"] = _return_views(result.backtest.equity.reindex(evaluation), benchmarks[bps])
            row[f"risk_matched_spy_{bps}"] = _matched_spy(prices, schedule, evaluation, bps, candidate)
            row[f"sector_concentration_{bps}"] = sector_concentration(result.backtest.weights.reindex(evaluation), current)
            if bps == 10:
                row["views"] = row["views_10"]
                selections = [decision for decision in result.decisions if decision["diagnostics"].get("rebalance")]
                insufficient = [decision["signal_date"] for decision in selections if decision["eligible_count"] < 30]
                row["universe_eligibility"] = {"rebalance_count": len(selections), "below_30_count": len(insufficient),
                                               "minimum_count": min((decision["eligible_count"] for decision in selections), default=0),
                                               "insufficient_dates": insufficient}
        row["metrics_valid"] = all(value == "PASS" for value in row["checks"].values())
        if history_evidence["status"] != "PASS":
            row["warnings"].append("WARN_MEMBERSHIP_HISTORY_INCOMPLETE")
        if coverage["coverage"] < .80:
            row["warnings"].append("WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT")
        if basis_coverage["coverage"] < .80:
            row["warnings"].append("WARN_POINT_IN_TIME_ELIGIBILITY_COVERAGE")
        if data_repairs["status"] != "PASS":
            row["warnings"].append("WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE")
        if row["holding_price_jumps_10"] or row["holding_price_jumps_25"]:
            row["warnings"].append("WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID")
        if benchmark_jumps:
            row["warnings"].append("WARN_BENCHMARK_PRICE_JUMPS")
        ex = row["views"]["excluding_best_year"]
        if ex and ex["strategy"]["cagr"] <= ex["spy"]["cagr"]:
            row["warnings"].append("WARN_ONE_YEAR_DEPENDENCY")
        row["qualified"] = qualifies(row)
        rows.append(row)
        write_json(directory / f"{strategy_id}.json", row)
    winner = select_winner(rows)
    status = "HISTORICAL_SCREEN_PASS" if winner else "NO_QUALIFIED_CANDIDATE"
    if not winner and all(not row["metrics_valid"] for row in rows):
        status = "INCONCLUSIVE"
    previous_path = root / "reports/v03/selection.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    payload = {"spec_version": "0.4", "evidence": "known_history", "run_id": run_id,
               "generated_at": datetime.now(timezone.utc).isoformat(), "snapshot_id": snapshot_id,
               "source_hash": source_hash, "universe_hash": json_hash(membership_hashes),
               "universe_policy": "historical_sp500_constituents",
               "period": {"start": str(evaluation[0].date()), "end": CUTOFF},
               "winner": winner, "status": status, "candidates": rows,
               "data_repairs": data_repairs, "membership_repairs": membership_repairs,
               "eligibility_basis": basis_coverage,
               "benchmark_10": benchmark_metrics[10], "benchmark_25": benchmark_metrics[25],
               "benchmark_price_jumps": benchmark_jumps, "membership_history": history_evidence,
               "price_coverage": coverage, "missing_pit_tickers": missing,
               "previous_v03": {key: previous[key] for key in ("run_id", "snapshot_id", "report_path")} if previous else None,
               "report_path": f"reports/v04/{run_id}/report.md"}
    if _source_hash(root) != source_hash:
        raise RuntimeError("source changed during research; v0.4 results were not published or frozen")
    _publish_result(root, directory, payload)
    progress(f"{status}; winner={winner}; report={directory / 'report.md'}")
    return payload
