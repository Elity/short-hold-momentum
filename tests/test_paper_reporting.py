import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pytest
import yaml

import shm.paper.reporting as reporting
from shm.paper import Fill, OrderTicket, generate_monthly_report, write_fill_csv, write_ticket_csv


def _paper_repo(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "paper/accounts").mkdir(parents=True)
    (tmp_path / "paper/p4.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "mode": "paper",
                "provider": "local_offline_simulator",
                "initial_equity_usd": 100_000,
                "forward_test_start": "2026-09-05",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config/costs.yaml").write_text(
        yaml.safe_dump({"per_side_bps": {"default": 10}}),
        encoding="utf-8",
    )
    (tmp_path / "paper/accounts/2026-09-05.json").write_text(
        json.dumps(
            {
                "as_of": "2026-09-05",
                "cash": 100_000,
                "mode": "paper",
                "positions": {},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _sessions(start: str, end: str) -> pd.DatetimeIndex:
    calendar = xcals.get_calendar(
        "XNYS",
        start=pd.Timestamp(start) - pd.Timedelta("7D"),
        end=pd.Timestamp(end) + pd.Timedelta("7D"),
    )
    return calendar.sessions_in_range(start, end)


def _write_prices(
    root: Path,
    ticker: str,
    sessions: pd.DatetimeIndex,
    *,
    closes: list[float],
) -> None:
    path = root / "data/raw/prices" / f"{ticker}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": sessions,
            "open": [100.0] * len(sessions),
            "high": [max(100.0, close) for close in closes],
            "low": [min(100.0, close) for close in closes],
            "close": closes,
            "volume": [100_000] * len(sessions),
            "adjusted": [True] * len(sessions),
            "source": ["synthetic"] * len(sessions),
            "downloaded_at": [pd.Timestamp("2026-11-02", tz="UTC")] * len(sessions),
        }
    ).to_parquet(path, index=False)


def _write_paper_log(root: Path, signal_date: str, **results: object) -> None:
    path = root / "experiments/log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "mode": "paper",
        "status": "PAPER_TICKET_READY",
        "period": {"end": signal_date},
        "results": {
            "selected": ["AAA"],
            "target_exposure": 1.0,
            "projected_cash": 0.0,
            "rounding_residual_usd": 0.0,
            "target_positions": {},
            "skipped_candidates": [],
            **results,
        },
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")


def test_first_forward_month_can_report_an_all_cash_account(tmp_path, monkeypatch) -> None:
    root = _paper_repo(tmp_path)
    monkeypatch.setattr(
        reporting,
        "_utc_now",
        lambda: pd.Timestamp("2026-10-02", tz="UTC"),
    )

    result = generate_monthly_report(root, "2026-09")

    assert result.inputs.start_date == pd.Timestamp("2026-09-08")
    assert result.inputs.paper_return == 0.0
    assert result.inputs.model_return == 0.0
    assert result.inputs.fill_count == 0
    assert (result.paper_equity == 100_000).all()
    assert (result.model_equity == 100_000).all()
    assert result.report_path == root / "reports/paper-2026-09.md"
    assert result.report_path.exists()


def test_prior_month_signal_carries_into_later_model_month(tmp_path, monkeypatch) -> None:
    root = _paper_repo(tmp_path)
    sessions = _sessions("2026-09-08", "2026-10-30")
    closes = [100.0 + max(0, index - 7) for index in range(len(sessions))]
    _write_prices(root, "AAA", sessions, closes=closes)
    _write_paper_log(root, "2026-09-17")
    monkeypatch.setattr(
        reporting,
        "_utc_now",
        lambda: pd.Timestamp("2026-11-02", tz="UTC"),
    )

    result = generate_monthly_report(root, "2026-10")

    assert result.model_equity.index[0] == pd.Timestamp("2026-10-01")
    assert result.model_equity.index[-1] == pd.Timestamp("2026-10-30")
    assert result.inputs.model_return > 0
    assert result.model_equity.iloc[-1] > result.model_equity.iloc[0]


def test_monthly_report_attributes_zero_cost_simulated_fill(tmp_path, monkeypatch) -> None:
    root = _paper_repo(tmp_path)
    sessions = _sessions("2026-09-08", "2026-09-30")
    _write_prices(root, "AAA", sessions, closes=[100.0] * len(sessions))
    _write_paper_log(
        root,
        "2026-09-17",
        target_positions={"AAA": 10},
        projected_cash=99_000.0,
        rounding_residual_usd=12.34,
        skipped_candidates=[
            {
                "ticker": "TOOEXPENSIVE",
                "reason": "insufficient_cash_for_one_share",
                "replacement_ticker": "AAA",
            }
        ],
    )
    write_ticket_csv(
        root / "paper/tickets/2026-09-17.csv",
        [OrderTicket("AAA", "buy", 10)],
    )
    write_fill_csv(
        root / "paper/fills/2026-09-18.csv",
        [Fill("AAA", 10, 100.0, "2026-09-18 09:30", 100.0)],
    )
    (root / "paper/accounts/2026-09-18.json").write_text(
        json.dumps(
            {
                "as_of": "2026-09-18",
                "cash": 99_000.0,
                "mode": "paper",
                "positions": {"AAA": 10},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reporting,
        "_utc_now",
        lambda: pd.Timestamp("2026-10-02", tz="UTC"),
    )

    result = generate_monthly_report(root, "2026-09")

    assert result.inputs.fill_count == 1
    assert result.inputs.realized_cost_bps == 0.0
    assert result.inputs.cost_multiple == 0.0
    assert result.inputs.hc07_triggered is False
    assert result.inputs.execution_price_impact_usd == 0.0
    assert result.inputs.integer_rounding_usd == pytest.approx(12.34)
    assert result.inputs.skipped_candidates[0].replacement_ticker == "AAA"


def test_monthly_report_rejects_an_incomplete_month(tmp_path, monkeypatch) -> None:
    root = _paper_repo(tmp_path)
    monkeypatch.setattr(
        reporting,
        "_utc_now",
        lambda: pd.Timestamp("2026-09-15", tz="UTC"),
    )

    with pytest.raises(ValueError, match="not a completed paper month"):
        generate_monthly_report(root, "2026-09")


def test_monthly_report_never_uses_pre_forward_history(tmp_path, monkeypatch) -> None:
    root = _paper_repo(tmp_path)
    (root / "paper/accounts/2026-09-04.json").write_text(
        json.dumps({"as_of": "2026-09-04", "positions": {"OLD": 1}}),
        encoding="utf-8",
    )
    _write_paper_log(root, "2026-09-04", selected=["OLD"])
    write_fill_csv(
        root / "paper/fills/2026-09-04.csv",
        [Fill("OLD", 1, 1.0, "2026-09-04 09:30", 1.0)],
    )
    monkeypatch.setattr(
        reporting,
        "_utc_now",
        lambda: pd.Timestamp("2026-10-02", tz="UTC"),
    )

    result = generate_monthly_report(root, "2026-09")

    assert result.inputs.paper_return == 0.0
    assert result.inputs.model_return == 0.0
    assert result.inputs.fill_count == 0
    with pytest.raises(ValueError, match="precedes forward_test_start"):
        generate_monthly_report(root, "2026-08")
