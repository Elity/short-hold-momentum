"""Dashboard projections of actual isolated v0.3 engine/paper artifacts."""
import json
from datetime import datetime

import pandas as pd
import pytest

from shm.service.dashboard import build_dashboard, read_report
from shm.service.store import ServiceStore
from test_v03_paper import FILL, SIGNAL, _init, _now, _run, paper_repo


def test_v03_dashboard_reads_separate_cost_books_and_real_risk_state(paper_repo):
    legacy = paper_repo / "paper/accounts/2026-09-05.json"
    original = legacy.read_bytes()
    _init(paper_repo)
    _run(paper_repo, SIGNAL)
    filled = _run(paper_repo, FILL)
    store = ServiceStore(paper_repo / "service.sqlite3")
    store.initialize()
    now = datetime.fromisoformat(_now(FILL))
    normal = build_dashboard(paper_repo, store, "Asia/Taipei", now=now, strategy_id="C3")
    stress = build_dashboard(paper_repo, store, "Asia/Taipei", now=now, strategy_id="C3", cost_bps=25)
    assert normal["account"]["total"] == filled["books"]["10"]["valuation"]["equity"]
    assert stress["account"]["total"] == filled["books"]["25"]["valuation"]["equity"]
    assert normal["account"]["total"] != stress["account"]["total"]
    assert sum(trade["commission"] for trade in stress["trades"]) > sum(trade["commission"] for trade in normal["trades"])
    assert normal["progress"]["completed"] == 1
    assert normal["strategy"]["performance_verdict"] == "PENDING_12_MONTHS"
    assert all(holding["peak"] and holding["trailing_line"] for holding in normal["holdings"])

    for holding in normal["holdings"]:
        path = paper_repo / "data/raw/prices" / f"{holding['symbol']}.parquet"
        frame = pd.read_parquet(path)
        frame.loc[frame["date"] == pd.Timestamp("2026-09-21"), ["open", "high", "low", "close"]] *= 0.75
        frame.to_parquet(path, index=False)
    _run(paper_repo, "2026-09-21")
    risk = build_dashboard(paper_repo, store, "Asia/Taipei", strategy_id="C3",
                           now=datetime.fromisoformat(_now("2026-09-21")))
    assert risk["risk"]["drawdown_alert"]
    assert risk["risk"]["drawdown"] <= -0.10
    assert any(holding["exit_reason"] == "atr_trailing_exit" for holding in risk["holdings"])
    assert risk["progress"]["completed"] == 1
    assert legacy.read_bytes() == original


def test_v03_reports_and_unstarted_candidates_do_not_fall_back_to_v04(paper_repo):
    store = ServiceStore(paper_repo / "service.sqlite3")
    store.initialize()
    report_dir = paper_repo / "paper/v03/C3/reports"
    report_dir.mkdir(parents=True)
    (report_dir / "2026-09.md").write_text("C3 forward report")
    (paper_repo / "reports").mkdir()
    (paper_repo / "reports/paper-2026-09.md").write_text("V04 report")
    (paper_repo / "reports/v03").mkdir()
    selection = {"evidence": "known_history", "winner": None, "candidates": [{"strategy_id": "C3", "qualified": False}]}
    (paper_repo / "reports/v03/selection.json").write_text(json.dumps(selection))
    dashboard = build_dashboard(paper_repo, store, "Asia/Taipei", strategy_id="C2")
    assert dashboard["account"]["total"] is None
    assert dashboard["reports"] == []
    assert dashboard["strategy"]["historical_screen"] == selection
    assert read_report(paper_repo, "monthly/2026-09", strategy_id="C3")["content"] == "C3 forward report"
    assert read_report(paper_repo, "monthly/2026-09")["content"] == "V04 report"
    with pytest.raises(ValueError):
        read_report(paper_repo, "monthly/2026-09", strategy_id="../C3")


def test_dashboard_reconciles_cash_stock_and_locked_corporate_receivable(paper_repo):
    from shm.v03.strategy import PortfolioState, PositionState

    _init(paper_repo)
    signal = _run(paper_repo, SIGNAL)
    # Seed an existing holding plus legally owed cash before a real scheduled
    # rebalance. NAV remains $100k, but the $10k entitlement is not spendable.
    available_before = {}
    for cost, book in signal["books"].items():
        state = PortfolioState.from_dict(book["state"])
        ticker = next(iter(state.pending.target_weights))
        frame = pd.read_parquet(paper_repo / f"data/raw/prices/{ticker}.parquet").set_index("date")
        mark = float(frame.loc[pd.Timestamp(SIGNAL), "close"])
        state.positions[ticker] = PositionState(100, mark, SIGNAL, mark, mark - 5)
        state.marks[ticker], state.mark_dates[ticker] = mark, SIGNAL
        state.corporate_receivables = {"fixture-merger": {
            "amount": 10000., "effective_session": SIGNAL,
            "cash_settlement_session": "2026-09-25", "evidence": "synthetic dated entitlement",
        }}
        state.cash = 100000 - 100 * mark - 10000
        available_before[cost] = state.cash
        book["state"] = state.to_dict()
    (paper_repo / f"paper/v03/C3/days/{SIGNAL}.json").write_text(json.dumps(signal))
    filled = _run(paper_repo, FILL)
    store = ServiceStore(paper_repo / "service.sqlite3")
    store.initialize()
    payload = build_dashboard(paper_repo, store, "Asia/Taipei", strategy_id="C3",
                              now=datetime.fromisoformat(_now(FILL)))
    account = payload["account"]
    book = filled["books"]["10"]
    stock_value = sum(holding["value"] for holding in payload["holdings"])
    assert account["total"] == pytest.approx(book["valuation"]["equity"])
    assert account["corporate_receivables"] == 10000.
    assert account["market"] == pytest.approx(stock_value)
    assert account["cash"] == pytest.approx(book["state"]["cash"])
    assert account["total"] == pytest.approx(stock_value + account["cash"] + 10000.)
    assert sum(holding["weight"] for holding in payload["holdings"]) + (
        account["cash"] + account["corporate_receivables"]
    ) / account["total"] * 100 == pytest.approx(100.)
    assert any("尚未到账，不能用于买入" in warning for warning in payload["warnings"])
    buys = sum(trade["notional"] + trade["cost"] for trade in book["execution"]["transactions"]
               if trade["side"] == "buy")
    sales = sum(trade["notional"] - trade["cost"] for trade in book["execution"]["transactions"]
                if trade["side"] == "sell")
    assert buys > available_before["10"] * .90
    assert buys <= available_before["10"] + sales + 1e-6
    assert account["cash"] == pytest.approx(available_before["10"] + sales - buys)
