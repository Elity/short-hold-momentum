"""Build a bounded, work-only old RadioShack research input from pinned WIKI rows."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
REPO = Path('/Users/fighting/code/short-hold-momentum')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = WORK / 'v04-rsh-identity-preflight/RSH-WIKI-source.parquet'
assert sha(source) == '36c70a34e8e1b1fef2f923202f01424473bb4f9d20af2612fa26ec41d832007f'
raw = pd.read_parquet(source).sort_values('date')
window = raw.loc[raw.date.between('2003-12-19', '2011-07-11')].reset_index(drop=True)
sessions = xc.get_calendar('XNYS', start='2003-01-01', end='2012-01-01').sessions_in_range(
    '2003-12-19', '2011-07-11').tz_localize(None)
assert len(window) == 1902 and pd.DatetimeIndex(window.date).equals(sessions)
assert window.ticker.eq('RSH').all() and window.split_ratio.eq(1).all()
assert window.adj_volume.eq(window.volume).all()
frame = pd.DataFrame({'date': window.date})
for key in ('open', 'high', 'low', 'close', 'volume'):
    frame[key] = window['adj_' + key].astype(float)
frame['as_traded_close'] = window.close.astype(float)
frame['dollar_volume'] = window.close * window.volume
frame['adjusted'] = True
frame['source'] = 'WIKI RSH; old RadioShack common stock, CIK 96289; bounded RSHCQ research identity'
values = frame[['open', 'high', 'low', 'close', 'volume', 'as_traded_close', 'dollar_volume']]
assert np.isfinite(values).all().all() and values.gt(0).all().all()
assert frame.high.ge(frame[['open', 'close', 'low']].max(axis=1)).all()
assert frame.low.le(frame[['open', 'close', 'high']].min(axis=1)).all()

factor = window.adj_close / window.close
observed = frame.close.pct_change()
economic = (window.close + window['ex-dividend']) / window.close.shift(1) - 1
return_error = float((observed - economic).abs().max())
assert return_error < 1e-12
events = window.loc[window['ex-dividend'].ne(0), ['date', 'ex-dividend']]
ledger = pd.read_csv(WORK / 'v04-rsh-dividend-followup/dividend-evidence.csv')
assert len(events) == len(ledger) == 7 and events['ex-dividend'].eq(.25).all()
manifest = REPO / 'data/reference/v04-remediation/manifest.json'
assert sha(manifest) == 'f72f790593308936868f0435511943648743047b116c54042e6c5b202a148389'
candidate = OUT / 'RSHCQ-RSH-through-2011-07-11.candidate.parquet'
frame.to_parquet(candidate, index=False)
result = {
    'status': 'WORK_ONLY_CANDIDATE_PENDING_INDEPENDENT_REVIEW',
    'network_requests': 0, 'repo_modified': False,
    'source': {'path': str(source), 'sha256': sha(source), 'ticker': 'RSH'},
    'candidate': {'path': str(candidate), 'sha256': sha(candidate), 'research_key': 'RSHCQ',
                  'first': '2003-12-19', 'last': '2011-07-11', 'rows': len(frame)},
    'baseline_manifest_sha256': sha(manifest),
    'adjusted_ohlcv_exactly_preserved': True,
    'nominal_close_and_dollar_volume_preserved': True,
    'maximum_total_return_identity_error': return_error,
    'ordinary_dividends': {'events': 7, 'amount_each': .25, 'total': 1.75,
                           'extra_cash_events_created': 0,
                           'primary_ex_dates_explicitly_verified': False},
    'factor_at_start': float(factor.iloc[0]), 'factor_at_end': float(factor.iloc[-1]),
    'limits': [
        'The source adjusted-level anchor includes later ordinary dividends as a common scale; later payments are not credited inside this bounded window.',
        'Amounts have issuer annual-filing support; 2005 cash passage uses a disclosed third-party filing mirror; exact ex-dates retain vendor grade with secondary Date/Div corroboration.',
        'No live global alias, successor-company prices, bankruptcy terminal cash, synthetic fill, or membership modification.',
        '2011-07-11 is a fixed schedule/quote boundary, not a legal stock termination; actual ten fixed strategy paths must be checked after research.'
    ]
}
(OUT / 'build-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
