import json
from datetime import UTC, datetime

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import yaml

import shm.runner as runner
from shm.checks import CheckResult, KR2Result
from shm.experiments import compute_file_hash
from shm.report import PerformanceMetrics
from shm.runner import run_development_backtest


def test_oos_verdict_uses_kr2_and_quality_eligibility() -> None:
    assert runner._verdict_for_kr2(KR2Result("PASS", True, True, True, "")) == "支持"
    assert runner._verdict_for_kr2(KR2Result("FAIL", False, True, True, "")) == "反驳"
    assert runner._verdict_for_kr2(KR2Result("FAIL", True, True, False, "")) == "无法判定"


def test_synthetic_approved_run_writes_report_daily_snapshot_and_log(tmp_path, monkeypatch) -> None:
    for directory in (
        "config",
        "data/raw/prices",
        "data/reference",
        "data/snapshots",
        "experiments/prereg",
        "reports",
    ):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)

    dates = {
        "calendar": "XNYS",
        "dev_start": "2024-01-02",
        "dev_end": "2025-03-31",
        "oos_start": "2025-04-01",
        "oos_end": None,
        "warmup_trading_days": 30,
        "rebalance_every_trading_days": 20,
    }
    params = {
        "signal": {
            "name": "xs_momentum_12_1",
            "lookback_trading_days": 20,
            "skip_trading_days": 5,
            "top_n": 2,
            "weighting": "equal",
            "tie_break": "ticker_asc",
        },
        "eligibility": {
            "min_price_usd": 5,
            "min_adv_usd": 1,
            "adv_window_days": 5,
            "require_full_history": True,
            "min_eligible_count": 2,
        },
        "risk": {
            "trend_filter": {
                "enabled": True,
                "benchmark": "SPY",
                "sma_days": 10,
                "off_exposure": 0,
            },
            "vol_target": {
                "enabled": True,
                "window_days": 5,
                "target_annual_vol": 0.15,
                "max_exposure": 1,
            },
        },
        "execution": {
            "fill": "next_open",
            "fractional_shares_in_backtest": True,
            "cash_yield_annual": 0,
        },
    }
    costs = {"model": "fixed_bps_on_notional", "per_side_bps": {"default": 10, "stress": 25, "floor": 5}}
    universe = {
        "frozen_on": "2026-09-04",
        "rule_text": "Synthetic fixed test universe.",
        "exclusions": [],
        "tickers": ["AAA", "BBB", "CCC"],
    }
    for name, payload in (("dates", dates), ("params", params), ("costs", costs), ("universe", universe)):
        (tmp_path / "config" / f"{name}.yaml").write_text(yaml.safe_dump(payload, sort_keys=False))

    prereg = tmp_path / "experiments/prereg/V01.md"
    prereg.write_text(
        "# V01\n"
        "- 假设（一句话，可证伪）：Synthetic baseline completes.\n"
        "- 与 V00 的唯一差别（OFAT）：signal.top_n: 2 → 1\n"
        "- 预测：No directional prediction.\n"
        "- 是否使用样本外：是\n"
        "- 样本外预测：Sharpe should remain above SPY.\n"
        "- owner 批准：[x] 日期：2026-09-04\n"
    )
    sessions = xcals.get_calendar("XNYS", start="2023-10-01", end="2025-06-01").sessions
    wave = np.sin(np.arange(len(sessions)) / 10) * 0.15
    for offset, ticker in enumerate(("AAA", "BBB", "CCC", "SPY")):
        close = (100 + offset * 10) * (1 + wave + np.arange(len(sessions)) * 0.0001)
        frame = pd.DataFrame(
            {
                "date": sessions,
                "open": close * 0.999,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000,
                "adjusted": True,
                "source": "yfinance",
                "downloaded_at": datetime(2026, 9, 4, tzinfo=UTC),
            }
        )
        frame.to_parquet(tmp_path / "data/raw/prices" / f"{ticker}.parquet", index=False)
    pd.DataFrame({"date": ["2020-01-02"], "tickers": ["AAA,BBB,CCC"]}).to_csv(
        tmp_path / "data/reference/sp500_history.csv", index=False
    )

    monkeypatch.setattr(runner, "_git_sha", lambda _root: "abc123")
    spy = pd.read_parquet(tmp_path / "data/raw/prices/SPY.parquet")
    outcome = run_development_backtest(
        repo_root=tmp_path,
        prereg_path=prereg,
        second_source_loader=lambda _start, _end: spy,
        ticker_second_source_loader=lambda _ticker, _start, _end: spy,
    )
    assert outcome.report_path.exists()
    assert outcome.daily_path.exists()
    assert "CHK-07" in outcome.report_path.read_text()
    log = json.loads((tmp_path / "experiments/log.jsonl").read_text().strip())
    assert log["run_id"] == outcome.run_id
    assert log["phase"] == "P2"
    assert log["variant_index"] == 1
    assert log["params"]["signal"]["top_n"] == 1
    assert log["universe_hash"] == compute_file_hash(tmp_path / "config/universe.yaml")
    assert runner._verdict_for_status("SUSPECT") == "无法判定"
    manifest = json.loads((tmp_path / "data/snapshots/manifest.json").read_text())
    assert manifest["snapshots"]

    reason = "owner approved final OOS check"
    oos_outcome = run_development_backtest(
        repo_root=tmp_path,
        prereg_path=prereg,
        unlock_oos=True,
        reason=reason,
        second_source_loader=lambda _start, _end: spy,
        ticker_second_source_loader=lambda _ticker, _start, _end: spy,
    )
    records = [json.loads(line) for line in (tmp_path / "experiments/log.jsonl").read_text().splitlines()]
    oos_log = records[-1]
    unlock = json.loads((tmp_path / "experiments/oos_unlocks.jsonl").read_text().strip())
    assert oos_log["run_id"] == oos_outcome.run_id == unlock["run_id"]
    assert oos_log["params_hash"] == log["params_hash"]
    assert oos_log["variant_index"] == log["variant_index"] == unlock["variant_index"]
    assert oos_log["oos_used"] is True
    assert oos_log["period"] == {"start": "2025-04-01", "end": "2025-05-30"}
    assert oos_log["expected"] == unlock["predicted"] == "Sharpe should remain above SPY."
    assert unlock["approved_by"] == "owner via ADR-002"
    assert oos_log["kr2"]["run_status_eligible"] is False
    assert oos_log["verdict"] == "无法判定"
    oos_report = oos_outcome.report_path.read_text()
    assert "## KR2 out-of-sample gate" in oos_report
    assert "--unlock-oos --reason 'owner approved final OOS check'" in oos_report


def test_suspect_checklist_contains_b01_through_b07(tmp_path) -> None:
    path = tmp_path / "suspect.md"
    metrics = PerformanceMetrics(0.31, -0.2, 1.0, 1.55, 1.0, 1.0, 20.0)
    transactions = pd.DataFrame(
        [
            {
                "signal_date": "2024-01-02",
                "execution_date": "2024-01-03",
                "ticker": "AAA",
                "side": "buy",
                "quantity": 10.0,
                "price": 10.0,
                "notional": 100.0,
                "cost": 0.1,
            },
            {
                "signal_date": "2024-01-22",
                "execution_date": "2024-01-23",
                "ticker": "AAA",
                "side": "sell",
                "quantity": 10.0,
                "price": 12.0,
                "notional": 120.0,
                "cost": 0.12,
            },
        ]
    )
    prices = {"AAA": pd.DataFrame({"date": ["2008-01-02", "2008-12-31"], "close": [10, 12]})}
    runner._write_suspect_checklist(
        path=path,
        full_lookahead=CheckResult("PASS"),
        prices=prices,
        universe_tickers=("AAA",),
        start="2008-01-01",
        end="2018-12-31",
        ticker_second_source_loader=lambda _ticker, _start, _end: prices["AAA"],
        execution_check=CheckResult("PASS"),
        strategy_metrics=metrics,
        stress_metrics=metrics,
        survivorship_check=CheckResult("PASS"),
        one_year_check=CheckResult("PASS"),
        transactions=transactions,
    )
    content = path.read_text()
    for item in range(1, 8):
        assert f"B-0{item}" in content
