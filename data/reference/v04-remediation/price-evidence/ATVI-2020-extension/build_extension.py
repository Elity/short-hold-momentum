"""Audited ATVI tail extension. Writes only this work directory."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import re

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from shm.v03.corporate_actions import AdjustmentBasis, CorporateAction, convert_position
from shm.v03.strategy import PositionState

ROOT = Path('/Users/fighting/code/short-hold-momentum')
WORK = Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work')
SOURCES = WORK / 'v04-source-options-next'
OUT = SOURCES / 'ATVI-2020-extension'
BASE = ROOT / 'data/research/v04/prices/ATVI-two-days-repaired.parquet'
SOURCE = SOURCES / '08-jackson-atvi-sample.body'
ANCHOR = pd.Timestamp('2018-03-27')
END = pd.Timestamp('2020-04-01')
DIVIDENDS = {'2018-03-28': .34, '2019-03-27': .37}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stats(series):
    series = pd.Series(series).dropna()
    return {'rows': len(series), 'median': float(series.median()), 'max': float(series.max()),
            'p95': float(series.quantile(.95)), 'over_1bp': int(series.gt(.0001).sum())}

meta = json.loads((SOURCES / '08-jackson-atvi-sample.meta.json').read_text())
assert sha(SOURCE) == meta['sha256']
metadata = json.loads((SOURCES / '03-jacksoncrow-metadata.body').read_text())
assert metadata['currentVersionNumber'] == 2
assert 'Close** - close price adjusted for splits' in metadata['description']
symbols = pd.read_csv(SOURCES / '10-jackson-symbols.body')
symbol = symbols.loc[symbols.Symbol.eq('ATVI')].iloc[0]
assert symbol['Security Name'] == 'Activision Blizzard, Inc - Common Stock' and symbol['ETF'] == 'N'
active = json.loads((ROOT / 'data/reference/v04-remediation/manifest.json').read_text())['price_overrides']['ATVI']
assert ROOT / active['path'] == BASE and active['sha256'] == sha(BASE)
base = pd.read_parquet(BASE)
assert base.date.max() == ANCHOR and base.date.is_monotonic_increasing and base.date.is_unique
raw = pd.read_csv(SOURCE, parse_dates=['Date']).set_index('Date').sort_index()
raw['provider_factor'] = raw['Adj Close'] / raw.Close
assert raw.index.is_unique and raw.index.max() == END
tail = raw.loc[(raw.index > ANCHOR) & (raw.index <= END)].copy()
calendar = xcals.get_calendar('XNYS', start='2018-03-01', end='2020-04-10')
expected = calendar.sessions_in_range(ANCHOR, END)[1:].tz_localize(None)
assert tail.index.equals(expected)
assert np.isfinite(tail[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]).all().all()
assert tail[['Open', 'High', 'Low', 'Close']].gt(0).all().all() and tail.Volume.ge(0).all()
assert tail.High.ge(tail[['Open', 'Close', 'Low']].max(axis=1)).all()
assert tail.Low.le(tail[['Open', 'Close', 'High']].min(axis=1)).all()

# The retained prefix and all historical patches keep their existing units.
# Tail rows are kept whole from one source and use the same precise total-return
# convention as WIKI: at an ex-date, f_new = f_old * (P_ex + D) / P_ex.
# A factor above one is a forward-adjusted unit, not an added cash transaction.
base_factor = float(base.iloc[-1].close / base.iloc[-1].as_traded_close)
factor = base_factor
factor_by_date, dividend_checks = [], []
prior_adjusted, prior_nominal = float(base.iloc[-1].close), float(base.iloc[-1].as_traded_close)
for date, row in tail.iterrows():
    dividend = DIVIDENDS.get(str(date.date()), 0.)
    if dividend:
        factor *= (float(row.Close) + dividend) / float(row.Close)
    adjusted_close = float(row.Close) * factor
    calculated = adjusted_close / prior_adjusted - 1
    economic = (float(row.Close) + dividend) / prior_nominal - 1
    assert abs(calculated - economic) < 1e-12
    if dividend:
        dividend_checks.append({'date': str(date.date()), 'cash_dividend': dividend,
                               'nominal_close': float(row.Close), 'factor': factor,
                               'adjusted_return': calculated, 'economic_return': economic,
                               'absolute_error': abs(calculated - economic)})
    factor_by_date.append(factor)
    prior_adjusted, prior_nominal = adjusted_close, float(row.Close)
tail['canonical_factor'] = factor_by_date
extension = pd.DataFrame({
    'date': tail.index,
    'open': tail.Open.to_numpy() * tail.canonical_factor.to_numpy(),
    'high': tail.High.to_numpy() * tail.canonical_factor.to_numpy(),
    'low': tail.Low.to_numpy() * tail.canonical_factor.to_numpy(),
    'close': tail.Close.to_numpy() * tail.canonical_factor.to_numpy(),
    'volume': tail.Volume.to_numpy(dtype=float),
    'as_traded_close': tail.Close.to_numpy(),
    'dollar_volume': (tail.Close * tail.Volume).to_numpy(),
    'adjusted': True,
    'source': 'Yahoo/yfinance via frozen Jackson Crow Kaggle v2; whole source OHLCV rows forward-adjusted from 2018-03-27 using verified dividends and WIKI total-return convention',
    'downloaded_at': pd.Timestamp(meta['requested_at_utc']),
})[base.columns]
candidate = pd.concat([base, extension], ignore_index=True)
path = OUT / 'ATVI-through-2020-04-01.candidate.parquet'
candidate.to_parquet(path, index=False)
back = pd.read_parquet(path)
pd.testing.assert_frame_equal(back.iloc[:len(base)].reset_index(drop=True), base.reset_index(drop=True))
assert back.date.max() == END and back.date.is_unique
assert sha(BASE) == active['sha256']

overlap = base.copy().set_index('date').join(raw, how='inner')
# WIKI confirms the latest historical split was 2008-09-08. Comparing later
# Close to nominal WIKI close avoids pretending earlier split-adjusted Close is
# an as-traded dollar price. SEC equity roll-forwards cover the extension period.
comparable = overlap.loc['2008-09-08':].copy()
factor_old = comparable.close / comparable.as_traded_close
differences = {}
largest = []
for old_field, new_field in [('open', 'Open'), ('high', 'High'), ('low', 'Low'), ('close', 'Close')]:
    nominal_old = comparable[old_field] / factor_old
    relative = (comparable[new_field] / nominal_old - 1).abs()
    differences[new_field] = stats(relative)
    for day in relative.nlargest(3).index:
        largest.append({'date': str(day.date()), 'field': new_field, 'old_nominal': float(nominal_old.loc[day]),
                        'new_split_adjusted': float(comparable.loc[day, new_field]), 'relative_difference': float(relative.loc[day])})
volume_difference = stats((comparable.Volume / comparable.volume - 1).abs())
stable = comparable.loc['2017-03-28':'2018-03-27']
basis_ratios = (stable.close / stable.as_traded_close) / stable.provider_factor
provider_anchor = float(raw.loc[ANCHOR, 'provider_factor'])
provider_on_anchor_units = tail['Adj Close'] / provider_anchor * base_factor
policy_difference = (extension.close.to_numpy() / provider_on_anchor_units.to_numpy() - 1)

# Re-read and invoke the real conversion helper in an explicitly synthetic,
# one-dollar-per-nominal-share unit check. This event is not exported as a real
# ATVI corporate action and is never supplied to research/paper decisions.
last = back.iloc[-1]
reloaded_factor = float(last.close / last.as_traded_close)
nominal_shares = 100.
adjusted_quantity = nominal_shares / reloaded_factor
unit_action = CorporateAction('SYNTHETIC-UNIT-CHECK', 'ATVI', '2020-04-01', '2020-04-01',
                              '2020-04-01', '2020-04-02', 1., 'synthetic unit check only', 'terminal_before_action')
unit_result = convert_position(PositionState(adjusted_quantity, float(last.close), '2020-04-01', float(last.close)),
                               unit_action, source_basis=AdjustmentBasis(reloaded_factor, '2020-04-01', 'candidate round-trip factor'))
assert abs(unit_result.cash_delta - 100.) < 1e-12
assert abs(adjusted_quantity * float(last.close) - nominal_shares * float(last.as_traded_close)) < 1e-10

annual = (OUT / 'ATVI-2019-10K.txt').read_text()
quarter = (OUT / 'ATVI-2020-Q1.txt').read_text()
excerpts = {}
for name, text, anchors in [
    ('2019-10K', annual, ['Year Per Share Amount Record Date Dividend Payment Date',
                         'CONSOLIDATED STATEMENTS OF CHANGES IN SHAREHOLDERS']),
    ('2020-Q1', quarter, ['number of shares of the registrant’s Common Stock outstanding at April 28, 2020',
                          'CONSOLIDATED STATEMENTS OF CHANGES IN SHAREHOLDERS',
                          'On February 6, 2020, our Board of Directors declared a cash dividend']),
]:
    excerpts[name] = []
    for anchor in anchors:
        i = text.find(anchor)
        assert i >= 0, anchor
        excerpts[name].append(text[max(0, i - 70):i + (3200 if 'STATEMENTS' in anchor else 1200)])
(OUT / 'primary-excerpts.json').write_text(json.dumps(excerpts, indent=2, ensure_ascii=False) + '\n')
audit = {
    'scope': 'Append only 2018-03-28 through 2020-04-01. Do not repair, rewrite or rescale the retained prefix.',
    'inputs': {str(p): sha(p) for p in [BASE, SOURCE, SOURCES / '08-jackson-atvi-sample.meta.json',
                                      SOURCES / '03-jacksoncrow-metadata.body', SOURCES / '10-jackson-symbols.body',
                                      OUT / 'ATVI-2019-10K.html', OUT / 'ATVI-2020-Q1.html']},
    'candidate': {'path': str(path), 'sha256': sha(path), 'rows': len(candidate), 'prefix_rows': len(base),
                  'new_rows': len(extension), 'first': str(candidate.date.min().date()), 'last': str(candidate.date.max().date()),
                  'prefix_round_trip_equal': True, 'original_base_file_unchanged': True},
    'tail_quality': {'expected_xnys_sessions': len(expected), 'missing_sessions': [], 'duplicate_dates': 0,
                     'invalid_ohlcv_rows': 0, 'zero_volume_rows': int(tail.Volume.eq(0).sum()),
                     'first_source_date': str(tail.index.min().date()), 'last_source_date': str(tail.index.max().date())},
    'identity': symbol.where(pd.notna(symbol), None).to_dict(),
    'nominal_basis_evidence': {
        'source_metadata': 'Close is split-adjusted; Volume is shares traded. It is not generally safe to treat all historical Close as nominal.',
        'scope_verified': '2018-03-28 through 2020-04-01 only',
        'source_has_embedded_action_table': False,
        'sec_share_rollforwards_millions': {'2017_end_issued': 1186, '2018_employee_options': 5,
            '2018_rsus': 2, '2018_tax_surrender': -1, '2018_end_issued': 1192,
            '2019_employee_options': 4, '2019_rsus': 2, '2019_tax_surrender': -1, '2019_end_issued': 1197,
            '2020_q1_employee_options': 1, '2020_q1_rsus': 1, '2020_q1_tax_surrender_rounded': 0,
            '2020_q1_end_issued': 1199, 'treasury_shares_unchanged': 429,
            '2020_04_28_outstanding_actual': 770485455},
        'no_split_conclusion': 'The audited annual and quarterly share roll-forwards reconcile issuance/surrender without split or reverse-split activity. Post-2008 overlap Close is on the same dollar scale as WIKI nominal close, excluding a later cumulative split factor. Together these support no split restoration in this extension; they do not validate early pre-2008 CSV nominal prices.',
    },
    'overlap': {'period': ['2008-09-08', '2018-03-27'], 'rows': len(comparable),
                'price_relative_difference': differences, 'volume_relative_difference': volume_difference,
                'largest_price_discrepancies': largest,
                'handling': 'All overlapping WIKI/patch rows stay unchanged; vendor differences are reported, not averaged or replaced.'},
    'adjustment_basis': {'anchor': str(ANCHOR.date()), 'anchor_old_factor': base_factor,
                         'anchor_source_factor': provider_anchor,
                         'old_to_new_adjusted_basis_ratio_recent_overlap': {
                             'period': ['2017-03-28', '2018-03-27'], 'rows': len(stable),
                             'median': float(basis_ratios.median()), 'min': float(basis_ratios.min()),
                             'max': float(basis_ratios.max())},
                         'canonical_formula': 'f_t = f_previous * (Close_t + dividend_t) / Close_t on ex-date; otherwise unchanged. All OHLC of that source row use the same f_t.',
                         'cash_events_exported': 0, 'dividend_checks': dividend_checks,
                         'first_tail_factor': float(tail.canonical_factor.iloc[0]), 'last_tail_factor': reloaded_factor,
                         'vs_vendor_AdjClose_rescaled_to_anchor': {'maximum_absolute_relative_difference': float(np.abs(policy_difference).max()),
                                                                  'last_relative_difference': float(policy_difference[-1])},
                         '2020_declared_dividend_excluded': 'The $0.41 dividend has record date 2020-04-15 and payment date 2020-05-06, after this source endpoint; no return or cash is credited early.'},
    'round_trip_unit_check': {'synthetic_only': True, 'nominal_shares': 100, 'adjusted_quantity': adjusted_quantity,
                              'factor': reloaded_factor, 'adjusted_market_value': adjusted_quantity * float(last.close),
                              'nominal_market_value': 100 * float(last.as_traded_close), 'one_dollar_nominal_cash_entitlement': unit_result.cash_delta},
    'open_gaps': ['2020-04-02 onward remains missing in this override. No extension to the 2023 Microsoft acquisition or 2026 cutoff is implied.',
                  'The wider historical identity, delisting, coverage and research gates remain unchanged; this extension is not a PASS declaration.'],
}
(OUT / 'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n')
proposal = {'ticker': 'ATVI', 'replace_only_price_override_entry': {
    **active, 'path': 'data/research/v04/prices/ATVI-through-2020-04-01.parquet', 'sha256': sha(path),
    'first': str(candidate.date.min().date()), 'last': str(candidate.date.max().date()),
    'method': 'Preserve prior WIKI and both IEX patches exactly; append 507 frozen Jackson Crow v2 whole OHLCV rows, verified nominal split basis, and canonical WIKI dividend total-return factors.',
    'prefix_sha256': sha(BASE), 'extension_source_sha256': sha(SOURCE),
    'audit_path_to_copy': 'audit.json', 'evidence_path_to_copy': 'report.md'},
    'candidate_file': str(path), 'keep_existing_unresolved_gates': True,
    'remaining_ATVI_gap_starts': '2020-04-02', 'new_corporate_actions': []}
(OUT / 'manifest-proposal.json').write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'candidate': audit['candidate'], 'overlap_rows': len(comparable),
                  'basis': audit['adjustment_basis'], 'unit_check': audit['round_trip_unit_check']}, indent=2))
