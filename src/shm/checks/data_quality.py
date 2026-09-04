from __future__ import annotations

from io import BytesIO
from urllib.request import urlopen

import pandas as pd

from shm.checks.core import CheckResult


def annual_close_returns(frame: pd.DataFrame) -> pd.Series:
    indexed = frame.copy()
    if "date" in indexed.columns:
        indexed["date"] = pd.to_datetime(indexed["date"]).dt.tz_localize(None)
        indexed = indexed.set_index("date")
    indexed.index = pd.DatetimeIndex(indexed.index).tz_localize(None)
    closes = indexed["close"].astype(float).sort_index()
    return closes.groupby(closes.index.year).apply(lambda values: values.iloc[-1] / values.iloc[0] - 1.0)


def check_spy_annual_returns(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    years: tuple[int, int, int] = (2008, 2012, 2018),
    tolerance: float = 0.01,
) -> CheckResult:
    first = annual_close_returns(primary)
    second = annual_close_returns(secondary)
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
    return download_stooq_ticker("SPY", start, end, timeout)
