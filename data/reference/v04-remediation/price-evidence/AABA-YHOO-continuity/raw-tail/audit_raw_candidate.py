"""Audit the pinned public AABA raw CSV without network or repository writes."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
RAW = OUT / 'AABA-szrlee-55639c5.source.csv'
NOTEBOOK = OUT / 'data_collection-55639c5.source.ipynb'
WIKI = OUT.parent / 'v04-aaba-identity/YHOO-WIKI-source.parquet'
COMMIT = '55639c5cfa7556c4372ff361c026acb792bfdcf4'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + '\n')


assert sha(RAW) == '219a6434d20f717ed921a8335ff9b3c9ca9d04b0c0b0e266db010cb922c040eb'
assert sha(NOTEBOOK) == '27f3e5b159dff5a91fb71fa02643c65ce90ce558384bcee3499992b65e4a0445'
assert sha(WIKI) == 'd144fb2c24d02561cfcc015b7a813d574ec8f7c0191cb3c2fa1ccb73eef16128'
data = pd.read_csv(RAW, parse_dates=['Date'])
assert data.columns.tolist() == ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Name']
assert data.Name.eq('AABA').all()
wiki = pd.read_parquet(WIKI)
cal = xc.get_calendar('XNYS', start='2006-01-01', end='2018-01-31')
sessions = cal.sessions_in_range(data.Date.min(), data.Date.max()).tz_localize(None)
numeric = data[['Open', 'High', 'Low', 'Close', 'Volume']]
valid = np.isfinite(numeric).all(axis=1) & (numeric > 0).all(axis=1)
valid &= data.High.ge(data[['Open', 'Close', 'Low']].max(axis=1))
valid &= data.Low.le(data[['Open', 'Close', 'High']].min(axis=1))
tail = data.loc[data.Date >= '2017-06-19'].copy()
tail_sessions = cal.sessions_in_range('2017-06-19', '2017-12-29').tz_localize(None)
assert len(tail) == 136 and pd.DatetimeIndex(tail.Date).equals(tail_sessions)
assert valid.loc[tail.index].all() and data.Date.is_unique and data.Date.is_monotonic_increasing
tail.to_csv(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.csv', index=False)
tail.to_parquet(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet', index=False)
pd.testing.assert_frame_equal(pd.read_parquet(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet'), tail.reset_index(drop=True))
data.loc[~valid].to_csv(OUT / 'unused-prefix-invalid-source-rows.csv', index=False)
missing = sessions.difference(data.Date)
assert missing.strftime('%Y-%m-%d').tolist() == ['2010-04-01']
assert data.loc[~valid, 'Date'].dt.strftime('%Y-%m-%d').tolist() == ['2011-08-02']

overlap = wiki.merge(data, left_on='date', right_on='Date')
overlap.to_csv(OUT / 'WIKI-Google-overlap-observations.csv', index=False)
statistics = {}
for start in ['2006-01-03', '2017-01-01', '2017-05-01']:
    sample = overlap.loc[overlap.date >= start]
    statistics[start] = {'shared_sessions': len(sample), 'fields': {}}
    for c in ['open', 'high', 'low', 'close', 'volume']:
        delta = (sample[c] - sample[c.title()]).abs()
        relative = delta / sample[c].abs()
        statistics[start]['fields'][c] = {'max_absolute_difference': float(delta.max()),
            'max_relative_difference': float(relative.max()), 'median_relative_difference': float(relative.median()),
            'count_above_one_percent': int(relative.gt(.01).sum())}
dump('overlap-statistics.json', statistics)
boundary = wiki.loc[wiki.date >= '2017-06-12'].merge(
    data.loc[data.Date.between('2017-06-12', '2017-06-23')], left_on='date', right_on='Date', how='outer')
boundary.to_csv(OUT / '2017-06-rename-boundary-observations.csv', index=False)
last_wiki = wiki.loc[wiki.date.eq(pd.Timestamp('2017-06-16'))].iloc[0]
same_day = data.loc[data.Date.eq(pd.Timestamp('2017-06-16'))].iloc[0]
first_tail = tail.iloc[0]

notebook = json.loads(NOTEBOOK.read_text())
cells = []
for i, cell in enumerate(notebook['cells']):
    source = ''.join(cell.get('source', []))
    if any(term in source for term in ['pandas_datareader', 'pdr.DataReader', 'datetime.datetime', "data['Name']"]):
        cells.append({'cell': i, 'source': source})
assert any("pdr.DataReader(ticker, 'google', start, end)" in c['source'] for c in cells)
dump('collection-notebook-provenance.json', {'notebook_path': str(NOTEBOOK), 'sha256': sha(NOTEBOOK),
    'commit': COMMIT, 'cells_read_only_not_executed': cells})
commit_meta = json.loads((OUT / 'request-02-file-commit.body.json').read_text())[0]
assert commit_meta['sha'] == COMMIT

audit = {
    'status': 'RAW_TAIL_CANDIDATE_VERIFIED_NOT_CANONICALIZED_NOT_APPLIED',
    'source': {'repository': 'https://github.com/szrlee/Stock-Time-Series-Analysis', 'author': 'szrlee',
        'commit': COMMIT, 'commit_date': commit_meta['commit']['committer']['date'],
        'path_in_repository': 'data/AABA_2006-01-01_to_2018-01-01.csv',
        'pinned_raw_url': json.loads((OUT / 'request-03.meta.json').read_text())['url'],
        'local_raw_path': str(RAW), 'raw_sha256': sha(RAW), 'bytes': RAW.stat().st_size,
        'upstream_declared_in_pinned_collection_code': 'Google Finance via pandas_datareader',
        'collection_call': "pdr.DataReader(ticker, 'google', start, end)",
        'ticker_label_added_by_collection_notebook': "data['Name'] = ticker",
        'Kaggle_relationship': 'Search returned this author repository and third-party notebooks linking the hinted Kaggle dataset; the actual retrieved/pinned source here is GitHub.',
        'Kaggle_dataset_version': None, 'Kaggle_version_verified': False,
        'not_a_new_Yahoo_refresh': True},
    'columns': data.columns.tolist(), 'absent_fields': ['Adj Close', 'Dividends', 'Stock Splits'],
    'full_source': {'rows': len(data), 'first': str(data.Date.min().date()), 'last': str(data.Date.max().date()),
        'missing_sessions': missing.strftime('%Y-%m-%d').tolist(), 'duplicate_dates': int(data.Date.duplicated().sum()),
        'invalid_rows': data.loc[~valid].to_dict('records'),
        'disposition': 'Full original file preserved; early defects excluded from the requested tail and never used to replace WIKI prefix.'},
    'requested_tail': {'rows': len(tail), 'first': str(tail.Date.min().date()), 'last': str(tail.Date.max().date()),
        'missing_sessions': [], 'invalid_rows': 0, 'duplicate_dates': 0, 'all_Name_AABA': True,
        'all_positive_integer_share_volume': bool((tail.Volume.gt(0) & tail.Volume.mod(1).eq(0)).all()),
        'first_observation': first_tail.to_dict(), 'last_observation': tail.iloc[-1].to_dict(),
        'csv_path': str(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.csv'),
        'csv_sha256': sha(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.csv'),
        'parquet_path': str(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet'),
        'parquet_sha256': sha(OUT / 'AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet')},
    'rename_boundary': {'WIKI_2017_06_16_close': float(last_wiki.close), 'Google_2017_06_16_close': float(same_day.Close),
        'close_difference': float(same_day.Close - last_wiki.close),
        'close_relative_difference': float(same_day.Close / last_wiki.close - 1),
        'Google_2017_06_19_open': float(first_tail.Open), 'Google_2017_06_19_close': float(first_tail.Close),
        'unadjusted_overnight_return_using_WIKI_prior_close': float(first_tail.Open / last_wiki.close - 1),
        'interpretation': 'Same price scale is supported by actual overlapping observations; not an instruction to rescale the series or substitute either close for an execution price.'},
    'overlap_statistics': statistics,
    'identity_reference': str(OUT.parent / 'v04-aaba-identity/audit.json'),
    'limitations': [
        'No adjusted-close, dividend or split columns; the complete 2017 H2 cash/split ledger and final adjustment convention are not verified by this source-only task.',
        'Some earlier OHLC and volumes disagree with WIKI; preserve WIKI prefix and assess any proposed join explicitly.',
        'The raw candidate does not itself certify every strategy-specific exit date, though it covers every session from June 19 to the last session of 2017.',
        'Kaggle version was not fetched; version here is the pinned GitHub commit plus content hashes.'
    ],
    'public_requests_used': 4, 'public_request_limit': 4,
    'request_ledger': [{'request': 1, 'kind': 'targeted web search', 'artifact': 'request-01-file-search.json'},
                       {'request': 2, 'kind': 'GitHub file commit metadata', 'artifact': 'request-02-file-commit.meta.json'},
                       {'request': 3, 'kind': 'pinned raw single CSV', 'artifact': 'request-03.meta.json'},
                       {'request': 4, 'kind': 'pinned collection notebook read-only', 'artifact': 'request-04.meta.json'}],
    'network_calls_by_audit_script': 0, 'canonical_price_series_generated': False,
    'repo_or_manifest_modified': False, 'backtest_run': False,
}
dump('audit.json', audit)
print(json.dumps({'status': audit['status'], 'source': audit['source'], 'tail': audit['requested_tail'],
                  'boundary': audit['rename_boundary']}, indent=2, default=str))
