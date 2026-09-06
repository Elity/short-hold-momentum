# ATVI 2017-08-07 single-day evidence and proposal

The day is absent in the original WIKI_PRICES.csv, its extracted parquet, and the current research override. No existing raw Yahoo ATVI cache is available. The defect is an upstream absent day, not an extraction or OHLC-validation deletion. The inspected pinned GitHub mirror repeats the same absence.

Independent recovery: Cam Nugent's Kaggle `camnugent/sandp500`, version 4, updated 2018-02-10. Direct Kaggle metadata identifies IEX as upstream; the included acquisition script calls `web.DataReader(stock,'iex', ...)`. ZIP/member hashes are fixed in the audit. A mismatched cached Browse response was excluded.

| Date | Open | High | Low | Close | Volume in shares | Dollar volume |
|---|---:|---:|---:|---:|---:|---:|
| 2017-08-07 | 62.14 | 62.85 | 61.80 | 62.51 | 7,287,073 | 455514933.23 |

Use the entire IEX row. The volume is the dataset's reported share count, not a rounded K/M display. Its precise venue/consolidation scope is not independently proven. WIKI and IEX volume differ: median absolute relative difference 1.3375%, maximum 66.8804% across 42 neighboring July-August overlaps. OHLC all match within $0.011 on 39/42 dates; conflicts are 2017-07-06, 2017-07-31, and 2017-08-01. The overlap CSV preserves each comparison. This does not approve all rows of either provider.

The current WIKI anchor ends 2018-03-27; there is no later recorded split/dividend after this target date, and all later raw/adjusted OHLC agree. The inserted day's factor is therefore 1 in that existing anchor. `as_traded_close=62.51`; `dollar_volume=62.51*7287073`. No corporate-action cash posting is involved.

`ATVI-with-2017-08-07.candidate.parquet` contains exactly one extra row. Every old row is unchanged; OHLC consistency, uniqueness, Parquet round-trip and input hashes pass. `ATVI-price-repair-proposal.json` supplies the work-only manifest proposal. No main data, source code, or manifest was edited.

The same downloaded ZIP contains no BCR file and zero BCR rows in all_stocks_5yr.csv, so it cannot supply BCR 2017-11-08. This local check made no new network request.

ATVI external requests were bounded at eight: two searches, GitHub commit lookup, pinned GitHub CSV, independent Kaggle ZIP, one provenance search, rejected Kaggle Browse, and direct Kaggle metadata. No further external lookup was made.
