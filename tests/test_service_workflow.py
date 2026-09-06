from types import SimpleNamespace

import pandas as pd
import pytest

from shm.service import workflow


def test_latest_completed_session_uses_market_close() -> None:
    assert workflow.latest_completed_session(pd.Timestamp("2026-09-05T00:00:00Z")) == pd.Timestamp(
        "2026-09-04"
    )


def test_completed_report_months_normalizes_month_end(tmp_path) -> None:
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "p4.yaml").write_text("forward_test_start: 2026-09-05\n", encoding="utf-8")

    assert workflow._completed_report_months(tmp_path, pd.Timestamp("2026-09-04")) == ()


def test_daily_workflow_runs_update_and_status_when_nothing_is_due(
    tmp_path, monkeypatch
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        workflow,
        "latest_completed_session",
        lambda now=None: pd.Timestamp("2026-09-04"),
    )
    monkeypatch.setattr(
        workflow,
        "build_paper_progress",
        lambda root: SimpleNamespace(
            next_rebalance_date=pd.Timestamp("2026-09-17"), pending_cycles=()
        ),
    )
    monkeypatch.setattr(workflow, "_forward_start", lambda root: pd.Timestamp("2026-09-05"))
    monkeypatch.setattr(workflow, "validate_required_price_caches", lambda root: "ok")
    monkeypatch.setattr(workflow, "_completed_report_months", lambda root, session: ())

    def run(command, cwd):
        commands.append(list(command))
        return "paper status: cycles=0/3"

    steps = []
    result = workflow.run_daily_workflow(
        tmp_path, command_runner=run,
        reporter=lambda name, status, *_: steps.append((name, status)),
    )

    assert result.market_session == "2026-09-04"
    assert [command[3:5] for command in commands] == [["data", "update"], ["paper", "status"]]
    assert [name for name, status in steps if status == "skipped"] == [
        "rebalance", "simulate-fills", "option-overlay", "monthly-report",
    ]


def test_sp500_workflow_uses_shared_throttled_queue_instead_of_legacy_downloader(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/sp500.yaml").write_text("enabled: true\n")
    monkeypatch.setattr(workflow, "latest_completed_session", lambda now=None: pd.Timestamp("2026-09-04"))
    monkeypatch.setattr(workflow, "build_paper_progress", lambda root: SimpleNamespace(
        next_rebalance_date=pd.Timestamp("2026-09-17"), pending_cycles=()))
    monkeypatch.setattr(workflow, "_forward_start", lambda root: pd.Timestamp("2026-09-05"))
    monkeypatch.setattr(workflow, "validate_required_price_caches", lambda root: "ok")
    monkeypatch.setattr(workflow, "_completed_report_months", lambda root, session: ())
    commands = []
    result = workflow.run_daily_workflow(tmp_path, command_runner=lambda command, cwd: commands.append(command) or "ok")
    assert [command[3] for command in commands] == ["sp500-refresh", "market-refresh-sp500", "paper"]
    assert not any(command[3:5] == ["data", "update"] for command in commands)
    assert "new risk paused" in result.actions[-1]


def test_daily_workflow_records_a_missed_rebalance_and_moves_forward(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        workflow,
        "latest_completed_session",
        lambda now=None: pd.Timestamp("2026-09-18"),
    )
    calls = 0

    def progress(root):
        nonlocal calls
        calls += 1
        next_date = "2026-09-17" if calls == 1 else "2026-10-15"
        return SimpleNamespace(next_rebalance_date=pd.Timestamp(next_date), pending_cycles=())

    monkeypatch.setattr(workflow, "build_paper_progress", progress)
    monkeypatch.setattr(workflow, "_forward_start", lambda root: pd.Timestamp("2026-09-05"))
    monkeypatch.setattr(workflow, "validate_required_price_caches", lambda root: "ok")
    monkeypatch.setattr(workflow, "_completed_report_months", lambda root, session: ())

    result = workflow.run_daily_workflow(tmp_path, command_runner=lambda command, cwd: "ok")

    assert "missed rebalance 2026-09-17" in result.actions
    assert (tmp_path / "paper/missed/2026-09-17.json").exists()


def test_cache_validation_clears_empty_success_marker(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "data/raw/prices"
    cache.mkdir(parents=True)
    (cache / "AAA.parquet").write_bytes(b"parquet")
    (cache / "SPY.coverage.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        workflow,
        "load_config_bundle",
        lambda path: SimpleNamespace(
            params=SimpleNamespace(
                risk=SimpleNamespace(trend_filter=SimpleNamespace(benchmark="SPY"))
            )
        ),
    )
    monkeypatch.setattr(
        workflow,
        "load_frozen_universe",
        lambda path: SimpleNamespace(active_tickers=("AAA",)),
    )

    with pytest.raises(RuntimeError, match="SPY"):
        workflow.validate_required_price_caches(tmp_path)

    assert not (cache / "SPY.coverage.json").exists()
