# TIE review-only candidate audit

**Status: UNVERIFIED_GAPS; eligible_for_freeze=false.**

2276 XNYS sessions, 2003-12-19 through 2013-01-04; 2274 complete candidate rows, 2 wholly unknown rows.
Unknown dates: 2005-03-14 (SEC/Yahoo closing-price conflict) and 2011-02-17 (no verified OHLCV).

Source counts: cache=1551, investing=597, workbook=126.
Whole rows follow cache before 2010-02-22, then workbook, then Investing. Rounded volume provenance is retained per row.

## Corporate actions and price bases

Verified action evidence supplies five historical split events and twelve $0.075 common cash dividends. The 2003 reverse split precedes this candidate and is not applied again.
Total-return OHLC uses strictly-future cash factors 1 - dividend / preceding-session split-only close. All 12 denominators are present. Split-only OHLC, nominal/as-traded OHLC, volume, factors and dollar_volume are exposed for audit.
Early vendor volume share basis remains unverified. Its dollar_volume uses the requested split-only close × vendor volume convention, explicitly labeled ASSUMED_VOLUME_SPLIT_BASIS. No liquidity gate is certified.

## Existing SEC quarterly checks

40 filing-quarter comparisons: 33 complete, 4 partial, 3 with no candidate data.
11 complete-quarter extrema mismatches remain at $0.011 tolerance. See SEC-quarter-range-checks.csv for every comparison and source/basis.
Each of the five SEC tables explicitly describes high and low sales prices, so daily highs/lows are compared, not extrema of daily closes. Report split bases are matched with multipliers 8 (2004 annual), 2 (2005 annual), and 1 (2006/2010/2011 annual).
Quarterly extrema agreement is a narrow corroboration; it is not proof that every daily bar is correct. Partial quarters cannot be certified from extrema.

| Filing | Quarter | SEC H/L | Candidate H/L on SEC basis |
|---|---|---|---|
| 2004 | 2004Q2 | 21.58 / 14.35 | 21.5800 / 15.1184 |
| 2004 | 2004Q4 | 26.60 / 18.51 | 26.6000 / 19.3000 |
| 2005 | 2005Q2 | 14.38 / 7.76 | 14.3750 / 7.8126 |
| 2005 | 2005Q3 | 21.20 / 12.32 | 21.2000 / 12.5650 |
| 2005 | 2004Q2 | 5.40 / 3.59 | 5.3950 / 3.7796 |
| 2005 | 2004Q4 | 6.65 / 4.63 | 6.6500 / 4.8250 |
| 2006 | 2005Q2 | 7.19 / 3.87 | 7.1875 / 3.9063 |
| 2006 | 2005Q3 | 10.60 / 6.16 | 10.6000 / 6.2825 |
| 2010 | 2010Q4 | 21.10 / 16.60 | 20.8800 / 16.6500 |
| 2011 | 2010Q4 | 21.10 / 16.60 | 20.8800 / 16.6500 |
| 2011 | 2011Q2 | 20.39 / 16.03 | 20.3600 / 16.0500 |

## Merger boundary

The SEC 8-K confirms legal merger on 2013-01-07 at $16.50 per remaining common share. January 8 is merger announcement and NYSE Form 25 date. No intraday effective/suspension time or cash-payment date is established.
January 4 is the last complete observed OHLCV bar. January 7 Investing OHLC exists but volume is missing, so it is retained separately and excluded from the candidate. This endpoint does not assert that January 4 was the exchange’s final tradable session.

## Reproduction and integrity

Run with `/Users/fighting/code/short-hold-momentum/.venv/bin/python /Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-corporate-actions/tie-candidate/generate_candidate.py`.
Frozen inputs, row/source-segment provenance, action denominators, source excerpts, input/output SHA256 hashes, and gap reports are saved in this directory. No main code, manifest, or raw cache is written.
Main source hashes unchanged during generation: True.
Candidate approval requires parent review of recovered intervals, daily-source conflicts, volume basis and merger boundary; it cannot freeze a winner.
