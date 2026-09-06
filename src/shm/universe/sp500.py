"""Dated S&P 500 membership verification from two public sources.

SPY's issuer publishes a dated fund holding snapshot, not a licensed real-time
index feed. Its equity list must agree exactly with Wikipedia's constituent
table. Historical research continues to use the separate immutable PIT source.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import exchange_calendars as xcals
import pandas as pd


# Verified links from the actual issuer product page, 2026-09-06.
SPY_PRODUCT_URL = "https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy"
SPY_HOLDINGS_URL = "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass
class FetchedDocument:
    url: str
    body: bytes
    fetched_at: str


@dataclass
class UniverseRefreshResult:
    status: str
    snapshot: dict | None
    allow_new_risk: bool
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _utc(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value))
    temporary.replace(path)


def _immutable(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError(f"immutable source conflict: {path.name}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def _fetch(url: str) -> FetchedDocument:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 SHM dated constituent verification",
                                    "Accept": "*/*"})
    with urlopen(request, timeout=30) as response:
        body = response.read(5_000_001)
        if len(body) > 5_000_000:
            raise ValueError("unexpectedly large constituent response")
        return FetchedDocument(response.url, body, _utc().isoformat())


def _xlsx_rows(body: bytes) -> list[dict[str, str]]:
    with ZipFile(BytesIO(body)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(item.itertext()) for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", _NS)]
        rows = []
        tree = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        for row in tree.findall(".//m:row", _NS):
            values = {}
            for cell in row.findall("m:c", _NS):
                column = re.sub(r"\d", "", cell.attrib["r"])
                value = cell.find("m:v", _NS)
                text = "" if value is None else (value.text or "")
                if cell.get("t") == "s":
                    text = shared[int(text)]
                elif cell.get("t") == "inlineStr":
                    inline = cell.find("m:is", _NS)
                    text = "".join(inline.itertext()) if inline is not None else ""
                values[column] = text.strip()
            rows.append(values)
        return rows


def parse_spy_holdings(body: bytes) -> dict:
    rows = _xlsx_rows(body)
    metadata = " ".join(" ".join(row.values()) for row in rows[:5])
    if "SPY" not in metadata or "S&P 500" not in metadata:
        raise ValueError("issuer workbook is not identified as SPY / S&P 500")
    match = re.search(r"As of\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", metadata, re.I)
    if not match:
        raise ValueError("issuer source holdings date is missing")
    as_of = datetime.strptime(match.group(1), "%d-%b-%Y").date().isoformat()
    header_index = next((i for i, row in enumerate(rows) if row.get("A") == "Name" and row.get("B") == "Ticker"), None)
    if header_index is None:
        raise ValueError("issuer equity table header missing")
    members, excluded = [], []
    for row in rows[header_index + 1:]:
        name, symbol, identifier = row.get("A", ""), row.get("B", ""), row.get("C", "")
        if not name or not symbol:
            continue
        if name == "US DOLLAR" and symbol == "-" and row.get("H") == "USD":
            excluded.append({"symbol": symbol, "name": name, "identifier": identifier, "reason": "fund_cash_not_index_equity"})
            continue
        if name.startswith("CONTRA ") and "CVR" in identifier and symbol[0].isdigit():
            excluded.append({"symbol": symbol, "name": name, "identifier": identifier, "reason": "contingent_value_right_not_index_equity"})
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?", symbol):
            raise ValueError(f"unrecognized issuer holding symbol: {symbol}")
        if row.get("H") != "USD" or not re.fullmatch(r"[A-Z0-9]{9}", identifier):
            raise ValueError(f"unverified currency/security identifier: {symbol}")
        members.append({"symbol": symbol, "issuer_name": name, "cusip": identifier,
                        "sedol": row.get("D", ""), "currency": "USD"})
    if len({item["symbol"] for item in members}) != len(members):
        raise ValueError("duplicate issuer symbols")
    if len({item["cusip"] for item in members}) != len(members):
        raise ValueError("duplicate issuer security identifiers")
    return {"as_of": as_of, "members": members, "excluded_non_index_assets": excluded}


class _ConstituentTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.depth = 0
        self.cell: list[str] | None = None
        self.row: list[str] = []
        self.rows: list[list[str]] = []
        self.superscript = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "table" and dict(attrs).get("id") == "constituents":
            self.active = True
        if not self.active:
            return
        if tag == "table":
            self.depth += 1
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "sup":
            self.superscript += 1

    def handle_data(self, data: str) -> None:
        if self.active and self.cell is not None and not self.superscript:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
        elif tag == "sup":
            self.superscript = max(0, self.superscript - 1)
        elif tag == "table":
            self.depth -= 1
            self.active = self.depth > 0


def parse_wikipedia_constituents(body: bytes) -> list[dict]:
    parser = _ConstituentTable()
    parser.feed(body.decode("utf-8"))
    if not parser.rows or not {"Symbol", "Security", "CIK", "GICS Sector", "GICS Sub-Industry"}.issubset(parser.rows[0]):
        raise ValueError("Wikipedia constituent table/identity columns missing")
    header, members = parser.rows[0], []
    for values in parser.rows[1:]:
        if len(values) != len(header):
            raise ValueError("incomplete Wikipedia constituent row")
        row = dict(zip(header, values))
        if not row["CIK"].isdigit() or not row["GICS Sector"]:
            raise ValueError(f"Wikipedia identity/sector missing: {row['Symbol']}")
        members.append({"symbol": row["Symbol"], "name": row["Security"], "cik": row["CIK"].zfill(10),
                        "sector": row["GICS Sector"], "sub_industry": row["GICS Sub-Industry"]})
    if len({item["symbol"] for item in members}) != len(members):
        raise ValueError("duplicate Wikipedia symbols")
    return members


def _completed_at(value: datetime) -> pd.Timestamp:
    value = _utc(value)
    day = pd.Timestamp(value.date())
    calendar = xcals.get_calendar("XNYS", start=day - pd.Timedelta(days=20), end=day + pd.Timedelta(days=14))
    dates = calendar.sessions_in_range(day - pd.Timedelta(days=15), day)
    complete = [date for date in dates if calendar.session_close(date) <= pd.Timestamp(value)]
    if not complete:
        raise ValueError("no completed session for verification timestamp")
    return complete[-1].tz_localize(None)


def _age_sessions(first: str, completed_session: object) -> int | None:
    start, end = pd.Timestamp(first), pd.Timestamp(completed_session).tz_localize(None).normalize()
    if start > end:
        return None
    calendar = xcals.get_calendar("XNYS", start=start - pd.Timedelta(days=7), end=end + pd.Timedelta(days=14))
    if not calendar.is_session(start):
        return None
    return len(calendar.sessions_in_range(start, end)) - 1


def sp500_freshness(snapshot: dict | None, completed_session: object, now: datetime | None = None) -> dict:
    if snapshot is None:
        return {"fresh": False, "source_age_sessions": None, "verification_age_sessions": None, "reason": "no_verified_snapshot"}
    current = _utc(now)
    source_age = _age_sessions(snapshot["source_as_of"], completed_session)
    verified = _utc(snapshot["verified_at"])
    verified_age = _age_sessions(str(_completed_at(verified).date()), completed_session)
    fresh = source_age is not None and source_age <= 1 and verified_age is not None and verified_age <= 1 and verified <= current
    return {"fresh": bool(fresh), "source_age_sessions": source_age, "verification_age_sessions": verified_age,
            "reason": "verified_daily_snapshot" if fresh else "source_or_verification_older_than_one_completed_session"}


def load_sp500_snapshot(repo_root: Path | str, as_of: str | None = None) -> dict | None:
    """Read the last-good current snapshot; never use this as a historical PIT feed."""
    folder = Path(repo_root) / "data/reference/sp500"
    if as_of is None:
        path = folder / "current.json"
        return json.loads(path.read_text()) if path.exists() else None
    candidates = [json.loads(path.read_text()) for path in (folder / "snapshots").glob("*.json")]
    candidates = [item for item in candidates if item["source_as_of"] <= as_of]
    return max(candidates, key=lambda item: (item["source_as_of"], item["verified_at"]), default=None)


def sp500_status(repo_root: Path | str, completed_session: object, now: datetime | None = None) -> dict:
    snapshot = load_sp500_snapshot(repo_root)
    path = Path(repo_root) / "data/reference/sp500/checks.json"
    check = json.loads(path.read_text()) if path.exists() else {}
    freshness = sp500_freshness(snapshot, completed_session, now)
    verified = check.get("status") == "verified" and snapshot is not None and check.get("snapshot_id") == snapshot["snapshot_id"]
    result = {"status": check.get("status", "unavailable"), "allow_new_risk": bool(verified and freshness["fresh"]),
              "error": check.get("error"), "source_urls": [], "added": check.get("added", []),
              "removed": check.get("removed", []), **freshness}
    if snapshot:
        result.update({name: snapshot[name] for name in ("snapshot_id", "source_as_of", "as_of", "fetched_at", "verified_at",
                                                       "verified_for_session", "security_count", "company_count")})
        result["source_urls"] = [source["url"] for source in snapshot["sources"]]
    else:
        result.update(source_as_of=None, as_of=None, fetched_at=None, verified_at=None, verified_for_session=None,
                      security_count=0, company_count=0)
    return result


def refresh_sp500_universe(
    repo_root: Path | str, *, as_of: object, now: datetime | None = None,
    fetcher: Callable[[str], bytes | FetchedDocument] | None = None,
) -> UniverseRefreshResult:
    """Two fetches per daily verification; a successful same-day repeat is offline.

    Failed, mismatched, stale or unexpectedly changed observations are recorded,
    but never replace current.json or authorize an additional equity purchase.
    """
    root, stamp = Path(repo_root), _utc(now)
    folder = root / "data/reference/sp500"
    previous = load_sp500_snapshot(root)
    check_path = folder / "checks.json"
    old_check = json.loads(check_path.read_text()) if check_path.exists() else {}
    if old_check.get("status") == "verified" and old_check.get("checked_at", "")[:10] == stamp.date().isoformat():
        status = sp500_status(root, as_of, stamp)
        if status["allow_new_risk"]:
            return UniverseRefreshResult("verified", previous, True, status["added"], status["removed"])
    documents = []
    fetch = fetcher or _fetch
    try:
        for url, kind in ((SPY_HOLDINGS_URL, "issuer_spy_holdings"), (WIKIPEDIA_URL, "wikipedia_constituents")):
            fetched = fetch(url)
            document = fetched if isinstance(fetched, FetchedDocument) else FetchedDocument(url, fetched, stamp.isoformat())
            digest = _hash(document.body)
            extension = ".xlsx" if kind == "issuer_spy_holdings" else ".html"
            relative = f"data/reference/sp500/sources/{digest}{extension}"
            _immutable(root / relative, document.body)
            documents.append((document, {"kind": kind, "url": document.url, "requested_url": url,
                                         "sha256": digest, "fetched_at": document.fetched_at, "path": relative}))
        issuer = parse_spy_holdings(documents[0][0].body)
        wiki = parse_wikipedia_constituents(documents[1][0].body)
        left = {item["symbol"]: item for item in issuer["members"]}
        right = {item["symbol"]: item for item in wiki}
        if set(left) != set(right):
            raise ValueError(f"sources disagree: issuer_only={sorted(set(left) - set(right))}; wikipedia_only={sorted(set(right) - set(left))}")
        if not 490 <= len(left) <= 520 or not 490 <= len({item["cik"] for item in wiki}) <= 510:
            raise ValueError("implausible constituent/company count")
        members = [{**left[symbol], **right[symbol], "yahoo_symbol": symbol.replace(".", "-")}
                   for symbol in sorted(left)]
        before = {item["symbol"]: item for item in previous["members"]} if previous else {}
        added, removed = sorted(set(left) - set(before)), sorted(set(before) - set(left))
        if previous and len(added) + len(removed) > 20:
            raise ValueError(f"unexpected large constituent change: added={added}; removed={removed}")
        changed_identity = [symbol for symbol in set(left) & set(before)
                            if before[symbol]["cik"] != right[symbol]["cik"] or before[symbol]["cusip"] != left[symbol]["cusip"]]
        if changed_identity:
            raise ValueError(f"security identity changed for existing ticker: {sorted(changed_identity)}")
        if previous and issuer["as_of"] < previous["source_as_of"]:
            raise ValueError("issuer source date regressed")
        # Verification happens after both source documents have been parsed.
        stamp = _utc(now)
        snapshot = {
            "schema_version": 1, "universe_id": "SP500", "as_of": issuer["as_of"], "source_as_of": issuer["as_of"],
            "fetched_at": max(source["fetched_at"] for _, source in documents), "verified_at": stamp.isoformat(),
            "verified_for_session": str(pd.Timestamp(as_of).date()), "security_count": len(members),
            "company_count": len({item["cik"] for item in members}), "members": members,
            "sources": [source for _, source in documents], "excluded_non_index_assets": issuer["excluded_non_index_assets"],
            "diff": {"added": added, "removed": removed},
            "claim": "Dated SPY issuer equity holdings agree with Wikipedia; not a real-time licensed index feed.",
        }
        freshness = sp500_freshness(snapshot, as_of, stamp)
        if not freshness["fresh"]:
            raise ValueError(f"stale source observation: source_as_of={issuer['as_of']}; {freshness['reason']}")
        snapshot_id = issuer["as_of"] + "-" + _hash(_canonical(snapshot))[:16]
        snapshot["snapshot_id"] = snapshot_id
        _immutable(folder / "snapshots" / f"{snapshot_id}.json", _canonical(snapshot))
        _write_json(folder / "current.json", snapshot)
        _write_json(check_path, {"status": "verified", "checked_at": stamp.isoformat(), "snapshot_id": snapshot_id,
                                 "source_as_of": issuer["as_of"], "verified_for_session": snapshot["verified_for_session"],
                                 "added": added, "removed": removed, "error": None})
        return UniverseRefreshResult("verified", snapshot, True, added, removed)
    except Exception as exc:
        error = str(exc)
        status = "stale" if "stale source" in error else "conflict" if isinstance(exc, ValueError) else "failed"
        _write_json(check_path, {"status": status, "checked_at": stamp.isoformat(), "error": error,
                                 "snapshot_id": previous["snapshot_id"] if previous else None,
                                 "source_urls": [source["url"] for _, source in documents], "added": [], "removed": []})
        return UniverseRefreshResult(status, previous, False, error=error)
