from __future__ import annotations

from io import BytesIO
from urllib.request import Request, urlopen

import pandas as pd

from shm.checks.core import CheckResult


STOOQ_SPY_MIRROR_URL = (
    "https://raw.githubusercontent.com/tousheng4/multiagent-market/"
    "wsr/data/raw/SPY_daily.csv"
)


def annual_close_returns(frame: pd.DataFrame) -> pd.Series:
    indexed = frame.copy()
    if "date" in indexed.columns:
        indexed["date"] = pd.to_datetime(indexed["date"]).dt.tz_localize(None)
        indexed = indexed.set_index("date")
    indexed.index = pd.DatetimeIndex(indexed.index).tz_localize(None)
    closes = indexed["close"].astype(float).sort_index()
    return closes.groupby(closes.index.year).apply(lambda values: values.iloc[-1] / values.iloc[0] - 1.0)


def _complete_calendar_years(frame: pd.DataFrame) -> set[int]:
    indexed = frame.copy()
    if "date" in indexed.columns:
        indexed["date"] = pd.to_datetime(indexed["date"]).dt.tz_localize(None)
        indexed = indexed.set_index("date")
    indexed.index = pd.DatetimeIndex(indexed.index).tz_localize(None)
    return {
        int(year)
        for year, values in indexed.groupby(indexed.index.year)
        if values.index.min().month == 1 and values.index.max().month == 12
    }


def check_spy_annual_returns(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    years: tuple[int, ...] | None = None,
    tolerance: float = 0.01,
) -> CheckResult:
    first = annual_close_returns(primary)
    second = annual_close_returns(secondary)
    if years is None:
        common = sorted(_complete_calendar_years(primary) & _complete_calendar_years(secondary))
        if len(common) < 3:
            return CheckResult("INCONCLUSIVE", "DQ-05 fewer than three complete comparison years")
        years = tuple(common[-3:])
    missing = [year for year in years if year not in first.index or year not in second.index]
    if missing:
        return CheckResult("INCONCLUSIVE", f"DQ-05 missing comparison years: {missing}")
    differences = {year: abs(float(first[year] - second[year])) for year in years}
    worst = max(differences.values())
    detail = ", ".join(f"{year}={difference:.2%}" for year, difference in differences.items())
    if worst > tolerance:
        return CheckResult("INCONCLUSIVE", f"DQ-05 annual-return differences exceed 1pp: {detail}")
    return CheckResult("PASS", f"DQ-05 annual-return differences: {detail}")


def download_stooq_ticker(
    ticker: str, start: str, end: str, timeout: float = 30.0
) -> pd.DataFrame:
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")
    symbol = ticker.lower().replace(".", "-")
    url = f"https://stooq.com/q/d/l/?s={symbol}.us&i=d&d1={start_compact}&d2={end_compact}"
    with urlopen(url, timeout=timeout) as response:
        payload = response.read()
    frame = pd.read_csv(BytesIO(payload))
    frame.columns = [str(column).lower() for column in frame.columns]
    if not {"date", "close"}.issubset(frame.columns):
        raise ValueError("Stooq SPY response is missing date/close")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").reset_index(drop=True)


def download_stooq_spy(start: str, end: str, timeout: float = 30.0) -> pd.DataFrame:
    request = Request(STOOQ_SPY_MIRROR_URL, headers={"User-Agent": "short-hold-momentum/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
    frame = pd.read_csv(BytesIO(payload))
    columns = {str(column).lower(): column for column in frame.columns}
    date_column = columns.get("data") or columns.get("date")
    close_column = columns.get("zamkniecie") or columns.get("close") or columns.get("adj close")
    if date_column is None or close_column is None:
        raise ValueError("Stooq SPY mirror is missing date/close")
    result = frame[[date_column, close_column]].rename(
        columns={date_column: "date", close_column: "close"}
    )
    result["date"] = pd.to_datetime(result["date"])
    start_stamp, end_stamp = pd.Timestamp(start), pd.Timestamp(end)
    return (
        result.loc[result["date"].between(start_stamp, end_stamp, inclusive="both")]
        .sort_values("date")
        .reset_index(drop=True)
    )
