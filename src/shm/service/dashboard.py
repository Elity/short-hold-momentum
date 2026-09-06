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


def list_reports(root: Path) -> list[dict]:
    reports = []
    for path in sorted((root / "reports").glob("paper-????-??.md"), reverse=True):
        month = path.stem.removeprefix("paper-")
        reports.append({
            "id": f"monthly/{month}", "kind": "monthly",
            "title": f"{month} · 模拟盘月报", "date": month,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        })
    for path in sorted((root / "paper/options").glob("????-??-??.json"), reverse=True):
        reports.append({
            "id": f"options/{path.stem}", "kind": "options",
            "title": f"{path.stem} · 期权覆盖评估", "date": path.stem,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        })
    return sorted(reports, key=lambda row: row["date"], reverse=True)


def read_report(root: Path, report_id: str) -> dict:
    monthly = re.fullmatch(r"monthly/(\d{4}-\d{2})", report_id)
    options = re.fullmatch(r"options/(\d{4}-\d{2}-\d{2})", report_id)
    if monthly:
        path = root / "reports" / f"paper-{monthly[1]}.md"
        kind = "monthly"
    elif options:
        path = root / "paper/options" / f"{options[1]}.json"
        kind = "options"
    else:
        raise FileNotFoundError("报告不存在")
    return {"id": report_id, "kind": kind, "content": path.read_text(encoding="utf-8")}


def build_dashboard(root: Path, store: ServiceStore, timezone_name: str, *, now=None) -> dict:
    now = now or datetime.now(UTC)
    result = build_portfolio(root, now=now)
    progress = build_paper_progress(root)
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
        "runs": runs, "reports": list_reports(root),
        "schedule": {
            "time": daily_time, "timezone": timezone_name,
            "next_at": scheduled.isoformat(), "due": scheduled <= local_now,
        },
        "progress": {
            "completed": len(progress.completed_cycles),
            "pending": len(progress.pending_cycles), "missed": len(progress.missed_cycles),
            "months": len(progress.monthly_reports),
            "next": _date(progress.next_rebalance_date),
            "complete": progress.p4_evidence_complete,
        },
    })
    return result
