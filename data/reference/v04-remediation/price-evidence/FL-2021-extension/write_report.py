from pathlib import Path
import hashlib,json
OUT=Path(__file__).parent
ROOT=Path('/Users/fighting/code/short-hold-momentum')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((OUT/'audit.json').read_text())
text=f'''# Foot Locker historical extension and explicit legacy repairs

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
  `48.59/(48.59+0.31) = {a['missed_dividend']['pre_ex_multiplier']}`. Nominal Close,
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
'''
for ex,amount,record,pay in a['tail_dividends']:
 text+=f'| {ex} | ${amount:.3f} | {record} | {pay} |\n'
text+='''
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

'''
for path in sorted(OUT.rglob('*')):
 if path.is_file() and path.name not in ('report.md','manifest-proposal.json','write_report.py') and path.suffix!='.png':
  text+=f'- `{path.relative_to(OUT)}`: `{sha(path)}`.\n'
(OUT/'report.md').write_text(text)
entry=json.loads((ROOT/'data/reference/v04-remediation/manifest.json').read_text())['price_overrides']['FL']
proposal={
 'ticker':'FL','expected_current_override_path':entry['path'],'expected_current_override_sha256':entry['sha256'],
 'candidate_file':str(OUT/a['repaired_candidate']['file']),
 'price_override':{**entry,'path':'data/research/v04/prices/FL-history-repaired-through-2021-08-19.parquet',
    'sha256':a['repaired_candidate']['sha256'],'last':'2021-08-19','invalid_rows':0,
    'method':'Append 856 whole-source daily rows; explicitly restore 2017-11-08 IEX row and missed 2018-01-18 $0.31 dividend using fixed WIKI total-return convention; raw nominal fields retained.',
    'evidence_path':'data/reference/v04-remediation/price-evidence/FL-2021-extension/report.md',
    'evidence_sha256':sha(OUT/'report.md')},
 'new_corporate_actions':[],'all_unresolved_gates_retained':True,
 'evidence_source_grades_and_quote_conflicts':'See report; bounded unit and cash-dividend verification, not all historical OHLCV certified.'}
(OUT/'manifest-proposal.json').write_text(json.dumps(proposal,indent=2)+'\n')
print(json.dumps({'candidate_sha256':a['repaired_candidate']['sha256'],'report_sha256':sha(OUT/'report.md')},indent=2))
