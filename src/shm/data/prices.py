"""Adjusted daily price download and parquet cache access."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd

from shm.experiments import validate_oos_unlock


PRICE_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjusted",
    "source",
    "downloaded_at",
]

DownloadFunction = Callable[..., pd.DataFrame]


class OOSReadLockedError(PermissionError):
    """Raised when backtest code attempts to read locked OOS observations."""


@dataclass(frozen=True)
class PriceUpdateResult:
    ticker: str
    path: Path
    frame: pd.DataFrame
    downloaded_rows: int
    attempts: int
    failed: bool = False
    error: str | None = None

    @property
    def cache_hit(self) -> bool:
        return not self.failed and self.downloaded_rows == 0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_date(value: date | str | pd.Timestamp) -> date:
    return pd.Timestamp(value).date()


def _normalise_dates(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, errors="coerce", utc=True)
    return result.dt.tz_convert(None).dt.normalize()


def _flatten_yfinance_columns(frame: pd.DataFrame, ticker: str | None) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    result = frame.copy()
    ticker_upper = ticker.upper() if ticker else None
    names = [str(name).lower() if name is not None else "" for name in result.columns.names]
    ticker_level = names.index("ticker") if "ticker" in names else result.columns.nlevels - 1
    values = list(dict.fromkeys(result.columns.get_level_values(ticker_level)))
    candidates = {str(value).upper(): value for value in values}
    requested = ticker_upper.replace(".", "-") if ticker_upper else None
    selected = candidates.get(requested) or candidates.get(ticker_upper)
    if selected is None and len(values) == 1:
        selected = values[0]
    if selected is not None:
        result = result.xs(selected, axis=1, level=ticker_level, drop_level=True)
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = result.columns.get_level_values(0)
    return result


def normalize_price_frame(
    frame: pd.DataFrame,
    *,
    ticker: str | None = None,
    downloaded_at: datetime | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Convert a yfinance response or cached frame to the price contract."""

    if frame.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    result = _flatten_yfinance_columns(frame.copy(), ticker)
    if "date" not in {str(column).lower() for column in result.columns}:
        result = result.rename_axis("date").reset_index()

    rename = {
        column: str(column).strip().lower().replace(" ", "_")
        for column in result.columns
    }
    result = result.rename(columns=rename)
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(result.columns))
    if missing:
        raise ValueError(f"price data missing columns: {', '.join(missing)}")

    result["date"] = _normalise_dates(result["date"])
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=list(required)).copy()
    result["volume"] = result["volume"].astype("int64")
    for column in ("open", "high", "low", "close"):
        result[column] = result[column].astype("float64")

    stamp = pd.Timestamp(downloaded_at or _utc_now())
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    if "downloaded_at" in result:
        existing = pd.to_datetime(result["downloaded_at"], errors="coerce", utc=True)
        result["downloaded_at"] = existing.fillna(stamp)
    else:
        result["downloaded_at"] = stamp
    result["adjusted"] = True
    result["source"] = "yfinance"
    return result[PRICE_COLUMNS].sort_values("date", kind="stable").reset_index(drop=True)


def _default_downloader(
    ticker: str, *, start: str, end: str, auto_adjust: bool
) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(
        ticker.replace(".", "-"),
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        actions=False,
        progress=False,
        threads=False,
    )


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _coverage_path(path: Path) -> Path:
    return path.with_suffix(".coverage.json")


def _coverage_contains(path: Path, start: date, end: date) -> bool:
    marker = _coverage_path(path)
    if not marker.exists():
        return False
    payload = json.loads(marker.read_text(encoding="utf-8"))
    return date.fromisoformat(payload["start"]) <= start and date.fromisoformat(payload["end"]) >= end


def _write_coverage(path: Path, start: date, end: date, timestamp: datetime) -> None:
    marker = _coverage_path(path)
    if marker.exists():
        payload = json.loads(marker.read_text(encoding="utf-8"))
        start = min(start, date.fromisoformat(payload["start"]))
        end = max(end, date.fromisoformat(payload["end"]))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"start": start.isoformat(), "end": end.isoformat(), "checked_at": timestamp.isoformat()})
        + "\n",
        encoding="utf-8",
    )


def _append_failure(
    path: Path,
    *,
    ticker: str,
    start: date,
    end: date,
    attempts: int,
    error: Exception,
    timestamp: datetime,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": timestamp.isoformat(),
        "ticker": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "attempts": attempts,
        "error": f"{type(error).__name__}: {error}",
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _load_unrestricted(path: Path, ticker: str | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return normalize_price_frame(pd.read_parquet(path), ticker=ticker)


def _slice_dates(
    frame: pd.DataFrame, start: date | None, end: date | None
) -> pd.DataFrame:
    result = frame
    if start is not None:
        result = result.loc[result["date"] >= pd.Timestamp(start)]
    if end is not None:
        result = result.loc[result["date"] <= pd.Timestamp(end)]
    return result.reset_index(drop=True)


def read_price_cache(
    path: Path | str,
    *,
    ticker: str | None = None,
    start: date | str | None = None,
    end: date | str | None = None,
    mode: Literal["backtest", "paper"] = "backtest",
    oos_start: date | str | None = None,
    unlock_oos: bool = False,
    reason: str | None = None,
    oos_audit_path: Path | str | None = None,
    oos_run_id: str | None = None,
    paper_sessions: int = 260,
) -> pd.DataFrame:
    """Read a cache while keeping OOS rows inaccessible by default.

    An explicit backtest request reaching ``oos_start`` is rejected. A request
    without an end date is safely truncated. Unlocking requires a reason and
    requires a matching persisted experiment-ledger record.
    """

    path = Path(path)
    if mode == "backtest" and oos_start is None:
        raise ValueError("backtest reads require oos_start")
    frame = _load_unrestricted(path, ticker=ticker)
    requested_start = _as_date(start) if start is not None else None
    requested_end = _as_date(end) if end is not None else None
    lock_date = _as_date(oos_start) if oos_start is not None else None

    if mode == "backtest" and lock_date is not None:
        explicit_oos = (
            (requested_start is not None and requested_start >= lock_date)
            or (requested_end is not None and requested_end >= lock_date)
        )
        if explicit_oos and not unlock_oos:
            raise OOSReadLockedError(
                f"backtest OOS data is locked from {lock_date.isoformat()}"
            )
        cached_oos = bool((frame["date"] >= pd.Timestamp(lock_date)).any())
        accesses_oos = explicit_oos or (unlock_oos and requested_end is None and cached_oos)
        if unlock_oos and accesses_oos:
            if not reason or not reason.strip():
                raise ValueError("unlock_oos requires a non-empty reason")
            if oos_audit_path is None or not oos_run_id:
                raise ValueError("unlock_oos requires a persisted audit record")
            validate_oos_unlock(
                oos_audit_path, run_id=oos_run_id, reason=reason.strip()
            )
        if not unlock_oos:
            frame = frame.loc[frame["date"] < pd.Timestamp(lock_date)]

    frame = _slice_dates(frame, requested_start, requested_end)
    if mode == "paper":
        if paper_sessions < 1:
            raise ValueError("paper_sessions must be positive")
        frame = frame.tail(paper_sessions).reset_index(drop=True)
    return frame


def update_price_cache(
    ticker: str,
    cache_dir: Path | str,
    *,
    start: date | str,
    end: date | str | None = None,
    downloader: DownloadFunction | None = None,
    retries: int = 3,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    failures_path: Path | str | None = None,
    now: datetime | None = None,
) -> PriceUpdateResult:
    """Update one ticker from the first uncached date, retrying transient errors."""

    if retries < 1:
        raise ValueError("retries must be at least one")
    ticker = ticker.strip().upper()
    cache_dir = Path(cache_dir)
    path = cache_dir / f"{ticker}.parquet"
    cached = _load_unrestricted(path, ticker=ticker)
    requested_start = _as_date(start)
    requested_end = _as_date(end) if end is not None else (now or _utc_now()).date()
    if _coverage_contains(path, requested_start, requested_end):
        return PriceUpdateResult(ticker, path, cached, 0, 0)
    next_date = requested_start
    if not cached.empty:
        next_date = max(requested_start, cached["date"].max().date() + timedelta(days=1))
    if next_date > requested_end:
        return PriceUpdateResult(ticker, path, cached, 0, 0)

    fetch = downloader or _default_downloader
    stamp = now or _utc_now()
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            downloaded = fetch(
                ticker,
                start=next_date.isoformat(),
                end=(requested_end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
            )
            fresh = normalize_price_frame(
                downloaded, ticker=ticker, downloaded_at=stamp
            )
            fresh = _slice_dates(fresh, next_date, requested_end)
            if cached.empty:
                combined = fresh.copy()
            elif fresh.empty:
                combined = cached.copy()
            else:
                combined = pd.concat([cached, fresh], ignore_index=True)
            if not combined.empty:
                combined = (
                    combined.drop_duplicates("date", keep="last")
                    .sort_values("date", kind="stable")
                    .reset_index(drop=True)
                )
                _write_parquet(combined, path)
            _write_coverage(path, requested_start, requested_end, stamp)
            return PriceUpdateResult(ticker, path, combined, len(fresh), attempt)
        except Exception as error:  # one ticker must not stop a batch
            last_error = error
            if attempt < retries:
                sleep(backoff_seconds * (2 ** (attempt - 1)))

    assert last_error is not None
    failure_file = Path(failures_path) if failures_path else cache_dir.parent / "_failures.jsonl"
    _append_failure(
        failure_file,
        ticker=ticker,
        start=next_date,
        end=requested_end,
        attempts=retries,
        error=last_error,
        timestamp=stamp,
    )
    return PriceUpdateResult(
        ticker, path, cached, 0, retries, failed=True, error=str(last_error)
    )


def update_price_caches(
    tickers: Iterable[str], cache_dir: Path | str, **kwargs: object
) -> dict[str, PriceUpdateResult]:
    """Update a universe independently so a failed ticker does not abort others."""

    return {
        ticker.strip().upper(): update_price_cache(ticker, cache_dir, **kwargs)
        for ticker in tickers
    }
