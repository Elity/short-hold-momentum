"""Automatic DQ-01/02/03/04/06 checks for daily price data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from typing import Any

import exchange_calendars as xcals
import pandas as pd

from .prices import normalize_price_frame


@dataclass(frozen=True)
class DataQualityReport:
    ticker: str
    duplicate_dates_removed: int
    non_session_rows_removed: int
    extreme_return_dates: tuple[str, ...]
    quarantine: bool
    dev_missing_sessions: int
    dev_total_sessions: int
    dev_missing_ratio: float
    exclude_for_missing_history: bool
    zero_volume_days: int
    zero_volume_ratio: float
    zero_volume_flag: bool

    @property
    def eligible(self) -> bool:
        return not self.quarantine and not self.exclude_for_missing_history

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityResult:
    frame: pd.DataFrame
    report: DataQualityReport


@lru_cache(maxsize=4096)
def _sessions(
    start: pd.Timestamp, end: pd.Timestamp, calendar: str
) -> pd.DatetimeIndex:
    if end < start:
        return pd.DatetimeIndex([])
    exchange = xcals.get_calendar(
        calendar,
        start=start - pd.Timedelta(days=10),
        end=end + pd.Timedelta(days=10),
    )
    return exchange.sessions_in_range(start, end).tz_localize(None)


def run_data_quality(
    ticker: str,
    frame: pd.DataFrame,
    *,
    dev_start: date | str,
    dev_end: date | str,
    calendar: str = "XNYS",
) -> QualityResult:
    """Repair DQ-01/02 and report DQ-03/04/06 eligibility flags."""

    clean = normalize_price_frame(frame, ticker=ticker)
    duplicate_count = int(clean.duplicated("date", keep="last").sum())
    clean = clean.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)

    if clean.empty:
        valid_sessions = pd.DatetimeIndex([])
    else:
        valid_sessions = _sessions(clean["date"].min(), clean["date"].max(), calendar)
    session_mask = clean["date"].isin(valid_sessions)
    non_session_count = int((~session_mask).sum())
    clean = clean.loc[session_mask].reset_index(drop=True)

    if clean.empty:
        extreme_dates: tuple[str, ...] = ()
    else:
        observed_sessions = _sessions(clean["date"].min(), clean["date"].max(), calendar)
        closes = clean.set_index("date")["close"].reindex(observed_sessions)
        returns = closes.pct_change(fill_method=None)
        extreme_dates = tuple(
            timestamp.date().isoformat()
            for timestamp in returns.index[returns.abs() > 0.50]
        )

    dev_sessions = _sessions(pd.Timestamp(dev_start), pd.Timestamp(dev_end), calendar)
    present_dev = clean.loc[clean["date"].isin(dev_sessions), "date"].nunique()
    dev_total = len(dev_sessions)
    dev_missing = dev_total - int(present_dev)
    dev_missing_ratio = dev_missing / dev_total if dev_total else 0.0

    zero_volume_days = int(clean["volume"].eq(0).sum())
    zero_volume_ratio = zero_volume_days / len(clean) if len(clean) else 0.0
    report = DataQualityReport(
        ticker=ticker.upper(),
        duplicate_dates_removed=duplicate_count,
        non_session_rows_removed=non_session_count,
        extreme_return_dates=extreme_dates,
        quarantine=len(extreme_dates) > 3,
        dev_missing_sessions=dev_missing,
        dev_total_sessions=dev_total,
        dev_missing_ratio=dev_missing_ratio,
        exclude_for_missing_history=dev_missing_ratio > 0.05,
        zero_volume_days=zero_volume_days,
        zero_volume_ratio=zero_volume_ratio,
        zero_volume_flag=zero_volume_ratio > 0.05,
    )
    return QualityResult(clean, report)
