"""Zero-network, read-only review of existing RSH evidence and raw observations."""
import csv
import hashlib
import json
import re
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
PRE = WORK / 'v04-rsh-identity-preflight'
IDENTITY = WORK / 'v04-rsh-primary-identity'
DIVIDENDS = WORK / 'v04-rsh-dividend-followup'
FIRST, LAST = '2003-12-19', '2011-07-11'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

hash_checks = []
for directory in (IDENTITY, DIVIDENDS):
    for source in json.loads((directory / 'source-index.json').read_text()):
        path = (directory / source['file']).resolve()
        actual = digest(path)
        hash_checks.append(dict(reference_directory=directory.name, file=str(path),
                                url=source.get('url'),
                                source_grade=source.get('source_grade', source.get('source_level')),
                                expected_sha256=source['sha256'], actual_sha256=actual,
                                match=actual == source['sha256']))

preflight = json.loads((PRE / 'audit.json').read_text())
for extension in ('csv', 'parquet'):
    path = Path(preflight['source'][extension + '_path'])
    expected = preflight['source'][extension + '_sha256']
    hash_checks.append(dict(reference_directory=PRE.name, file=str(path),
                            source_grade='Vendor WIKI observations',
                            expected_sha256=expected, actual_sha256=digest(path),
                            match=digest(path) == expected))

raw = pd.read_csv(PRE / 'RSH-WIKI-source.csv', parse_dates=['date']).set_index('date').sort_index()
window = raw.loc[FIRST:LAST].copy()
calendar = xc.get_calendar('XNYS', start=FIRST, end=LAST).sessions_in_range(FIRST, LAST)
if calendar.tz is not None:
    calendar = calendar.tz_localize(None)
missing = calendar.difference(window.index)
extra = window.index.difference(calendar)
bad = ((window[['open','high','low','close','volume']] <= 0).any(axis=1)
       | (window['high'] < window[['open','close','low']].max(axis=1))
       | (window['low'] > window[['open','close','high']].min(axis=1))
       | ~np.isfinite(window.select_dtypes(include='number')).all(axis=1))
factor = window.adj_close / window.close
factor_step = factor / factor.shift(1)
dividend_step = 1 + window['ex-dividend'] / window.close
factor_residual = (factor_step - dividend_step).abs().iloc[1:]
observed_gross_return = window.adj_close / window.adj_close.shift(1)
cash_reinvest_gross_return = (window.close + window['ex-dividend']) / window.close.shift(1)
return_residual = (observed_gross_return - cash_reinvest_gross_return).abs().iloc[1:]
cash = window.loc[window['ex-dividend'] != 0]
all_scale_residuals = {
    column: float((window['adj_' + column] - window[column] * factor).abs().max())
    for column in ('open','high','low','close')
}
amounts = json.loads((DIVIDENDS / 'dividend-evidence.json').read_text())
assert cash.index.strftime('%Y-%m-%d').tolist() == [row['source_WIKI_ex_date'] for row in amounts]
assert cash['ex-dividend'].tolist() == [row['source_WIKI_cash'] for row in amounts]
assert all(row['secondary_date_and_amount_match'] for row in amounts)

fund_checks = []
for anchor in json.loads((PRE / 'existing-primary-fund-price-anchors.json').read_text()):
    path = Path(anchor['source_path'])
    text = re.sub(r'\s+', ' ', path.read_text())
    hash_checks.append(dict(reference_directory=PRE.name, file=str(path),
                            url=anchor['source_url'],
                            source_grade='Fund SEC filing, independent holdings valuation; not issuer corporate-action notice',
                            expected_sha256=anchor['source_sha256'], actual_sha256=digest(path),
                            match=digest(path) == anchor['source_sha256']))
    match = re.search(r'RadioShack Corp\.\s*\.+\s*([\d,]+)\s+([\d,]+)', text)
    assert match
    shares, value = (int(part.replace(',', '')) for part in match.groups())
    date = pd.Timestamp(anchor['date'])
    dated_table_header_present = ('SCHEDULE OF INVESTMENTS' in text and
                                  date.strftime('%B %d, %Y').upper() in text and
                                  'COMMON STOCKS SHARES VALUE' in text)
    nominal = float(window.at[date, 'close'])
    fund_checks.append(dict(date=anchor['date'], shares=shares, reported_value_usd=value,
                            parsed_source_line=match.group(0), dated_table_header_present=dated_table_header_present,
                            implied_price=value / shares, raw_close=nominal,
                            adjusted_close_not_nominal=float(window.at[date, 'adj_close']),
                            total_rounding_difference_usd=nominal * shares - value,
                            passes_integer_dollar_rounding=abs(nominal * shares - value) <= 0.5,
                            file=str(path), source_sha256=digest(path)))

quarter_checks = []
quarter_text = re.sub(r'\s+', ' ', (IDENTITY / '2010-SEC-10K.indexed.txt').read_text())
with (IDENTITY / 'SEC-2009-2010-quarter-price-check.csv').open() as handle:
    saved_quarters = list(csv.DictReader(handle))
for row in saved_quarters:
    quarter = pd.Period(row['quarter'], freq='Q')
    section = window.loc[quarter.start_time:quarter.end_time]
    high, low = float(section.high.max()), float(section.low.min())
    date_label = quarter.end_time.strftime('%B %d, %Y')
    # The year-end rows include dollar signs; other quarters omit them.
    pattern = (re.escape(date_label) + r'\s+(?:\$\s*)?(' + re.escape(row['SEC_high']) +
               r'0?)\s+(?:\$\s*)?(' + re.escape(row['SEC_low']) + r'0?)\s')
    primary_table_pair_present = re.search(pattern, quarter_text) is not None
    quarter_checks.append(dict(quarter=row['quarter'], issuer_high=float(row['SEC_high']),
                               issuer_low=float(row['SEC_low']), recomputed_raw_high=high,
                               recomputed_raw_low=low, primary_table_pair_present=primary_table_pair_present,
                               exact_match=(high == float(row['SEC_high']) and low == float(row['SEC_low']))))

write_json('source-hash-review.json', hash_checks)
write_json('nominal-price-anchors.json', fund_checks)
write_json('quarter-price-review.json', quarter_checks)
write_json('window-and-total-return-review.json', dict(
    window=[FIRST,LAST], research_key='RSHCQ', actual_historical_symbol='RSH',
    source_archive_rows=len(raw), window_rows=len(window), expected_sessions=len(calendar),
    missing_sessions=missing.strftime('%Y-%m-%d').tolist(), extra_sessions=extra.strftime('%Y-%m-%d').tolist(),
    duplicated_dates=int(window.index.duplicated().sum()), invalid_ohlcv_rows=int(bad.sum()),
    nonunit_splits=int((window.split_ratio != 1).sum()),
    raw_and_adjusted_volume_identical=bool(window.volume.equals(window.adj_volume)),
    cash_dates=cash.index.strftime('%Y-%m-%d').tolist(), cash_amounts=cash['ex-dividend'].tolist(),
    factor_at_start=float(factor.iloc[0]), factor_at_end=float(factor.iloc[-1]),
    max_factor_step_residual=float(factor_residual.max()),
    max_common_ohlc_factor_residual=all_scale_residuals,
    max_daily_total_return_gross_residual=float(return_residual.max()),
    dividend_convention='Adjusted close gross return equals (current nominal close + same-date cash dividend) / prior nominal close; nominal closing-price reinvestment convention.',
    later_actions_included_in_window_cash=False,
    total_return_audit_is_not_a_claim_of_actual_pay_date_cash_reinvestment=True,
    application_candidate_read=False, generated_price_rows=0,
))
assert all(item['match'] for item in hash_checks)
assert len(window) == 1902 and len(missing) == len(extra) == 0
assert not bad.any() and not window.index.has_duplicates
assert (window.split_ratio == 1).all()
assert factor_residual.max() < 1e-12 and return_residual.max() < 1e-12
assert all(item['passes_integer_dollar_rounding'] and item['dated_table_header_present'] for item in fund_checks)
assert all(item['exact_match'] and item['primary_table_pair_present'] for item in quarter_checks)
summary = dict(status='NO_OBSERVED_EVIDENCE_CONFLICT_WITHIN_BOUNDED_WINDOW',
               network_requests=0, repo_writes=0, generated_price_rows=0,
               hash_references_checked=len(hash_checks),
               distinct_hashed_files=len({item['file'] for item in hash_checks}),
               fund_anchors_matched=len(fund_checks), issuer_quarters_matched=len(quarter_checks),
               source_window_rows=len(window), cash_events=len(cash),
               max_factor_step_residual=float(factor_residual.max()),
               max_daily_total_return_gross_residual=float(return_residual.max()),
               actual_fixed_strategy_exit_window_proven=False,
               canonical_candidate_audited=False,
               recommendation='Evidence sufficient to construct and review a research-only canonical series within the exact window; application still requires candidate and actual-path boundary checks.')
write_json('checks.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
