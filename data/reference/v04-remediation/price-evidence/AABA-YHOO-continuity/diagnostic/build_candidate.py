"""Build a work-only AABA diagnostic; acceptance requires a separate action review."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
WIKI = WORK / 'v04-aaba-identity/YHOO-WIKI-source.parquet'
TAIL = WORK / 'v04-aaba-tail-candidate/AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert sha(WIKI) == 'd144fb2c24d02561cfcc015b7a813d574ec8f7c0191cb3c2fa1ccb73eef16128'
assert sha(TAIL) == '1bbe90f4d5467505946ea8e6fb2bc77884ada785cbdd3db698c9d7f604c93ee1'
wiki = pd.read_parquet(WIKI)
wiki = wiki.loc[wiki.date.ge('2003-10-01')].copy()
tail = pd.read_parquet(TAIL).rename(columns=str.lower)
assert wiki.date.max() == pd.Timestamp('2017-06-16')
assert tail.date.min() == pd.Timestamp('2017-06-19')
assert wiki['ex-dividend'].eq(0).all()
assert (wiki.adj_close / wiki.close).iloc[-1] == 1.0

# Preserve vendor split-adjusted WIKI history. Nominal eligibility inputs are
# raw Close and dollar turnover, not current adjusted prices.
prefix = pd.DataFrame({'date': wiki.date,
    **{field: wiki['adj_' + field] for field in ('open', 'high', 'low', 'close', 'volume')},
    'as_traded_close': wiki.close, 'dollar_volume': wiki.close * wiki.volume,
    'adjusted': True, 'source': 'WIKI YHOO; issuer identity reviewed as historical AABA'})

# This unit-factor continuation is diagnostic until primary action evidence is
# reviewed. It does not infer dividends from absent fields in the raw source.
suffix = tail[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
suffix['as_traded_close'] = tail.close
suffix['dollar_volume'] = tail.close * tail.volume
suffix['adjusted'] = True
suffix['source'] = 'Google Finance AABA via szrlee fixed commit 55639c5; action review pending'
candidate = pd.concat([prefix, suffix], ignore_index=True)
calendar = xc.get_calendar('XNYS', start=candidate.date.min(), end=candidate.date.max())
sessions = calendar.sessions_in_range(candidate.date.min(), candidate.date.max()).tz_localize(None)
numeric = candidate[['open', 'high', 'low', 'close', 'volume', 'as_traded_close', 'dollar_volume']]
assert len(candidate) == 3588
assert pd.DatetimeIndex(candidate.date).equals(sessions)
assert np.isfinite(numeric).all().all() and numeric.gt(0).all().all()
assert candidate.high.ge(candidate[['open', 'low', 'close']].max(axis=1)).all()
assert candidate.low.le(candidate[['open', 'high', 'close']].min(axis=1)).all()
assert candidate.date.is_unique
for field in ('open', 'high', 'low', 'close', 'volume'):
    assert np.array_equal(candidate[field].iloc[:len(wiki)], wiki['adj_' + field])
    assert np.array_equal(candidate[field].iloc[len(wiki):], tail[field])
assert np.array_equal(candidate.as_traded_close.iloc[:len(wiki)], wiki.close)
path = OUT / 'AABA-YHOO-through-2017-12-29.diagnostic.parquet'
candidate.to_parquet(path, index=False)
details = {
    'status': 'DIAGNOSTIC_NOT_APPLIED_ACTION_REVIEW_REQUIRED',
    'candidate_path': str(path), 'candidate_sha256': sha(path),
    'rows': len(candidate), 'prefix_rows': len(wiki), 'tail_rows': len(tail),
    'first': str(candidate.date.min().date()), 'last': str(candidate.date.max().date()),
    'sources': {str(WIKI): sha(WIKI), str(TAIL): sha(TAIL)},
    'prefix_adjusted_OHLCV_preserved_exactly': True,
    'nominal_close_and_dollar_volume_preserved': True,
    'raw_tail_unscaled': True, 'missing_sessions': [], 'invalid_rows': 0,
    'conditional_total_return_assumption': 'No mandatory distributions or split units affecting the appended 2017 interval; requires separate primary action review.',
    'no_terminal_cash_or_membership_change_created': True,
    'no_repo_files_modified': True,
}
(OUT / 'build-audit.json').write_text(json.dumps(details, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(details, ensure_ascii=False, indent=2))
