"""Build an auditable FL extension; keep original files and explicit repair versions."""
from pathlib import Path
import hashlib
import json
import shutil

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path('/Users/fighting/code/short-hold-momentum')
WORK = Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work')
OUT = Path(__file__).parent
SOURCE = WORK / 'v04-source-options-next/sheepb-extracted/FL.parquet'
END = pd.Timestamp('2021-08-19')
ANCHOR = pd.Timestamp('2018-03-27')
DIVIDENDS = [
    ('2018-04-19', .345, '2018-04-20', '2018-05-04'),
    ('2018-07-19', .345, '2018-07-20', '2018-08-03'),
    ('2018-10-18', .345, '2018-10-19', '2018-11-02'),
    ('2019-01-17', .345, '2019-01-18', '2019-02-01'),
    ('2019-04-17', .38, '2019-04-18', '2019-05-03'),
    ('2019-07-18', .38, '2019-07-19', '2019-08-02'),
    ('2019-10-17', .38, '2019-10-18', '2019-11-01'),
    ('2020-01-16', .38, '2020-01-17', '2020-01-31'),
    ('2020-04-16', .40, '2020-04-17', '2020-05-01'),
    ('2020-10-15', .15, '2020-10-16', '2020-10-30'),
    ('2021-01-14', .15, '2021-01-15', '2021-01-29'),
    ('2021-04-15', .20, '2021-04-16', '2021-04-30'),
    ('2021-07-15', .20, '2021-07-16', '2021-07-30'),
]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
entry = json.loads((ROOT / 'data/reference/v04-remediation/manifest.json').read_text())['price_overrides']['FL']
base_path = ROOT / entry['path']
assert sha(base_path) == entry['sha256'] == '8e74d578db3db6d7bf02452e4965f15f30e22986d0321ef86d8bce78907de7e4'
base = pd.read_parquet(base_path)
assert len(base) == 3646 and base.date.max() == ANCHOR
extraction = json.loads((WORK / 'v04-source-options-next/sheepb-extraction.json').read_text())
source_record = next(x for x in extraction['series'] if x['ticker'] == 'FL')
assert sha(SOURCE) == source_record['sha256']
metadata = json.loads((WORK / 'v04-source-options-next/04-sheepb-metadata.body').read_text())
assert metadata['currentVersionNumber'] == 1 and 'yfinance' in metadata['description']
primary_pdf = OUT / '09-issuer-2020-annual.pdf'
assert sha(primary_pdf) == '96f87144b12cb476652a08d023e698611bb2db7f9c82de30ac5bc9d485f53b52'
followup = WORK / 'FL-source-followup'
assert sha(followup / '03-FL-2021Q2.body') == 'a06ac2f937c9973c593ab91537e7feba6fbd4ce61c3060a90e00a81018785827'
shutil.copytree(followup, OUT / 'primary-followup', dirs_exist_ok=True)

raw = pd.read_parquet(SOURCE)
assert raw.Name.eq('FL').all() and raw['Company Name'].eq('Foot Locker').all()
raw['Date'] = pd.to_datetime(raw.Date)
raw = raw.set_index('Date').sort_index()
assert raw.index.is_unique and raw.index.max() == END
raw['provider_factor'] = raw['Adj Close'] / raw.Close
tail = raw.loc[raw.index > ANCHOR].copy()
cal = xcals.get_calendar('XNYS', start=base.date.min(), end=END)
assert tail.index.equals(cal.sessions_in_range(ANCHOR, END)[1:].tz_localize(None))
observed = raw.index[(raw.index > ANCHOR) & raw.provider_factor.pct_change().abs().gt(1e-5)]
assert observed.strftime('%Y-%m-%d').tolist() == [x[0] for x in DIVIDENDS]
for ex, amount, record, pay in DIVIDENDS:
    assert str(cal.previous_session(record).date()) == ex
assert sum(x[1] for x in DIVIDENDS if '2018-02-04' <= x[0] <= '2019-02-02') == 1.38
assert sum(x[1] for x in DIVIDENDS if '2019-02-03' <= x[0] <= '2020-02-01') == 1.52
assert abs(sum(x[1] for x in DIVIDENDS if '2020-02-02' <= x[0] <= '2021-01-30') - .70) < 1e-14

factor = float(base.iloc[-1].close / base.iloc[-1].as_traded_close)
lookup = {d: a for d,a,_,_ in DIVIDENDS}
factors, checks = [], []
previous_adjusted = float(base.iloc[-1].close)
previous_nominal = float(base.iloc[-1].as_traded_close)
for date, row in tail.iterrows():
    dividend = lookup.get(str(date.date()), 0.)
    factor *= (row.Close + dividend) / row.Close
    close = row.Close * factor
    error = abs(close / previous_adjusted - (row.Close + dividend) / previous_nominal)
    assert error < 1e-12
    factors.append(factor)
    if dividend:
        checks.append({'date': str(date.date()), 'dividend': dividend, 'nominal_close': float(row.Close),
                       'factor': factor, 'total_return_identity_error': error})
    previous_adjusted, previous_nominal = close, float(row.Close)
tail['canonical_factor'] = factors
extension = pd.DataFrame({'date': tail.index,
    **{k.lower(): (tail[k] * tail.canonical_factor).to_numpy() for k in ('Open','High','Low','Close')},
    'volume': tail.Volume.to_numpy(), 'as_traded_close': tail.Close.to_numpy(),
    'dollar_volume': (tail.Close * tail.Volume).to_numpy(), 'adjusted': True,
    'source': 'Yahoo/yfinance via SheepB v1; whole rows, canonical WIKI total-return factors; issuer dividend evidence',
    'downloaded_at': pd.Timestamp(SOURCE.stat().st_mtime, unit='s', tz='UTC'),
})[base.columns].astype({'date': base.date.dtype, 'downloaded_at': base.downloaded_at.dtype})
v1 = pd.concat([base, extension], ignore_index=True)
v1_path = OUT / 'FL-extended-prefix-unchanged.parquet'
v1.to_parquet(v1_path, index=False)
assert_frame_equal(pd.read_parquet(v1_path).iloc[:len(base)], base, check_exact=True)

# Explicit old missing row, from a whole IEX row and the unchanged local basis.
iex = pd.read_csv(OUT / 'IEX-FL.csv').set_index('date')
missing_date = '2017-11-08'
quote = iex.loc[missing_date]
same = raw.loc[missing_date]
price_errors = {k: abs(float(quote[k.lower()]) - float(same[k])) for k in ('Open','High','Low','Close')}
assert max(price_errors.values()) < .00001
prefix = base.set_index('date')
neighbor_factors = prefix.loc['2017-11-07':'2017-11-09', 'close'] / prefix.loc['2017-11-07':'2017-11-09', 'as_traded_close']
assert np.allclose(neighbor_factors, 1., rtol=0, atol=1e-12)
row = {'date': pd.Timestamp(missing_date),
       **{k: float(quote[k]) for k in ('open','high','low','close','volume')},
       'as_traded_close': float(quote.close), 'dollar_volume': float(quote.close * quote.volume),
       'adjusted': True, 'source': 'IEX via Cam Nugent sandp500 v4; full 2017-11-08 row; preserved canonical unit',
       'downloaded_at': pd.Timestamp((OUT/'IEX-FL.csv').stat().st_mtime,unit='s',tz='UTC')}
missing_row = pd.DataFrame([row])[base.columns].astype({'date': base.date.dtype, 'downloaded_at': base.downloaded_at.dtype})
v2 = pd.concat([v1, missing_row], ignore_index=True).sort_values('date').reset_index(drop=True)

# Old WIKI omitted the issuer-confirmed January 2018 cash dividend. Apply the
# established ex-close/(ex-close + D) convention only before the ex-date.
ex_date = pd.Timestamp('2018-01-18')
ex_close = float(prefix.loc[ex_date, 'as_traded_close'])
old_ex_factor = float(prefix.loc[ex_date, 'close'] / ex_close)
assert old_ex_factor == float(prefix.loc['2018-01-17','close'] / prefix.loc['2018-01-17','as_traded_close']) == 1.
correction = ex_close / (ex_close + .31)
mask = v2.date.lt(ex_date)
v2.loc[mask, ['open','high','low','close']] *= correction
indexed = v2.set_index('date')
expected_return = (ex_close + .31) / float(prefix.loc['2018-01-17','as_traded_close']) - 1
assert abs(indexed.loc[ex_date,'close'] / indexed.loc['2018-01-17','close'] - 1 - expected_return) < 1e-12
for column in ('volume','as_traded_close','dollar_volume'):
    assert np.array_equal(indexed.loc[prefix.index,column], prefix[column])
assert_frame_equal(indexed.loc[indexed.index >= ex_date], v1.set_index('date').loc[lambda f: f.index >= ex_date], check_exact=True)
full_sessions = cal.sessions_in_range(base.date.min(), END).tz_localize(None)
assert pd.DatetimeIndex(v2.date).equals(full_sessions)
assert np.isfinite(v2[['open','high','low','close','volume']]).all().all()
assert v2[['open','high','low','close','volume']].gt(0).all().all()
assert v2.high.ge(v2[['open','close','low']].max(axis=1)).all()
assert v2.low.le(v2[['open','close','high']].min(axis=1)).all()
v2_path = OUT / 'FL-history-repaired-through-2021-08-19.parquet'
v2.to_parquet(v2_path, index=False)
assert_frame_equal(pd.read_parquet(v2_path), v2, check_exact=True)
assert sha(base_path) == entry['sha256']

overlap = prefix.join(raw, how='inner')
existing_factor = overlap.close / overlap.as_traded_close
comparisons = {}
for key in ('Open','High','Low','Close'):
    ratio = overlap[key] / (overlap[key.lower()] / existing_factor)
    comparisons[key] = {'rows': len(ratio), 'median_ratio': float(ratio.median()),
                        'p99_absolute_relative_error': float((ratio-1).abs().quantile(.99)),
                        'max_absolute_relative_error': float((ratio-1).abs().max())}
    assert abs(ratio.median() - 1) < 1e-6
yearly = (overlap.Close / overlap.as_traded_close).groupby(overlap.index.year).median().to_dict()
assert all(abs(value-1) < 1e-6 for value in yearly.values())
audit = {'status': 'VERIFIED_BOUNDED_EXTENSION_WITH_EXPLICIT_LEGACY_REPAIRS',
    'base': {'path': entry['path'], 'sha256': entry['sha256'], 'rows': len(base)},
    'source': {'path': str(SOURCE), 'sha256': sha(SOURCE), 'dataset': 'sheepb/stock-market-dataset-20002021',
               'version': 1, 'upstream': 'Yahoo/yfinance', 'archive_sha256': extraction['source_sha256']},
    'prefix_preserving_candidate': {'file': v1_path.name, 'sha256': sha(v1_path), 'rows': len(v1)},
    'repaired_candidate': {'file': v2_path.name, 'sha256': sha(v2_path), 'rows': len(v2),
                           'first': str(v2.date.min().date()), 'last': str(v2.date.max().date())},
    'new_tail_rows': len(extension), 'old_missing_row': {'date': missing_date, 'nominal_iex_row': row,
        'IEX_sha256': sha(OUT/'IEX-FL.csv'), 'Yahoo_price_absolute_errors': price_errors,
        'Yahoo_volume_difference': float(same.Volume-quote.volume)},
    'missed_dividend': {'ex_date': '2018-01-18', 'cash': .31, 'record': '2018-01-19', 'payable': '2018-02-02',
        'ex_nominal_close': ex_close, 'pre_ex_multiplier': correction,
        'primary': 'primary-followup/2017Q4-issuer-dividend-indexed.txt'},
    'dividend_checks': checks, 'tail_dividends': DIVIDENDS, 'nominal_overlap': comparisons,
    'yearly_nominal_close_ratios': yearly, 'full_xnys_calendar_complete': True,
    'physical_ohlcv_invalid_rows': 0, 'ordinary_dividend_cash_actions_created': 0,
    'source_independence': 'WIKI versus Yahoo source overlap; IEX versus Yahoo only for missing row. Multiple Yahoo archives are not independent vendors.',
    'limits': ['Some exact dividend record/pay dates use secondary tables corroborated by provider factors; issuer sources confirm annual amounts and selected individual payments.',
               '2021Q2 full share table ends July31; September3 cover share count and nominal overlap support the August19 endpoint, not a daily corporate-action ledger.',
               'No prices after August19,2021 or terminal event are supplied; all global unresolved research gates remain.']}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2,default=str)+'\n')
print(json.dumps({'rows':len(v2),'tail':len(extension),'correction':correction,'sha256':sha(v2_path),'source_years_nominal_match':len(yearly)},indent=2))
