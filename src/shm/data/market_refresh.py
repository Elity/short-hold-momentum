"""Serial, resumable current-market cache refresh, separate from legacy V04.

The budget counts provider ``history`` calls, including full-history repairs.
Yahoo's internal cookie/metadata HTTP calls are not claimed as one request each.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from typing import Callable, Iterable

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from shm.data.prices import ELIGIBILITY_COLUMNS, normalize_price_frame


class ProviderPause(RuntimeError):
    def __init__(self, message: str, *, retry_after: str | float | None = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.status_code = 429


class YahooHistorySource:
    """Fetch raw prices/actions once and preserve Yahoo Retry-After headers."""

    def __init__(self) -> None:
        self.session = None

    def __call__(self, ticker: str, *, start: str, end: str, auto_adjust: bool) -> pd.DataFrame:
        import yfinance as yf
        from curl_cffi.requests import Session
        from yfinance.exceptions import YFRateLimitError

        if self.session is None:
            class RateAwareSession(Session):
                pause: ProviderPause | None = None

                def request(self, *args, **kwargs):
                    if self.pause is not None:
                        raise YFRateLimitError()
                    response = super().request(*args, **kwargs)
                    retry = response.headers.get("Retry-After")
                    if response.status_code == 429 or retry is not None:
                        self.pause = ProviderPause(
                            f"Yahoo HTTP {response.status_code} requested global pause", retry_after=retry,
                        )
                        raise YFRateLimitError()
                    return response

            self.session = RateAwareSession(impersonate="chrome")
        self.session.pause = None
        try:
            result = yf.Ticker(ticker.replace(".", "-"), session=self.session).history(
                start=start, end=end, interval="1d", auto_adjust=False,
                actions=True, raise_errors=True, timeout=15,
            )
        except Exception as error:
            if self.session.pause is not None:
                raise self.session.pause from error
            raise
        if self.session.pause is not None:
            raise self.session.pause
        if result.empty:
            return result
        required = {"Open", "High", "Low", "Close", "Volume", "Adj Close", "Stock Splits", "Dividends"}
        missing = sorted(required - set(result.columns))
        if missing:
            raise ValueError(f"YAHOO_MISSING_FIELDS: {', '.join(missing)}")
        result = result.sort_index().copy()
        close = pd.to_numeric(result["Close"], errors="coerce")
        adjustment = pd.to_numeric(result["Adj Close"], errors="coerce") / close
        actions = result[["Stock Splits", "Dividends"]].apply(pd.to_numeric, errors="coerce")
        if not np.isfinite(actions).all().all() or actions["Stock Splits"].lt(0).any():
            raise ValueError("YAHOO_INVALID_ACTIONS: split/dividend history is unknown")
        if not np.isfinite(adjustment).all() or adjustment.le(0).any():
            raise ValueError("YAHOO_INVALID_ADJUSTMENT: Adj Close / Close must be finite and positive")
        # Yahoo Close and Volume are split-adjusted. Undo only subsequent
        # splits for the nominal price; the split-date quote is already post-split.
        split_factors = actions["Stock Splits"].replace(0, 1.0)
        future_splits = split_factors.shift(-1, fill_value=1.0).iloc[::-1].cumprod().iloc[::-1]
        result["as_traded_close"] = close * future_splits
        result["dollar_volume"] = close * pd.to_numeric(result["Volume"], errors="coerce")
        # Keep the existing total-return OHLC contract independently of the
        # nominal-price and unadjusted-dollar-volume eligibility fields.
        for column in ("Open", "High", "Low", "Close"):
            result[column] = pd.to_numeric(result[column], errors="coerce") * adjustment
        return result


def _utc(now: object | None = None) -> pd.Timestamp:
    value = pd.Timestamp(now if now is not None else datetime.now(UTC))
    return value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC")


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def _lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _calendar(as_of: pd.Timestamp):
    return xcals.get_calendar("XNYS", start=as_of - pd.Timedelta(days=800),
                             end=as_of + pd.Timedelta(days=15))


def _validated_date(as_of: object, now: object | None) -> tuple[pd.Timestamp, pd.DatetimeIndex]:
    date = pd.Timestamp(as_of).tz_localize(None).normalize()
    calendar = _calendar(date)
    stamp = _utc(now)
    if date not in calendar.sessions or calendar.session_close(date) > stamp:
        raise ValueError("market refresh requires a completed XNYS session")
    if stamp - pd.Timestamp(calendar.session_close(date)) < pd.Timedelta(days=14):
        completed = [d for d in calendar.sessions if calendar.session_close(d) <= stamp]
        if date != completed[-1]:
            raise ValueError("market refresh requires the latest completed session")
    else:
        raise ValueError("historical dates cannot be refreshed as current-market observations")
    return date, calendar.sessions[calendar.sessions <= date][-260:]


def _load(path: Path, ticker: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return normalize_price_frame(pd.read_parquet(path), ticker=ticker)


def _valid_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    price = frame[["open", "high", "low", "close"]]
    valid = np.isfinite(price).all(axis=1) & price.gt(0).all(axis=1)
    valid &= np.isfinite(frame["volume"]) & frame["volume"].ge(0) & frame["high"].ge(frame["low"])
    return frame.loc[valid].drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def _cache_status(frame: pd.DataFrame, as_of: pd.Timestamp, window: pd.DatetimeIndex) -> dict:
    valid = _valid_rows(frame.loc[frame["date"] <= as_of]) if not frame.empty else frame
    eligibility = _eligibility_status(valid)
    if valid.empty:
        return {"fresh": False, "latest": None, "gaps": [], "history_ready": False, "quality_warnings": [],
                **eligibility}
    dates = pd.DatetimeIndex(valid["date"])
    # Listing-before-first-observation is not asserted. Short histories stay
    # explicitly ineligible for the 260-session strategy, even with a fresh tail.
    expected = window[window >= dates.min()]
    gaps = expected[~expected.isin(dates)]
    tail = valid.loc[valid["date"] >= window[0], ["date", "close"]].set_index("date").reindex(expected)
    jumps = tail["close"].pct_change(fill_method=None).abs().gt(0.5)
    warnings = [f"LARGE_PRICE_JUMP:{date.date()}" for date in tail.index[jumps]]
    return {"fresh": bool(as_of in dates and not len(gaps)), "latest": str(dates.max().date()),
            "gaps": [str(date.date()) for date in gaps],
            "history_ready": bool(window.isin(dates).all()), "quality_warnings": warnings, **eligibility}


def _eligibility_status(frame: pd.DataFrame) -> dict:
    known_rows = 0
    if all(column in frame for column in ELIGIBILITY_COLUMNS):
        known = np.isfinite(frame[ELIGIBILITY_COLUMNS]).all(axis=1)
        known &= frame["as_traded_close"].gt(0) & frame["dollar_volume"].ge(0)
        known_rows = int(known.sum())
    return {"eligibility_rows": known_rows, "eligibility_expected_rows": len(frame),
            "eligibility_fields_ready": bool(len(frame) and known_rows == len(frame))}


def _pause_details(error: Exception, now: pd.Timestamp, strike: int) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry = getattr(error, "retry_after", None) or headers.get("Retry-After")
    status = getattr(error, "status_code", None) or getattr(response, "status_code", None)
    rate_limited = status == 429 or error.__class__.__name__ == "YFRateLimitError" or bool(
        re.search(r"\b429\b|too many requests", str(error), re.IGNORECASE)
    )
    if not rate_limited and retry is None:
        return None
    delay = min(3600.0, 60.0 * (2 ** min(strike, 6)))
    if retry is not None:
        try:
            provider_delay = float(retry)
        except (TypeError, ValueError):
            try:
                provider_delay = (_utc(parsedate_to_datetime(str(retry))) - now).total_seconds()
            except (TypeError, ValueError, OverflowError):
                provider_delay = 0.0
        delay = max(delay, provider_delay)
    return delay


def _replace_cache(root: Path, ticker: str, frame: pd.DataFrame, as_of: str, reason: str) -> dict | None:
    path = root / "data/raw/prices" / f"{ticker}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = None
    if path.exists():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        directory = root / "data/snapshots/backups/market-refresh" / as_of
        backup = directory / f"{ticker}-{digest[:16]}.parquet"
        directory.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copyfile(path, backup)
        archive = {"ticker": ticker, "as_of": as_of, "sha256": digest,
                   "reason": reason, "path": backup.relative_to(root).as_posix()}
        with (directory.parent / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(archive, sort_keys=True) + "\n")
    temporary = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)
    return archive


def refresh_market_cache(
    repo_root: Path | str,
    universe: Iterable[str],
    *,
    as_of: object,
    held_tickers: Iterable[str] = (),
    listed_expected: int | None = None,
    daily_budget: int = 600,
    min_interval_seconds: float = 1.0,
    history_start: str = "2003-10-01",
    require_point_in_time_eligibility: bool = False,
    downloader: Callable | None = None,
    now: object | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Refresh a fixed as-of queue; rate limits return a resumable global pause."""
    if daily_budget < 1 or min_interval_seconds < 1.0:
        raise ValueError("daily budget must be positive and source interval at least one second")
    root = Path(repo_root)
    as_of, window = _validated_date(as_of, now)
    date_text = str(as_of.date())
    active = sorted({str(ticker).strip().upper() for ticker in universe})
    critical = list(dict.fromkeys(["SPY", *sorted({str(t).strip().upper() for t in held_tickers})]))
    queue = list(dict.fromkeys([*critical, *active]))
    if any(not ticker or "/" in ticker or "\\" in ticker for ticker in queue):
        raise ValueError("invalid market ticker")
    directory = root / "data/market_refresh"
    state_path = directory / "state.json"
    source = downloader or YahooHistorySource()
    with _lock(directory):
        state = json.loads(state_path.read_text()) if state_path.exists() else {"budgets": {}, "tickers": {}}
        budget_day = str(_utc(now).date())
        budget_used = int(state["budgets"].get(budget_day, 0))
        calls = 0
        results = {}

        def checkpoint():
            state["budgets"][budget_day] = budget_used
            _save(state_path, state)

        def request(ticker: str, start: pd.Timestamp):
            nonlocal calls, budget_used
            if budget_used >= daily_budget:
                raise RuntimeError("REQUEST_BUDGET_EXHAUSTED")
            pause = state.get("next_retry")
            if pause and _utc(pause) > _utc(now):
                raise RuntimeError("GLOBAL_SOURCE_PAUSED")
            previous = state.get("last_request_at")
            if previous:
                wait = min_interval_seconds - (_utc(now) - _utc(previous)).total_seconds()
                if wait > 0:
                    sleep(wait)
            calls += 1
            budget_used += 1
            state["last_request_at"] = _utc(now).isoformat()
            checkpoint()  # Count even a process interruption during the provider call.
            raw = source(ticker, start=str(start.date()),
                         end=str((as_of + pd.Timedelta(days=1)).date()), auto_adjust=True)
            if raw is None or raw.empty:
                raise ValueError("EMPTY_RESPONSE: no coverage advanced")
            normalized = normalize_price_frame(raw, ticker=ticker, downloaded_at=_utc(now))
            normalized = _valid_rows(normalized)
            normalized = normalized.loc[(normalized["date"] >= start) & (normalized["date"] <= as_of)]
            if normalized.empty:
                raise ValueError("EMPTY_OR_INVALID_RESPONSE: no coverage advanced")
            if require_point_in_time_eligibility and not _eligibility_status(normalized)["eligibility_fields_ready"]:
                raise ValueError("MISSING_ELIGIBILITY_FIELDS: as_traded_close/dollar_volume require complete coverage")
            state["rate_limit_strikes"] = 0
            state["next_retry"] = None
            return normalized

        for ticker in queue:
            path = root / "data/raw/prices" / f"{ticker}.parquet"
            prior = state["tickers"].get(ticker, {})
            try:
                cached = _load(path, ticker)
                cached = _valid_rows(cached.loc[cached["date"] <= as_of].copy())
            except Exception as error:
                # A corrupt cache is repairable, but never reported as fresh.
                cached = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
                prior = {**prior, "cache_error": str(error)}
            cache_status = _cache_status(cached, as_of, window)
            full_repair = bool(prior.get("needs_full_refresh"))
            repair_reason = prior.get("refresh_reason", "adjusted_history_repair")
            if require_point_in_time_eligibility and not cached.empty and not cache_status["eligibility_fields_ready"]:
                full_repair = True
                repair_reason = "point_in_time_eligibility_upgrade"
                prior = {**prior, "date": date_text, "needs_full_refresh": True,
                         "refresh_reason": repair_reason}
                state["tickers"][ticker] = prior
            result = {"date": date_text, "ticker": ticker, **cache_status, "requested": 0,
                      "status": "cache_hit" if cache_status["fresh"] and not full_repair else "pending"}
            before_calls = calls
            if cache_status["fresh"] and not full_repair:
                results[ticker] = result
                continue
            global_pause = state.get("next_retry")
            ticker_pause = prior.get("next_retry") if prior.get("date") == date_text else None
            if (global_pause and _utc(global_pause) > _utc(now)) or (ticker_pause and _utc(ticker_pause) > _utc(now)):
                result.update(status="paused", fresh=False, next_retry=global_pause or ticker_pause)
                results[ticker] = result
                continue
            if budget_used >= daily_budget:
                result.update(status="budget_exhausted", fresh=False,
                              next_retry=(_utc(now).normalize() + pd.Timedelta(days=1)).isoformat())
                results[ticker] = result
                continue
            try:
                first = pd.Timestamp(history_start)
                if full_repair or cached.empty:
                    fetch_start = first
                else:
                    valid_dates = pd.DatetimeIndex(_valid_rows(cached)["date"])
                    overlap = valid_dates[-5] if len(valid_dates) >= 5 else valid_dates[0]
                    fetch_start = max(first, min(overlap, pd.Timestamp(cache_status["gaps"][0]))
                                      if cache_status["gaps"] else overlap)
                fresh = request(ticker, fetch_start)
                overlap = cached.set_index("date").index.intersection(fresh.set_index("date").index)
                changed = False
                if not full_repair and len(overlap):
                    old = cached.set_index("date").loc[overlap, ["open", "high", "low", "close"]].to_numpy()
                    new = fresh.set_index("date").loc[overlap, ["open", "high", "low", "close"]].to_numpy()
                    changed = not np.allclose(old, new, rtol=1e-5, atol=1e-7, equal_nan=False)
                if changed:
                    full_repair = True
                    repair_reason = "adjusted_history_repair"
                    state["tickers"][ticker] = {"date": date_text, "needs_full_refresh": True,
                                                "status": "adjusted_history_changed", "refresh_reason": repair_reason}
                    checkpoint()
                    fresh = request(ticker, first)
                if full_repair:
                    # Do not mix old and new adjusted units or infer an action factor.
                    if not cached.empty and fresh["date"].min() > max(first, cached["date"].min()):
                        raise ValueError("INCOMPLETE_HISTORY_REPAIR: original history would be lost")
                    combined = fresh
                elif cached.empty:
                    combined = fresh.copy()
                else:
                    combined = pd.concat([cached, fresh], ignore_index=True).drop_duplicates("date", keep="last")
                combined = _valid_rows(combined)
                updated_status = _cache_status(combined, as_of, window)
                if full_repair and not updated_status["fresh"]:
                    raise ValueError("INCOMPLETE_HISTORY_REPAIR: latest session or interior gap missing")
                archive = _replace_cache(root, ticker, combined, date_text,
                                         repair_reason if full_repair else "incremental_overlap")
                result.update(updated_status, status="updated" if updated_status["fresh"] else "incomplete",
                              history_reloaded=full_repair, archive=archive)
                if not updated_status["fresh"]:
                    result["error"] = "INCOMPLETE_RESPONSE: missing current session or interior gap"
                    result["next_retry"] = (_utc(now) + pd.Timedelta(minutes=5)).isoformat()
                state["tickers"][ticker] = {**result, "needs_full_refresh": False}
            except Exception as error:
                delay = _pause_details(error, _utc(now), int(state.get("rate_limit_strikes", 0)))
                if delay is not None:
                    state["rate_limit_strikes"] = int(state.get("rate_limit_strikes", 0)) + 1
                    state["next_retry"] = (_utc(now) + pd.Timedelta(seconds=delay)).isoformat()
                    retry = state["next_retry"]
                    status = "rate_limited"
                elif str(error) == "REQUEST_BUDGET_EXHAUSTED":
                    retry = (_utc(now).normalize() + pd.Timedelta(days=1)).isoformat()
                    status = "budget_exhausted"
                else:
                    retry = (_utc(now) + pd.Timedelta(minutes=5)).isoformat()
                    status = "failed"
                result.update(status=status, fresh=False, error=str(error), next_retry=retry)
                state["tickers"][ticker] = {**result, "needs_full_refresh": full_repair,
                                            "refresh_reason": repair_reason}
            result["requested"] = calls - before_calls
            if ticker in state["tickers"]:
                state["tickers"][ticker]["requested"] = result["requested"]
            results[ticker] = result
            if result["requested"]:
                with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({**result, "observed_at": _utc(now).isoformat()}, sort_keys=True) + "\n")
            checkpoint()
        fresh_names = [ticker for ticker in queue if results[ticker]["fresh"]]
        missing = [ticker for ticker in queue if not results[ticker]["fresh"]]
        retry_times = [result["next_retry"] for result in results.values() if result.get("next_retry")]
        summary = {
            "date": date_text, "listed_expected": listed_expected if listed_expected is not None else len(active),
            "active_now": len(active), "expected": len(queue), "queue": queue,
            "requested": calls, "provider_calls": calls, "daily_provider_calls": budget_used,
            "daily_budget": daily_budget, "fresh": len(fresh_names),
            "require_point_in_time_eligibility": require_point_in_time_eligibility,
            "eligibility_fields_ready": sum(results[ticker]["eligibility_fields_ready"] for ticker in queue),
            "universe_eligibility_fields_ready": sum(results[ticker]["eligibility_fields_ready"] for ticker in active),
            "eligibility_fields_missing": [ticker for ticker in queue if not results[ticker]["eligibility_fields_ready"]],
            "eligibility_rows": sum(results[ticker]["eligibility_rows"] for ticker in queue),
            "eligibility_expected_rows": sum(results[ticker]["eligibility_expected_rows"] for ticker in queue),
            "universe_fresh": sum(ticker in fresh_names for ticker in active),
            "fresh_tickers": fresh_names, "missing": missing, "complete": not missing,
            "critical_complete": all(ticker in fresh_names for ticker in critical),
            "eligible_data_ready": [ticker for ticker in active if results[ticker]["fresh"] and results[ticker]["history_ready"]],
            "quality_warnings": {ticker: result["quality_warnings"] for ticker, result in results.items() if result["quality_warnings"]},
            "next_retry": min(retry_times) if retry_times else None,
            "results": results,
        }
        state["last_summary"] = {key: value for key, value in summary.items() if key != "results"}
        checkpoint()
        _save(directory / f"{date_text}.json", summary)
        return summary
