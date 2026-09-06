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
