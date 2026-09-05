import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import shm.cli as cli
from shm.paper import Fill, OrderTicket, write_fill_csv, write_ticket_csv
from shm.runner import DataUpdateSummary, RunOutcome


def test_data_update_forwards_through_oos(monkeypatch) -> None:
    received: dict[str, object] = {}

    def update(**kwargs: object) -> DataUpdateSummary:
        received.update(kwargs)
        return DataUpdateSummary(1, 0, 0, 0)

    monkeypatch.setattr(cli, "update_development_data", update)
    assert cli.main(["data", "update", "--through-oos", "--skip-pit"]) == 0
    assert received["through_oos"] is True
    assert received["include_pit"] is False


def test_backtest_forwards_oos_unlock_reason(tmp_path, monkeypatch) -> None:
    received: dict[str, object] = {}

    def run(**kwargs: object) -> RunOutcome:
        received.update(kwargs)
        return RunOutcome("run-1", "PASS", Path("report.md"), Path("daily.parquet"))

    monkeypatch.setattr(cli, "run_development_backtest", run)
    reason = "owner approved final OOS check"
    assert (
        cli.main(
            [
                "backtest",
                "run",
                "--repo-root",
                str(tmp_path),
                "--prereg",
                "experiments/prereg/V04.md",
                "--unlock-oos",
                "--reason",
                reason,
            ]
        )
        == 0
    )
    assert received["unlock_oos"] is True
    assert received["reason"] == reason


def test_paper_rebalance_loads_snapshot_and_stays_offline(tmp_path, monkeypatch) -> None:
    account_path = tmp_path / "paper-account.json"
    account_path.write_text(
        json.dumps({"mode": "paper", "cash": 100_000, "positions": {"HPQ": 50}}),
        encoding="utf-8",
    )
    received: dict[str, object] = {}

    def run(account, repo_root, as_of):
        received.update(account=account, repo_root=repo_root, as_of=as_of)
        return SimpleNamespace(
            as_of=pd.Timestamp("2026-09-17"),
            params_hash="2064365d",
            selected=("HPQ",),
            ticket_plan=SimpleNamespace(tickets=()),
            ticket_path=tmp_path / "paper/tickets/2026-09-17.csv",
        )

    monkeypatch.setattr(cli, "run_paper_rebalance", run)
    assert (
        cli.main(
            [
                "paper",
                "rebalance",
                "--repo-root",
                str(tmp_path),
                "--account",
                str(account_path),
                "--as-of",
                "2026-09-17",
            ]
        )
        == 0
    )
    assert received["repo_root"] == tmp_path.resolve()
    assert received["as_of"] == "2026-09-17"
    assert received["account"].cash == 100_000
    assert received["account"].positions == {"HPQ": 50}


def test_paper_rebalance_rejects_live_account_snapshot(tmp_path, capsys) -> None:
    account_path = tmp_path / "paper-account.json"
    account_path.write_text(
        json.dumps({"mode": "live", "cash": 100_000, "positions": {}}),
        encoding="utf-8",
    )

    assert (
        cli.main(
            [
                "paper",
                "rebalance",
                "--repo-root",
                str(tmp_path),
                "--account",
                str(account_path),
                "--as-of",
                "2026-09-17",
            ]
        )
        == 2
    )
    assert "live endpoints are forbidden" in capsys.readouterr().err


def test_paper_fill_ingestion_writes_confirmed_account_snapshot(tmp_path) -> None:
    account_path = tmp_path / "account-before.json"
    account_path.write_text(
        json.dumps({"mode": "paper", "cash": 1_000, "positions": {}}),
        encoding="utf-8",
    )
    ticket_path = write_ticket_csv(
        tmp_path / "paper/tickets/2026-09-17.csv",
        [OrderTicket("AAA", "buy", 5)],
    )
    fill_path = write_fill_csv(
        tmp_path / "paper/fills/2026-09-18.csv",
        [Fill("AAA", 5, 101, "2026-09-18 09:30", 100, commission=1)],
    )
    output_path = tmp_path / "paper/accounts/2026-09-18.json"

    assert (
        cli.main(
            [
                "paper",
                "ingest-fills",
                "--repo-root",
                str(tmp_path),
                "--account",
                str(account_path),
                "--tickets",
                str(ticket_path),
                "--fills",
                str(fill_path),
                "--output-account",
                str(output_path),
            ]
        )
        == 0
    )
    updated = json.loads(output_path.read_text(encoding="utf-8"))
    assert updated == {"cash": 494.0, "mode": "paper", "positions": {"AAA": 5}}
