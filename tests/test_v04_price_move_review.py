from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from shm.v03.research import _correctness, _holding_price_jumps
from shm.v04.history import MANIFEST_PATH, load_verified_price_moves
from shm.v04.research import review_holding_price_jumps


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def review_data(tmp_path):
    dates = pd.to_datetime(["2020-03-06", "2020-03-09"])
    frame = pd.DataFrame({"date": dates, "close": [100., 40.]})
    price_path = tmp_path / "data/raw/prices/APA.parquet"
    price_path.parent.mkdir(parents=True)
    frame.to_parquet(price_path, index=False)
    evidence = tmp_path / "event.md"
    evidence.write_text("Dated price archive and contemporary reports confirm the market decline")
    entry = {"id": "APA-market-decline", "ticker": "APA", "date": "2020-03-09",
             "quote_window": "close_to_close", "expected_return": -.6,
             "input_path": "data/raw/prices/APA.parquet", "input_sha256": sha(price_path),
             "evidence_path": "event.md", "evidence_sha256": sha(evidence)}
    manifest = tmp_path / MANIFEST_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"verified_price_moves": [entry]}))
    prepared = SimpleNamespace(dates=dates, tickers=("APA",), returns=np.array([[np.nan], [-.6]]))
    bt = SimpleNamespace(weights=pd.DataFrame({"APA": .1}, index=dates),
                         equity=pd.Series([100_000., 94_000.], index=dates),
                         cash=pd.Series(90_000., index=dates), transactions=pd.DataFrame(),
                         execution_fallbacks=pd.DataFrame())
    return tmp_path, frame, price_path, evidence, manifest, entry, prepared, bt


def test_exact_hash_pinned_review_keeps_raw_loss_and_does_not_clear_signal_gap(review_data):
    root, frame, price, evidence, _, entry, prepared, bt = review_data
    reviews, hashes, audit = load_verified_price_moves(root, {"APA": frame}, {entry["input_path"]: sha(price)}, {})
    assert reviews == (entry,) and audit["rejected"] == []
    assert hashes["event.md"] == sha(evidence)
    jumps = _holding_price_jumps(prepared, bt, prepared.dates[1:])
    original = deepcopy(jumps)
    result = SimpleNamespace(backtest=bt, warnings=[{"date": "2020-03-09", "warning": "MISSING_ATR20:KHC"}])
    assert _correctness(result, prepared.dates[1:], holding_price_jumps=jumps)["HOLDING_PRICE_JUMPS"] == "INCONCLUSIVE"
    pending, verified = review_holding_price_jumps(jumps, reviews)
    assert not pending and verified[0]["verification"] == entry
    checks = _correctness(result, prepared.dates[1:], holding_price_jumps=pending)
    assert checks["HOLDING_PRICE_JUMPS"] == "PASS" and checks["SIGNAL_DATA"] == "INCONCLUSIVE"
    assert jumps == original and jumps[0]["return"] == -.6
    assert bt.equity.iloc[-1] == 94_000.


@pytest.mark.parametrize("change,reason", [
    ("input", "input_sha256_mismatch"), ("evidence", "evidence_sha256_mismatch"),
    ("inactive_source", "input_not_current_price_source"),
])
def test_changed_or_unused_source_review_does_not_exempt_jump(review_data, change, reason):
    root, frame, price, evidence, _, entry, prepared, bt = review_data
    hashes, repairs = {entry["input_path"]: sha(price)}, {}
    if change == "input":
        # Even a stale caller hash cannot approve a file replaced after loading.
        frame.assign(close=[100., 30.]).to_parquet(price, index=False)
    elif change == "evidence":
        evidence.write_text("Evidence changed after the review")
    else:
        other = root / "override.parquet"
        other.write_bytes(price.read_bytes())
        hashes["override.parquet"] = sha(other)
        repairs = {"price_overrides": {"APA": {"path": "override.parquet"}}}
    reviews, _, audit = load_verified_price_moves(root, {"APA": frame}, hashes, repairs)
    assert reviews == () and audit["rejected"][0]["reason"] == reason
    jumps = _holding_price_jumps(prepared, bt, prepared.dates[1:])
    pending, verified = review_holding_price_jumps(jumps, reviews)
    assert not verified and pending[0]["verification_rejection"] == "no_accepted_review"
    assert _correctness(SimpleNamespace(backtest=bt, warnings=[]), prepared.dates[1:],
                        holding_price_jumps=pending)["HOLDING_PRICE_JUMPS"] == "INCONCLUSIVE"


@pytest.mark.parametrize("field,value,reason", [
    ("ticker", "OTHER", "event_identity_mismatch"),
    ("date", "2020-03-10", "event_identity_mismatch"),
    ("quote_window", "fill_to_close", "event_identity_mismatch"),
    ("return", -.600001, "expected_return_mismatch"),
])
def test_review_is_specific_to_ticker_date_quote_window_and_return(review_data, field, value, reason):
    root, frame, price, _, _, entry, prepared, bt = review_data
    reviews, _, _ = load_verified_price_moves(root, {"APA": frame}, {entry["input_path"]: sha(price)}, {})
    jumps = _holding_price_jumps(prepared, bt, prepared.dates[1:])
    jumps[0][field] = value
    original = deepcopy(jumps)
    pending, verified = review_holding_price_jumps(jumps, reviews)
    assert not verified and pending[0]["verification_rejection"] == reason
    assert jumps == original


def test_no_manifest_preserves_default_unverified_behavior(tmp_path):
    reviews, hashes, audit = load_verified_price_moves(tmp_path, {}, {}, {})
    assert reviews == () and hashes == {} and audit == {"accepted": [], "rejected": []}
    pending, verified = review_holding_price_jumps(
        [{"ticker": "APA", "date": "2020-03-09", "return": -.6, "prior_weight": .1}], reviews)
    assert not verified and pending[0]["verification_rejection"] == "no_accepted_review"
