"""Append only the primary-evidence-verified ATVI 2020-2021 tail under work/."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from shm.v03.corporate_actions import AdjustmentBasis, CorporateAction, convert_position
from shm.v03.strategy import PositionState

ROOT = Path('/Users/fighting/code/short-hold-momentum')
WORK = Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-source-options-next')
OUT = WORK / 'ATVI-2021-extension'
SOURCE = WORK / 'sheepb-extracted/ATVI.parquet'
ANCHOR = pd.Timestamp('2020-04-01')
END = pd.Timestamp('2021-08-19')
DIVIDENDS = {'2020-04-14': .41, '2021-04-14': .47}
PRIMARY = [
    {'url': 'https://www.sec.gov/Archives/edgar/data/718877/000162828021002828/atvi-20201231.htm',
     'file': 'ATVI-2020-10K.html', 'expected_sha256': '079fa346fae873ef3d050841c7254cfe7fd91f6073d2dc909d7c22019f4571fd',
     'scope': '2020 full-year share roll-forward and 2020/2021 dividend declaration, record and payment dates'},
    {'url': 'https://www.sec.gov/Archives/edgar/data/718877/000162828021021200/atvi-20210930.htm',
     'file': 'ATVI-2021-Q3.html', 'expected_sha256': 'e99b107be442d5dc77d9e371bad448984562fbece84817e3192e194d83395195',
     'scope': 'Quarterly 2020/2021 share roll-forwards through September 2021; confirmation of actual 2021 dividend payment'},
]

def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()

active = json.loads((ROOT / 'data/reference/v04-remediation/manifest.json').read_text())['price_overrides']['ATVI']
base_path = ROOT / active['path']
assert sha(base_path) == active['sha256'] == 'c6beda01fad277fa3c202d419180163c816f3daaf54978600fed94eb10d46d7b'
base = pd.read_parquet(base_path)
assert len(base) == 4154 and base.date.max() == ANCHOR and base.date.is_unique
extraction = json.loads((WORK / 'sheepb-extraction.json').read_text())
source_record = next(item for item in extraction['series'] if item['ticker'] == 'ATVI')
assert sha(SOURCE) == source_record['sha256'] == '7b77347e5ecada0deb3675257f34b09b39119dc5b5e250043ea91fd623d67395'
download = json.loads((WORK / 'sheepb-2021-download.json').read_text())
assert sha(WORK / 'sheepb-2021-v1.zip') == extraction['source_sha256'] == download['sha256']
metadata = json.loads((WORK / '04-sheepb-metadata.body').read_text())
assert metadata['currentVersionNumber'] == 1 and 'yfinance' in metadata['description']
for document in PRIMARY:
    assert sha(OUT / document['file']) == document['expected_sha256']

raw = pd.read_parquet(SOURCE)
raw['Date'] = pd.to_datetime(raw.Date)
assert raw.Name.eq('ATVI').all() and raw['Company Name'].eq('Activision Blizzard').all()
raw = raw.set_index('Date').sort_index()
assert raw.index.is_unique and raw.index.max() == END
raw['provider_factor'] = raw['Adj Close'] / raw.Close
tail = raw.loc[(raw.index > ANCHOR) & (raw.index <= END)].copy()
calendar = xcals.get_calendar('XNYS', start='2020-04-01', end='2021-08-31')
sessions = calendar.sessions_in_range(ANCHOR, END)[1:].tz_localize(None)
assert len(tail) == 349 and tail.index.equals(sessions)
assert np.isfinite(tail[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]).all().all()
assert tail[['Open', 'High', 'Low', 'Close', 'Volume']].gt(0).all().all()
assert tail.High.ge(tail[['Open', 'Close', 'Low']].max(axis=1)).all()
assert tail.Low.le(tail[['Open', 'Close', 'High']].min(axis=1)).all()
assert tail.Volume.eq(np.floor(tail.Volume)).all()

observed_changes = raw.index[(raw.index > ANCHOR) & raw.provider_factor.pct_change().abs().gt(1e-5)]
assert [str(day.date()) for day in observed_changes] == list(DIVIDENDS)
for ex_date in DIVIDENDS:
    # Both record dates are ordinary XNYS sessions; T+2 ex-date is the previous
    # session, and the same Yahoo provider's captured factor changes there.
    record = str(pd.Timestamp(ex_date).year) + '-04-15'
    assert str(calendar.previous_session(record).date()) == ex_date

factor = float(base.iloc[-1].close / base.iloc[-1].as_traded_close)
initial_factor = factor
previous_adjusted, previous_nominal = float(base.iloc[-1].close), float(base.iloc[-1].as_traded_close)
factor_by_date, dividend_checks = [], []
for day, row in tail.iterrows():
    dividend = DIVIDENDS.get(str(day.date()), 0.)
    if dividend:
        factor *= (float(row.Close) + dividend) / float(row.Close)
    adjusted_close = float(row.Close) * factor
    model_return = adjusted_close / previous_adjusted - 1
    actual_total_return = (float(row.Close) + dividend) / previous_nominal - 1
    assert abs(model_return - actual_total_return) < 1e-12
    factor_by_date.append(factor)
    if dividend:
        dividend_checks.append({'ex_date': str(day.date()), 'dividend': dividend, 'record_date': str(day.year) + '-04-15',
                               'payment_date': str(day.year) + '-05-06', 'ex_nominal_close': float(row.Close),
                               'new_factor': factor, 'model_return': model_return,
                               'economic_total_return': actual_total_return, 'absolute_error': abs(model_return - actual_total_return)})
    previous_adjusted, previous_nominal = adjusted_close, float(row.Close)
tail['canonical_factor'] = factor_by_date
timestamp = pd.Timestamp(SOURCE.stat().st_mtime, unit='s', tz='UTC')
extension = pd.DataFrame({
    'date': tail.index, 'open': (tail.Open * tail.canonical_factor).to_numpy(),
    'high': (tail.High * tail.canonical_factor).to_numpy(), 'low': (tail.Low * tail.canonical_factor).to_numpy(),
    'close': (tail.Close * tail.canonical_factor).to_numpy(), 'volume': tail.Volume.to_numpy(),
    'as_traded_close': tail.Close.to_numpy(), 'dollar_volume': (tail.Close * tail.Volume).to_numpy(),
    'adjusted': True,
    'source': 'Yahoo/yfinance via frozen SheepB Kaggle v1; whole source OHLCV rows forward-adjusted from existing 2020-04-01 basis using SEC-confirmed dividends and WIKI total-return convention',
    'downloaded_at': timestamp,
})[base.columns]
candidate_path = OUT / 'ATVI-through-2021-08-19.candidate.parquet'
pd.concat([base, extension], ignore_index=True).to_parquet(candidate_path, index=False)
candidate = pd.read_parquet(candidate_path)
assert len(candidate) == 4503 and candidate.date.max() == END and candidate.date.is_unique
pd.testing.assert_frame_equal(candidate.iloc[:len(base)].reset_index(drop=True), base.reset_index(drop=True))
assert sha(base_path) == active['sha256']
assert np.array_equal(candidate.iloc[len(base):].as_traded_close.to_numpy(), tail.Close.to_numpy())
assert np.array_equal(candidate.iloc[len(base):].dollar_volume.to_numpy(), (tail.Close * tail.Volume).to_numpy())

overlap = base.set_index('date').loc['2018-03-28':].join(raw, how='inner')
old_factor = overlap.close / overlap.as_traded_close
overlap_checks = {}
for old, new in [('open', 'Open'), ('high', 'High'), ('low', 'Low'), ('close', 'Close')]:
    delta = (overlap[new] / (overlap[old] / old_factor) - 1).abs()
    assert delta.max() < 1e-12
    overlap_checks[new] = {'rows': len(delta), 'maximum_relative_difference': float(delta.max()), 'median_relative_difference': float(delta.median())}
volume_diff = overlap.loc[overlap.volume.ne(overlap.Volume), ['volume', 'Volume']].rename_axis('date').reset_index()
volume_diff['date'] = volume_diff['date'].astype(str)
stable = overlap.loc['2019-03-27':]
ratios = (stable.close / stable.as_traded_close) / stable.provider_factor
vendor_anchor = float(raw.loc[ANCHOR, 'provider_factor'])
vendor_rescaled = tail['Adj Close'] / vendor_anchor * initial_factor
vendor_method_difference = extension.close.to_numpy() / vendor_rescaled.to_numpy() - 1

last = candidate.iloc[-1]
reloaded_factor = float(last.close / last.as_traded_close)
units = 100. / reloaded_factor
unit_action = CorporateAction('SYNTHETIC-UNIT-CHECK', 'ATVI', '2021-08-19', '2021-08-19',
                              '2021-08-19', '2021-08-20', 1., 'synthetic dimensional check only', 'terminal_before_action')
unit_result = convert_position(PositionState(units, float(last.close), '2021-08-19', float(last.close)), unit_action,
                               source_basis=AdjustmentBasis(reloaded_factor, '2021-08-19', 'candidate parquet round-trip factor'))
assert abs(unit_result.cash_delta - 100.) < 1e-12
assert abs(units * float(last.close) - 100. * float(last.as_traded_close)) < 1e-10

annual = (OUT / 'ATVI-2020-10K.txt').read_text()
quarter = (OUT / 'ATVI-2021-Q3.txt').read_text()
excerpts = []
for label, text, phrases in [
    ('2020-10K', annual, ['Year Per Share Amount Record Date Dividend Payment Date',
                         'On February 4, 2021, our Board of Directors declared a cash dividend of $0.47',
                         'CONSOLIDATED STATEMENTS OF CHANGES IN SHAREHOLDERS’ EQUITY']),
    ('2021-Q3', quarter, ['CONSOLIDATED STATEMENTS OF CHANGES IN SHAREHOLDERS’ EQUITY',
                         'On May 6, 2021, we made an aggregate cash dividend payment of $ 365 million']),
]:
    for phrase in phrases:
        index = text.find(phrase)
        assert index >= 0, phrase
        excerpts.append({'document': label, 'anchor': phrase,
                         'text': text[max(0, index - 70):index + (6000 if 'STATEMENTS' in phrase else 1300)]})
(OUT / 'primary-excerpts.json').write_text(json.dumps(excerpts, indent=2, ensure_ascii=False) + '\n')
(OUT / 'primary-source-provenance.json').write_text(json.dumps(PRIMARY, indent=2, ensure_ascii=False) + '\n')
audit = {
    'status': 'VERIFIED_BOUNDED_PRICE_EXTENSION_NOT_A_RESEARCH_PASS',
    'source': {'dataset': 'sheepb/stock-market-dataset-20002021', 'version': 1,
               'upstream_provider': 'Yahoo Finance via yfinance',
               'capture_dataset': 'SheepB stock-market-dataset-20002021 v1',
               'prior_capture_dataset': 'Jackson Crow stock-market-dataset',
               'prior_capture_upstream_provider': 'Yahoo Finance via yfinance',
               'independent_price_vendor': False,
               'download_url': download['url'], 'zip_sha256': download['sha256'], 'zip_rehashed': True,
               'member': 'full_stock_df.csv', 'extracted_parquet': str(SOURCE), 'extracted_sha256': sha(SOURCE),
               'extraction_record': source_record, 'metadata_sha256': sha(WORK / '04-sheepb-metadata.body'),
               'local_extraction_time_used_as_downloaded_at': timestamp.isoformat()},
    'retained_prefix': {'repo_path': active['path'], 'sha256': active['sha256'], 'rows': len(base),
                        'last': str(ANCHOR.date()), 'all_columns_equal_after_round_trip': True,
                        'original_file_and_manifest_untouched': True,
                        'inherited_issue_not_modified': '2016-11-25 old-prefix Open is below Low; parent will independently verify and replace the whole source row in a separate audited remediation.'},
    'candidate': {'work_path': str(candidate_path), 'sha256': sha(candidate_path), 'rows': len(candidate),
                  'appended_rows': len(extension), 'first_new_day': '2020-04-02', 'last': str(END.date()),
                  'missing_xnys_days_in_appended_tail': [], 'duplicate_days': 0, 'invalid_ohlcv_rows_in_appended_tail': 0},
    'primary_documents': PRIMARY,
    'ordinary_dividends': dividend_checks,
    'split_and_share_units': {
        'conclusion': 'No split or reverse split in the appended interval; nominal Close and Volume may be used directly only for this verified interval.',
        'primary_rollforward_millions': {
            '2020_begin_issued': 1197, '2020_options_issued': 5, '2020_rsus_issued': 1,
            '2020_tax_surrender_rounded': 0, '2020_end_issued': 1203,
            '2021_q1_options': 1, '2021_q1_rsus': 4, '2021_q1_tax_surrender': -2,
            '2021_q1_end_issued': 1206, '2021_q2_end_issued': 1206,
            '2021_q3_options_rounded': 0, '2021_q3_rsus': 2, '2021_q3_tax_surrender': -1,
            '2021_q3_end_issued': 1207, 'treasury_shares_unchanged': 429},
        'reasoning': 'Full-year 2020 and quarterly 2021 share roll-forwards attribute changes to employee equity issuance and tax surrender, with no split/reverse-split line. Complete post-2018 raw OHLC overlap is unchanged, excluding a later net split rescaling. The Q3 statement covers the August 19 endpoint.',
        'limit': 'Financial statements published later verify historical units only. They are not used as point-in-time selection signals.'},
    'overlap': {'period': ['2018-03-28', '2020-04-01'], 'rows': len(overlap), 'nominal_ohlc': overlap_checks,
                'interpretation': 'Agreement across two capture dates of the same Yahoo Finance/yfinance upstream, not independent-vendor price corroboration. Volume differences are capture revisions; prefix values are retained.',
                'volume_changes_not_applied_to_prefix': volume_diff.to_dict('records'),
                'maximum_volume_relative_difference': float((overlap.Volume / overlap.volume - 1).abs().max())},
    'basis': {'anchor': str(ANCHOR.date()), 'initial_canonical_factor': initial_factor,
              'anchor_provider_factor': vendor_anchor, 'last_canonical_factor': reloaded_factor,
              'constant_basis_comparison_period': ['2019-03-27', '2020-04-01'],
              'old_canonical_to_sheep_adjusted_ratio': {'median': float(ratios.median()), 'min': float(ratios.min()), 'max': float(ratios.max())},
              'formula': 'On ex-date f_new=f_old*(Close_ex+D)/Close_ex; otherwise f is unchanged. Every appended OHLC row is kept whole from SheepB and multiplied by that single row factor.',
              'ordinary_cash_events_added': 0,
              'maximum_return_identity_error': max(item['absolute_error'] for item in dividend_checks),
              'maximum_relative_difference_vs_constant_rescaled_vendor_AdjClose': float(np.abs(vendor_method_difference).max()),
              'nominal_fields_unchanged': True},
    'unit_round_trip': {'synthetic_only': True, 'nominal_shares': 100., 'adjusted_quantity': units,
                        'factor': reloaded_factor, 'nominal_value': 100. * float(last.as_traded_close),
                        'adjusted_value': units * float(last.close), 'one_dollar_per_nominal_share_cash': unit_result.cash_delta},
    'remaining_gap': {'first_missing_day': '2021-08-20', 'includes_later_terminal_event': True,
                      'existing_unresolved_gates_retained': True, 'study_cutoff_unchanged': '2026-09-04'},
}
(OUT / 'audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n')
proposal = {
    'ticker': 'ATVI', 'candidate_file': str(candidate_path),
    'expected_current_override_path': active['path'], 'expected_current_override_sha256': active['sha256'],
    'price_override': {**active, 'path': 'data/research/v04/prices/ATVI-through-2021-08-19.parquet',
        'sha256': sha(candidate_path), 'last': str(END.date()), 'prefix_sha256': active['sha256'],
        'extension_source_sha256': sha(SOURCE), 'extension_zip_sha256': download['sha256'],
        'upstream_provider': 'Yahoo Finance via yfinance', 'independent_price_vendor': False,
        'method': 'Preserve all 4154 currently active rows exactly; append 349 whole SheepB v1 OHLCV rows through 2021-08-19. SEC-confirmed 2020/2021 ordinary dividends use the frozen WIKI total-return convention; nominal fields remain separate.',
        'evidence_path': 'data/reference/v04-remediation/price-evidence/ATVI-2021-extension/report.md',
        'evidence_sha256': sha(OUT / 'report.md') if (OUT / 'report.md').exists() else None},
    'evidence_copy_from': str(OUT), 'new_corporate_actions': [],
    'existing_unresolved_gates_must_be_retained': True, 'remaining_ATVI_gap_starts': '2021-08-20',
}
(OUT / 'manifest-proposal.json').write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'candidate': audit['candidate'], 'dividends': dividend_checks,
                  'basis': audit['basis'], 'unit_round_trip': audit['unit_round_trip']}, indent=2))
