from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape

import pytest

from shm.universe.sp500 import (
    SPY_HOLDINGS_URL, WIKIPEDIA_URL, load_sp500_snapshot, parse_spy_holdings,
    parse_wikipedia_constituents, refresh_sp500_universe, sp500_freshness, sp500_status,
)


NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
TOMORROW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def source_documents(*, date="03-Sep-2026", names=None, wiki_names=None, changed_cik=None):
    names = names or [f"S{i:03d}" for i in range(500)]
    wiki_names = wiki_names or names
    identity = {name: int(name[1:]) + 1000 for name in set(names) | set(wiki_names)}
    rows = [
        {"A": "Fund Name:", "B": "State Street SPDR S&P 500 ETF Trust"},
        {"A": "Ticker Symbol:", "B": "SPY"}, {"A": "Holdings:", "B": f"As of {date}"}, {},
        dict(zip("ABCDEFGH", ["Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"])),
    ]
    rows.extend({"A": "Company " + name, "B": name, "C": f"{identity[name]:09d}", "D": "1234567", "H": "USD"} for name in names)
    rows += [{"A": "US DOLLAR", "B": "-", "C": "999USDZ92", "H": "USD"},
             {"A": "CONTRA HOLOGIC INCORPO", "B": "2602335D", "C": "436CVR021", "H": "USD"}]
    xml_rows = []
    for index, row in enumerate(rows, 1):
        cells = "".join(f'<c r="{column}{index}" t="inlineStr"><is><t>{escape(value)}</t></is></c>' for column, value in row.items())
        xml_rows.append(f'<row r="{index}">{cells}</row>')
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>")
    header = ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry", "CIK"]
    wiki = '<table id="constituents"><tr>' + "".join(f"<th>{name}</th>" for name in header) + "</tr>"
    for name in wiki_names:
        cik = identity[name] if changed_cik != name else identity[name] + 10000
        values = [name, "Company " + name, "Industrials", "Industrial Machinery", f"{cik:010d}"]
        wiki += "<tr>" + "".join(f"<td>{value}</td>" for value in values) + "</tr>"
    return {SPY_HOLDINGS_URL: data.getvalue(), WIKIPEDIA_URL: (wiki + "</table>").encode()}


def test_verified_dated_snapshot_is_immutable_and_same_day_refresh_is_offline(tmp_path):
    documents, calls = source_documents(), []
    def fetch(url):
        calls.append(url)
        return documents[url]
    first = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=fetch)
    assert first.allow_new_risk and first.status == "verified"
    assert first.snapshot["source_as_of"] == "2026-09-03"
    assert first.snapshot["verified_for_session"] == "2026-09-04"
    assert first.snapshot["security_count"] == first.snapshot["company_count"] == 500
    assert len(first.snapshot["excluded_non_index_assets"]) == 2
    path = tmp_path / "data/reference/sp500/snapshots" / f"{first.snapshot['snapshot_id']}.json"
    original = path.read_bytes()
    second = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=fetch)
    assert second.allow_new_risk and len(calls) == 2
    refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=fetch)
    assert len(calls) == 4 and path.read_bytes() == original
    assert len(list(path.parent.glob("*.json"))) == 2


def test_fresh_fetch_does_not_make_old_source_current(tmp_path):
    documents = source_documents(date="02-Sep-2026")
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__)
    assert result.status == "stale" and not result.allow_new_risk
    assert load_sp500_snapshot(tmp_path) is None


def test_network_failure_preserves_last_good_but_blocks_new_buys(tmp_path):
    documents = source_documents()
    first = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__)
    def fail(_):
        raise TimeoutError("provider timeout")
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=fail)
    assert result.status == "failed" and result.snapshot == first.snapshot
    status = sp500_status(tmp_path, "2026-09-04", TOMORROW)
    assert status["fresh"] and not status["allow_new_risk"]
    assert load_sp500_snapshot(tmp_path) == first.snapshot


def test_disagreement_duplicates_and_large_changes_are_not_silently_accepted(tmp_path):
    names = [f"S{i:03d}" for i in range(500)]
    documents = source_documents(names=names)
    original = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__).snapshot
    mismatch = source_documents(names=names, wiki_names=names[:-1] + ["S999"])
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=mismatch.__getitem__)
    assert result.status == "conflict" and "sources disagree" in result.error
    duplicates = source_documents(names=names + [names[0]])
    with pytest.raises(ValueError, match="duplicate issuer"):
        parse_spy_holdings(duplicates[SPY_HOLDINGS_URL])
    with pytest.raises(ValueError, match="duplicate Wikipedia"):
        parse_wikipedia_constituents(duplicates[WIKIPEDIA_URL])
    changed = source_documents(names=names[11:] + [f"S{i:03d}" for i in range(500, 511)])
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=changed.__getitem__)
    assert "large constituent change" in result.error
    assert load_sp500_snapshot(tmp_path) == original


def test_same_ticker_identity_reuse_is_rejected_and_normal_add_remove_is_recorded(tmp_path):
    names = [f"S{i:03d}" for i in range(500)]
    documents = source_documents(names=names)
    refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__)
    changed = source_documents(names=names, changed_cik=names[0])
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=changed.__getitem__)
    assert "security identity changed" in result.error
    legitimate = source_documents(names=names[:-1] + ["S999"])
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=legitimate.__getitem__)
    assert result.allow_new_risk
    assert result.added == ["S999"] and result.removed == ["S499"]


def test_source_and_verification_each_expire_by_completed_sessions(tmp_path):
    documents = source_documents()
    result = refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__)
    # September 7 is a market holiday: Sep 8 is two completed sessions after Sep 3.
    later = datetime(2026, 9, 9, 2, tzinfo=timezone.utc)
    status = sp500_freshness(result.snapshot, "2026-09-08", later)
    assert not status["fresh"] and status["source_age_sessions"] == 2
    assert status["verification_age_sessions"] == 1
