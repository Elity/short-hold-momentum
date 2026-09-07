"""Build work-only HFC extensions from the frozen WIKI prefix and SheepB snapshot.

No network, repository writes, backtest, or winner selection is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
REPO = Path("/Users/fighting/code/short-hold-momentum")
ORIGINAL = REPO / "data/research/v04/prices/HFC.parquet"
WIKI = WORK / "v04-remediation-archive/prices/HFC.parquet"
SHEEPB = WORK / "v04-source-options-next/sheepb-extracted/HFC.parquet"
ZIP = WORK / "v04-source-options-next/sheepb-2021-v1.zip"
RECEIPT = WORK / "v04-source-options-next/sheepb-2021-download.json"
IEX = WORK / "v04-corporate-actions-next/ATVI-independent-sp500.source.zip"
JACKSON = WORK / "v04-member-extensions/HFC-followup/HFC-jackson.csv"
MEMBERSHIP = REPO / "data/reference/sp500_history.csv"
EXPECTED = {
    "canonical": "8e32b35e068f736fc1c6719ab85979d5a2717dc8a1a4bca90a4d2cf2eff06b54",
    "wiki": "e20be066f5a4537478a899d7af9c2d934009f2ba758bb819dce8d7a293da0f05",
    "sheepb": "196aea2aefc53bc736c9d8008cbc77142cfae321f8b0192d64d6be2669d1b0bc",
    "sheepb_archive": "22f61a91843c579577a1757bd31653fd998ba8054723da3d4b41d994cda46373",
    "jackson": "ba6ec25dec06336d613fd61b7bf404486f209ad36cf51bc5521c03f35b440901",
}
CASH_ROWS = [
    ("2018-05-22", .33, "2018-05-23", "2018-06-14"),
    ("2018-08-22", .33, "2018-08-23", "2018-09-20"),
    ("2018-11-20", .33, "2018-11-21", "2018-12-12"),
    ("2019-02-26", .33, "2019-02-27", "2019-03-13"),
    ("2019-05-17", .33, "2019-05-20", "2019-06-05"),
    ("2019-08-21", .33, "2019-08-22", "2019-09-04"),
    ("2019-11-26", .35, "2019-11-27", "2019-12-11"),
    ("2020-02-21", .35, "2020-02-24", "2020-03-05"),
    ("2020-05-22", .35, "2020-05-26", "2020-06-18"),
    ("2020-08-14", .35, "2020-08-17", "2020-09-02"),
    ("2020-11-20", .35, "2020-11-23", "2020-12-07"),
    ("2021-02-26", .35, "2021-03-01", "2021-03-10"),
]
SOURCE_URL = "https://www.kaggle.com/datasets/sheepb/stock-market-dataset-20002021"
PRIMARY_URLS = {
    "2020_10k": "https://www.sec.gov/Archives/edgar/data/48039/000004803921000012/hfc-20201231.htm",
    "2021_10k": "https://www.sec.gov/Archives/edgar/data/48039/000004803922000014/hfc-20211231.htm",
    "quarterly_table": "https://www.sec.gov/Archives/edgar/data/48039/000004803921000012/R47.htm",
    "2018_may": "https://www.hollyfrontier.com/investor-relations/press-releases/Press-Release-Details/2018/HollyFrontier-Corporation-Announces-Regular-Cash-Dividend-592018/default.aspx",
    "2018_august": "https://www.businesswire.com/news/home/20180802005255/en/HollyFrontier-Corporation-Reports-Quarterly-Results-Announces-Regular",
    "2018_november": "https://www.sec.gov/Archives/edgar/data/48039/000004803918000070/hfc-form8xkdividendsnovemb.htm",
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n")


def iso(index):
    return pd.DatetimeIndex(index).strftime("%Y-%m-%d").tolist()


def valid_bars(df):
    c = df[["open", "high", "low", "close", "volume"]]
    return (np.isfinite(c).all(axis=1) & (c > 0).all(axis=1)
            & (c.high >= c[["open", "close", "low"]].max(axis=1))
            & (c.low <= c[["open", "close", "high"]].min(axis=1)))


inputs = {k: {"path": str(p), "sha256": sha(p)} for k, p in {
    "canonical": ORIGINAL, "wiki": WIKI, "sheepb": SHEEPB,
    "sheepb_archive": ZIP, "membership": MEMBERSHIP, "iex_archive": IEX, "jackson": JACKSON,
}.items()}
for name, digest in EXPECTED.items():
    assert inputs[name]["sha256"] == digest, f"Changed source {name}"
for name, path in [("HFC-original.parquet", ORIGINAL), ("HFC-WIKI-source.parquet", WIKI),
                   ("HFC-SheepB-source.parquet", SHEEPB), ("HFC-JacksonCrow-source.csv", JACKSON)]:
    shutil.copyfile(path, OUT / name)

old = pd.read_parquet(ORIGINAL).sort_values("date").reset_index(drop=True)
wiki = pd.read_parquet(WIKI)
wiki["date"] = pd.to_datetime(wiki.date)
sheepb = pd.read_parquet(SHEEPB)
sheepb["date"] = pd.to_datetime(sheepb.Date)
sheepb = sheepb.sort_values("date").reset_index(drop=True)
assert sheepb.Name.eq("HFC").all() and sheepb["Company Name"].eq("HollyFrontier").all()
assert old.date.is_unique and sheepb.date.is_unique
calendar = xcals.get_calendar("XNYS", start="2003-01-01", end="2022-12-31")
sessions = calendar.sessions_in_range(old.date.min(), sheepb.date.max()).tz_localize(None)
tail = sheepb.loc[sheepb.date > old.date.max()].copy().reset_index(drop=True)
assert len(tail) == 856
assert pd.DatetimeIndex(tail.date).equals(sessions[sessions > old.date.max()])

events = pd.DataFrame(CASH_ROWS, columns=["date", "cash_dividend", "record_date", "pay_date"])
events["date"] = pd.to_datetime(events.date)
events["kind"] = "ordinary_cash_dividend"
events["exact_date_evidence"] = "SheepB factor step plus secondary A2 Finance history in request-01"
events["amount_evidence"] = "SEC quarterly/year totals; 2018 issuer declarations in request-08"
events["primary_individual_ex_date_obtained"] = False
events.to_csv(OUT / "tail-dividend-events.csv", index=False)
cash = events.set_index("date").cash_dividend
tail["cash_dividend"] = tail.date.map(cash).fillna(0.)
tail["canonical_factor"] = (1 + tail.cash_dividend / tail.Close).cumprod()
tail["vendor_adjustment_factor"] = tail["Adj Close"] / tail.Close
assert np.isclose(tail.cash_dividend.sum(), 4.08)

new = pd.DataFrame({"date": tail.date})
for c in ["open", "high", "low", "close"]:
    new[c] = tail[c.title()] * tail.canonical_factor
new["volume"] = tail.Volume
new["as_traded_close"] = tail.Close
new["dollar_volume"] = tail.Close * tail.Volume
new["adjusted"] = True
new["source"] = "SheepB 2021 v1 frozen yfinance archive; nominal OHLCV plus cash-dividend forward normalization"
captured = pd.Timestamp(RECEIPT.stat().st_mtime, unit="s", tz="UTC")
new["downloaded_at"] = pd.Series([captured] * len(new), dtype=old.downloaded_at.dtype)
new = new[old.columns]
pure = pd.concat([old, new], ignore_index=True)
pd.testing.assert_frame_equal(pure.iloc[:len(old)].reset_index(drop=True), old)
assert valid_bars(pure).all()
assert pure.date.is_unique and pure.date.is_monotonic_increasing
assert np.allclose(new.dollar_volume, new.as_traded_close * new.volume)
assert np.allclose(old.dollar_volume, wiki.close * wiki.volume)
assert np.allclose(old.volume, wiki.adj_volume)
assert pure.iloc[len(old)].date == pd.Timestamp("2018-03-28")
pure_path = OUT / "HFC-tail-prefix-unchanged.candidate.parquet"
pure.to_parquet(pure_path, index=False)
pd.testing.assert_frame_equal(pd.read_parquet(pure_path), pure)

repair_date = pd.Timestamp("2018-02-27")
repair_cash = .33
repair_close = float(old.loc[old.date.eq(repair_date), "as_traded_close"].iloc[0])
repair_factor = repair_close / (repair_close + repair_cash)
missing = sessions.difference(pure.date)
assert iso(missing) == ["2017-11-08"]
jackson = pd.read_csv(JACKSON)
jackson["date"] = pd.to_datetime(jackson.Date)
neighbors = sheepb.merge(jackson, on="date", suffixes=("_sheepb", "_jackson"))
neighbors = neighbors.loc[neighbors.date.between("2017-11-06", "2017-11-10")]
neighbor_differences = {c: float((neighbors[c + "_sheepb"] - neighbors[c + "_jackson"]).abs().max())
                        for c in ["Open", "High", "Low", "Close", "Volume"]}
assert len(neighbors) == 5 and all(d == 0 for d in neighbor_differences.values())
neighbors.to_csv(OUT / "missing-session-two-snapshot-neighbors.csv", index=False)
missing_source = sheepb.loc[sheepb.date.eq(missing[0])].iloc[0]
before = old.loc[old.date.eq(pd.Timestamp("2017-11-07"))].iloc[0]
after = old.loc[old.date.eq(pd.Timestamp("2017-11-09"))].iloc[0]
insertion_factor = float(before.close / before.as_traded_close)
assert abs(insertion_factor - after.close / after.as_traded_close) < 1e-12
inserted = before.copy()
inserted["date"] = missing[0]
for c in ["open", "high", "low", "close"]:
    inserted[c] = missing_source[c.title()] * insertion_factor
inserted["volume"] = missing_source.Volume
inserted["as_traded_close"] = missing_source.Close
inserted["dollar_volume"] = missing_source.Close * missing_source.Volume
inserted["source"] = "SheepB whole nominal row; exact OHLCV agreement with JacksonCrow v2; adjacent WIKI factor"
inserted["downloaded_at"] = captured
inserted = pd.DataFrame([inserted], columns=old.columns).astype(old.dtypes.to_dict())
corrected = pd.concat([pure, inserted], ignore_index=True).sort_values("date").reset_index(drop=True)
affected = corrected.date < repair_date
for c in ["open", "high", "low", "close"]:
    corrected.loc[affected, c] *= repair_factor
corrected.loc[affected, "source"] += "; includes omitted 2018-02-27 USD 0.33 dividend repair"
unchanged_columns = ["date", "volume", "as_traded_close", "dollar_volume", "adjusted", "downloaded_at"]
pd.testing.assert_frame_equal(corrected.loc[corrected.date.isin(pure.date), unchanged_columns].reset_index(drop=True), pure[unchanged_columns])
pd.testing.assert_frame_equal(corrected.loc[corrected.date >= repair_date].reset_index(drop=True), pure.loc[pure.date >= repair_date].reset_index(drop=True))
assert valid_bars(corrected).all()
assert len(corrected) == 4503 and pd.DatetimeIndex(corrected.date).equals(sessions)
corrected_path = OUT / "HFC-tail-plus-prefix-repairs.candidate.parquet"
corrected.to_parquet(corrected_path, index=False)
pd.testing.assert_frame_equal(pd.read_parquet(corrected_path), corrected)

raw_fields = ["open", "high", "low", "close", "volume"]
raw_prefix = wiki[["date", *raw_fields]].copy()
raw_prefix["raw_source"] = "WIKI"
raw_added = pd.concat([tail, sheepb.loc[sheepb.date.eq(missing[0])]], ignore_index=True)
raw_added = raw_added[["date", *[c.title() for c in raw_fields]]].rename(columns={c.title(): c for c in raw_fields})
raw_added["raw_source"] = "SheepB"
raw_rows = pd.concat([raw_prefix, raw_added], ignore_index=True).sort_values("date")
raw_rows = raw_rows.rename(columns={c: "nominal_" + c for c in raw_fields})
row_audit = raw_rows.merge(pure[["date", *raw_fields, "dollar_volume", "source"]].rename(
    columns={c: "prefix_preserving_" + c for c in [*raw_fields, "dollar_volume", "source"]}), on="date", how="left")
row_audit = row_audit.merge(corrected[["date", *raw_fields, "dollar_volume", "source"]].rename(
    columns={c: "repaired_" + c for c in [*raw_fields, "dollar_volume", "source"]}), on="date", how="left")
row_audit["prefix_preserving_factor"] = row_audit.prefix_preserving_close / row_audit.nominal_close
row_audit["repaired_factor"] = row_audit.repaired_close / row_audit.nominal_close
row_audit["cash_dividend_tail_or_prefix_repair"] = row_audit.date.map(cash).fillna(0.)
row_audit.loc[row_audit.date.eq(repair_date), "cash_dividend_tail_or_prefix_repair"] = repair_cash
row_audit.to_csv(OUT / "raw-and-canonical-row-audit.csv", index=False)
assert np.allclose(row_audit.repaired_dollar_volume, row_audit.nominal_close * row_audit.nominal_volume)

previous = pure.close.shift(1)
nominal_previous = pure.as_traded_close.shift(1)
expected_returns = (pure.as_traded_close + pure.date.map(cash).fillna(0.)) / nominal_previous - 1
tail_error = ((pure.close / previous - 1) - expected_returns).iloc[len(old):].abs().max()
assert tail_error < 1e-12
dividend_returns = []
for d, cash_amount in [(repair_date, repair_cash), *zip(events.date, events.cash_dividend)]:
    k = corrected.index[corrected.date.eq(d)][0]
    actual = corrected.loc[k, "close"] / corrected.loc[k - 1, "close"] - 1
    expected = (corrected.loc[k, "as_traded_close"] + cash_amount) / corrected.loc[k - 1, "as_traded_close"] - 1
    assert abs(actual - expected) < 1e-12
    dividend_returns.append({"date": d.date().isoformat(), "cash_dividend": cash_amount,
                             "actual_adjusted_return": actual, "nominal_plus_cash_return": expected,
                             "absolute_error": abs(actual - expected)})
write_json("dividend-return-validation.json", dividend_returns)

all_source = sheepb.copy()
all_source["vendor_factor"] = all_source["Adj Close"] / all_source.Close
all_source["vendor_factor_step"] = all_source.vendor_factor.pct_change()
all_source["inferred_cash_yahoo_convention"] = all_source.Close.shift(1) * (1 - 1 / (1 + all_source.vendor_factor_step))
steps = all_source.loc[(all_source.date > old.date.max()) & all_source.vendor_factor_step.abs().gt(1e-5)]
assert set(steps.date) == set(events.date)
steps.to_csv(OUT / "tail-vendor-factor-steps.csv", index=False)
assert np.allclose(steps.inferred_cash_yahoo_convention, steps.date.map(cash), atol=2e-5)
tail.to_csv(OUT / "added-tail-raw-and-factor.csv", index=False)

overlap = wiki.merge(all_source, on="date", suffixes=("_wiki", "_sheepb"))
statistics = {}
for start in ["2011-09-02", "2017-09-27", "2018-01-01"]:
    sample = overlap.loc[overlap.date >= start]
    stats = {"shared_sessions": len(sample), "fields": {}}
    for col in ["open", "high", "low", "close", "volume"]:
        abs_diff = (sample[col] - sample[col.title()]).abs()
        rel_diff = abs_diff / sample[col].abs()
        stats["fields"][col] = {"max_absolute_difference": float(abs_diff.max()),
            "max_relative_difference": float(rel_diff.max()), "p99_relative_difference": float(rel_diff.quantile(.99)),
            "median_relative_difference": float(rel_diff.median()), "count_over_one_percent": int(rel_diff.gt(.01).sum())}
    statistics[start] = stats
recent = wiki.loc[wiki.date >= "2017-09-27"].merge(all_source, on="date", how="outer", suffixes=("_wiki", "_sheepb"))
recent = recent.loc[recent.date.between("2017-09-27", old.date.max())].sort_values("date")
recent["wiki_factor"] = recent.adj_close / recent.close
recent["wiki_factor_step"] = recent.wiki_factor.pct_change(fill_method=None)
recent.to_csv(OUT / "old-final-six-months-factor-audit.csv", index=False)
recent_steps = recent.loc[recent.wiki_factor_step.abs().gt(1e-5) | recent.vendor_factor_step.abs().gt(1e-5)]
recent_steps.to_csv(OUT / "old-final-six-months-factor-steps.csv", index=False)
assert iso(recent_steps.date) == ["2017-11-20", "2018-02-27"]
assert wiki.loc[wiki.date.eq(repair_date), "ex-dividend"].iloc[0] == 0
assert wiki.loc[wiki.date.eq(pd.Timestamp("2017-11-20")), "ex-dividend"].iloc[0] == .33

missing_observation = all_source.loc[all_source.date.isin(missing)].copy()
missing_observation["disposition"] = "Inserted only in explicit repaired variant after exact JacksonCrow v2 OHLCV corroboration"
missing_observation.to_csv(OUT / "missing-session-source-observation.csv", index=False)
with zipfile.ZipFile(IEX) as archive:
    iex_members = [x for x in archive.namelist() if "hfc" in x.lower()]
assert iex_members == []

members = pd.read_csv(MEMBERSHIP)
members["date"] = pd.to_datetime(members.date)
members["hfc_member"] = members.tickers.str.split(",").map(lambda x: "HFC" in x)
member_daily = members.set_index("date").hfc_member.reindex(sessions, method="ffill").fillna(False)
member_sessions = sessions[member_daily.to_numpy()]
coverage = pd.DataFrame({"date": sessions, "hfc_member": member_daily.to_numpy(), "observed_prefix_preserving": sessions.isin(pure.date),
                        "observed_repaired": sessions.isin(corrected.date)})
coverage["full_260_session_window_prefix_preserving"] = coverage.observed_prefix_preserving.rolling(260, min_periods=260).sum().eq(260)
coverage["full_260_session_window_repaired"] = coverage.observed_repaired.rolling(260, min_periods=260).sum().eq(260)
coverage.to_csv(OUT / "session-coverage-and-260-window.csv", index=False)
affected_member_days = coverage.loc[coverage.hfc_member & ~coverage.full_260_session_window_prefix_preserving, "date"]
member_rows = members.loc[members.hfc_member]
membership_audit = {
    "first_membership_snapshot": str(member_rows.date.min().date()),
    "last_membership_snapshot": str(member_rows.date.max().date()),
    "first_member_session": str(member_sessions.min().date()),
    "last_member_session": str(member_sessions.max().date()),
    "member_sessions_total": len(member_sessions),
    "original_member_price_overlap": int(member_sessions.isin(old.date).sum()),
    "candidate_member_price_overlap": int(member_sessions.isin(pure.date).sum()),
    "missing_member_sessions": iso(member_sessions.difference(pure.date)),
    "prefix_preserving_member_sessions_with_incomplete_260_session_window": len(affected_member_days),
    "repaired_member_sessions_with_incomplete_260_session_window": int((coverage.hfc_member & ~coverage.full_260_session_window_repaired).sum()),
    "affected_260_window_first": str(affected_member_days.min().date()),
    "affected_260_window_last": str(affected_member_days.max().date()),
    "prefix_preserving_first_member_date_with_complete_260_session_window": str(coverage.loc[coverage.hfc_member & coverage.full_260_session_window_prefix_preserving, "date"].min().date()),
    "repaired_first_member_date_with_complete_260_session_window": str(coverage.loc[coverage.hfc_member & coverage.full_260_session_window_repaired, "date"].min().date()),
    "scope": "Calendar coverage only; not a claim about every engine eligibility filter or actual selection.",
    "zero_overlap_reason": "Frozen WIKI archive ends 2018-03-27, before first membership snapshot 2018-06-18.",
    "tail_after_membership": "Real marks through 2021-08-19 support later exits; no post-membership ranking eligibility implied.",
}

excerpts = {}
for name in ["HFC-2020-10K.txt", "HFC-2021-10K.txt"]:
    text = (OUT / "primary-evidence" / name).read_text()
    excerpts[name] = {"capture_characters": len(text), "partial_capture": True, "quotes": {}}
    for term in ["Cash dividends declared per common share", "one-year suspension", "162,414,838", "163,001,510", "Trading Symbol"]:
        excerpts[name]["quotes"][term] = [text[max(0, m.start()-100):m.end()+350]
            for m in list(re.finditer(re.escape(term), text, flags=re.I))[:2]]
write_json("primary-excerpts.json", excerpts)
repair_info = {
    "date": str(repair_date.date()), "cash_dividend": repair_cash, "nominal_ex_date_close": repair_close,
    "backward_factor": repair_factor, "affected_existing_rows": int(old.date.lt(repair_date).sum()),
    "evidence": "SheepB factor step and A2 Finance exact-date history; primary 2018 total 1.32 less later three issuer-supported 0.33 payments leaves 0.33.",
    "old_wiki_ex_dividend": 0, "old_wiki_factor_step": 0,
    "unchanged_on_and_after_date": str(repair_date.date()), "unchanged_fields_for_existing_rows": unchanged_columns,
    "changed_fields": ["open", "high", "low", "close", "source"],
    "missing_session_repair_applied": True,
    "missing_row_repair": {"date": "2017-11-08", "whole_row_source": "SheepB", "corroboration": "JacksonCrow v2; same Yahoo upstream, distinct archived capture",
        "five_session_max_absolute_differences": neighbor_differences, "adjacent_wiki_factor_before_dividend_correction": insertion_factor,
        "final_inserted_adjustment_factor": insertion_factor * repair_factor,
        "nominal_ohlcv": {c: float(missing_source[c]) for c in ["Open", "High", "Low", "Close", "Volume"]}},
}
write_json("prefix-dividend-repair.json", repair_info)

products = {}
for key, p, df in [("prefix_preserving", pure_path, pure), ("prefix_dividend_corrected", corrected_path, corrected)]:
    products[key] = {"path": str(p), "sha256": sha(p), "rows": len(df),
        "first": str(df.date.min().date()), "last": str(df.date.max().date()),
        "invalid_rows": int((~valid_bars(df)).sum()), "legacy_gap": iso(sessions.difference(df.date)),
        "preserves_entire_old_prefix": key == "prefix_preserving"}
assert sha(ORIGINAL) == inputs["canonical"]["sha256"]
assert sha(WIKI) == inputs["wiki"]["sha256"]
assert sha(SHEEPB) == inputs["sheepb"]["sha256"]
audit = {
    "status": "WORK_ONLY_REVIEWABLE_CANDIDATES_NOT_APPLIED", "ticker": "HFC", "issuer": "HollyFrontier Corporation",
    "inputs": inputs, "products": products, "new_sessions": len(tail), "new_first": str(tail.date.min().date()),
    "new_last": str(tail.date.max().date()), "new_cash_events": len(events), "new_cash_total": float(events.cash_dividend.sum()),
    "tail_terminal_factor_prefix_preserving": float(tail.canonical_factor.iloc[-1]),
    "tail_terminal_factor_dividend_corrected": float(tail.canonical_factor.iloc[-1]),
    "tail_max_dividend_return_error": float(tail_error), "overlap_statistics": statistics,
    "membership": membership_audit, "prefix_dividend_repair": repair_info,
    "old_final_six_month_factor_steps": recent_steps[["date", "ex-dividend", "wiki_factor_step", "vendor_factor_step", "inferred_cash_yahoo_convention"]].to_dict("records"),
    "iex_archive_hfc_members": iex_members, "missing_row_inserted_in_repaired_variant": True,
    "downloaded_at_new_rows": str(captured), "downloaded_at_provenance": "Source download-receipt filesystem mtime; not exchange publication time.",
    "source_independence": "SheepB and JacksonCrow are distinct frozen Yahoo/yfinance captures, not independent vendors. WIKI is separate nominal overlap; primary issuer/SEC records support corporate actions.",
    "nominal_units": "Supported inference from post-2011-split price overlap, source Close convention, no tail split-sized factor steps, and primary 2018-2021 share-count scale. No complete official split inventory was obtained.",
    "source_disagreements": "Prefix Close agrees closely, but some OHLC and volume rows differ. Existing prefix OHLCV are not replaced from SheepB.",
    "volume_semantics": "Existing canonical volume equals WIKI adj_volume, while existing dollar_volume equals WIKI nominal close times nominal volume. Tail and inserted row use nominal volume after the last observed split. Raw and canonical fields are kept separately; no adjusted-price ADV substitution.",
    "special_dividends": "No additional 2018-2021 specials are supported; annual totals reconcile to ordinary events. Older special dividends are outside tail scope.",
    "primary_capture_limit": "2020/2021 10-K Browse captures end within MD&A; complete financial statements/share roll-forwards were not read.",
    "external_request_budget": {"subagent_used": 8, "subagent_limit": 8, "parent_additional_jackson_request": 1, "misdirected_excluded": [2], "unavailable": [6, 7], "additional_requests_by_generator": 0},
    "repository_price_unchanged": True, "backtest_run": False, "selection_or_gate_claim": False,
    "primary_urls": PRIMARY_URLS,
}
write_json("audit.json", audit)
write_json("manifest-proposal.json", {
    "status": "PROPOSAL_ONLY_NOT_APPLIED", "choose_explicitly_between_variants": True,
    "ticker": "HFC", "source_ticker": "HFC", "source_name": "HollyFrontier Corp.",
    "original": inputs["canonical"], "candidates": products,
    "method": "Append whole nominal SheepB rows with ordinary cash dividends normalized to WIKI forward total-return convention. Pure variant preserves existing prefix. Corrected variant additionally inserts the corroborated 2017-11-08 whole row and repairs the omitted 2018-02-27 dividend by multiplying earlier OHLC by Pex/(Pex+D), preserving the old terminal anchor and identical appended tail.",
    "cash_dividend_handling": "Embedded in adjusted OHLC only; do not separately credit these dividends again.",
    "source_archive_sha256": inputs["sheepb_archive"]["sha256"],
    "evidence_audit": str(OUT / "audit.json"), "limitations": ["Pure variant retains 2017-11-08 gap; repaired variant changes historical adjusted OHLC", "Nominal-unit assessment is supported inference, not exhaustive primary split ledger", "Some prefix OHLCV vendor disagreements", "Primary annual captures are partial", "SheepB/JacksonCrow are same upstream vendor"],
})
print(json.dumps({"products": products, "membership": membership_audit, "repair": repair_info,
                  "max_return_error": tail_error, "tail_terminal_factor": float(tail.canonical_factor.iloc[-1])}, indent=2, default=str))
