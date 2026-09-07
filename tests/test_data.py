from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from shm.data import (
    OOSReadLockedError,
    create_snapshot,
    read_price_cache,
    run_data_quality,
    update_price_cache,
    update_price_caches,
    normalize_price_frame,
)
from shm.experiments import record_oos_unlock


def _prices(dates: list[str], closes: list[float] | None = None) -> pd.DataFrame:
    values = closes or [100.0 + index for index in range(len(dates))]
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(dates),
            "Open": values,
            "High": [value + 1 for value in values],
            "Low": [value - 1 for value in values],
            "Close": values,
            "Volume": [1_000] * len(dates),
        }
    ).set_index("Date")


def test_cache_is_incremental_cache_first_and_adjusted(tmp_path) -> None:
    calls: list[dict[str, object]] = []

    def download(ticker: str, **kwargs: object) -> pd.DataFrame:
        calls.append({"ticker": ticker, **kwargs})
        return _prices(["2024-01-03"])

    cache_dir = tmp_path / "raw" / "prices"
    first = update_price_cache(
        "aapl",
        cache_dir,
        start="2024-01-02",
        end="2024-01-03",
        downloader=download,
        now=datetime(2024, 1, 4, tzinfo=UTC),
    )
    assert first.downloaded_rows == 1
    assert calls == [
        {
            "ticker": "AAPL",
            "start": "2024-01-02",
            "end": "2024-01-04",
            "auto_adjust": True,
        }
    ]
    assert first.frame.columns.tolist() == [
        "date", "open", "high", "low", "close", "volume",
        "adjusted", "source", "downloaded_at",
    ]
    assert first.frame["adjusted"].all()
    assert first.frame["source"].eq("yfinance").all()

    second = update_price_cache(
        "AAPL",
        cache_dir,
        start="2024-01-02",
        end="2024-01-03",
        downloader=lambda *_args, **_kwargs: pytest.fail("cache hit downloaded again"),
    )
    assert second.cache_hit


def test_empty_successful_range_is_cached(tmp_path) -> None:
    calls = 0

    def download(_ticker: str, **_kwargs: object) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return pd.DataFrame()

    cache_dir = tmp_path / "raw" / "prices"
    first = update_price_cache(
        "PLTR",
        cache_dir,
        start="2005-01-01",
        end="2018-12-31",
        downloader=download,
        now=datetime(2019, 1, 1, tzinfo=UTC),
    )
    second = update_price_cache(
        "PLTR",
        cache_dir,
        start="2005-01-01",
        end="2018-12-31",
        downloader=download,
        now=datetime(2019, 1, 2, tzinfo=UTC),
    )
    assert first.cache_hit and second.cache_hit
    assert calls == 1


def test_multiindex_ticker_named_low_does_not_collide_with_low_price_field() -> None:
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["LOW"]],
        names=["Price", "Ticker"],
    )
    frame = pd.DataFrame([[10, 11, 9, 10.5, 1000]], index=[pd.Timestamp("2024-01-02")], columns=columns)
    normalized = normalize_price_frame(frame, ticker="LOW")
    assert normalized.loc[0, "low"] == 9


def test_price_contract_preserves_eligibility_basis_and_correction_provenance() -> None:
    frame = _prices(["2024-01-02"])
    frame["as_traded_close"] = 200.0
    frame["dollar_volume"] = 20_000_000.0
    frame["source"] = "verified historical correction"
    normalized = normalize_price_frame(normalize_price_frame(frame, ticker="TEST"), ticker="TEST")
    assert normalized.loc[0, "as_traded_close"] == 200.0
    assert normalized.loc[0, "dollar_volume"] == 20_000_000.0
    assert normalized.loc[0, "source"] == "verified historical correction"


def test_retry_and_one_ticker_failure_do_not_abort_batch(tmp_path) -> None:
    attempts: dict[str, int] = {}
    sleeps: list[float] = []

    def download(ticker: str, **_kwargs: object) -> pd.DataFrame:
        attempts[ticker] = attempts.get(ticker, 0) + 1
        if ticker == "BAD" or attempts[ticker] == 1:
            raise RuntimeError("rate limited")
        return _prices(["2024-01-02"])

    results = update_price_caches(
        ["AAPL", "BAD"],
        tmp_path / "raw" / "prices",
        start="2024-01-02",
        end="2024-01-02",
        downloader=download,
        retries=3,
        backoff_seconds=0.25,
        sleep=sleeps.append,
        now=datetime(2024, 1, 3, tzinfo=UTC),
    )
    assert results["AAPL"].attempts == 2
    assert not results["AAPL"].failed
    assert results["BAD"].failed
    assert sleeps == [0.25, 0.25, 0.5]
    failure = json.loads((tmp_path / "raw" / "_failures.jsonl").read_text().strip())
    assert failure["ticker"] == "BAD"
    assert failure["attempts"] == 3


def test_quality_repairs_and_flags_dq_rules() -> None:
    sessions = pd.to_datetime(
        [
            "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
            "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11",
            "2024-01-12", "2024-01-16",
        ]
    )
    closes = [100.0, 200.0, 50.0, 150.0, 40.0, 120.0, 121.0, 122.0, 123.0, 124.0]
    frame = _prices([day.date().isoformat() for day in sessions], closes).reset_index()
    frame.loc[:1, "Volume"] = 0
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    weekend = frame.iloc[[0]].copy()
    weekend["Date"] = pd.Timestamp("2024-01-06")
    frame = pd.concat([frame, weekend], ignore_index=True)

    result = run_data_quality(
        "AAPL", frame, dev_start="2024-01-02", dev_end="2024-01-17"
    )
    report = result.report
    assert report.duplicate_dates_removed == 1  # DQ-01
    assert report.non_session_rows_removed == 1  # DQ-02
    assert len(report.extreme_return_dates) == 5  # DQ-03
    assert report.quarantine
    assert report.dev_missing_ratio > 0.05  # DQ-04
    assert report.exclude_for_missing_history
    assert report.zero_volume_ratio > 0.05  # DQ-06
    assert report.zero_volume_flag
    assert result.frame["date"].is_unique
    assert pd.Timestamp("2024-01-06") not in set(result.frame["date"])


def test_oos_lock_defaults_safe_and_unlock_calls_audit_hook(tmp_path) -> None:
    path = tmp_path / "AAPL.parquet"
    raw = _prices(["2018-12-31", "2019-01-02"]).reset_index()
    raw.to_parquet(path, index=False)

    with pytest.raises(ValueError, match="require oos_start"):
        read_price_cache(path)

    safe = read_price_cache(path, oos_start="2019-01-01")
    assert safe["date"].max() == pd.Timestamp("2018-12-31")
    with pytest.raises(OOSReadLockedError):
        read_price_cache(path, end="2019-01-02", oos_start="2019-01-01")
    with pytest.raises(ValueError, match="non-empty reason"):
        read_price_cache(
            path, end="2019-01-02", oos_start="2019-01-01", unlock_oos=True
        )
    with pytest.raises(ValueError, match="persisted audit record"):
        read_price_cache(
            path,
            end="2019-01-02",
            oos_start="2019-01-01",
            unlock_oos=True,
            reason="owner approved candidate",
        )
    audit_path = tmp_path / "oos_unlocks.jsonl"
    record_oos_unlock(
        audit_path,
        run_id="run-1",
        variant_index=1,
        reason="owner approved candidate",
        predicted="The candidate should retain its edge.",
        approved_by="owner",
    )

    unlocked = read_price_cache(
        path,
        end="2019-01-02",
        oos_start="2019-01-01",
        unlock_oos=True,
        reason="owner approved candidate",
        oos_audit_path=audit_path,
        oos_run_id="run-1",
    )
    assert len(unlocked) == 2


def test_snapshot_manifest_hashes_every_used_parquet(tmp_path) -> None:
    prices = tmp_path / "data" / "raw" / "prices"
    prices.mkdir(parents=True)
    aapl = prices / "AAPL.parquet"
    spy = prices / "SPY.parquet"
    _prices(["2024-01-02"]).to_parquet(aapl)
    _prices(["2024-01-02", "2024-01-03"]).to_parquet(spy)
    manifest = tmp_path / "data" / "snapshots" / "manifest.json"

    first = create_snapshot(
        {"AAPL": aapl, "SPY": spy},
        manifest,
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    second = create_snapshot(
        {"SPY": spy, "AAPL": aapl},
        manifest,
        created_at=datetime(2024, 1, 5, tzinfo=UTC),
    )
    payload = json.loads(manifest.read_text())
    assert first.id == second.id
    assert len(payload["snapshots"]) == 1
    assert set(payload["snapshots"][0]["files"]) == {"AAPL", "SPY"}
    assert all(
        len(item["sha256"]) == 64
        for item in payload["snapshots"][0]["files"].values()
    )
