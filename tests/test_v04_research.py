from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from shm.v04.profiles import SP500_IDS, candidate_config
from shm.v04 import research


def _candidate(strategy="S500-C4"):
    return {"strategy_id": strategy, "config": candidate_config(strategy), "module_count": 2,
            "checks": {"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS"},
            "metrics_valid": True,
            "metrics_10": {"cagr": .18, "maxdd": -.12, "turnover": 2},
            "metrics_25": {"cagr": .17, "maxdd": -.13, "turnover": 2},
            "benchmark_10": {"cagr": .16, "maxdd": -.3},
            "benchmark_25": {"cagr": .159, "maxdd": -.301}}


def test_historical_membership_does_not_extend_june_list_to_september():
    history = pd.DataFrame({"date": pd.to_datetime(["2000-01-03", "2026-06-30"]),
                            "members": [("OLD",), ("NEW",)]})
    schedule = pd.to_datetime(["2026-06-29", "2026-07-29"])
    evaluation = pd.to_datetime(["2026-06-30", "2026-09-04"])
    membership, evidence = research.historical_membership(history, schedule, evaluation)
    assert membership[pd.Timestamp("2026-06-29")] == ("OLD",)
    assert membership[pd.Timestamp("2026-07-29")] == ()
    assert evidence["status"] == "INCONCLUSIVE"
    assert evidence["required_end"] == "2026-09-04"
    assert evidence["source_last_date"] == "2026-06-30"


def test_pit_price_coverage_counts_valid_bars_and_uses_published_members():
    date = pd.Timestamp("2026-06-29")
    frame = pd.DataFrame({"date": [date], "open": [10.], "high": [11.], "low": [9.],
                          "close": [10.], "volume": [100.]})
    prices = {ticker: frame.copy() for ticker in ("A", "B", "C", "D")}
    membership = {date: ("A", "B", "C", "D", "MISSING"), pd.Timestamp("2026-07-29"): ()}
    assert research.price_coverage(prices, membership)["coverage"] == .8
    prices["D"].loc[0, "open"] = np.nan
    assert research.price_coverage(prices, membership)["coverage"] == .6


def test_s500_gate_requires_both_costs_and_freeze_uses_full_profile_and_pit_hash(tmp_path, monkeypatch):
    row = _candidate()
    assert research.qualifies(row)
    failed = deepcopy(row)
    failed["metrics_25"]["cagr"] = .1
    assert research.select_winner([failed]) is None
    failed = deepcopy(row)
    failed["checks"]["MEMBERSHIP_HISTORY_COVERAGE"] = "INCONCLUSIVE"
    assert research.select_winner([failed]) is None
    monkeypatch.setattr(research, "render_research_v04", lambda payload: "verified fixture")
    payload = {"winner": "S500-C4", "run_id": "v04-fixture", "candidates": [row],
               "universe_hash": "pit-file-hash", "generated_at": "2026-09-06T12:00:00Z",
               "snapshot_id": "snapshot", "source_hash": "source", "status": "HISTORICAL_SCREEN_PASS"}
    research._publish_result(tmp_path, tmp_path / "reports/v04/v04-fixture", payload)
    research._publish_result(tmp_path, tmp_path / "reports/v04/v04-fixture", payload)
    frozen = json.loads((tmp_path / "config/v04/winner.json").read_text())
    assert frozen["strategy_id"] == "S500-C4" and frozen["spec_version"] == "0.4"
    assert frozen["config"] == candidate_config("S500-C4")
    assert frozen["config"]["base_candidate"]["target_vol"] == .20
    assert frozen["params_hash"] == research.json_hash(candidate_config("S500-C4"))
    assert frozen["universe_hash"] == "pit-file-hash"
    assert frozen["research_run_id"] == payload["run_id"] and frozen["frozen_at"] == payload["generated_at"]
    assert len((tmp_path / "experiments/v04/log.jsonl").read_text().splitlines()) == 1
    assert not (tmp_path / "config/v03/winner.json").exists()


@pytest.mark.parametrize("history_last,polluted", [("2026-06-30", False), ("2026-09-04", True)])
def test_orchestrator_runs_only_ten_pit_paths_and_never_qualifies_missing_history_or_tie_jump(
    tmp_path, monkeypatch, history_last, polluted,
):
    root = tmp_path
    (root / "config/v04").mkdir(parents=True)
    (root / "experiments/prereg/v04").mkdir(parents=True)
    (root / "data/reference/sp500").mkdir(parents=True)
    (root / "config/v04/research.yaml").write_text(yaml.safe_dump({
        "spec_version": "0.4", "candidate_ids": list(SP500_IDS), "cutoff": "2026-09-04",
        "dev_start": "2005-01-01", "cost_bps": [10, 25], "minimum_pit_coverage": .8,
        "universe": "historical_sp500_constituents",
    }))
    for strategy in SP500_IDS:
        (root / "experiments/prereg/v04" / f"{strategy}.md").write_text("Owner批准 fixture")
    pd.DataFrame({"date": ["2000-01-03", history_last], "tickers": ["OLD,TIE", "OLD,TIE"]}).to_csv(
        root / "data/reference/sp500_history.csv", index=False,
    )
    (root / "data/reference/sp500/current.json").write_text(json.dumps({
        "source_as_of": "2026-09-03", "members": [{"symbol": "CURRENT_ONLY", "sector": "Technology"}],
    }))
    schedule = pd.to_datetime(["2026-06-29", "2026-07-29"])
    monkeypatch.setattr(research, "xnys_rebalance_dates", lambda *args, **kwargs: schedule)
    loaded, called, matched = [], [], []

    def load_prices(repo, tickers, start, end):
        loaded.extend(tickers)
        dates = research.xcals.get_calendar("XNYS", start=start, end=end).sessions
        prices = {}
        for ticker in tickers:
            close = np.full(len(dates), 10.0)
            if ticker == "TIE" and polluted:
                close[dates.get_loc(pd.Timestamp("2026-07-01"))] = 19_000.0
            prices[ticker] = pd.DataFrame({"date": dates, "open": close, "high": close + 1,
                                           "low": close - 1, "close": close, "volume": 2_000_000.0})
        return prices, {"fixture": "fixture-hash"}, []

    def simulate(prices, universe, candidate, sessions, schedule, *, cost_bps, prepared):
        called.append((candidate, cost_bps, tuple(universe), prepared))
        equity = pd.Series(100_000.0, index=sessions)
        bt = SimpleNamespace(equity=equity, cash=equity * .5, costs=equity * 0,
                             weights=pd.DataFrame({"TIE": .5, "OLD": 0.0}, index=sessions),
                             transactions=pd.DataFrame(), execution_fallbacks=pd.DataFrame())
        return SimpleNamespace(backtest=bt, warnings=[], final_state=SimpleNamespace(corporate_receivables={}), decisions=[{
            "signal_date": str(date.date()), "eligible_count": 2, "diagnostics": {"rebalance": True},
        } for date in schedule])

    def matched_spy(prices, schedule, evaluation, bps, candidate):
        matched.append((candidate, bps))
        return {"cagr": .1, "maxdd": -.2}

    monkeypatch.setattr(research, "_load_prices", load_prices)
    monkeypatch.setattr(research, "run_simulation", simulate)
    monkeypatch.setattr(research, "_matched_spy", matched_spy)
    result = research.run_research_v04(root, progress=lambda _: None)
    assert len(called) == 10 and len(matched) == 10
    assert [(candidate, bps) for candidate, bps, _, _ in called] == [
        (f"C{i}", bps) for i in range(5) for bps in (10, 25)
    ]
    assert matched[-2:] == [("C4", 10), ("C4", 25)]
    assert set(loaded) == {"OLD", "TIE", "SPY"}
    assert all("CURRENT_ONLY" not in universe for _, _, universe, _ in called)
    assert result["status"] == "INCONCLUSIVE" and result["winner"] is None
    assert result["period"]["end"] == "2026-09-04"
    assert all(not row["metrics_valid"] and not row["qualified"] and row["pit"] is None for row in result["candidates"])
    if polluted:
        assert all(row["checks"]["HOLDING_PRICE_JUMPS_10"] == "INCONCLUSIVE" for row in result["candidates"])
        assert all(row["holding_price_jumps_10"][0]["ticker"] == "TIE" for row in result["candidates"])
    else:
        assert all(row["checks"]["MEMBERSHIP_HISTORY_COVERAGE"] == "INCONCLUSIVE" for row in result["candidates"])
    assert not (root / "config/v04/winner.json").exists()
    assert not (root / "experiments/oos_unlocks.jsonl").exists()
    report = (root / result["report_path"]).read_text()
    assert "指标无效" in report
    assert (root / "reports/v04/selection.json").exists()
