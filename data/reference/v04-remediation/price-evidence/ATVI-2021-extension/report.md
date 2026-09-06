# ATVI through 2021-08-19: bounded price extension

Status: **VERIFIED_BOUNDED_PRICE_EXTENSION_NOT_A_RESEARCH_PASS**. This work-only candidate appends 349 complete XNYS daily rows from 2020-04-02 through 2021-08-19 to the active 4,154-row ATVI prefix. The resulting candidate contains 4,503 rows. Every column and value in the existing prefix is preserved after the parquet round-trip. No repository code, active manifest, deployed data, study cutoff, selection rule, or gate is changed by this evidence package.

The parent audit has identified an inherited invalid OHLC row on 2016-11-25 in the old prefix: Open is below Low. It remains unchanged here to honor the exact-prefix contract. The parent will independently verify and replace that whole row, with separate evidence. The validity results below apply to the 349 appended rows; this candidate is not a certification that every inherited row is valid.

## Source identity and limits

The appended rows are from the frozen Kaggle dataset `sheepb/stock-market-dataset-20002021`, version 1, member `full_stock_df.csv`. Dataset metadata identifies `yfinance` as the collection software and a last update of 2021-08-25. The extracted series has `Name=ATVI` and `Company Name=Activision Blizzard` throughout. Its 5,444 source rows end on 2021-08-19.

- Dataset download: <https://www.kaggle.com/api/v1/datasets/download/sheepb/stock-market-dataset-20002021?datasetVersionNumber=1>
- Frozen zip SHA256: `22f61a91843c579577a1757bd31653fd998ba8054723da3d4b41d994cda46373`.
- Extracted ATVI parquet SHA256: `7b77347e5ecada0deb3675257f34b09b39119dc5b5e250043ea91fd623d67395`.
- Metadata SHA256: `d763dcf15eebed98f3a80bfc65d2269c47905825b77e3417fca6498141bbbc3e`.

The full zip was re-hashed, and the extraction record links that zip to the exact ATVI parquet. The original metadata, download record, and extraction record are retained with this package. The new source and the prior Jackson Crow capture both have **Yahoo Finance via yfinance as their upstream provider**. They are different captures of the same provider, not independent price vendors. SEC filings independently verify corporate-action facts and share units; they do not independently verify each daily market price. No Yahoo API requests or rate-limit workarounds were used for this extension.

The local extraction timestamp, 2026-09-06T18:47:25.012402773Z, is retained as the new rows' `downloaded_at` audit field. It is not a claim that the dataset or these verification documents were available to the simulated strategy on each historical date. This is retrospective data remediation within the already-observed research period.

## Primary corporate-action evidence

1. Activision Blizzard 2020 Form 10-K: <https://www.sec.gov/Archives/edgar/data/718877/000162828021002828/atvi-20201231.htm>. Saved as `ATVI-2020-10K.html`, SHA256 `079fa346fae873ef3d050841c7254cfe7fd91f6073d2dc909d7c22019f4571fd`.
2. Activision Blizzard 2021 Q3 Form 10-Q: <https://www.sec.gov/Archives/edgar/data/718877/000162828021021200/atvi-20210930.htm>. Saved as `ATVI-2021-Q3.html`, SHA256 `e99b107be442d5dc77d9e371bad448984562fbece84817e3192e194d83395195`.

Both originals were hash-checked. Plain-text extractions and anchored excerpts are retained in `primary-excerpts.json`.

| Dividend | Declaration | Record date | Payment date | Actual payment evidence |
|---|---|---|---|---|
| $0.41 per share | 2020-02-06 | 2020-04-15 | 2020-05-06 | 2020 10-K confirms $316 million paid |
| $0.47 per share | 2021-02-04 | 2021-04-15 | 2021-05-06 | 2021 Q3 10-Q confirms $365 million paid |

The ex-dates used here are **2020-04-14** and **2021-04-14**. Each is the previous XNYS session before the primary record date under the ordinary T+2 settlement convention then in force. These are also the only material changes in the captured Yahoo `Adj Close / Close` factor during the appended interval. The filings directly state the record and payment dates; they do not directly state the ex-dates in the quoted passages. This distinction is explicit.

The 2020 annual statement of changes in shareholders' equity reports issued shares increasing from 1,197 million at 2019 year-end to 1,203 million at 2020 year-end: employee options add 5 million, restricted stock units add 1 million, and tax surrender rounds to zero at the statement's precision. The 2021 quarterly statement reports 1,206 million issued shares after Q1 (options +1 million, restricted units +4 million, tax surrender −2 million), 1,206 million after Q2, and 1,207 million after Q3 (restricted units +2 million, tax surrender −1 million; options round to zero). Treasury shares remain approximately 429 million throughout. Rounding applies to all these values.

These complete share roll-forwards attribute the changes to employee equity issuance and tax surrender, with no stock-split or reverse-split entry. The Q3 report covers the 2021-08-19 endpoint. Together with the unchanged nominal OHLC overlap, they support using the source's nominal `Close` and `Volume` directly in this bounded extension, without a split multiplier. The later filings are used only to verify historical units, never as point-in-time selection signals or independent sample-out evidence.

## Price and unit construction

The active prefix is `data/research/v04/prices/ATVI-through-2020-04-01.parquet`, SHA256 `c6beda01fad277fa3c202d419180163c816f3daaf54978600fed94eb10d46d7b`. It comprises the original 3,647 rows plus the previously verified 507-row extension. Its final row defines the retained total-return unit basis:

`f(2020-04-01) = adjusted_close / as_traded_close = 1.0133240449687022`.

For each appended date, all four OHLC components come from the same SheepB source row. No prices are mixed between captures. Retain the factor on ordinary days; on an ordinary ex-dividend day use the already-adopted forward total-return convention:

`f_new = f_old × (Close_ex + cash_dividend) / Close_ex`.

Multiply every OHLC component by that date's single factor. Retain `as_traded_close = source Close`, `volume = source Volume`, and `dollar_volume = source Close × source Volume`. Do not use the total-return-adjusted close for the dollar-volume screen. No separate ordinary-dividend cash event is added, so reinvested dividend return is not counted twice. A factor above 1 is a unit basis; it is not additional cash or additional yield.

| Ex-date | Source nominal close | Dividend | New canonical factor | Maximum return identity error |
|---|---:|---:|---:|---:|
| 2020-04-14 | 63.279998779296875 | 0.41 | 1.0198895137811492 | 0 |
| 2021-04-14 | 96.69000244140624 | 0.47 | 1.0248470901527873 | 1.12e-16 |

The row-by-row assertion checks `adjusted_close_today / adjusted_close_previous − 1 = (nominal_close_today + dividend_today) / nominal_close_previous − 1`, with error below 1e-12. The fixed formula is not fitted to improve strategy performance. A constant rescaling of Yahoo's `Adj Close` would differ by up to 9.713055278837146e-5 in relative price (about 0.0097%) over this tail because the dividend adjustment conventions differ. The active prefix's frozen convention is preserved instead of silently switching methods.

The two captures overlap on 507 sessions from 2018-03-28 through 2020-04-01. Recovering nominal OHLC from the existing prefix produces identical source prices within floating-point error (maximum relative error 2.23e-16). There are two volume revisions: 2019-07-18 has 8,158,500 in the retained Jackson Crow capture and 8,157,700 in SheepB; 2019-10-25 has 6,319,800 and 6,320,200 respectively. These are same-upstream capture differences. Neither is applied to the retained prefix.

## Candidate checks and handoff

Candidate: `ATVI-through-2021-08-19.candidate.parquet`.

SHA256: `3ae0974fa6785531839c5743c16243894e5d60ff6cd322577a864e727ea82a74`.

Checks performed by `build_extension.py`:

- 4,503 candidate rows; all 4,154 prefix rows equal in every column after serialization and reload; active source prefix hash unchanged.
- Exactly 349 appended XNYS sessions, 2020-04-02 through 2021-08-19, with no missing or duplicate tail sessions.
- All appended OHLCV values finite and positive; each tail row obeys Low ≤ Open/Close ≤ High; volume is integral.
- Appended nominal close and dollar volume match the source exactly; all four adjusted price components use one source row and one factor.
- A synthetic dimensional check reloads the final parquet factor. 100 nominal shares correspond to 97.57553196066712 adjusted units; nominal and adjusted holdings both value to approximately $8,316.99981689453. A synthetic $1-per-nominal-share conversion produces exactly $100 cash. This is only a unit check; it creates no real corporate action or trading event.

`audit.json` holds the detailed assertions, factors, exact source references, same-provider limitation, and inherited-row issue. `manifest-proposal.json` proposes the repository-relative price path `data/research/v04/prices/ATVI-through-2021-08-19.parquet` and evidence path `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/report.md`, with pinned hashes. It is a proposal only and must be reconciled with the parent's separately audited correction of the inherited 2016-11-25 row before final integration.

The unresolved ATVI interval starts **2021-08-20**, including the eventual terminal acquisition event. All existing unresolved-data gates remain. This extension neither fills that gap nor grants a research PASS. Frozen S500-C0…C4 rules, 10/25 bps costs, the 2026-09-04 cutoff, and V04 legacy records remain untouched.
