"""Version-isolated forward paper ledgers using the shared v0.3 decision engine.

Daily JSON files are the committed ledger. ``state.json`` is only a recoverable
cache, so an interrupted write or a repeated daily job cannot apply fills twice.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Iterator, Mapping

import exchange_calendars as xcals
import pandas as pd
import yaml

from shm.data.prices import read_price_cache
from shm.paper.core import paper_xnys_window
from shm.universe.calendar import xnys_rebalance_dates
from shm.v04.profiles import base_candidate, candidate_config, family, version, account_directory
from shm.v03.engine import advance_open
from shm.v03.strategy import (
    CANDIDATES,
    PortfolioState,
    evaluate_close,
    prepare_inputs,
)


COST_BOOKS = (10, 25)
INITIAL_CASH = 100_000.0
INCOMPLETE_EXECUTION = {
    "unfilled_entry", "pending_exit", "incomplete_open_valuation",
    "missed_execution", "unverified_price_basis", "new_risk_blocked",
}


def _jsonable(value: object) -> object:
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True,
                   allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _hash(payload: object) -> str:
    canonical = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _utc(now: object | None = None) -> pd.Timestamp:
    stamp = pd.Timestamp(now if now is not None else datetime.now(UTC))
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _calendar(start: object, end: object):
    return xcals.get_calendar(
        "XNYS", start=pd.Timestamp(start).normalize() - pd.Timedelta(days=10),
        end=pd.Timestamp(end).normalize() + pd.Timedelta(days=10),
    )


def _latest_completed(now: object | None = None) -> pd.Timestamp:
    stamp = _utc(now)
    day = stamp.normalize().tz_localize(None)
    calendar = _calendar(day - pd.Timedelta(days=14), day)
    completed = [s for s in calendar.sessions if calendar.session_close(s) <= stamp]
    return pd.Timestamp(completed[-1]).normalize()


def _current_session(as_of: object | None, now: object | None) -> pd.Timestamp:
    latest = _latest_completed(now)
    requested = latest if as_of is None else pd.Timestamp(as_of).normalize()
    if requested.tzinfo is not None:
        requested = requested.tz_localize(None)
    if requested != latest:
        raise ValueError(
            "v0.3 paper decisions require the latest completed XNYS session; "
            "historical dates cannot be backfilled as timely forward signals"
        )
    return requested


def _directory(root: Path, strategy_id: str) -> Path:
    return account_directory(root, strategy_id)


@contextmanager
def _locked(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _winner(root: Path, strategy_id: str) -> dict:
    path = root / "config" / family(strategy_id) / "winner.json"
    if not path.exists():
        raise ValueError("v0.3 paper requires a frozen qualifying winner")
    winner = _read(path)
    if winner.get("strategy_id") != strategy_id or winner.get("spec_version") != version(strategy_id):
        raise ValueError("only the frozen v0.3 winner may initialize or run paper")
    if winner.get("params_hash") != _hash(winner.get("config")):
        raise ValueError("frozen v0.3 candidate hash does not match its configuration")
    if winner["params_hash"] != _hash(candidate_config(strategy_id)):
        raise ValueError("implemented v0.3 candidate differs from the frozen configuration")
    if version(strategy_id) == "0.3":
        owner_hash = hashlib.sha256((root / "config/universe.yaml").read_bytes()).hexdigest()
        if winner.get("universe_hash") != owner_hash:
            raise ValueError("owner universe changed after v0.3 winner freeze")
    if list(winner.get("cost_bps", [])) != list(COST_BOOKS):
        raise ValueError("v0.3 paper requires both 10 and 25 bps ledgers")
    return winner


def _schedule(root: Path, through: object) -> pd.DatetimeIndex:
    dates = yaml.safe_load((root / "config/dates.yaml").read_text(encoding="utf-8"))
    return xnys_rebalance_dates(
        dates["dev_start"], pd.Timestamp(through),
        warmup_trading_days=int(dates["warmup_trading_days"]),
        every_trading_days=int(dates["rebalance_every_trading_days"]),
    )


def _next_signal(root: Path, after: object) -> str:
    after = pd.Timestamp(after)
    future = _schedule(root, after + pd.Timedelta(days=90))
    return str(future[future > after][0].date())


def _manifest(root: Path, strategy_id: str) -> tuple[Path, dict]:
    directory = _directory(root, strategy_id)
    manifest = _read(directory / "manifest.json")
    if manifest["winner_hash"] != _hash(_winner(root, strategy_id)):
        raise ValueError("v0.3 winner identity changed; existing ledger is immutable")
    return directory, manifest


def _daily_rows(directory: Path) -> list[dict]:
    return [_read(path) for path in sorted((directory / "days").glob("????-??-??.json"))]


def _initial_state(manifest: dict) -> dict:
    return {
        "strategy_id": manifest["strategy_id"],
        "last_session": manifest["initialized_after_session"],
        "forward_start": None,
        "books": {
            str(cost): {"state": PortfolioState(cash=INITIAL_CASH).to_dict(),
                        "benchmark": None}
            for cost in COST_BOOKS
        },
    }


def _latest_state(directory: Path, manifest: dict) -> dict:
    paths = sorted((directory / "days").glob("????-??-??.json"))
    return _read(paths[-1]) if paths else _initial_state(manifest)


def init_paper_v03(
    repo_root: Path | str,
    strategy_id: str,
    *,
    as_of: object | None = None,
    now: object | None = None,
) -> dict:
    """Initialize only the frozen winner; first trading signal must be future."""
    root = Path(repo_root)
    directory = _directory(root, strategy_id)
    session = _current_session(as_of, now)
    winner = _winner(root, strategy_id)
    frozen_at = _utc(winner["frozen_at"])
    if frozen_at > _utc(now):
        raise ValueError("winner freeze time is in the future")
    first_signal = _next_signal(root, max(session, _latest_completed(frozen_at)))
    with _locked(directory):
        if (directory / "manifest.json").exists():
            _manifest(root, strategy_id)
        else:
            manifest = {
                "spec_version": version(strategy_id), "strategy_id": strategy_id,
                "winner_hash": _hash(winner), "winner": winner,
                "initial_cash": INITIAL_CASH, "cost_bps": list(COST_BOOKS),
                "initialized_at": _utc(now).isoformat(),
                "initialized_after_session": str(session.date()),
                "first_signal_date": first_signal,
                "provider": "local_offline_simulator",
                "execution_evidence": "modeled_cost_not_broker_execution",
            }
            _write(directory / "manifest.json", manifest)
            _write(directory / "state.json", _initial_state(manifest))
    return paper_v03_status(root, strategy_id)


def _prepare_day(root: Path, as_of: pd.Timestamp, states: list[PortfolioState], strategy_id: str = "C0"):
    owner = yaml.safe_load((root / "config/universe.yaml").read_text(encoding="utf-8"))
    excluded = set(owner.get("exclusions", []))
    universe = tuple(t for t in owner["tickers"] if t not in excluded)
    if version(strategy_id) == "0.4":
        from shm.universe.sp500 import load_sp500_snapshot
        snapshot = load_sp500_snapshot(root)
        if snapshot is None:
            universe = ()
        else:
            universe = tuple(item["symbol"] for item in snapshot["members"])
    tickers = set(universe) | {"SPY"}
    for state in states:
        tickers.update(state.positions)
    window = paper_xnys_window(as_of)
    prices = {}
    for ticker in sorted(tickers):
        path = root / "data/raw/prices" / f"{ticker}.parquet"
        if path.exists():
            prices[ticker] = read_price_cache(
                path, ticker=ticker, start=window[0], end=as_of,
                mode="paper", paper_sessions=260,
            )
    prepared = prepare_inputs(prices, universe, window, _schedule(root, as_of),
                              require_point_in_time_eligibility=version(strategy_id) == "0.4")
    return prepared, prices


def _apply_sp500_gate(root: Path, session: pd.Timestamp, state: PortfolioState, decision, now,
                      *, before_open: bool = False) -> str | None:
    from shm.universe.sp500 import sp500_status
    source = sp500_status(root, session, now=now)
    market_path = root / "data/market_refresh/latest.json"
    market = _read(market_path) if market_path.exists() else {}
    prices_ready = (market.get("date") == str(session.date()) and market.get("complete") is True
                    and market.get("require_point_in_time_eligibility") is True
                    and not market.get("eligibility_fields_missing"))
    decision.diagnostics["universe"] = source
    decision.diagnostics["price_snapshot_complete"] = prices_ready
    if not source.get("allow_new_risk") or not prices_ready:
        reason = ("MISSING_VERIFIED_SP500_UNIVERSE" if not source.get("allow_new_risk")
                  else "MISSING_COMPLETE_SP500_PRICE_SNAPSHOT")
        decision.warnings.append(reason)
        decision.diagnostics["allow_new_risk"] = False
        if not before_open:
            decision.target_weights = None
            state.pending = decision if decision.exits else None
            state.latest_decision = decision.to_dict()
        return reason
    return None


def _price(prices: dict, ticker: str, session: str, column: str) -> float | None:
    frame = prices.get(ticker)
    if frame is None or frame.empty:
        return None
    if "date" in frame.columns:
        frame = frame.set_index("date")
    values = frame[column].reindex([pd.Timestamp(session)])
    value = values.iloc[0]
    return float(value) if pd.notna(value) and value > 0 else None


def _benchmark(
    previous: dict | None, prices: dict, forward_start: str, session: str, cost: int,
) -> dict:
    """Same-start passive SPY reference, explicitly a model rather than fills."""
    benchmark = dict(previous) if previous else {
        "cash": INITIAL_CASH, "quantity": 0.0, "entry_date": None,
        "entry_price": None, "equity": INITIAL_CASH,
        "theoretical_reference": True,
    }
    if benchmark.get("mark_date") and benchmark.get("mark"):
        refreshed = _price(prices, "SPY", benchmark["mark_date"], "close")
        if refreshed is not None:
            factor = refreshed / benchmark["mark"]
            benchmark["quantity"] /= factor
            if benchmark.get("entry_price") is not None:
                benchmark["entry_price"] *= factor
    calendar = _calendar(forward_start, session)
    entry = str(calendar.next_session(pd.Timestamp(forward_start)).date())
    if benchmark["entry_date"] is None and session >= entry:
        price = _price(prices, "SPY", entry, "open")
        if price is not None:
            quantity = INITIAL_CASH / (price * (1 + cost / 10_000))
            benchmark.update(cash=0.0, quantity=quantity, entry_date=entry,
                             entry_price=price, modeled_entry_cost=quantity * price * cost / 10_000)
    close = _price(prices, "SPY", session, "close")
    if benchmark["quantity"] and close is not None:
        benchmark["equity"] = benchmark["cash"] + benchmark["quantity"] * close
    if close is not None:
        benchmark.update(mark=close, mark_date=session)
    benchmark["complete"] = close is not None and (session < entry or benchmark["entry_date"] is not None)
    return benchmark


def _decision_incomplete(decision: dict) -> bool:
    return any(warning.startswith("MISSING_") or warning == "INSUFFICIENT_ELIGIBLE_UNIVERSE"
               for warning in decision.get("warnings", []))


def _valuation(state: PortfolioState) -> dict:
    payload = state.to_dict()
    marks = payload.get("marks", {})
    equity = float(payload["cash"])
    holdings = []
    for ticker, position in payload["positions"].items():
        mark = marks.get(ticker, position["average_cost"])
        quantity = float(position["quantity"])
        market_value = quantity * float(mark) if mark is not None else None
        if market_value is not None:
            equity += market_value
        holdings.append({"ticker": ticker, **position, "mark": mark,
                         "market_value": market_value,
                         "unrealized_pnl": None if market_value is None else
                         market_value - quantity * float(position["average_cost"])})
    high_water = float(payload.get("equity_high_water") or INITIAL_CASH)
    return {"cash": float(payload["cash"]), "equity": equity,
            "positions": holdings, "drawdown": equity / high_water - 1,
            "equity_high_water": high_water,
            "drawdown_warning": equity / high_water <= 0.90,
            "stock_exposure": (equity - float(payload["cash"])) / equity if equity else 0.0}


def _run_paper_day(
    repo_root: Path | str,
    strategy_id: str,
    *,
    as_of: object | None = None,
    now: object | None = None,
) -> dict:
    """Process exactly the latest closed session, never fabricate missed signals."""
    root = Path(repo_root)
    session = _current_session(as_of, now)
    text_date = str(session.date())
    directory, manifest = _manifest(root, strategy_id)
    with _locked(directory):
        path = directory / "days" / f"{text_date}.json"
        if path.exists():
            committed = _read(path)
            _write(directory / "state.json", _latest_state(directory, manifest))
            return committed
        previous = _latest_state(directory, manifest)
        last = pd.Timestamp(previous["last_session"])
        if session <= last:
            return {"status": "awaiting_next_session", "strategy_id": strategy_id,
                    "last_session": str(last.date())}
        calendar = _calendar(last, session)
        missed = [str(day.date()) for day in calendar.sessions_in_range(last, session)
                  if last < day < session]
        schedule = _schedule(root, session)
        started = previous["forward_start"]
        may_start = session >= pd.Timestamp(manifest["first_signal_date"]) and session in schedule
        states = [PortfolioState.from_dict(previous["books"][str(c)]["state"]) for c in COST_BOOKS]
        result = {
            "spec_version": version(strategy_id), "strategy_id": strategy_id,
            "params_hash": manifest["winner"]["params_hash"],
            "last_session": text_date, "observed_at": _utc(now).isoformat(),
            "forward_start": started or (text_date if may_start else None),
            "missed_sessions": missed,
            "missed_rebalances": [date for date in missed if pd.Timestamp(date) in schedule],
            "timeliness": "missed_sessions_detected" if missed else "on_time",
            "books": {},
        }
        if result["forward_start"] is None:
            result.update(status="awaiting_first_rebalance", books=previous["books"])
        else:
            try:
                prepared, prices = _prepare_day(root, session, states, strategy_id)
                for cost, state in zip(COST_BOOKS, states):
                    entry_gate_reason = None
                    if version(strategy_id) == "0.4" and state.pending is not None:
                        # Yesterday's permission cannot authorize buys after today's
                        # source/price verification fails. Keep targets for reductions.
                        entry_gate_reason = _apply_sp500_gate(
                            root, session, state, state.pending, now, before_open=True,
                        )
                    pending = _jsonable(state.pending)
                    execution = advance_open(prepared, session, state, cost_bps=cost,
                                             integer_shares=True)
                    if entry_gate_reason:
                        execution.events.append({"action": "new_risk_blocked",
                                                 "signal_date": pending["signal_date"],
                                                 "execution_date": text_date,
                                                 "reason": entry_gate_reason})
                    decision = evaluate_close(prepared, session, base_candidate(strategy_id), state)
                    if version(strategy_id) == "0.4":
                        _apply_sp500_gate(root, session, state, decision, now)
                    serialized_decision = _jsonable(decision)
                    serialized_execution = _jsonable(execution)
                    execution_incomplete = any(event.get("action") in INCOMPLETE_EXECUTION
                                               for event in serialized_execution.get("events", []))
                    valuation = _valuation(state)
                    benchmark = _benchmark(previous["books"][str(cost)].get("benchmark"),
                                           prices, result["forward_start"], text_date, cost)
                    cycle = bool(pending and pending.get("kind") == "rebalance"
                                 and pending.get("execution_date") == text_date
                                 and not _decision_incomplete(pending)
                                 and not state.blocked_exits and not execution_incomplete)
                    result["books"][str(cost)] = {
                        "cost_bps": cost, "state": state.to_dict(),
                        "execution": serialized_execution, "decision": serialized_decision,
                        "complete": not execution_incomplete and not _decision_incomplete(serialized_decision)
                            and benchmark["complete"],
                        "valuation": valuation, "benchmark": benchmark,
                        "rebalance_cycle_completed": cycle,
                        "cumulative_return": valuation["equity"] / INITIAL_CASH - 1,
                        "spy_cumulative_return": benchmark["equity"] / INITIAL_CASH - 1
                            if benchmark["complete"] else None,
                        "excess_return": (valuation["equity"] - benchmark["equity"]) / INITIAL_CASH
                            if benchmark["complete"] else None,
                    }
                result["status"] = "incomplete" if any(
                    not book["complete"] for book in result["books"].values()
                ) else "processed"
            except Exception as error:
                _write(directory / "errors" / f"{text_date}.json", {
                    "session": text_date, "observed_at": _utc(now).isoformat(),
                    "status": "incomplete", "error": str(error),
                })
                raise
        _write(path, result)
        _write(directory / "state.json", result)
    return result


def run_paper_v03(
    repo_root: Path | str,
    strategy_id: str,
    *,
    as_of: object | None = None,
    now: object | None = None,
) -> dict:
    """Run one forward day and generate any now-completed observed month reports."""
    result = _run_paper_day(repo_root, strategy_id, as_of=as_of, now=now)
    root = Path(repo_root)
    directory, manifest = _manifest(root, strategy_id)
    latest = _latest_state(directory, manifest)
    start = latest["forward_start"]
    if start is not None:
        _write_drawdown_review(directory, latest)
        session = _latest_completed(now)
        rows = _daily_rows(directory)
        for period in pd.period_range(pd.Timestamp(start).to_period("M"), session.to_period("M"), freq="M"):
            if (directory / "reports" / f"{period}.json").exists():
                continue
            calendar = _calendar(period.start_time, period.end_time)
            sessions = calendar.sessions_in_range(period.start_time.normalize(), period.end_time.normalize())
            observed = any(pd.Timestamp(row["last_session"]).to_period("M") == period and row["forward_start"] for row in rows)
            if observed and len(sessions) and calendar.session_close(sessions[-1]) <= _utc(now):
                report_paper_v03(root, strategy_id, str(period), now=now)
    return result


def _write_drawdown_review(directory: Path, day: dict) -> None:
    triggering = [cost for cost, book in day["books"].items()
                  if "DRAWDOWN_10_PERCENT_REVIEW" in book.get("decision", {}).get("warnings", [])]
    if not triggering:
        return
    path = directory / "reviews" / f"{day['last_session']}.json"
    with _locked(directory):
        if path.exists():
            return
        review = {
            "kind": "drawdown_review", "strategy_id": day["strategy_id"],
            "date": day["last_session"], "triggering_cost_bps": triggering,
            "forced_liquidation": False,
            "execution_evidence": "modeled_cost_not_broker_execution",
            "books": {cost: {**book["valuation"], "complete": book["complete"],
                              "risk_exit_reasons": book["decision"]["exits"],
                              "warnings": book["decision"]["warnings"]}
                      for cost, book in day["books"].items()},
        }
        lines = [f"# {day['strategy_id']} · {day['last_session']} 回撤复盘", "",
                 "10% 是预警线，本次预警不单独触发强制清仓。以下为模型成本账本，非券商实测执行。", "",
                 "| 成本账本 | 净值 | 净值高水位 | 当前回撤 |", "|---|---:|---:|---:|"]
        for cost, book in review["books"].items():
            lines.append(f"| {cost} bps | ${book['equity']:,.2f} | "
                         f"${book['equity_high_water']:,.2f} | {book['drawdown']:.2%} |")
        lines.extend(["", "| 成本账本 | 持仓 | 股数 | 当前市值 | 未实现盈亏 |", "|---|---|---:|---:|---:|"])
        for cost, book in review["books"].items():
            for position in book["positions"]:
                lines.append(f"| {cost} bps | {position['ticker']} | {position['quantity']:g} | "
                             f"{position['market_value']} | {position['unrealized_pnl']} |")
            lines.extend(["", f"{cost} bps 当日风险退出原因：" + json.dumps(book["risk_exit_reasons"], ensure_ascii=False),
                          "数据及风险提示：" + ", ".join(book["warnings"])])
        lines.extend(["", "按逐日成交、成本、股票贡献及同期SPY检查偏差；"
                      "本报告记录触发时账户事实，不将单次回撤解释为策略因果结论。"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        _write(path, review)


def paper_v03_status(repo_root: Path | str, strategy_id: str) -> dict:
    """Read forward progress without annualizing a short observation window."""
    root = Path(repo_root)
    directory, manifest = _manifest(root, strategy_id)
    rows = _daily_rows(directory)
    latest = rows[-1] if rows else _initial_state(manifest)
    start = latest["forward_start"]
    last = latest["last_session"]
    long_enough = bool(start and pd.Timestamp(last) >= pd.Timestamp(start) + pd.DateOffset(months=12))
    reports = [_read(path) for path in sorted((directory / "reports").glob("????-??.json"))]
    completed_reports = [report["month"] for report in reports if report.get("complete")]
    cycles = [row["last_session"] for row in rows if all(
        row["books"][str(cost)].get("rebalance_cycle_completed", False) for cost in COST_BOOKS
    )]
    missed = sorted({day for row in rows for day in row.get("missed_sessions", [])
                     if start is not None and day >= start})
    observed = [row for row in rows if row["forward_start"]]
    complete_forward = bool(observed) and not missed and all(row.get("status") == "processed" for row in observed)
    performance_verdict = "PENDING_12_MONTHS"
    full_year_passes = []
    books = {}
    for cost in COST_BOOKS:
        book = latest["books"][str(cost)]
        state = PortfolioState.from_dict(book["state"])
        valuation = book.get("valuation", _valuation(state))
        decision = book.get("decision", {})
        diagnostics = decision.get("diagnostics", {})
        market_allowed = diagnostics.get("allow_new_risk", False)
        pending = _jsonable(state.pending) or {}
        books[str(cost)] = {
            **valuation, "cost_bps": cost,
            "cumulative_return": book.get("cumulative_return") if start else None,
            "spy_cumulative_return": book.get("spy_cumulative_return") if start else None,
            "excess_return": book.get("excess_return") if start else None,
            "benchmark": book.get("benchmark"), "pending": pending,
            "blocked_exits": _jsonable(state.blocked_exits),
            "allow_new_risk": bool(market_allowed) and not _decision_incomplete(decision),
            "pending_exit_symbols": sorted(set(pending.get("exits", {})) | set(state.blocked_exits)),
            "max_total_exposure": float(diagnostics.get("exposure_cap", 0.0)),
            "decision": decision,
            "complete": book.get("complete", start is None),
        }
        if long_enough and complete_forward:
            equity = pd.Series([INITIAL_CASH, *[row["books"][str(cost)]["valuation"]["equity"] for row in observed]])
            spy = pd.Series([INITIAL_CASH, *[row["books"][str(cost)]["benchmark"]["equity"] for row in observed]])
            years = (pd.Timestamp(last) - pd.Timestamp(start)).days / 365.25
            cagr = (equity.iloc[-1] / INITIAL_CASH) ** (1 / years) - 1
            spy_cagr = (spy.iloc[-1] / INITIAL_CASH) ** (1 / years) - 1
            maxdd = float((equity / equity.cummax() - 1).min())
            spy_maxdd = float((spy / spy.cummax() - 1).min())
            full_year_passes.append(cagr > spy_cagr and abs(maxdd) < abs(spy_maxdd))
            books[str(cost)].update(cagr=float(cagr), spy_cagr=float(spy_cagr),
                                    max_drawdown=maxdd, spy_max_drawdown=spy_maxdd)
    if long_enough:
        performance_verdict = "INCOMPLETE" if not complete_forward else "PASS" if all(full_year_passes) else "FAIL"
    errors = sorted((directory / "errors").glob("????-??-??.json"))
    latest_error = _read(errors[-1]) if errors and errors[-1].stem > last else None
    return {
        "spec_version": version(strategy_id), "strategy_id": strategy_id,
        "params_hash": manifest["winner"]["params_hash"],
        "first_signal_date": manifest["first_signal_date"],
        "forward_start": start, "last_session": last,
        "next_rebalance_date": _next_signal(root, last),
        "status": latest.get("status", "awaiting_first_rebalance"),
        "completed_rebalance_cycles": len(cycles), "cycle_dates": cycles,
        "monthly_report_count": len(completed_reports), "monthly_reports": completed_reports,
        "drawdown_reviews": [path.name for path in sorted((directory / "reviews").glob("*.md"))],
        "operational_acceptance": len(cycles) >= 3 and len(completed_reports) >= 3 and not missed,
        "performance_verdict": performance_verdict,
        "annualized_return": {cost: book["cagr"] for cost, book in books.items()}
            if long_enough and complete_forward else None,
        "latest_error": latest_error,
        "missed_sessions": missed, "books": books,
        "execution_evidence": "modeled_cost_not_broker_execution",
    }


def report_paper_v03(
    repo_root: Path | str,
    strategy_id: str,
    month: str,
    *,
    now: object | None = None,
) -> dict:
    """Persist one completed-month operational report from observed daily ledgers."""
    root = Path(repo_root)
    directory, manifest = _manifest(root, strategy_id)
    period = pd.Period(month, freq="M")
    calendar = _calendar(period.start_time, period.end_time)
    sessions = calendar.sessions_in_range(period.start_time.normalize(), period.end_time.normalize())
    if not len(sessions) or calendar.session_close(sessions[-1]) > _utc(now):
        raise ValueError("monthly report requires a completed XNYS calendar month")
    with _locked(directory):
        path = directory / "reports" / f"{period}.json"
        if path.exists():
            return _read(path)
        rows = _daily_rows(directory)
        started = next((row["forward_start"] for row in rows if row["forward_start"]), None)
        if started is None or pd.Timestamp(started) > sessions[-1]:
            raise ValueError("no observed v0.3 forward account exists for this month")
        expected = {str(s.date()) for s in sessions if s >= pd.Timestamp(started)}
        observed = [row for row in rows if row["last_session"] in expected]
        if not observed:
            raise ValueError("no observed v0.3 sessions exist for this month")
        missing = sorted(expected - {row["last_session"] for row in observed})
        complete = not missing and all(row.get("status") == "processed" for row in observed)
        preceding = [row for row in rows if row["last_session"] < min(expected) and row["forward_start"]]
        books = {}
        for cost in COST_BOOKS:
            key = str(cost)
            end = observed[-1]["books"][key]
            initial = preceding[-1]["books"][key] if preceding else None
            initial_equity = initial["valuation"]["equity"] if initial else INITIAL_CASH
            initial_spy = initial["benchmark"]["equity"] if initial else INITIAL_CASH
            spy_equity = end["benchmark"]["equity"]
            books[key] = {
                "cost_bps": cost, "opening_equity": initial_equity,
                "closing_equity": end["valuation"]["equity"],
                "monthly_return": end["valuation"]["equity"] / initial_equity - 1,
                "spy_monthly_return": spy_equity / initial_spy - 1
                    if end["benchmark"]["complete"] and (initial is None or initial["benchmark"]["complete"]) else None,
                "modeled_cost": sum(float(row["books"][key]["execution"].get("cost", 0.0)) for row in observed),
                "drawdown_warning_sessions": [row["last_session"] for row in observed
                                               if row["books"][key]["valuation"]["drawdown_warning"]],
                "option_overlay_pnl": None,
            }
        report = {
            "strategy_id": strategy_id, "spec_version": version(strategy_id), "month": str(period),
            "forward_start": started, "complete": complete,
            "last_observed_session": observed[-1]["last_session"],
            "missing_sessions": missing, "observed_sessions": len(observed),
            "books": books, "annualized_return": None,
            "performance_verdict": "PENDING_12_MONTHS" if sessions[-1] < pd.Timestamp(started) + pd.DateOffset(months=12)
                else "ELIGIBLE_FOR_12_MONTH_REVIEW",
            "execution_evidence": "modeled_cost_not_broker_execution",
        }
        text = [f"# {strategy_id} · {period} 前向模拟月报", "",
                f"观察起点：{started}；完整性：{'完整' if complete else '不完整'}。", "",
                "| 模型成本 | 期末资产 | 当月收益 | SPY同期 | 当月模型成本 |",
                "|---|---:|---:|---:|---:|"]
        for book in books.values():
            spy_return = f"{book['spy_monthly_return']:.2%}" if book["spy_monthly_return"] is not None else "估值不完整"
            text.append(f"| {book['cost_bps']} bps | ${book['closing_equity']:,.2f} | "
                        f"{book['monthly_return']:.2%} | {spy_return} | "
                        f"${book['modeled_cost']:,.2f} |")
        text.extend(["", "期权仅草稿，未计权利金。官方开盘价与模型成本不是券商实测执行证据。",
                     "完整年前只观察累计及同期相对收益，不据短期年化给出 PASS。"])
        if missing:
            text.extend(["", "缺少运行日：" + ", ".join(missing)])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".md").write_text("\n".join(text) + "\n", encoding="utf-8")
        _write(path, report)
    return report
