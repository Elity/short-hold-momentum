"""Read-only, hash-pinned repairs for historical membership and price inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from shm.pipeline import load_pit_history


MANIFEST_PATH = "data/reference/v04-remediation/manifest.json"
MEMBERSHIP_PATH = "data/reference/sp500_history.csv"


def _manifest(root: Path) -> tuple[dict, dict]:
    path = root / MANIFEST_PATH
    if not path.exists():
        return {}, {}
    content = path.read_bytes()
    return json.loads(content), {MANIFEST_PATH: hashlib.sha256(content).hexdigest()}


def _checked_hash(path: Path, expected: str | None = None) -> str:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and actual != expected:
        raise ValueError(f"{path.name}: SHA256 mismatch")
    return actual


def load_membership(root: Path | str) -> tuple[pd.DataFrame, dict, dict]:
    """Append dated membership evidence and normalize documented ticker aliases."""
    root = Path(root)
    manifest, hashes = _manifest(root)
    membership = manifest.get("membership", {})
    base = root / MEMBERSHIP_PATH
    expected = membership["base_sha256"] if manifest else None
    hashes[MEMBERSHIP_PATH] = _checked_hash(base, expected)
    history = load_pit_history(base)
    extension_dates = []
    if membership.get("extension_path"):
        path = root / membership["extension_path"]
        hashes[str(path.relative_to(root))] = _checked_hash(path, membership["extension_sha256"])
        extension = pd.read_csv(path)
        if set(extension.columns) != {"date", "tickers"}:
            raise ValueError("membership extension requires exactly date,tickers columns")
        extension["date"] = pd.to_datetime(extension["date"]).dt.normalize()
        dates = extension["date"]
        if (dates.isna().any() or not dates.is_monotonic_increasing or dates.duplicated().any()
                or not dates.gt(history["date"].max()).all()):
            raise ValueError("membership extension dates must strictly increase after the base history")
        extension["members"] = extension["tickers"].fillna("").map(
            lambda value: tuple(ticker for ticker in str(value).split(",") if ticker)
        )
        extension_dates = [str(date.date()) for date in dates]
        history = pd.concat([history, extension], ignore_index=True)

    aliases = manifest.get("aliases", {})
    canonical = {old: entry["ticker"] for old, entry in aliases.items()}
    corrections = membership.get("duplicate_member_corrections", [])
    for correction in corrections:
        path = root / correction["evidence_path"]
        hashes[str(path.relative_to(root))] = _checked_hash(path, correction["evidence_sha256"])
        remove, retain = correction["remove"], correction["retain"]
        if remove == retain or canonical.get(remove, remove) != canonical.get(retain, retain):
            raise ValueError("duplicate correction requires documented aliases of the same security")
        mask = history["date"].between(correction["start"], correction["end"])
        if int(mask.sum()) != correction["expected_rows"]:
            raise ValueError("duplicate correction row count mismatch")
        for index in history.index[mask]:
            row = history.at[index, "members"]
            if row.count(remove) != 1 or row.count(retain) != 1:
                raise ValueError("duplicate correction requires both original members exactly once")
            history.at[index, "members"] = tuple(ticker for ticker in row if ticker != remove)
    changed = 0
    members = []
    for row in history.itertuples():
        normalized = tuple(canonical.get(ticker, ticker) for ticker in row.members)
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{row.date.date()}: duplicate members after ticker alias normalization")
        changed += sum(old != new for old, new in zip(row.members, normalized))
        members.append(normalized)
    history["members"] = members
    history["tickers"] = [",".join(row) for row in members]
    unresolved = manifest.get("unresolved", [])
    evidence = {
        "status": "INCONCLUSIVE" if unresolved else "PASS",
        "unresolved": unresolved,
        "alias_count": len(aliases), "alias_member_changes": changed, "aliases": aliases,
        "extension_dates": extension_dates,
        "duplicate_member_corrections": corrections,
    }
    return history, hashes, evidence


def apply_price_repairs(root: Path | str, prices: dict, hashes: dict, missing: list[str],
                        start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict, dict, list[str], dict]:
    """Replace only requested securities; quarantined members remain missing."""
    root = Path(root)
    manifest, manifest_hashes = _manifest(root)
    repaired, repaired_hashes = dict(prices), {**hashes, **manifest_hashes}
    missing_set = set(missing)
    targets = set(prices) | missing_set
    quarantined = {ticker: detail for ticker, detail in manifest.get("quarantined", {}).items()
                   if ticker in targets}
    applied = {}
    for ticker, detail in manifest.get("price_overrides", {}).items():
        if ticker not in targets or ticker in quarantined:
            continue
        path = root / detail["path"]
        repaired_hashes[str(path.relative_to(root))] = _checked_hash(path, detail["sha256"])
        frame = pd.read_parquet(path)
        if "adjusted" not in frame or not frame["adjusted"].eq(True).all():
            raise ValueError(f"{ticker}: adjusted total-return OHLC override is required")
        frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert(None).dt.normalize()
        frame = frame.loc[frame["date"].between(start, end)].sort_values("date")
        frame = frame.drop_duplicates("date", keep="last")
        columns = ["date", "open", "high", "low", "close", "volume"]
        columns += [key for key in ("as_traded_close", "dollar_volume") if key in frame]
        frame = frame[columns].copy()
        if frame.empty:
            repaired.pop(ticker, None)
            missing_set.add(ticker)
        else:
            repaired[ticker] = frame
            missing_set.discard(ticker)
        applied[ticker] = {**detail, "rows": len(frame)}
    for ticker in quarantined:
        repaired.pop(ticker, None)
        missing_set.add(ticker)
    unresolved = manifest.get("unresolved", [])
    evidence = {
        "status": "INCONCLUSIVE" if unresolved else "PASS",
        "unresolved": unresolved,
        "price_override_count": len(applied), "price_overrides": applied,
        "quarantined_count": len(quarantined), "quarantined": quarantined,
    }
    return repaired, repaired_hashes, sorted(missing_set), evidence
