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


@pytest.fixture
def yahoo_bars():
    return pd.DataFrame({
        "Open": [9.0, 10.0, 10.5, 11.0], "High": [11.0, 11.5, 12.0, 12.5],
        "Low": [8.0, 9.0, 10.0, 10.5], "Close": [10.0, 10.5, 11.0, 11.5],
        "Adj Close": [8.0, 8.4, 9.9, 11.5], "Volume": [400, 400, 400, 0],
        "Stock Splits": [0.0, 2.0, 0.0, 4.0], "Dividends": [0.0, 0.0, 1.0, 0.0],
    }, index=pd.date_range("2026-09-01", periods=4, name="Date"))


def test_default_source_requests_raw_history_once_and_separates_price_bases(monkeypatch, yahoo_bars):
    import yfinance as yf
    seen = {"calls": 0}
    class Ticker:
        def __init__(self, symbol, *, session):
            seen["symbol"] = symbol
        def history(self, **kwargs):
            seen.update(kwargs)
            seen["calls"] += 1
            return yahoo_bars
    monkeypatch.setattr(yf, "Ticker", Ticker)
    source = YahooHistorySource()
    result = source("BRK.B", start="2026-08-01", end="2026-09-05", auto_adjust=True)
    assert seen["symbol"] == "BRK-B"
    assert seen["calls"] == 1
    assert seen["raise_errors"] and seen["auto_adjust"] is False and seen["actions"] is True
    np.testing.assert_allclose(result.as_traded_close, [80, 42, 44, 11.5])
    np.testing.assert_allclose(result.dollar_volume, [4000, 4200, 4400, 0])
    for column in ("Open", "High", "Low", "Close"):
        np.testing.assert_allclose(result[column], yahoo_bars[column] * [0.8, 0.8, 0.9, 1.0])
    assert result.Volume.equals(yahoo_bars.Volume)


@pytest.mark.parametrize("missing", ["Adj Close", "Stock Splits", "Dividends"])
def test_default_source_rejects_unknown_adjustment_or_actions(monkeypatch, yahoo_bars, missing):
    import yfinance as yf
    class Ticker:
        def __init__(self, *args, **kwargs):
            pass
        def history(self, **kwargs):
            return yahoo_bars.drop(columns=missing)
    monkeypatch.setattr(yf, "Ticker", Ticker)
    with pytest.raises(ValueError, match="YAHOO_MISSING_FIELDS"):
        YahooHistorySource()("AAA", start="2026-09-01", end="2026-09-05", auto_adjust=True)


def test_strict_eligibility_upgrades_fresh_legacy_history_with_backup_and_budget_resume(tmp_path, bars):
    spy_path = save(tmp_path, "SPY", bars)
    aaa_path = save(tmp_path, "AAA", bars)
    originals = {"SPY": spy_path.read_bytes(), "AAA": aaa_path.read_bytes()}
    enriched = bars.assign(as_traded_close=bars.close * 4, dollar_volume=bars.close * bars.volume)
    calls = []
    source = source_for(enriched, calls)
    first = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now=NOW, downloader=source,
                                 daily_budget=1, sleep=lambda _: None, require_point_in_time_eligibility=True)
    assert calls == [("SPY", "2003-10-01", "2026-09-05", True)]
    assert first["fresh"] == first["eligibility_fields_ready"] == 1
    assert first["eligibility_fields_missing"] == ["AAA"]
    assert first["eligible_data_ready"] == [] and not first["complete"]
    assert aaa_path.read_bytes() == originals["AAA"]
    state = json.loads((tmp_path / "data/market_refresh/state.json").read_text())
    assert state["tickers"]["AAA"]["needs_full_refresh"]
    resumed = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now="2026-09-07T12:00:00Z",
                                   downloader=source, daily_budget=1, sleep=lambda _: None,
                                   require_point_in_time_eligibility=True)
    assert resumed["complete"] and resumed["requested"] == 1
    assert calls[-1] == ("AAA", "2003-10-01", "2026-09-05", True)
    assert resumed["eligibility_fields_ready"] == 2 and resumed["universe_eligibility_fields_ready"] == 1
    assert resumed["eligibility_rows"] == resumed["eligibility_expected_rows"] == 2 * len(bars)
    for ticker, response in (("SPY", first), ("AAA", resumed)):
        row = response["results"][ticker]
        assert row["history_reloaded"]
        assert row["archive"]["reason"] == "point_in_time_eligibility_upgrade"
        assert (tmp_path / row["archive"]["path"]).read_bytes() == originals[ticker]
        written = pd.read_parquet(tmp_path / "data/raw/prices" / f"{ticker}.parquet")
        np.testing.assert_allclose(written.as_traded_close, enriched.as_traded_close)
        np.testing.assert_allclose(written.dollar_volume, enriched.dollar_volume)


def test_strict_eligibility_upgrade_honors_pause_and_rejects_incomplete_provider_fields(tmp_path, bars):
    enriched = bars.assign(as_traded_close=bars.close, dollar_volume=bars.close * bars.volume)
    save(tmp_path, "SPY", enriched)
    path = save(tmp_path, "AAA", bars)
    original = path.read_bytes()
    calls = []
    def limited(ticker, **kwargs):
        calls.append(ticker)
        raise ProviderPause("HTTP 429", retry_after="120")
    first = refresh_market_cache(tmp_path, ["AAA", "BBB"], as_of=ASOF, now=NOW,
                                 downloader=limited, sleep=lambda _: None, require_point_in_time_eligibility=True)
    assert calls == ["AAA"] and first["results"]["BBB"]["status"] == "paused"
    assert first["next_retry"] == "2026-09-06T12:02:00+00:00"
    assert path.read_bytes() == original
    incomplete = enriched.copy()
    incomplete.loc[0, "as_traded_close"] = np.nan
    failed = refresh_market_cache(tmp_path, ["AAA"], as_of=ASOF, now="2026-09-06T12:02:01Z",
                                  downloader=source_for(incomplete, []), sleep=lambda _: None,
                                  require_point_in_time_eligibility=True)
    assert "MISSING_ELIGIBILITY_FIELDS" in failed["results"]["AAA"]["error"]
    assert path.read_bytes() == original and not failed["complete"]


def test_strict_eligibility_zero_dollar_volume_is_known_and_short_history_stays_ineligible(tmp_path, bars):
    enriched = bars.assign(as_traded_close=bars.close, dollar_volume=bars.close * bars.volume)
    enriched.loc[enriched.index[-1], ["volume", "dollar_volume"]] = 0
    save(tmp_path, "SPY", enriched)
    save(tmp_path, "IPO", enriched.iloc[-60:])
    def forbidden(*args, **kwargs):
        raise AssertionError("complete eligibility fields must not request Yahoo")
    result = refresh_market_cache(tmp_path, ["IPO"], as_of=ASOF, now=NOW, downloader=forbidden,
                                  require_point_in_time_eligibility=True)
    assert result["requested"] == 0 and result["complete"]
    assert result["eligibility_fields_ready"] == 2
    assert not result["results"]["IPO"]["history_ready"]
    assert result["eligible_data_ready"] == []
