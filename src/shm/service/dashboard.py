"""Read-only projections of the paper ledger for the investment dashboard."""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from shm.data.prices import read_price_cache
from shm.paper.core import PaperAccount, read_fill_csv, read_ticket_csv
from shm.paper.status import build_paper_progress
from shm.service.store import ServiceStore
from shm.service.workflow import latest_completed_session
from shm.universe.core import indexed_prices

STRATEGIES = {
    "V04": "V04 · 原策略",
    "C0": "C0 · 当期资格轮动",
    "C1": "C1 · 每日市场趋势退出",
    "C2": "C2 · 个股 SMA50",
    "C3": "C3 · ATR20 跟踪退出",
    "C4": "C4 · 20% 波动率预算",
    "S500-C0": "S500-C0 · 跨行业 S&P 500 轮动",
    "S500-C1": "S500-C1 · 每日市场趋势退出",
    "S500-C2": "S500-C2 · 个股 SMA50",
    "S500-C3": "S500-C3 · ATR20 跟踪退出",
    "S500-C4": "S500-C4 · 20% 波动率预算",
}


def _strategy_id(value: str) -> str:
    if value not in STRATEGIES:
        raise ValueError("未知策略版本")
    return value


def _strategy_metadata(root: Path, strategy_id: str, cost_bps: int) -> dict:
    sp500 = strategy_id.startswith("S500-")
    selection_path = root / "reports" / ("v04" if sp500 else "v03") / "selection.json"
    selection = json.loads(selection_path.read_text()) if selection_path.exists() else None
    manifest_path = _paper_directory(root, strategy_id) / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    mode = "legacy" if strategy_id == "V04" else manifest.get("account_mode", "qualified" if manifest else None)
    return {
        "id": strategy_id, "label": STRATEGIES[strategy_id],
        "version": "0.4" if sp500 else "0.2" if strategy_id == "V04" else "0.3",
        "universe_label": "跨行业 S&P 500 · 历史时点成分股" if sp500 else "原股票池",
        "evidence": "forward_paper",
        "cost_bps": 0 if strategy_id == "V04" else cost_bps,
        "cost_assumption": (
            "官方开盘价、零佣金的本地模型，不构成实测券商执行成本。"
            if strategy_id == "V04" else
            f"单边 {cost_bps} bps 为模型成本假设，非实测券商成交；期权草稿收益不入账。"
        ),
        "historical_screen": selection,
        "account_mode": mode,
        "historical_qualification": "UNVALIDATED" if mode == "observation" else None,
    }


def _paper_directory(root: Path, strategy_id: str) -> Path:
    return root / "paper" / ("v04" if strategy_id.startswith("S500-") else "v03") / strategy_id


def _date(value) -> str:
    return str(pd.Timestamp(value).date())


def _number(value) -> float | None:
    return float(value) if value is not None and math.isfinite(float(value)) else None


def _accounts(root: Path) -> list[tuple[pd.Timestamp, PaperAccount]]:
    result = []
    for path in sorted((root / "paper/accounts").glob("????-??-??.json")):
        payload = json.loads(path.read_text())
        result.append((
            pd.Timestamp(payload.get("as_of", path.stem)).normalize(),
            PaperAccount(
                cash=payload["cash"], positions=payload["positions"], mode=payload["mode"]
            ),
        ))
    if not result:
        raise ValueError("尚无账户快照，请先建立 P4 模拟账户")
    return sorted(result, key=lambda item: item[0])


def _ledger(root: Path, snapshots, warnings: list[str]):
    start, initial = snapshots[0]
    end, current = snapshots[-1]
    shares = dict(initial.positions)
    cost = {ticker: None for ticker in shares}
    trades, plans = [], []
    realized = 0.0
    unknown_realized = False
    calendar = xcals.get_calendar(
        "XNYS", start=start - pd.Timedelta("10D"), end=end + pd.Timedelta("10D")
    )
    for path in sorted((root / "paper/tickets").glob("????-??-??.csv")):
        if pd.Timestamp(path.stem) < start:
            continue
        for ticket in read_ticket_csv(path):
            plans.append({
                "signal_date": path.stem, "symbol": ticket.ticker,
                "side": ticket.side, "qty": ticket.qty, "reason": ticket.reason,
                "order_type": ticket.order_type, "time_in_force": ticket.time_in_force,
            })
    for path in sorted((root / "paper/fills").glob("????-??-??.csv")):
        day = pd.Timestamp(path.stem)
        if not start <= day <= end:
            continue
        signal = _date(calendar.previous_session(day))
        tickets = {
            row.ticker: row
            for row in read_ticket_csv(root / "paper/tickets" / f"{signal}.csv")
        }
        # Match ingestion: sells release cash before buys, then execution order.
        fills = sorted(
            read_fill_csv(path),
            key=lambda fill: (0 if tickets[fill.ticker].side == "sell" else 1, fill.fill_time),
        )
        for index, fill in enumerate(fills):
            ticket = tickets[fill.ticker]
            ticker, qty = fill.ticker, fill.qty
            held = shares.get(ticker, 0)
            book = cost.get(ticker, 0.0)
            average = book / held if held and book is not None else None
            profit = None
            if ticket.side == "buy":
                shares[ticker] = held + qty
                cost[ticker] = (
                    book + qty * fill.fill_price + fill.commission
                    if book is not None else None
                )
            else:
                if qty > held:
                    raise ValueError(f"{ticker} 卖出数量超过已记录持仓")
                if average is not None:
                    profit = qty * (fill.fill_price - average) - fill.commission
                    realized += profit
                else:
                    unknown_realized = True
                shares[ticker] = held - qty
                cost[ticker] = average * (held - qty) if average is not None else None
                if not shares[ticker]:
                    shares.pop(ticker)
                    cost.pop(ticker)
            trades.append({
                "id": f"{path.stem}-{index}", "date": path.stem,
                "filled_at": str(fill.fill_time), "signal_date": signal,
                "symbol": ticker, "side": ticket.side, "qty": qty,
                "price": fill.fill_price, "amount": qty * fill.fill_price,
                "commission": fill.commission, "realized_pnl": profit,
                "cost": average, "reason": ticket.reason,
            })
    if shares != dict(current.positions):
        warnings.append("成交记录与当前账户持仓不一致，成本及已实现盈亏暂不可用")
        cost = {ticker: None for ticker in current.positions}
        unknown_realized = True
    return trades, plans, cost, None if unknown_realized else realized


def _marks(root: Path, tickers, start, end, warnings):
    result = {}
    for ticker in sorted(tickers):
        try:
            frame = read_price_cache(
                root / "data/raw/prices" / f"{ticker}.parquet",
                ticker=ticker, start=_date(start - pd.Timedelta("10D")),
                end=_date(end), mode="paper", paper_sessions=260,
            )
            result[ticker] = indexed_prices(frame)["close"]
        except (OSError, ValueError, KeyError) as exc:
            warnings.append(f"{ticker} 行情不可用：{exc}")
            result[ticker] = pd.Series(dtype=float)
    return result


def build_portfolio(root: Path, *, now: datetime | None = None) -> dict:
    snapshots = _accounts(root)
    start, initial = snapshots[0]
    account_day, current = snapshots[-1]
    market_day = latest_completed_session(now)
    warnings: list[str] = []
    trades, plans, costs, realized = _ledger(root, snapshots, warnings)
    symbols = {ticker for _, account in snapshots for ticker in account.positions}
    prices = _marks(root, symbols | {"SPY"}, start, market_day, warnings)
    holdings = []
    for ticker, qty in current.positions.items():
        price = _number(prices[ticker].get(market_day))
        book = costs.get(ticker)
        if price is None:
            warnings.append(f"{ticker} 缺少 {_date(market_day)} 收盘价，当前资产估值待补齐")
        if book is None:
            warnings.append(f"{ticker} 缺少完整成本依据，持仓盈亏待补齐")
        value = price * qty if price is not None else None
        pnl = value - book if value is not None and book is not None else None
        holdings.append({
            "symbol": ticker, "qty": qty, "cost": book / qty if book is not None else None,
            "price": price, "value": value, "pnl": pnl,
            "pnl_percent": pnl / book * 100 if pnl is not None and book else None,
            "quote_date": _date(market_day) if price is not None else None,
        })
    complete_marks = all(h["value"] is not None for h in holdings)
    complete_costs = all(h["pnl"] is not None for h in holdings)
    market_value = sum(h["value"] for h in holdings) if complete_marks else None
    total = current.cash + market_value if market_value is not None else None
    unrealized = sum(h["pnl"] for h in holdings) if complete_costs else None
    initial_equity = initial.cash if not initial.positions else None
    gain = total - initial_equity if total is not None and initial_equity is not None else None
    for holding in holdings:
        holding["weight"] = holding["value"] / total * 100 if total else None
    holdings.sort(key=lambda h: h["value"] if h["value"] is not None else -1, reverse=True)

    chart = [{"date": _date(start), "equity": initial_equity, "benchmark": initial_equity}]
    calendar = xcals.get_calendar(
        "XNYS", start=start - pd.Timedelta("10D"), end=max(start, market_day) + pd.Timedelta("10D")
    )
    days = calendar.sessions_in_range(start, market_day) if start <= market_day else []
    spy = prices["SPY"]
    base = spy.loc[spy.index <= start]
    base_price = _number(base.iloc[-1]) if not base.empty else None
    if base_price is None:
        chart[0]["benchmark"] = None
    for day in days:
        applicable = [snapshot for snapshot in snapshots if snapshot[0] <= day]
        if not applicable:
            continue
        _, daily_account = applicable[-1]
        values = [_number(prices[ticker].get(day)) for ticker in daily_account.positions]
        equity = daily_account.cash + sum(
            qty * price for qty, price in zip(daily_account.positions.values(), values)
        ) if all(price is not None for price in values) else None
        spy_price = _number(spy.get(day))
        benchmark = (
            initial_equity * spy_price / base_price
            if initial_equity is not None and spy_price is not None and base_price else None
        )
        point = {"date": _date(day), "equity": equity, "benchmark": benchmark}
        if chart[-1]["date"] == point["date"]:
            chart[-1] = point
        else:
            chart.append(point)
    day_pnl = None
    if len(chart) > 1 and chart[-1]["equity"] is not None and chart[-2]["equity"] is not None:
        day_pnl = chart[-1]["equity"] - chart[-2]["equity"]
    return {
        "account": {
            "cash": current.cash, "market": market_value, "total": total,
            "unrealized": unrealized, "realized": realized, "gain": gain,
            "gain_percent": gain / initial_equity * 100 if gain is not None and initial_equity else None,
            "day": day_pnl, "initial": initial_equity, "start": _date(start),
            "asof": _date(account_day), "valuation_date": _date(max(start, market_day)),
            "market_session": _date(market_day),
        },
        "holdings": holdings, "trades": list(reversed(trades)),
        "tickets": sorted(plans, key=lambda row: row["signal_date"], reverse=True),
        "chart": chart, "warnings": warnings,
    }


def list_reports(root: Path, *, strategy_id: str = "V04") -> list[dict]:
    _strategy_id(strategy_id)
    reports = []
    directory = root / "reports" if strategy_id == "V04" else _paper_directory(root, strategy_id) / "reports"
    pattern = "paper-????-??.md" if strategy_id == "V04" else "????-??.md"
    for path in sorted(directory.glob(pattern), reverse=True):
        month = path.stem.removeprefix("paper-")
        reports.append({
            "id": f"monthly/{month}", "kind": "monthly",
            "title": f"{month} · 模拟盘月报", "date": month,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        })
    option_directory = root / "paper/options" if strategy_id == "V04" else _paper_directory(root, strategy_id) / "options"
    for path in sorted(option_directory.glob("????-??-??.json"), reverse=True):
        reports.append({
            "id": f"options/{path.stem}", "kind": "options",
            "title": f"{path.stem} · 期权覆盖评估", "date": path.stem,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        })
    return sorted(reports, key=lambda row: row["date"], reverse=True)


def read_report(root: Path, report_id: str, *, strategy_id: str = "V04") -> dict:
    _strategy_id(strategy_id)
    monthly = re.fullmatch(r"monthly/(\d{4}-\d{2})", report_id)
    options = re.fullmatch(r"options/(\d{4}-\d{2}-\d{2})", report_id)
    if monthly:
        path = (root / "reports" / f"paper-{monthly[1]}.md" if strategy_id == "V04"
                else _paper_directory(root, strategy_id) / "reports" / f"{monthly[1]}.md")
        kind = "monthly"
    elif options:
        directory = root / "paper/options" if strategy_id == "V04" else _paper_directory(root, strategy_id) / "options"
        path = directory / f"{options[1]}.json"
        kind = "options"
    else:
        raise FileNotFoundError("报告不存在")
    return {"id": report_id, "kind": kind, "content": path.read_text(encoding="utf-8")}


def _build_v03_portfolio(root: Path, strategy_id: str, cost_bps: int, now: datetime) -> dict:
    directory = _paper_directory(root, strategy_id)
    manifest_path = directory / "manifest.json"
    market_day = _date(latest_completed_session(now))
    empty = {
        "account": {key: None for key in (
            "cash", "market", "total", "unrealized", "realized", "gain", "gain_percent",
            "day", "initial", "start", "asof", "valuation_date",
        )},
        "holdings": [], "trades": [], "tickets": [], "chart": [], "warnings": [],
        "progress": {"completed": 0, "pending": 0, "missed": 0, "months": 0,
                     "next": None, "complete": False},
        "performance_verdict": "NOT_STARTED", "risk": None,
    }
    empty["account"]["market_session"] = market_day
    if not manifest_path.exists():
        return empty

    from shm.paper.v03 import paper_v03_status

    status = paper_v03_status(root, strategy_id)
    manifest = json.loads(manifest_path.read_text())
    current = status["books"][str(cost_bps)]
    initial = manifest["initial_cash"]
    total = current["equity"]
    start = status["forward_start"] or (manifest["initialized_at"][:10] if status["account_mode"] == "observation"
                                        else manifest["initialized_after_session"])
    rows = [json.loads(path.read_text()) for path in sorted((directory / "days").glob("????-??-??.json"))]
    trades, plans, chart = [], [], []
    corporate_cash_pnl = 0.0
    for row in rows:
        if not row.get("forward_start"):
            continue
        day = row["last_session"]
        book = row["books"][str(cost_bps)]
        corporate_cash_pnl += sum(float(event.get("realized_cash_pnl", 0.0))
                                  for event in book.get("execution", {}).get("events", [])
                                  if event.get("action") == "corporate_action_conversion")
        for index, trade in enumerate(book.get("execution", {}).get("transactions", [])):
            realized = trade.get("realized_pnl")
            quantity = trade["quantity"]
            average_cost = ((trade["notional"] - trade["cost"] - realized) / quantity
                            if realized is not None and trade["side"] == "sell" else None)
            trades.append({
                "id": f"{day}-{index}", "date": trade["execution_date"],
                "filled_at": xcals.get_calendar("XNYS").session_open(pd.Timestamp(day)).isoformat(),
                "signal_date": trade["signal_date"], "symbol": trade["ticker"],
                "side": trade["side"], "qty": quantity, "price": trade["price"],
                "amount": trade["notional"], "commission": trade["cost"],
                "realized_pnl": realized, "cost": average_cost,
                "reason": trade["reason"], "event_type": trade["event_type"],
            })
        decision = book.get("decision", {})
        positions = book["state"]["positions"]
        exits = decision.get("exits", {})
        for ticker, reason in exits.items():
            plans.append({"signal_date": day, "symbol": ticker, "side": "sell",
                          "qty": positions.get(ticker, {}).get("quantity"),
                          "reason": reason, "event_type": "risk_exit"})
        for ticker, weight in (decision.get("target_weights") or {}).items():
            if ticker not in exits:
                plans.append({"signal_date": day, "symbol": ticker, "side": "target",
                              "qty": None, "target_weight": weight,
                              "reason": "rebalance", "event_type": "rebalance"})
        benchmark = book.get("benchmark")
        chart.append({"date": day, "equity": book["valuation"]["equity"],
                      "benchmark": benchmark["equity"] if benchmark and benchmark.get("complete") else None})
    if not chart:
        chart = [{"date": start, "equity": initial, "benchmark": None}]
    exits = {**current.get("blocked_exits", {}), **current.get("pending", {}).get("exits", {})}
    mark_dates = rows[-1]["books"][str(cost_bps)]["state"].get("mark_dates", {}) if rows else {}
    holdings = []
    for position in current["positions"]:
        reason = exits.get(position["ticker"])
        if isinstance(reason, dict):
            reason = reason.get("reason")
        cost = position["average_cost"] * position["quantity"]
        holdings.append({
            "symbol": position["ticker"], "qty": position["quantity"],
            "cost": position["average_cost"], "price": position["mark"],
            "value": position["market_value"], "pnl": position["unrealized_pnl"],
            "pnl_percent": position["unrealized_pnl"] / cost * 100 if cost and position["unrealized_pnl"] is not None else None,
            "weight": position["market_value"] / total * 100 if total and position["market_value"] is not None else None,
            "quote_date": mark_dates.get(position["ticker"]), "entry_date": position["entry_date"],
            "peak": position["peak_close"], "trailing_line": position["trailing_stop"],
            "exit_reason": reason,
        })
    warnings = list(current["decision"].get("warnings", []))
    for holding in holdings:
        if holding["quote_date"] != status["last_session"]:
            warnings.append(f"{holding['symbol']} 最新估值沿用 {holding['quote_date'] or '未知日期'} 行情，当前交易日价格待补齐。")
    if current["drawdown_warning"]:
        warnings.append("账户回撤已触及 10% 预警线，需复盘；预警本身不触发强制清仓。")
    if status["missed_sessions"]:
        warnings.append("存在错过的前向交易日：" + ", ".join(status["missed_sessions"]))
    unrealized = [holding["pnl"] for holding in holdings]
    receivables = float(current.get("corporate_receivables", 0.0))
    if receivables:
        warnings.append(f"并购现金应收 ${receivables:,.2f} 已计入资产，尚未到账，不能用于买入。")
    return {
        "account": {
            "cash": current["cash"], "market": total - current["cash"] - receivables, "total": total,
            "corporate_receivables": receivables,
            "unrealized": sum(unrealized) if all(value is not None for value in unrealized) else None,
            "realized": sum(trade["realized_pnl"] or 0 for trade in trades) + corporate_cash_pnl,
            "gain": total - initial, "gain_percent": (total / initial - 1) * 100,
            "day": chart[-1]["equity"] - chart[-2]["equity"] if len(chart) > 1 else None,
            "initial": initial, "start": start, "asof": status["last_session"],
            "initialized_at": manifest["initialized_at"],
            "valuation_date": status["last_session"], "market_session": market_day,
            "spy_return": current["spy_cumulative_return"], "excess_return": current["excess_return"],
        },
        "holdings": sorted(holdings, key=lambda holding: holding["value"] or 0, reverse=True),
        "trades": list(reversed(trades)), "tickets": list(reversed(plans)),
        "chart": chart, "warnings": warnings,
        "progress": {"completed": status["completed_rebalance_cycles"],
                     "pending": int(bool(current["pending"])), "missed": len(status["missed_sessions"]),
                     "months": status["monthly_report_count"], "next": status["next_rebalance_date"],
                     "complete": status["operational_acceptance"]},
        "performance_verdict": status["performance_verdict"] if status["forward_start"] else "AWAITING_FIRST_SIGNAL",
        "risk": {"drawdown": current["drawdown"], "equity_peak": current["equity_high_water"],
                 "drawdown_alert": current["drawdown_warning"],
                 "allow_new_risk": current["allow_new_risk"],
                 "max_total_exposure": current["max_total_exposure"]},
    }


def build_dashboard(root: Path, store: ServiceStore, timezone_name: str, *, now=None,
                    strategy_id: str = "V04", cost_bps: int = 10) -> dict:
    _strategy_id(strategy_id)
    if cost_bps not in (10, 25):
        raise ValueError("模型成本只支持 10 或 25 bps")
    now = now or datetime.now(UTC)
    if strategy_id == "V04":
        result = build_portfolio(root, now=now)
        progress = build_paper_progress(root)
        result["progress"] = {
            "completed": len(progress.completed_cycles),
            "pending": len(progress.pending_cycles), "missed": len(progress.missed_cycles),
            "months": len(progress.monthly_reports), "next": _date(progress.next_rebalance_date),
            "complete": progress.p4_evidence_complete,
        }
    else:
        result = _build_v03_portfolio(root, strategy_id, cost_bps, now)
    since = (now - timedelta(days=90)).isoformat()
    runs = [asdict(run) for run in store.list_runs(limit=None, since=since)]
    local_now = now.astimezone(ZoneInfo(timezone_name))
    daily_time = store.get_setting("daily_time", "05:30")
    hour, minute = map(int, daily_time.split(":"))
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if store.find_scheduled_run(str(local_now.date())):
        scheduled += timedelta(days=1)
    result.update({
        "generated_at": now.isoformat(),
        "runs": runs, "reports": list_reports(root, strategy_id=strategy_id),
        "schedule": {
            "time": daily_time, "timezone": timezone_name,
            "next_at": scheduled.isoformat(), "due": scheduled <= local_now,
        },
        "strategy": _strategy_metadata(root, strategy_id, cost_bps),
        "strategies": [{"id": key, "label": label} for key, label in STRATEGIES.items()],
    })
    result["strategy"]["performance_verdict"] = result.pop("performance_verdict", "LEGACY_FORWARD")
    if strategy_id.startswith("S500-"):
        from shm.universe.sp500 import load_sp500_snapshot, sp500_status

        source = sp500_status(root, latest_completed_session(now), now=now)
        market_path = root / "data/market_refresh/latest.json"
        market = json.loads(market_path.read_text()) if market_path.exists() else {}
        snapshot = load_sp500_snapshot(root)
        symbols = [member["symbol"] for member in snapshot["members"]] if snapshot else []
        current_session = _date(latest_completed_session(now))
        same_day = market.get("date") == current_session
        observations = market.get("results", {})
        source["market_data"] = {
            "date": market.get("date"), "same_session": same_day,
            "quote_current": sum(observations.get(ticker, {}).get("latest") == current_session for ticker in symbols) if same_day else 0,
            "history_complete": market.get("universe_fresh", 0) if same_day else 0,
            "expected": len(symbols), "complete": bool(same_day and market.get("complete")),
            "eligibility_basis_ready": market.get("universe_eligibility_fields_ready", 0) if same_day else 0,
            "eligibility_basis_required": market.get("require_point_in_time_eligibility") is True,
            "missing": market.get("missing", []), "provider_calls": market.get("requested"),
        }
        source["market_data"]["complete"] = bool(
            source["market_data"]["complete"] and source["market_data"]["eligibility_basis_required"]
            and not market.get("eligibility_fields_missing")
        )
        result["universe"] = source
        if not source["market_data"]["complete"]:
            result["warnings"].append("S&P 500 同日行情或历史窗口尚未齐全，新增仓位暂停；已有持仓风险检查继续。")
            if result.get("risk"):
                result["risk"]["allow_new_risk"] = False
        if not source["allow_new_risk"]:
            result["warnings"].append("S&P 500 来源未通过当前交易日核验，暂停新增买入；已有持仓继续执行风险退出。")
            if result.get("risk"):
                result["risk"]["allow_new_risk"] = False
    return result
