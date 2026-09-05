from pathlib import Path

import shm.cli as cli
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
