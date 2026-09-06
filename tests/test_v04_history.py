import hashlib
import json

import pandas as pd
import pytest

from shm.pipeline import pit_universe_provider
from shm.v04 import history


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base(root, tickers="OLD"):
    path = root / history.MEMBERSHIP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": ["2026-06-29", "2026-06-30"], "tickers": [tickers, tickers]}).to_csv(
        path, index=False,
    )
    return path


def _manifest(root, **entries):
    path = root / history.MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries))
    return path


def _extension(root, dates, tickers=None):
    path = root / "data/reference/v04-remediation/membership.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "tickers": tickers or ["NEW"] * len(dates)}).to_csv(path, index=False)
    return path


def _override(root, ticker="NEW", adjusted=True):
    path = root / f"data/reference/v04-remediation/{ticker}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.to_datetime(["2026-06-29", "2026-06-30", "2026-07-01"]),
                  "open": [10., 11., 12.], "high": [11., 12., 13.], "low": [9., 10., 11.],
                  "close": [10., 11., 12.], "volume": [100., 100., 100.],
                  "as_traded_close": [20., 22., 24.], "dollar_volume": [2000., 2200., 2400.],
                  "adjusted": adjusted, "unused": "ignored"}).to_parquet(path, index=False)
    return {"path": str(path.relative_to(root)), "sha256": _sha(path), "reason": "verified archive"}


def test_optional_manifest_preserves_base_and_price_inputs(tmp_path):
    base = _base(tmp_path)
    content = base.read_bytes()
    loaded, hashes, evidence = history.load_membership(tmp_path)
    assert loaded["members"].tolist() == [("OLD",), ("OLD",)]
    assert hashes == {history.MEMBERSHIP_PATH: _sha(base)}
    assert evidence["alias_count"] == 0 and evidence["extension_dates"] == []
    prices = {"OLD": pd.DataFrame({"close": [1.]})}
    repaired, returned_hashes, missing, repair_evidence = history.apply_price_repairs(
        tmp_path, prices, hashes, ["MISSING"], pd.Timestamp("2026-06-29"), pd.Timestamp("2026-06-30"),
    )
    assert repaired == prices and returned_hashes == hashes and missing == ["MISSING"]
    assert repair_evidence["status"] == "PASS"
    assert base.read_bytes() == content


def test_extension_and_alias_continue_same_security_without_backfilling_future_members(tmp_path):
    base = _base(tmp_path)
    content = base.read_bytes()
    extension = _extension(tmp_path, ["2026-07-01", "2026-07-02"], ["NEW", "NEW,FUTURE"])
    manifest = _manifest(tmp_path, membership={"base_sha256": _sha(base),
        "extension_path": str(extension.relative_to(tmp_path)), "extension_sha256": _sha(extension)},
        aliases={"OLD": {"ticker": "NEW", "reason": "same legal security renamed"}})
    loaded, hashes, evidence = history.load_membership(tmp_path)
    provider = pit_universe_provider(loaded)
    assert provider(pd.Timestamp("2026-06-30")).tickers == ("NEW",)
    assert provider(pd.Timestamp("2026-07-01")).tickers == ("NEW",)
    assert provider(pd.Timestamp("2026-07-02")).tickers == ("NEW", "FUTURE")
    assert set(hashes) == {str(path.relative_to(tmp_path)) for path in (base, extension, manifest)}
    assert evidence["alias_count"] == 1 and evidence["alias_member_changes"] == 2
    assert evidence["extension_dates"] == ["2026-07-01", "2026-07-02"]
    assert base.read_bytes() == content


@pytest.mark.parametrize("dates", [
    ["2026-06-30"], ["2026-07-02", "2026-07-01"], ["2026-07-01", "2026-07-01"],
])
def test_extension_rejects_overlap_unsorted_or_duplicate_dates(tmp_path, dates):
    base = _base(tmp_path)
    extension = _extension(tmp_path, dates)
    _manifest(tmp_path, membership={"base_sha256": _sha(base),
        "extension_path": str(extension.relative_to(tmp_path)), "extension_sha256": _sha(extension)})
    with pytest.raises(ValueError, match="strictly increase after"):
        history.load_membership(tmp_path)


def test_alias_collision_is_rejected(tmp_path):
    base = _base(tmp_path, "OLD,NEW")
    _manifest(tmp_path, membership={"base_sha256": _sha(base)}, aliases={"OLD": {"ticker": "NEW"}})
    with pytest.raises(ValueError, match="duplicate members"):
        history.load_membership(tmp_path)


def test_explicit_duplicate_correction_checks_identity_rows_and_keeps_original(tmp_path):
    base = _base(tmp_path, "OLD,NEW")
    content = base.read_bytes()
    evidence = tmp_path / "evidence.md"
    evidence.write_text("Issuer announcement proves OLD became NEW")
    correction = {"start": "2026-06-29", "end": "2026-06-30", "remove": "NEW", "retain": "OLD",
                  "expected_rows": 2, "evidence_path": "evidence.md", "evidence_sha256": _sha(evidence)}
    entries = {"membership": {"base_sha256": _sha(base), "duplicate_member_corrections": [correction]},
               "aliases": {"OLD": {"ticker": "NEW"}}}
    _manifest(tmp_path, **entries)
    loaded, hashes, details = history.load_membership(tmp_path)
    assert loaded.members.tolist() == [("NEW",), ("NEW",)]
    assert base.read_bytes() == content and hashes["evidence.md"] == _sha(evidence)
    assert details["duplicate_member_corrections"] == [correction]
    correction["expected_rows"] = 1
    _manifest(tmp_path, **entries)
    with pytest.raises(ValueError, match="row count mismatch"):
        history.load_membership(tmp_path)
    correction["expected_rows"] = 2
    entries["aliases"] = {}
    _manifest(tmp_path, **entries)
    with pytest.raises(ValueError, match="same security"):
        history.load_membership(tmp_path)


def test_base_hash_mismatch_stops_before_csv_parser(tmp_path, monkeypatch):
    _base(tmp_path)
    _manifest(tmp_path, membership={"base_sha256": "wrong"})
    monkeypatch.setattr(history, "load_pit_history", lambda path: pytest.fail("must check hash first"))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        history.load_membership(tmp_path)


def test_price_repairs_preserve_raw_fields_limit_targets_and_quarantine_missing(tmp_path):
    base = _base(tmp_path, "NEW,TIE")
    override = _override(tmp_path)
    raw_path = tmp_path / "data/raw/prices/TIE.parquet"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"untouched original cache")
    raw_hash = _sha(raw_path)
    unresolved = [{"id": "TIE", "reason": "security identity remains unresolved"}]
    manifest = _manifest(tmp_path, membership={"base_sha256": _sha(base)}, price_overrides={
        "NEW": override, "OUTSIDE": {"path": "never-read.parquet", "sha256": "bad"},
        "TIE": {"path": "also-never-read.parquet", "sha256": "bad"}},
        quarantined={"TIE": {"reason": "polluted prices"}, "OUTSIDE": {"reason": "not requested"}},
        unresolved=unresolved)
    prices = {"TIE": pd.DataFrame({"close": [9999.]}), "SPY": pd.DataFrame({"close": [100.]})}
    hashes = {str(raw_path.relative_to(tmp_path)): raw_hash}
    missing = ["NEW", "STILL_MISSING"]
    repaired, repaired_hashes, returned_missing, evidence = history.apply_price_repairs(
        tmp_path, prices, hashes, missing, pd.Timestamp("2026-06-30"), pd.Timestamp("2026-06-30"),
    )
    assert set(repaired) == {"NEW", "SPY"}
    assert repaired["NEW"]["date"].tolist() == [pd.Timestamp("2026-06-30")]
    assert repaired["NEW"]["as_traded_close"].tolist() == [22.]
    assert repaired["NEW"]["dollar_volume"].tolist() == [2200.]
    assert list(repaired["NEW"].columns) == ["date", "open", "high", "low", "close", "volume",
                                            "as_traded_close", "dollar_volume"]
    assert returned_missing == ["STILL_MISSING", "TIE"]
    assert repaired_hashes[override["path"]] == override["sha256"]
    assert repaired_hashes[history.MANIFEST_PATH] == _sha(manifest)
    assert evidence["status"] == "INCONCLUSIVE" and evidence["unresolved"] == unresolved
    assert evidence["price_override_count"] == evidence["quarantined_count"] == 1
    assert evidence["quarantined"]["TIE"]["reason"] == "polluted prices"
    assert history.load_membership(tmp_path)[0]["members"].tolist() == [("NEW", "TIE")] * 2
    assert set(prices) == {"TIE", "SPY"} and missing == ["NEW", "STILL_MISSING"]
    assert hashes == {str(raw_path.relative_to(tmp_path)): raw_hash} and _sha(raw_path) == raw_hash


@pytest.mark.parametrize("bad_hash", [True, False])
def test_override_rejects_bad_hash_before_parsing_or_unadjusted_data(tmp_path, monkeypatch, bad_hash):
    override = _override(tmp_path, adjusted=False)
    if bad_hash:
        override["sha256"] = "wrong"
        monkeypatch.setattr(pd, "read_parquet", lambda path: pytest.fail("must check hash first"))
    _manifest(tmp_path, price_overrides={"NEW": override})
    with pytest.raises(ValueError, match="SHA256 mismatch" if bad_hash else "adjusted total-return"):
        history.apply_price_repairs(tmp_path, {}, {}, ["NEW"],
                                    pd.Timestamp("2026-06-29"), pd.Timestamp("2026-06-30"))
