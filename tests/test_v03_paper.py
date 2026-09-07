"""Forward ledger checks: shared execution, real timing, isolation and recovery."""

from dataclasses import asdict
import hashlib
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest
import yaml

from shm.paper.v03 import (
    _hash, _prepare_day, init_paper_v03, paper_v03_status,
    report_paper_v03, run_paper_v03,
)
from shm.v03.engine import advance_open
from shm.v03.strategy import CANDIDATES, PortfolioState, evaluate_close
from shm.v04.profiles import candidate_config


SIGNAL = "2026-09-17"
FILL = "2026-09-18"


def _now(date):
    return f"{date}T23:00:00Z"


@pytest.fixture
def paper_repo(tmp_path):
    root = tmp_path / "repo"
    (root / "config/v03").mkdir(parents=True)
    (root / "data/raw/prices").mkdir(parents=True)
    tickers = [f"T{i:02}" for i in range(30)]
    (root / "config/universe.yaml").write_text(yaml.safe_dump({
        "tickers": tickers, "exclusions": [], "frozen_on": "2026-09-04",
        "rule_text": "Synthetic forward fixture",
    }))
    (root / "config/dates.yaml").write_text(yaml.safe_dump({
        "calendar": "XNYS", "dev_start": "2005-01-01", "dev_end": "2018-12-31",
        "oos_start": "2019-01-01", "oos_end": None,
        "warmup_trading_days": 260, "rebalance_every_trading_days": 20,
    }))
    config = asdict(CANDIDATES["C3"])
    winner = {
        "spec_version": "0.3", "strategy_id": "C3", "params_hash": _hash(config),
        "config": config, "research_run_id": "synthetic-test",
        "universe_hash": hashlib.sha256((root / "config/universe.yaml").read_bytes()).hexdigest(),
        "frozen_at": "2026-09-06T12:00:00Z", "cost_bps": [10, 25],
        "evidence": "known_history",
    }
    (root / "config/v03/winner.json").write_text(json.dumps(winner))
    sessions = xcals.get_calendar("XNYS", start="2025-01-01", end="2026-10-01").sessions
    step = np.arange(len(sessions), dtype=float)
    for i, ticker in enumerate([*tickers, "SPY"]):
        close = 40 + i + step * (0.03 + i * 0.001)
        frame = pd.DataFrame({
            "date": sessions, "open": close - 0.05, "high": close + 0.8,
            "low": close - 0.8, "close": close, "volume": 2_000_000.0,
            "as_traded_close": close, "dollar_volume": close * 2_000_000.0,
            "downloaded_at": pd.Timestamp("2026-09-06T12:00:00Z"),
        })
        frame.to_parquet(root / "data/raw/prices" / f"{ticker}.parquet", index=False)
    (root / "paper/accounts").mkdir(parents=True)
    (root / "paper/accounts/2026-09-05.json").write_text('{"cash":100000,"positions":{}}\n')
    return root


def _init(root):
    return init_paper_v03(root, "C3", as_of="2026-09-04", now="2026-09-06T23:00:00Z")


def _run(root, date):
    return run_paper_v03(root, "C3", as_of=date, now=_now(date))


def test_sp500_profile_uses_separate_ledger_and_requires_verified_snapshot(paper_repo, monkeypatch):
    import shm.universe.sp500 as sources
    config = candidate_config("S500-C3")
    (paper_repo / "config/v04").mkdir()
    (paper_repo / "config/v04/winner.json").write_text(json.dumps({
        "spec_version": "0.4", "strategy_id": "S500-C3", "config": config,
        "params_hash": _hash(config), "research_run_id": "synthetic-sp500-test",
        "universe_hash": "historical-membership-hash", "cost_bps": [10, 25],
        "frozen_at": "2026-09-06T12:00:00Z", "evidence": "known_history",
    }))
    symbols = yaml.safe_load((paper_repo / "config/universe.yaml").read_text())["tickers"]
    monkeypatch.setattr(sources, "load_sp500_snapshot", lambda root: {"members": [{"symbol": t} for t in symbols]})
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": True, "source_as_of": SIGNAL})
    init_paper_v03(paper_repo, "S500-C3", as_of="2026-09-04", now="2026-09-06T23:00:00Z")
    market = paper_repo / "data/market_refresh/latest.json"
    market.parent.mkdir(parents=True)
    market.write_text(json.dumps({"date": SIGNAL, "complete": True, "require_point_in_time_eligibility": True}))
    signal = run_paper_v03(paper_repo, "S500-C3", as_of=SIGNAL, now=_now(SIGNAL))
    assert signal["spec_version"] == "0.4"
    assert signal["books"]["10"]["state"]["pending"]["target_weights"]
    market.write_text(json.dumps({"date": FILL, "complete": True, "require_point_in_time_eligibility": True}))
    filled = run_paper_v03(paper_repo, "S500-C3", as_of=FILL, now=_now(FILL))
    assert filled["books"]["10"]["state"]["positions"]
    assert (paper_repo / "paper/v04/S500-C3/days" / f"{FILL}.json").exists()
    assert not (paper_repo / "paper/v03/S500-C3").exists()


def test_stale_sp500_gate_retains_existing_risk_exits(paper_repo, monkeypatch):
    import shm.universe.sp500 as sources
    from shm.paper.v03 import _apply_sp500_gate
    from shm.v03.strategy import Decision
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": False})
    decision = Decision(SIGNAL, FILL, "rebalance", {"NEW": .2}, {"HELD": "market_trend_exit"},
                        diagnostics={"allow_new_risk": True})
    state = PortfolioState(pending=decision)
    _apply_sp500_gate(paper_repo, pd.Timestamp(SIGNAL), state, decision, _now(SIGNAL))
    assert decision.target_weights is None
    assert not decision.allow_new_risk
    assert state.pending.exits == {"HELD": "market_trend_exit"}
    assert "MISSING_VERIFIED_SP500_UNIVERSE" in decision.warnings


@pytest.mark.parametrize("unavailable", ["source", "prices"])
def test_sp500_rechecks_pending_buys_before_open_and_preserves_sales(paper_repo, monkeypatch, unavailable):
    import shm.universe.sp500 as sources
    from shm.v03.strategy import Decision, PositionState

    config = candidate_config("S500-C3")
    (paper_repo / "config/v04").mkdir()
    (paper_repo / "config/v04/winner.json").write_text(json.dumps({
        "spec_version": "0.4", "strategy_id": "S500-C3", "config": config,
        "params_hash": _hash(config), "research_run_id": "synthetic-gate-test",
        "universe_hash": "historical-membership-hash", "cost_bps": [10, 25],
        "frozen_at": "2026-09-06T12:00:00Z", "evidence": "known_history",
    }))
    symbols = yaml.safe_load((paper_repo / "config/universe.yaml").read_text())["tickers"]
    monkeypatch.setattr(sources, "load_sp500_snapshot", lambda root: {"members": [{"symbol": t} for t in symbols]})
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": True})
    init_paper_v03(paper_repo, "S500-C3", as_of="2026-09-04", now="2026-09-06T23:00:00Z")
    market = paper_repo / "data/market_refresh/latest.json"
    market.parent.mkdir(parents=True)
    market.write_text(json.dumps({"date": SIGNAL, "complete": True, "require_point_in_time_eligibility": True}))
    signal = run_paper_v03(paper_repo, "S500-C3", as_of=SIGNAL, now=_now(SIGNAL))
    marks = {
        ticker: float(pd.read_parquet(paper_repo / f"data/raw/prices/{ticker}.parquet")
                      .set_index("date").loc[pd.Timestamp(SIGNAL), "close"])
        for ticker in ("T00", "T01")
    }
    pending = Decision(SIGNAL, FILL, "rebalance", {"T01": .02, "T02": .20},
                       {"T00": "market_trend_exit"}, diagnostics={"allow_new_risk": True})
    for book in signal["books"].values():
        state = PortfolioState(
            cash=100000 - sum(200 * mark for mark in marks.values()),
            positions={ticker: PositionState(200, mark, SIGNAL, mark) for ticker, mark in marks.items()},
            marks=marks, mark_dates={ticker: SIGNAL for ticker in marks},
            equity_high_water=100000, pending=pending, last_open=SIGNAL, last_close=SIGNAL,
        )
        book["state"] = state.to_dict()
    (paper_repo / f"paper/v04/S500-C3/days/{SIGNAL}.json").write_text(json.dumps(signal))
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": unavailable != "source"})
    market.write_text(json.dumps({"date": FILL, "complete": unavailable != "prices", "require_point_in_time_eligibility": True}))

    filled = run_paper_v03(paper_repo, "S500-C3", as_of=FILL, now=_now(FILL))
    reason = "MISSING_VERIFIED_SP500_UNIVERSE" if unavailable == "source" else "MISSING_COMPLETE_SP500_PRICE_SNAPSHOT"
    for book in filled["books"].values():
        assert all(trade["side"] == "sell" for trade in book["execution"]["transactions"])
        positions = book["state"]["positions"]
        assert "T00" not in positions and "T02" not in positions
        assert 0 < positions["T01"]["quantity"] < 200
        assert any(event.get("reason") == reason for event in book["execution"]["events"])
        assert not book["complete"] and not book["rebalance_cycle_completed"]


def test_only_frozen_winner_starts_on_next_signal_and_leaves_v04_untouched(paper_repo):
    legacy = paper_repo / "paper/accounts/2026-09-05.json"
    before = legacy.read_bytes()
    with pytest.raises(ValueError, match="frozen"):
        init_paper_v03(paper_repo, "C2", now="2026-09-06T23:00:00Z")
    status = _init(paper_repo)
    assert status["first_signal_date"] == SIGNAL
    assert status["forward_start"] is None
    assert status["books"]["10"]["equity"] == 100000
    waiting = _run(paper_repo, "2026-09-08")
    assert waiting["status"] == "awaiting_first_rebalance"
    assert all(not book["state"]["positions"] for book in waiting["books"].values())
    assert legacy.read_bytes() == before
    owner = paper_repo / "config/universe.yaml"
    owner.write_text(owner.read_text() + "# changed\n")
    with pytest.raises(ValueError, match="universe changed"):
        _run(paper_repo, SIGNAL)


def test_shared_engine_cost_books_and_day_commit_survive_restart(paper_repo):
    _init(paper_repo)
    first = _run(paper_repo, SIGNAL)
    assert first["forward_start"] == SIGNAL
    assert all(not b["state"]["positions"] for b in first["books"].values())
    filled = _run(paper_repo, FILL)
    assert filled["status"] == "processed"
    assert all(book["execution"]["transactions"] for book in filled["books"].values())
    assert filled["books"]["25"]["execution"]["cost"] > filled["books"]["10"]["execution"]["cost"]
    for cost in (10, 25):
        state = PortfolioState(cash=100000)
        for date in (SIGNAL, FILL):
            prepared, prices = _prepare_day(paper_repo, pd.Timestamp(date), [state])
            assert all(frame["date"].max() <= pd.Timestamp(date) for frame in prices.values())
            advance_open(prepared, date, state, cost_bps=cost, integer_shares=True)
            evaluate_close(prepared, date, "C3", state)
        assert state.to_dict() == filled["books"][str(cost)]["state"]
    directory = paper_repo / "paper/v03/C3"
    committed = (directory / f"days/{FILL}.json").read_bytes()
    (directory / "state.json").unlink()
    assert _run(paper_repo, FILL) == filled
    assert (directory / f"days/{FILL}.json").read_bytes() == committed
    assert json.loads((directory / "state.json").read_text()) == filled
    status = paper_v03_status(paper_repo, "C3")
    assert status["completed_rebalance_cycles"] == 1
    assert status["annualized_return"] is None
    assert status["performance_verdict"] == "PENDING_12_MONTHS"


def test_missed_open_is_explicit_and_never_backfills_a_buy(paper_repo):
    _init(paper_repo)
    _run(paper_repo, SIGNAL)
    late = _run(paper_repo, "2026-09-21")
    assert FILL in late["missed_sessions"]
    for book in late["books"].values():
        assert not book["state"]["positions"]
        assert not book["execution"]["transactions"]
        assert any(e["action"] == "missed_execution" for e in book["execution"]["events"])
        assert not book["rebalance_cycle_completed"]
    with pytest.raises(ValueError, match="cannot be backfilled"):
        run_paper_v03(paper_repo, "C3", as_of=FILL, now=_now("2026-09-21"))


def test_risk_exit_does_not_count_as_rebalance_or_buy_back(paper_repo):
    _init(paper_repo)
    _run(paper_repo, SIGNAL)
    filled = _run(paper_repo, FILL)
    ticker = next(iter(filled["books"]["10"]["state"]["positions"]))
    path = paper_repo / "data/raw/prices" / f"{ticker}.parquet"
    frame = pd.read_parquet(path)
    drop = frame["date"] == pd.Timestamp("2026-09-21")
    frame.loc[drop, ["open", "high", "low", "close"]] *= 0.75
    frame.to_parquet(path, index=False)
    signal = _run(paper_repo, "2026-09-21")
    assert signal["books"]["10"]["decision"]["exits"][ticker] == "atr_trailing_exit"
    exited = _run(paper_repo, "2026-09-22")
    sales = exited["books"]["10"]["execution"]["transactions"]
    assert len(sales) == 1 and sales[0]["ticker"] == ticker and sales[0]["side"] == "sell"
    assert sales[0]["event_type"] == "risk_exit"
    assert ticker not in exited["books"]["10"]["state"]["positions"]
    assert paper_v03_status(paper_repo, "C3")["completed_rebalance_cycles"] == 1
    for held, position in filled["books"]["10"]["state"]["positions"].items():
        if held != ticker:
            assert exited["books"]["10"]["state"]["positions"][held]["quantity"] == position["quantity"]


def test_missing_entry_and_incomplete_month_never_count_as_acceptance(paper_repo):
    _init(paper_repo)
    signal = _run(paper_repo, SIGNAL)
    ticker = signal["books"]["10"]["decision"]["selected"][0]
    path = paper_repo / "data/raw/prices" / f"{ticker}.parquet"
    frame = pd.read_parquet(path)
    frame.loc[frame["date"] == pd.Timestamp(FILL), "open"] = np.nan
    frame.to_parquet(path, index=False)
    filled = _run(paper_repo, FILL)
    assert filled["status"] == "incomplete"
    assert any(e["action"] == "unfilled_entry" for e in filled["books"]["10"]["execution"]["events"])
    assert paper_v03_status(paper_repo, "C3")["completed_rebalance_cycles"] == 0
    with pytest.raises(ValueError, match="completed XNYS"):
        report_paper_v03(paper_repo, "C3", "2026-09", now=_now(FILL))
    _run(paper_repo, "2026-10-01")
    assert (paper_repo / "paper/v03/C3/reports/2026-09.json").exists()
    report = report_paper_v03(paper_repo, "C3", "2026-09", now="2026-10-01T23:00:00Z")
    assert not report["complete"] and report["missing_sessions"]
    status = paper_v03_status(paper_repo, "C3")
    assert status["monthly_report_count"] == 0
    assert not status["operational_acceptance"]
    assert status["performance_verdict"] == "PENDING_12_MONTHS"


def test_drawdown_review_is_idempotent_and_never_counts_as_month_or_cycle(paper_repo):
    _init(paper_repo)
    _run(paper_repo, SIGNAL)
    filled = _run(paper_repo, FILL)
    for ticker in filled["books"]["10"]["state"]["positions"]:
        path = paper_repo / "data/raw/prices" / f"{ticker}.parquet"
        frame = pd.read_parquet(path)
        frame.loc[frame["date"] == pd.Timestamp("2026-09-21"), ["open", "high", "low", "close"]] *= 0.8
        frame.to_parquet(path, index=False)
    day = _run(paper_repo, "2026-09-21")
    review_path = paper_repo / "paper/v03/C3/reviews/2026-09-21.json"
    review = json.loads(review_path.read_text())
    before = review_path.read_bytes()
    assert set(review["books"]) == {"10", "25"}
    assert review["forced_liquidation"] is False
    assert all(b["drawdown"] < -0.10 and b["positions"] for b in review["books"].values())
    assert review_path.with_suffix(".md").exists()
    assert all(not book["execution"]["transactions"] for book in day["books"].values())
    assert _run(paper_repo, "2026-09-21") == day
    assert review_path.read_bytes() == before
    status = paper_v03_status(paper_repo, "C3")
    assert status["completed_rebalance_cycles"] == 1
    assert status["monthly_report_count"] == 0
    assert status["drawdown_reviews"] == ["2026-09-21.md"]
