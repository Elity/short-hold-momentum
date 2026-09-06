"""Read-only AABA/YHOO identity and local source audit. No network or repo writes."""
from pathlib import Path
import hashlib
import json
import zipfile

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
REPO = Path('/Users/fighting/code/short-hold-momentum')
ARCHIVE = WORK / 'v04-remediation-archive/wiki-prices.zip'
CSV = OUT / 'YHOO-WIKI-source.csv'
PARQUET = OUT / 'YHOO-WIKI-source.parquet'
MEMBERSHIP = REPO / 'data/reference/sp500_history.csv'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + '\n')


assert sha(ARCHIVE) == 'adfd226694c6f3ec2c56b585d973764180a39a3ec516601721e90096dc1de94f'
if not CSV.exists():
    with zipfile.ZipFile(ARCHIVE) as archive, archive.open('WIKI_PRICES.csv') as source, CSV.open('wb') as target:
        target.write(source.readline())
        for line in source:
            if line.startswith(b'YHOO,'):
                target.write(line)
assert sha(CSV) == '541a561639c60238b208fb40465611357ba24c3f262b21b9b69dd2ced8954959'
data = pd.read_csv(CSV, parse_dates=['date'])
data.to_parquet(PARQUET, index=False)
cal = xc.get_calendar('XNYS', start='1996-01-01', end='2019-12-31')
sessions = cal.sessions_in_range(data.date.min(), data.date.max()).tz_localize(None)
numeric = data[['open', 'high', 'low', 'close', 'volume']]
valid = np.isfinite(numeric).all(axis=1) & (numeric > 0).all(axis=1)
valid &= data.high.ge(data[['open', 'close', 'low']].max(axis=1))
valid &= data.low.le(data[['open', 'close', 'high']].min(axis=1))
assert len(data) == 5332 and len(sessions) == 5332
assert data.ticker.eq('YHOO').all() and valid.all()
assert pd.DatetimeIndex(data.date).equals(sessions) and data.date.is_unique

members = pd.read_csv(MEMBERSHIP, parse_dates=['date'])
flag = members.tickers.str.split(',').map(lambda x: 'AABA' in x)
old_ticker_flag = members.tickers.str.split(',').map(lambda x: 'YHOO' in x)
changes = members.loc[flag.ne(flag.shift(fill_value=False)), ['date']].copy()
changes['member'] = flag[flag.ne(flag.shift(fill_value=False))].to_numpy()
changes.to_csv(OUT / 'membership-transitions.csv', index=False)
daily_member = pd.Series(flag.to_numpy(), index=members.date).reindex(sessions, method='ffill').fillna(False)
coverage = pd.DataFrame({'date': sessions, 'member_as_AABA': daily_member.to_numpy(), 'YHOO_quote_observed': sessions.isin(data.date)})
coverage.to_csv(OUT / 'membership-source-coverage.csv', index=False)
data.loc[data.date >= '2017-05-01'].to_csv(OUT / 'YHOO-last-observations.csv', index=False)
events = data.loc[data['ex-dividend'].ne(0) | data.split_ratio.ne(1), ['date', 'ex-dividend', 'split_ratio']]
events.to_csv(OUT / 'WIKI-vendor-action-observations.csv', index=False)

with zipfile.ZipFile(WORK / 'v04-corporate-actions-next/ATVI-independent-sp500.source.zip') as z:
    iex_matches = [n for n in z.namelist() if 'aaba' in n.lower() or 'yhoo' in n.lower()]
with zipfile.ZipFile(WORK / 'v04-source-options-next/sheepb-2021-v1.zip') as z:
    symbols = pd.read_csv(z.open('symbol_company.csv'))
    sheepb_matches = symbols.loc[symbols.Symbol.isin(['AABA', 'YHOO'])].to_dict('records')

sources = []
for filename in sorted((OUT / 'primary-evidence').glob('request-*.json')):
    r = json.loads(filename.read_text())
    for hit in r['webResults']:
        url = hit['url']
        identity = None
        if url.endswith('/d389206d8k.htm'):
            identity = '2017-06-19-name-ticker-continuity-8k'
        elif url.endswith('/d408809dn2.htm'):
            identity = '2017-06-16-investment-company-registration-N2'
        elif url.endswith('/d409905dex99a5b.htm'):
            identity = '2017-06-08-optional-tender-extension'
        elif url.endswith('/d389202dex99a5d.htm'):
            identity = '2017-06-19-optional-tender-preliminary-results'
        elif 'prnewswire.com' in url and '300471904' in url:
            identity = '2017-06-09-SP-index-removal-announcement'
        elif url.endswith('/d794671d8k.htm'):
            identity = '2019-10-04-actual-halt-and-dissolution-8k'
        if identity:
            dest = OUT / 'primary-evidence' / (identity + '.txt')
            dest.write_text(hit['content'] + '\n')
            sources.append({'id': identity, 'url': url, 'capture_path': str(dest),
                            'retrieval_file': str(filename), 'chars': len(hit['content'])})

timeline = [
    {'date': '1999-12-08', 'event': 'First AABA label in local historical membership table; identity is then Yahoo/YHOO.', 'scope': 'local history; original inclusion day not independently verified'},
    {'date': '2017-06-09', 'event': 'S&P issuer announcement: Hilton to replace Yahoo before June 19 open; closed-end fund ineligible.', 'scope': 'primary index announcement'},
    {'date': '2017-06-13', 'event': 'Yahoo sold operating business to Verizon; approximately $4.5 billion paid to the corporate fund, not an automatic payout to each common shareholder.', 'scope': 'completed event in June 19 8-K and June 16 N-2'},
    {'date': '2017-06-16', 'event': 'Yahoo renamed Altaba and registered as closed-end investment company; last YHOO trading day and last observed WIKI quote; final member day.', 'scope': 'primary issuer and index evidence plus local quote'},
    {'date': '2017-06-19', 'event': 'AABA trading begins at Nasdaq open; shares continue without shareholder action; not S&P 500 eligible from the open.', 'scope': 'primary issuer and index evidence'},
    {'date': '2019-10-02', 'event': 'Nasdaq halted AABA after regular trading closed.', 'scope': 'actual event in October 4 8-K; no terminal-price inference'},
    {'date': '2019-10-04', 'event': 'Dissolution effective at 16:00 Eastern; stock transfer books closed; holders retain rights to later liquidating distributions.', 'scope': 'actual event in October 4 8-K; not a zero-value or full-cash assumption'},
]
dump('event-timeline.json', timeline)
audit = {
    'status': 'IDENTITY_RESOLVED_PRECHANGE_QUOTES_RECOVERED_POSTCHANGE_QUOTES_MISSING',
    'entity': {'cik': '0001011006', 'jurisdiction': 'Delaware', 'prior_name': 'Yahoo! Inc.', 'new_name': 'Altaba Inc.',
               'old_ticker': 'YHOO', 'old_ticker_last_trade_date': '2017-06-16', 'new_ticker': 'AABA',
               'new_ticker_first_trade_date': '2017-06-19', 'old_cusip': '984332106', 'new_cusip': '021346101',
               'holder_treatment': 'same shareholder ownership continues; no action required; no automatic cash or Verizon-share payout',
               'bookkeeping_interpretation': 'identity rename with unchanged held units, not a priced acquisition liquidation'},
    'membership': {'local_label': 'AABA', 'YHOO_label_snapshot_count': int(old_ticker_flag.sum()),
                   'first_local_member_snapshot': str(members.loc[flag, 'date'].min().date()),
                   'last_local_member_snapshot': str(members.loc[flag, 'date'].max().date()),
                   'removal_effective_before_open': '2017-06-19', 'replacement': 'HLT',
                   'daily_member_sessions_covered_by_WIKI': int(daily_member.sum())},
    'source': {'archive': str(ARCHIVE), 'archive_sha256': sha(ARCHIVE), 'source_csv': str(CSV), 'csv_sha256': sha(CSV),
               'source_parquet': str(PARQUET), 'parquet_sha256': sha(PARQUET),
               'first': str(data.date.min().date()), 'last': str(data.date.max().date()), 'rows': len(data),
               'missing_XNYS_sessions': [], 'duplicate_dates': 0, 'invalid_OHLCV_rows': 0,
               'research_start_2003_10_01_rows': int(data.date.ge('2003-10-01').sum()),
               'dev_2005_01_01_onward_rows': int(data.date.ge('2005-01-01').sum()),
               'final_nominal_close': float(data.close.iloc[-1]), 'final_close_is_terminal_settlement': False,
               'corporate_action_scope': 'Vendor fields show five splits, no cash dividends; individual historic actions not primary-revalidated in this identity-only task.'},
    'local_postchange_source_inventory': {'IEX_archive_name_matches': iex_matches, 'SheepB_symbol_matches': sheepb_matches,
                                         'WIKI_AABA_present': False},
    'recoverable_alias_interval': {'member_key': 'AABA', 'price_source_ticker': 'YHOO', 'from': '1996-04-12', 'through': '2017-06-16',
                                   'research_slice_from': '2003-10-01', 'member_window_from': '1999-12-08',
                                   'status': 'identity mapping supported; partial price input only, not deployment-ready held-position history'},
    'remaining_evidence': [
        'Actual AABA nominal OHLCV from 2017-06-19 through the latest actual exit needed by the existing strategy schedule.',
        'A quote/adjustment overlap check around June 16/19 before joining any new source; do not infer opening price from old close or scale across a fake cash payout.',
        'If a tested position reaches 2019 liquidation, obtain actual distribution dates/amounts, residual rights and available marks; neither last quote nor liquidation announcement is full settlement.',
        'Historic WIKI split observations still inherit existing source evidence limits; do not claim a newly primary-verified full action ledger.'
    ],
    'forbidden_inferences': ['2017 operating-asset sale equals holder cash merger', '2017-06-16 source tail equals mandatory sale date',
                             'index removal equals security extinguishment', 'optional preliminary tender price is universal execution price',
                             'AABA is Alibaba BABA or Yahoo Japan'],
    'exit_boundary': 'No legal share termination in June 2017. Existing holdings need AABA quotes until actual strategy exit. A June 16 signal can require a June 19 next-open price; the eligibility-to-fill rule must be evaluated explicitly, not guessed.',
    'primary_sources': sources, 'public_requests_used': 4, 'public_request_limit': 4,
    'network_calls_by_audit_script': 0, 'repo_or_manifest_modified': False, 'backtest_run': False,
}
dump('audit.json', audit)
dump('identity-mapping-proposal.json', {k: audit[k] for k in ['status', 'entity', 'recoverable_alias_interval', 'exit_boundary', 'remaining_evidence', 'forbidden_inferences', 'primary_sources']})
print(json.dumps({'status': audit['status'], 'source': audit['source'], 'membership': audit['membership'], 'local_sources': audit['local_postchange_source_inventory']}, indent=2))
