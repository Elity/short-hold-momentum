from __future__ import annotations

from datetime import date
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd


def normalize_session(value: date | pd.Timestamp | str) -> pd.Timestamp:
    """Return a timezone-naive, normalized session label."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


@lru_cache(maxsize=4096)
def trailing_xnys_sessions(
    signal_date: date | pd.Timestamp | str,
    count: int,
) -> pd.DatetimeIndex:
    """Return ``count`` XNYS sessions ending at ``signal_date`` (inclusive)."""
    if count < 1:
        raise ValueError("count must be positive")

    end = normalize_session(signal_date)
    start_hint = end - pd.Timedelta(days=int(max(370, count * 3)))
    calendar = xcals.get_calendar("XNYS", start=start_hint, end=end)
    if not calendar.is_session(end):
        raise ValueError(f"{end.date()} is not an XNYS session")
    return calendar.sessions_window(end, -count)


@lru_cache(maxsize=128)
def xnys_rebalance_dates(
    dev_start: date | pd.Timestamp | str,
    dev_end: date | pd.Timestamp | str,
    *,
    warmup_trading_days: int,
    every_trading_days: int,
) -> pd.DatetimeIndex:
    """Build the deterministic XNYS rebalance schedule from the spec."""
    if warmup_trading_days < 1:
        raise ValueError("warmup_trading_days must be positive")
    if every_trading_days < 1:
        raise ValueError("every_trading_days must be positive")

    start = normalize_session(dev_start)
    end = normalize_session(dev_end)
    if end < start:
        raise ValueError("dev_end must be on or after dev_start")

    history_start = start - pd.Timedelta(days=int(max(370, warmup_trading_days * 3)))
    calendar = xcals.get_calendar("XNYS", start=history_start, end=end)
    sessions = calendar.sessions
    first_position = int(sessions.searchsorted(start, side="left"))
    first_position = max(first_position, warmup_trading_days)
    return sessions[first_position::every_trading_days]
