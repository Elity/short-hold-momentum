from hashlib import sha256
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from shm.data.market_refresh import ProviderPause, YahooHistorySource, refresh_market_cache
from shm.data.prices import normalize_price_frame


ASOF = "2026-09-04"
NOW = "2026-09-06T12:00:00Z"


@pytest.fixture
def bars():
    sessions = xcals.get_calendar("XNYS", start="2025-01-01", end=ASOF).sessions[-280:]
    close = 40 + np.arange(len(sessions)) / 100
    return pd.DataFrame({"date": sessions, "open": close, "high": close + 1,
                         "low": close - 1, "close": close, "volume": 2_000_000})


def save(root, ticker, frame):
    path = root / "data/raw/prices" / f"{ticker}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize_price_frame(frame, ticker=ticker, downloaded_at=pd.Timestamp(NOW)).to_parquet(path, index=False)
    return path


def source_for(bars, calls):
    def download(ticker, *, start, end, auto_adjust):
        calls.append((ticker, start, end, auto_adjust))
        return bars.loc[(bars.date >= pd.Timestamp(start)) & (bars.date < pd.Timestamp(end))].copy()
    return download


def test_latest_valid_cache_hits_make_zero_requests_and_keep_canonical_symbols(tmp_path, bars):
    save(tmp_path, "SPY", bars)
    save(tmp_path, "BRK.B", bars)
    def forbidden(*args, **kwargs):
        raise AssertionError("fresh cache must not request Yahoo")
    result = refresh_market_cache(tmp_path, ["BRK.B"], as_of=ASOF, now=NOW, downloader=forbidden)
    assert result["requested"] == 0 and result["complete"]
    assert result["fresh"] == 2 and result["listed_expected"] == result["active_now"] == 1
    assert result["eligible_data_ready"] == ["BRK.B"]
    assert all(row["date"] == ASOF for row in result["results"].values())
    assert (tmp_path / "data/raw/prices/BRK.B.parquet").exists()


def test_priority_spacing_and_persisted_budget_resume_without_redownloading_successes(tmp_path, bars):
    calls, waits = [], []
    source = source_for(bars, calls)
    first = refresh_market_cache(tmp_path, ["BBB", "BRK.B", "AAA"], held_tickers=["AAA"],
                                 as_of=ASOF, now=NOW, downloader=source, sleep=waits.append, daily_budget=2)
    assert [call[0] for call in calls] == ["SPY", "AAA"]
    assert waits == [1.0]
    assert first["critical_complete"] and not first["complete"]
    assert first["missing"] == ["BBB", "BRK.B"]
    resumed = refresh_market_cache(tmp_path, ["BBB", "BRK.B", "AAA"], held_tickers=["AAA"],
                                   as_of=ASOF, now=NOW, downloader=source, sleep=waits.append, daily_budget=4)
    assert resumed["requested"] == 2 and resumed["daily_provider_calls"] == 4
    assert [call[0] for call in calls] == ["SPY", "AAA", "BBB", "BRK.B"]
    assert resumed["complete"]
    assert all(wait >= 1 for wait in waits)


def test_429_pauses_entire_queue_and_honors_retry_after_across_runs(tmp_path, bars):
    save(tmp_path, "SPY", bars)
    calls = []
    download = source_for(bars, calls)
    def limited(ticker, **kwargs):
        if ticker == "BBB":
            calls.append((ticker, kwargs["start"], kwargs["end"], True))
            raise ProviderPause("HTTP 429", retry_after="120")
        return download(ticker, **kwargs)
    first = refresh_market_cache(tmp_path, ["AAA", "BBB", "CCC"], as_of=ASOF, now=NOW,
                                 downloader=limited, sleep=lambda _: None)
    assert [call[0] for call in calls] == ["AAA", "BBB"]
    assert first["results"]["CCC"]["status"] == "paused"
    assert first["next_retry"] == "2026-09-06T12:02:00+00:00"
    paused = refresh_market_cache(tmp_path, ["AAA", "BBB", "CCC"], as_of=ASOF,
                                  now="2026-09-06T12:00:30Z", downloader=download, sleep=lambda _: None)
    assert paused["requested"] == 0
    resumed = refresh_market_cache(tmp_path, ["AAA", "BBB", "CCC"], as_of=ASOF,
                                   now="2026-09-06T12:02:01Z", downloader=download, sleep=lambda _: None)
    assert resumed["requested"] == 2 and resumed["complete"]
    assert [call[0] for call in calls] == ["AAA", "BBB", "BBB", "CCC"]


def test_five_session_overlap_detects_adjusted_scale_and_archives_before_full_replacement(tmp_path, bars):
    save(tmp_path, "SPY", bars)
    path = save(tmp_path, "AAA", bars.iloc[:-1])
    original = path.read_bytes()
    revised = bars.copy()
    revised[["open", "high", "low", "close"]] *= 0.5
    calls = []
    result = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now=NOW,
                                  downloader=source_for(revised, calls), sleep=lambda _: None)
    assert len(calls) == 2
    assert calls[0][1] == str(bars.iloc[-6].date.date())
    assert calls[1][1] == "2003-10-01"
    assert result["complete"] and result["results"]["AAA"]["history_reloaded"]
    written = pd.read_parquet(path)
    np.testing.assert_allclose(written.close, revised.close)
    archive = result["results"]["AAA"]["archive"]
    assert archive["sha256"] == sha256(original).hexdigest()
    assert (tmp_path / archive["path"]).read_bytes() == original


def test_budget_interruption_keeps_old_basis_and_resumes_full_repair_next_day(tmp_path, bars):
    save(tmp_path, "SPY", bars)
    path = save(tmp_path, "AAA", bars.iloc[:-1])
    original = path.read_bytes()
    revised = bars.copy()
    revised[["open", "high", "low", "close"]] *= 0.5
    calls = []
    source = source_for(revised, calls)
    interrupted = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now=NOW,
                                        daily_budget=1, downloader=source, sleep=lambda _: None)
    assert interrupted["requested"] == 1 and not interrupted["complete"]
    assert path.read_bytes() == original
    state = json.loads((tmp_path / "data/market_refresh/state.json").read_text())
    assert state["tickers"]["AAA"]["needs_full_refresh"]
    resumed = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now="2026-09-07T12:00:00Z",
                                   daily_budget=1, downloader=source, sleep=lambda _: None)
    assert resumed["requested"] == 1 and resumed["complete"]
    assert calls[-1][1] == "2003-10-01"
    np.testing.assert_allclose(pd.read_parquet(path).close, revised.close)


def test_empty_response_and_interior_gap_do_not_claim_coverage(tmp_path, bars):
    save(tmp_path, "SPY", bars)
    path = save(tmp_path, "AAA", bars.iloc[:-1])
    original = path.read_bytes()
    empty = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now=NOW,
                                 downloader=lambda *args, **kwargs: pd.DataFrame(), sleep=lambda _: None)
    assert not empty["complete"] and empty["missing"] == ["AAA"]
    assert "EMPTY_RESPONSE" in empty["results"]["AAA"]["error"]
    assert path.read_bytes() == original
    save(tmp_path, "AAA", bars.drop(bars.index[-3]))
    gap = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now="2026-09-06T12:06:00Z",
                               downloader=lambda *args, **kwargs: bars.iloc[-1:].copy(), sleep=lambda _: None)
    assert not gap["complete"] and gap["results"]["AAA"]["gaps"]
    calls = []
    filled = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now="2026-09-06T12:12:00Z",
                                  downloader=source_for(bars, calls), sleep=lambda _: None)
    assert filled["complete"] and filled["eligible_data_ready"] == ["AAA"]
    assert not list((tmp_path / "data/raw/prices").glob("*.coverage*"))


def test_default_source_requests_raising_single_ticker_history(monkeypatch, bars):
    import yfinance as yf
    seen = {}
    class Ticker:
        def __init__(self, symbol, *, session):
            seen["symbol"] = symbol
        def history(self, **kwargs):
            seen.update(kwargs)
            return bars
    monkeypatch.setattr(yf, "Ticker", Ticker)
    source = YahooHistorySource()
    assert source("BRK.B", start="2026-08-01", end="2026-09-05", auto_adjust=True) is bars
    assert seen["symbol"] == "BRK-B"
    assert seen["raise_errors"] and seen["auto_adjust"] and seen["actions"] is False
