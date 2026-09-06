from copy import deepcopy
import json
from types import SimpleNamespace

import pandas as pd
import pytest
import numpy as np

from shm.v03.research import performance, qualifies, select_winner
from shm.v03.research import _correctness, _load_prices, _publish_result, _spy_buy_hold
from shm.v03.research import _holding_price_jumps, _benchmark_price_jumps, render_research


def candidate(name="C1"):
    return {"strategy_id": name, "checks": {"DATA": "PASS"}, "module_count": 1,
            "metrics_10": {"cagr": .18, "maxdd": -.12, "turnover": 2.0},
            "metrics_25": {"cagr": .17, "maxdd": -.13, "turnover": 2.0},
            "benchmark_10": {"cagr": .16, "maxdd": -.30},
            "benchmark_25": {"cagr": .159, "maxdd": -.301}}


def test_gate_uses_net_return_and_both_costs_not_sharpe_or_ten_percent():
    row = candidate()
    assert qualifies(row)  # 10% is not a hard drawdown limit.
    row["metrics_25"]["cagr"] = .15
    assert not qualifies(row)
    row = candidate()
    row["checks"]["DATA"] = "INCONCLUSIVE"
    assert not qualifies(row)


def test_winner_is_deterministic_and_no_winner_is_valid():
    first, second = candidate("C1"), candidate("C2")
    second["metrics_25"]["cagr"] += .01
    assert select_winner([first, second]) == "C2"
    second = deepcopy(first)
    second["strategy_id"] = "C0"
    second["module_count"] = 0
    assert select_winner([first, second]) == "C0"
    first["metrics_10"]["cagr"] = .1
    assert select_winner([first]) is None


def test_performance_includes_first_fill_cost_and_initial_peak():
    equity = pd.Series([99_900., 100_000.], index=pd.bdate_range("2026-01-05", periods=2))
    value = performance(equity)
    assert value["cagr"] == pytest.approx(0)
    assert value["maxdd"] == pytest.approx(-.001)
    assert value["net_return"] == 0


def test_spy_starts_on_common_first_open_and_pays_entry_cost():
    dates = pd.bdate_range("2026-01-05", periods=2)
    frame = pd.DataFrame({"date": dates, "open": [100., 110.], "close": [110., 120.]})
    equity = _spy_buy_hold(frame, dates, 25)
    assert equity.iloc[0] == pytest.approx(100_000 * 1.10 / 1.0025)
    assert equity.iloc[1] == pytest.approx(100_000 * 1.20 / 1.0025)


def test_quality_includes_prior_close_that_determined_first_evaluation_trade():
    dates = pd.bdate_range("2026-01-05", periods=4)
    bt = SimpleNamespace(
        equity=pd.Series(100_000., index=dates), cash=pd.Series(100_000., index=dates),
        weights=pd.DataFrame({"AAA": 0.0}, index=dates), transactions=pd.DataFrame(),
        execution_fallbacks=pd.DataFrame(),
    )
    result = SimpleNamespace(backtest=bt, warnings=[{"date": str(dates[0].date()), "warning": "MISSING_SPY_HISTORY"}])
    assert _correctness(result, dates[2:])["SIGNAL_DATA"] == "PASS"
    result.warnings.append({"date": str(dates[1].date()), "warning": "MISSING_SPY_HISTORY"})
    assert _correctness(result, dates[2:])["SIGNAL_DATA"] == "INCONCLUSIVE"


def test_unadjusted_prices_cannot_be_reported_as_total_return(tmp_path):
    folder = tmp_path / "data/raw/prices"
    folder.mkdir(parents=True)
    date = pd.Timestamp("2026-01-05")
    pd.DataFrame({"date": [date], "open": [10.], "high": [11.], "low": [9.], "close": [10.],
                  "volume": [1_000_000.], "adjusted": [False]}).to_parquet(folder / "AAA.parquet")
    with pytest.raises(ValueError, match="adjusted total-return"):
        _load_prices(tmp_path, ["AAA"], date, date)


def publication_payload(winner="C1"):
    return {"run_id": "run-one", "winner": winner, "candidates": [{"strategy_id": "C1", "config": {"id": "C1"}}],
            "universe_hash": "universe", "generated_at": "2026-09-06T00:00:00Z", "snapshot_id": "data",
            "source_hash": "source", "status": "HISTORICAL_SCREEN_PASS" if winner else "NO_QUALIFIED_CANDIDATE"}


def test_publication_recovers_missing_freeze_without_duplicate_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr("shm.v03.research.render_research", lambda payload: "reviewable report")
    folder = tmp_path / "reports/v03/run-one"
    folder.mkdir(parents=True)
    payload = publication_payload()
    # Model a crash after caching selection but before publishing its freeze.
    (folder / "selection.json").write_text(json.dumps(payload))
    _publish_result(tmp_path, folder, payload)
    _publish_result(tmp_path, folder, payload)
    assert json.loads((tmp_path / "config/v03/winner.json").read_text())["strategy_id"] == "C1"
    assert len((tmp_path / "experiments/v03/log.jsonl").read_text().splitlines()) == 1
    assert not (tmp_path / "experiments/oos_unlocks.jsonl").exists()


def test_conflicting_or_no_winner_cannot_publish_over_existing_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr("shm.v03.research.render_research", lambda payload: "report")
    frozen = tmp_path / "config/v03/winner.json"
    frozen.parent.mkdir(parents=True)
    frozen.write_text(json.dumps({"research_run_id": "old-run", "strategy_id": "C3"}))
    for winner in ("C1", None):
        with pytest.raises(ValueError, match="already frozen"):
            _publish_result(tmp_path, tmp_path / "reports/v03/run-one", publication_payload(winner))
    assert not (tmp_path / "reports/v03/selection.json").exists()
    assert not (tmp_path / "experiments/v03/log.jsonl").exists()
    assert json.loads(frozen.read_text())["strategy_id"] == "C3"


def test_no_winner_publishes_without_creating_a_simulation_winner(tmp_path, monkeypatch):
    monkeypatch.setattr("shm.v03.research.render_research", lambda payload: "no winner")
    _publish_result(tmp_path, tmp_path / "reports/v03/run-one", publication_payload(None))
    assert not (tmp_path / "config/v03/winner.json").exists()
    assert json.loads((tmp_path / "reports/v03/selection.json").read_text())["winner"] is None


def test_price_jump_gate_uses_previous_actual_exposure_and_checks_spy():
    dates = pd.bdate_range("2026-01-05", periods=3)
    prepared = SimpleNamespace(
        dates=dates, tickers=("AAA", "UNHELD", "SPY"), ticker_index={"AAA": 0, "UNHELD": 1, "SPY": 2},
        returns=np.array([[np.nan, np.nan, np.nan], [1800., 9999., .60], [-.90, 0., .01]]),
    )
    bt = SimpleNamespace(
        weights=pd.DataFrame({"AAA": [.04, 0., 0.], "UNHELD": 0., "SPY": 0.}, index=dates),
        equity=pd.Series(100_000., index=dates), cash=pd.Series(100_000., index=dates),
        transactions=pd.DataFrame(), execution_fallbacks=pd.DataFrame(),
    )
    jumps = _holding_price_jumps(prepared, bt, dates[1:])
    assert jumps == [{"date": str(dates[1].date()), "ticker": "AAA", "return": 1800., "prior_weight": .04}]
    benchmark_jumps = _benchmark_price_jumps(prepared, dates[1:])
    assert benchmark_jumps[0]["ticker"] == "SPY"
    checks = _correctness(SimpleNamespace(backtest=bt, warnings=[]), dates[1:],
                          holding_price_jumps=jumps, benchmark_price_jumps=benchmark_jumps)
    assert checks["HOLDING_PRICE_JUMPS"] == "INCONCLUSIVE"
    assert checks["BENCHMARK_PRICE_JUMPS"] == "INCONCLUSIVE"
    winner = candidate()
    winner["checks"] = checks
    assert not qualifies(winner)


def test_report_with_pit_price_pollution_does_not_present_raw_cagr_as_a_result():
    payload = publication_payload(None)
    row = candidate()
    row.update({"qualified": False, "warnings": ["WARN_PIT_PRICE_JUMPS_RAW_METRICS_INVALID"],
                "views": {"annual_returns": {}, "since_2019": None, "excluding_best_year": None},
                "risk_matched_spy_10": {"cagr": .10, "maxdd": -.20}})
    row["metrics_10"].update(avg_exposure=.5, avg_holding_days=40)
    row["pit"] = {"coverage": .77, "status": "INCONCLUSIVE", "metrics_10": {"cagr": .3074, "maxdd": -.30},
                  "holding_price_jumps_10": [{"date": "2010-02-22", "ticker": "TIE", "return": 1897.8, "prior_weight": .041}],
                  "holding_price_jumps_25": []}
    payload.update(candidates=[row], period={"start": "2005-01-04", "end": "2026-09-04"},
                   benchmark_10=row["benchmark_10"], benchmark_25=row["benchmark_25"])
    report = render_research(payload)
    assert "30.74%" not in report
    assert "原始年化/回撤诊断数不可用" in report
    assert "2010-02-22" in report and "TIE" in report


def test_new_open_positions_are_checked_until_close_without_counting_pre_entry_gaps():
    dates = pd.to_datetime(["2026-06-29", "2026-06-30"])
    tickers = ("NEW_UP", "NEW_DOWN", "GAP_BEFORE_ENTRY", "UNHELD", "SPY")
    prepared = SimpleNamespace(
        dates=dates, tickers=tickers,
        returns=np.array([[0., 0., 0., 0., 0.], [100., -.90, 9.2, 9998.9, 0.]]),
        closes=np.array([[10., 10., 10., 10., 10.], [1010., 1., 102., 99999., 10.]]),
    )
    bt = SimpleNamespace(
        equity=pd.Series(100_000., index=dates), cash=pd.Series(40_000., index=dates),
        weights=pd.DataFrame([[0., 0., 0., 0., 0.], [.2, .2, .2, 0., 0.]], index=dates, columns=tickers),
        transactions=pd.DataFrame([
            {"signal_date": dates[0], "execution_date": dates[1], "ticker": ticker, "side": "buy", "price": price}
            for ticker, price in (("NEW_UP", 10.), ("NEW_DOWN", 10.), ("GAP_BEFORE_ENTRY", 100.))
        ]), execution_fallbacks=pd.DataFrame(),
    )
    jumps = _holding_price_jumps(prepared, bt, dates[1:])
    assert {item["ticker"] for item in jumps} == {"NEW_UP", "NEW_DOWN"}
    assert [item["return"] for item in jumps] == pytest.approx([100., -.90])
    assert all(item["prior_weight"] == 0 and item["quote_window"] == "fill_to_close" for item in jumps)
    checks = _correctness(SimpleNamespace(backtest=bt, warnings=[]), dates[1:],
                          holding_price_jumps=jumps, benchmark_price_jumps=[])
    assert checks["HOLDING_PRICE_JUMPS"] == "INCONCLUSIVE"
    row = candidate()
    row["checks"] = checks
    assert not qualifies(row)
