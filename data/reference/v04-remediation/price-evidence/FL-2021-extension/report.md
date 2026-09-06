# Foot Locker historical extension and explicit legacy repairs

Status: reviewed bounded data repair, ready for the next fixed research snapshot;
not a full research PASS. Candidate has **4,503 XNYS sessions, 2003-10-01 through
2021-08-19**, with no missing/duplicate sessions or invalid physical OHLCV rows.
The original WIKI file and an extension-only intermediate are preserved.

## Changes and source contract

Append 856 whole OHLCV rows from frozen SheepB v1, Yahoo/yfinance upstream.
Source symbol FL and company Foot Locker agree with issuer common-stock/NYSE
identity (CIK 850209). The source archive hash and extracted ticker hash are in
`audit.json`; the frozen publisher metadata explicitly identifies yfinance.
No Yahoo request, registration, paid data or broad market scan was used.

Keep the nominal source Close and share Volume separate from total-return
prices. Dollar volume is nominal Close times Volume. Starting at the retained
2018-03-27 factor of 1, update the factor only on supported ordinary ex-dates:
`f_new = f_old * (Close_ex + dividend) / Close_ex`. Multiply all four OHLC fields
from the same source row by this factor. Do not import a newer Adj Close scale,
mix vendors within a row, or add a second ordinary-dividend cash event.

Correct two legacy defects explicitly in version 2:

- The missing 2017-11-08 row is supplied as the complete IEX row: O29.07,
  H29.97, L28.42, C29.88, V3,012,717. Yahoo agrees on prices within floating-point
  precision; its volume differs by the amount recorded in the audit. Use all
  IEX fields together, with the unchanged neighboring canonical factor of 1.
- WIKI omitted the $0.31 ordinary dividend with record date 2018-01-19 and
  payable date 2018-02-02. The issuer's 2017-11-15 release directly confirms
  amount/record/pay; the prior XNYS session is 2018-01-18 under the then-current
  ordinary T+2 convention, also corroborated by provider factors and dividend
  histories. Multiply only pre-ex OHLC by
  `48.59/(48.59+0.31) = 0.9936605316973415`. Nominal Close,
  Volume and dollar volume remain unchanged. All existing rows on/after the
  ex-date are unchanged, including the March 27 anchor and appended tail.

## Dividend evidence and exact dates

The issuer-hosted 2020 annual PDF was downloaded successfully and its relevant
pages were rendered and visually checked: PDF page 36 / Form 10-K page 17 shows
annual per-share dividends of **$1.24 (2017), $1.38 (2018), $1.52 (2019), $0.70
(2020)**. PDF page 58 / Form 10-K page 39 contains the complete equity rollforward;
the report's financing discussion confirms $0.70 was both declared and paid in
fiscal 2020. Annual totals include January payments in the appropriate fiscal
year, not the calendar year.

Issuer releases confirm the increase to $0.345 for 2018, the January 2019
$0.345 payment, July 2019 $0.38, the April/May 2020 $0.40 payment, suspension
of the second-quarter 2020 dividend, reinstatement of $0.15 for October 2020,
and $0.20 in 2021. The successful complete issuer-hosted **RTF**, not PDF, of
the 2021Q2 10-Q confirms $0.40 paid/declared for the first half of 2021.

Individual ex/record/pay dates that are not explicitly quoted in an issuer
release use the saved secondary histories (StreetInsider/RTTNews and
DividendHistory), cross-checked against the complete provider-factor event
calendar and ordinary T+2 exchange sessions. This is a stated source grade,
not a claim that each exact ex-date was independently published by the SEC.
Amounts are fixed from issuer records and annual reconciliation, never solved
backward from adjustment factors. Trendlyne rounds $0.345 to $0.34 and omits
the April 2020 payment; those values were not used. Investing's displayed dates
are a day earlier than the corroborated calendar and are not used.

| Ex-date | Dividend per share | Record date | Payable date |
|---|---:|---|---|
| 2018-04-19 | $0.345 | 2018-04-20 | 2018-05-04 |
| 2018-07-19 | $0.345 | 2018-07-20 | 2018-08-03 |
| 2018-10-18 | $0.345 | 2018-10-19 | 2018-11-02 |
| 2019-01-17 | $0.345 | 2019-01-18 | 2019-02-01 |
| 2019-04-17 | $0.380 | 2019-04-18 | 2019-05-03 |
| 2019-07-18 | $0.380 | 2019-07-19 | 2019-08-02 |
| 2019-10-17 | $0.380 | 2019-10-18 | 2019-11-01 |
| 2020-01-16 | $0.380 | 2020-01-17 | 2020-01-31 |
| 2020-04-16 | $0.400 | 2020-04-17 | 2020-05-01 |
| 2020-10-15 | $0.150 | 2020-10-16 | 2020-10-30 |
| 2021-01-14 | $0.150 | 2021-01-15 | 2021-01-29 |
| 2021-04-15 | $0.200 | 2021-04-16 | 2021-04-30 |
| 2021-07-15 | $0.200 | 2021-07-16 | 2021-07-30 |

## Nominal share units and limits

The 2020 annual statement reconciles issued shares (thousands):
121,262 +93 +175 -8,597 =112,933 in 2018;
112,933 +89 +187 -9,021 =104,188 in 2019;
104,188 +121 +297 -913 =103,693 in 2020.
Changes reflect employee/director issuance and treasury retirement, with no
split item. The complete 2021Q2 issuer RTF reconciles first-half issued shares
103,693 +479 +344 =104,516 and treasury shares -74 -195 -746 +301 =-714.
Issued and outstanding shares are distinct; September 3 cover outstanding
shares are 103,807,679.

The full share table ends July31; the September3 cover is subsequent scale
corroboration, not an August transaction ledger. Together with provider
documentation and 3,646 nominal-close overlaps whose yearly median ratios are
1 in all 16 years, these facts support one nominal share unit through the
August19 archive endpoint. This is not an official exhaustive split ledger.

Unit agreement does not establish identical prices at every historical point:
old nominal Open differs from Yahoo by as much as 16.45%, High by 14.74%, and
Close by 0.84%; the largest observations remain listed in
`largest-retained-quote-differences.json`. Neither vendor is silently chosen
to improve a return; existing prices are retained apart from the explicitly
documented missing-row and missed-dividend fixes. Quote conflicts remain
visible and are not a full certification of old daily data. The largest price conflict, 2017-05-19, was separately checked:
IEX matches WIKI's entire OHLC (60.50/61.40/58.13/58.72); Yahoo's Open and
High both equal the previous Yahoo close 70.4499969. Preserve the independently
corroborated WIKI row. Vendor volumes differ and remain unchanged; see
`retained-2017-05-19-review.json`. Other quote conflicts are not thereby resolved.
Multiple dated
Yahoo captures are not independent market-data vendors. Reported share volume
is preserved; exact venue/consolidation scope has not been independently audited.

## Verification and application boundary

All 856 new dates equal the XNYS tail calendar. Every tail return reproduces
`(Close_today + D_today)/Close_previous - 1` to less than 1e-12. Fiscal dividend
totals reconcile, the old missing dividend reproduces the same identity,
nominal/volume fields are unchanged for every old row, and both parquet
round-trips are checked. Final history contains every expected XNYS session.
The source old file's hash remains unchanged.

The historical member period ends 2019-08-08; this bounded extension supplies
that missing period and later quotes for scheduled exits. It does not invent
prices after 2021-08-19 or a 2025 terminal transaction, and it does not remove
any global PRICE_REPAIR_EVIDENCE item, alter candidates/costs/cutoff, or certify
independent out-of-sample performance. All data remain already-observed research.

Supporting file hashes:

- `01-dividend-discovery.json`: `cc55aefb07e5d212feb558bdb9c368472dadbdb1aa42b7d53400f8e8bd1b1ded`.
- `02-sec-filings.json`: `79ce8e8c6041c7720d0c388ab3e327ff987fd7273c2f6da117c4b52762a88cbd`.
- `03-issuer-dividends.json`: `d62292db5b9d8d0cf1a6d20c0c8660541f8b97c4fbb3347f8c1e59dae4eb1378`.
- `04-FL-2020-10K.html`: `46847ca89f9563fd48436dab17674163fafd4f700e18bc0023f32ae886016439`.
- `05-FL-2021-10K.html`: `c531152c94c893b04661889fea41a17fcb72de2d6902f5eb97483e8f7e327410`.
- `06-issuer-annual.json`: `99e9ae74b506e3cb16420a321ad9fad26d4161850eb7c2d49c37a642cc4db2a3`.
- `07-issuer-2021-dividend.json`: `a857e46ae93354e44b286bfb54df3f57ef4e7fd14a22e1e910c85b7c3a556743`.
- `08-issuer-2020-dividend.json`: `da7fb64c9cbbcd9252e880e0d3bac78cf8a6adaaa4ea81987e41f80fd2fb5b56`.
- `09-issuer-2020-annual.pdf`: `96f87144b12cb476652a08d023e698611bb2db7f9c82de30ac5bc9d485f53b52`.
- `09-issuer-2020-annual.txt`: `fca378735f195cd6792fcbfcd58a0cf413cabb2dd3ba0d41183c00fd22aa3358`.
- `11-issuer-jan2018.json`: `7910d81b7d5def887326d4ab36a19f819e2352207b39157382a7be430e37deb7`.
- `12-issuer-apr2019.json`: `1b3480f2d72d3a8fcb2e79da43adfc67d4e659a30d68e431649cae086afb92f4`.
- `FL-extended-prefix-unchanged.parquet`: `0d3d3e45f7a71bef2bed16d538ec22807ec8f6457bdacdd98796dca1ff220307`.
- `FL-history-repaired-through-2021-08-19.parquet`: `33946ddd8eac2b907e4e82f75b5177d08fa3cb405e8e46c7fafc646fb9fd8a2f`.
- `IEX-FL.csv`: `fb58716cd2188dcdbea9fbfd5b1dc9d883f2a5d18586830587b8d1f6d4c576e7`.
- `audit.json`: `a2ade38ccedc4e43a3f28777127c6bc9fb8f12d97e46a1b07d8479c397a29044`.
- `build_candidate.py`: `e1b00a54ca25c0a39e6922f9435345c61abfb8c824b17a7111eccc409fa33e38`.
- `fetch_filings.py`: `07f3a91fa58b3b294340e4cba1d411146044df144b10d0faa739ea1c0aa8e791`.
- `fetch_issuer_reports.py`: `13c5315cd7e7e637d318b11782bbc6036bdb86938c67169e77a55a660c1c907f`.
- `filings-retrieval.json`: `a90ad9a390b87619433f6a7229ee72ec9fb7fb2ee724249d10815ddddb9573a1`.
- `issuer-reports-retrieval.json`: `a47e33cf524ce8150804243ffa93b36b47f214f2ff5f7b580a627f5b42535efc`.
- `largest-retained-quote-differences.json`: `b4ed748aad01e36f6c173dc410e74b8dc83f3d43cbcbdc8bb4db70b9fe99bed0`.
- `primary-annual-excerpts.json`: `bcb03a5bad58fddff76e29cbc72a39a9405371673090839e32ab2cf47bcc86df`.
- `primary-followup/01-search.json`: `08fd8ff2286c622622b712ca48eedc1c02f67aecea078c92409311d49c4d109f`.
- `primary-followup/02-search.json`: `33bca84489b4e7b469ea55dd62c23c422df94c4deb1dc2a17e842ce850385127`.
- `primary-followup/03-FL-2021Q2-normalized.txt`: `994f9e1a36b57330d10ec0f5138beae17bb63e11851fef258a0b676a874c3d00`.
- `primary-followup/03-FL-2021Q2-retrieval.json`: `adde13d8a36f54bdfa59ca6e5456dd3b444a471109ff16840712f3363b03f65c`.
- `primary-followup/03-FL-2021Q2.body`: `a06ac2f937c9973c593ab91537e7feba6fbd4ce61c3060a90e00a81018785827`.
- `primary-followup/03-FL-2021Q2.txt`: `0f5b0a2ea9fc277c3027981ce905e3162423a14ef0c04a06bc2989bd7fce04d1`.
- `primary-followup/2017Q4-company-release-prnewswire-indexed.txt`: `1787cfee26a76b1bf4da61f7d42a28714abe0047ca742553f50fa98410da4778`.
- `primary-followup/2017Q4-issuer-dividend-indexed.txt`: `85532cd0da4f234105180f0e0b38f2fffaf7ac8c607fb8887af90bb13277f4cb`.
- `primary-followup/2021Q2-equity-excerpt.txt`: `58c3c54506fecc9a9f814f6cd3de3de7bbaf5c50029a573780b2567dba0ffd42`.
- `primary-followup/2021Q2-issuer-indexed-1.txt`: `512b13607ff6fe9137c48bdbc2e6920e1fdb6ef6f125c2631b8d20b015a7c2ed`.
- `primary-followup/2021Q2-issuer-indexed-2.txt`: `a5f6ab24ecd6b54c499c6e9a183f6849543ae86614b77adacd06afc37f52f1e0`.
- `primary-followup/facts.json`: `cf275ffc25f171a0ecba9840225e4ccbbd0852019b5055cdd2479408eff07377`.
- `primary-followup/request-log.json`: `d5ad0c9ea0635e92f68c5a6b17f01d32ed32fc4c1006d6bf73ac0723f2a0b824`.
- `retained-2017-05-19-review.json`: `2d5018eb1ac33c485d3a22324d9941c678452bff51916a0552cfee9cbec8fc63`.
