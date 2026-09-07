"""Construct one work-only ADS candidate from the saved, explicit issuer ledger."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

OUT = Path(__file__).parent
WORK = OUT.parent
PRE = WORK / 'v04-ads-bounded-preflight'
EVIDENCE = WORK / 'v04-ads-primary-followup'
START, ANCHOR, END = map(pd.Timestamp, ('2012-12-12', '2018-03-27', '2020-07-02'))
PRICE = ['open', 'high', 'low', 'close']
NOMINAL = ['as_traded_close', 'volume', 'dollar_volume']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources = {x['source']: x for x in json.loads((PRE / 'source-index.json').read_text())
               if x['source'] in ('canonical', 'wiki', 'sheepb', 'iex')}
    for item in sources.values():
        assert sha(Path(item['path'])) == item['sha256']
    ledger_path = EVIDENCE / 'dividend-ledger.json'
    ledger = json.loads(ledger_path.read_text())
    events = {pd.Timestamp(e['source_observed_date']): e for e in ledger}
    assert len(events) == len(ledger) == 15
    assert all(e['ticker'] == 'ADS' and e['amount_source_ids'] and
               not e['amount_inferred_from_factor'] and
               type(e['issuer_confirmed_amount']) in (float, int) and
               np.isfinite(e['issuer_confirmed_amount']) and e['issuer_confirmed_amount'] > 0
               for e in ledger)
    assert sum(e['event_role'] == 'old_WIKI_recorded_cash' for e in ledger) == 4
    assert sum(e['event_role'] == 'tail_event' for e in ledger) == 9
    old_missing = {d for d, e in events.items() if e['event_role'] == 'old_prefix_unrecorded_event'}
    assert old_missing == {pd.Timestamp('2017-11-13'), pd.Timestamp('2018-02-13')}
    cash = {d: float(e['issuer_confirmed_amount']) for d, e in events.items()}
    base = pd.read_parquet(sources['canonical']['path']).set_index('date').sort_index()
    wiki = pd.read_parquet(sources['wiki']['path'])
    wiki['date'] = pd.to_datetime(wiki.date)
    wiki = wiki.set_index('date').sort_index()
    raw = pd.read_parquet(sources['sheepb']['path'])
    raw['Date'] = pd.to_datetime(raw.Date)
    raw = raw.set_index('Date').sort_index()
    iex = pd.read_csv(sources['iex']['path'], parse_dates=['date']).set_index('date')
    assert len(base) == 3646 and base.index.max() == ANCHOR and base.index.is_unique
    assert wiki.index.equals(base.index) and wiki.ticker.eq('ADS').all()
    assert wiki.split_ratio.eq(1).all()
    assert raw.index.is_unique and raw.Name.eq('ADS').all()
    assert raw['Company Name'].eq('Alliance Data Systems').all() and iex.Name.eq('ADS').all()
    recorded = wiki.loc[wiki['ex-dividend'].ne(0), 'ex-dividend'].to_dict()
    assert len(recorded) == 4 and all(cash[d] == v for d, v in recorded.items())
    old_factor = base.close / base.as_traded_close
    prefix = base.copy()

    # Whole missing IEX day, on the unchanged neighboring old scale.
    missing = pd.Timestamp('2017-11-08')
    assert missing not in base.index
    before = old_factor.loc[old_factor.index < missing].iloc[-1]
    after = old_factor.loc[old_factor.index > missing].iloc[0]
    assert abs(before - after) < 1e-10
    quote = iex.loc[missing]
    row = base.iloc[0].copy()
    row[PRICE] = quote[PRICE].to_numpy(dtype=float) * before
    row[NOMINAL] = [quote.close, quote.volume, quote.close * quote.volume]
    row['source'] = 'IEX whole missing 2017-11-08 row; old neighboring factor then two verified cash corrections'
    row['downloaded_at'] = pd.NaT  # Original retrieval timestamp is not established.
    prefix.loc[missing] = row
    prefix = prefix.sort_index().astype(base.dtypes.to_dict())

    # Keep the existing March 27 anchor. Correct only the two omitted events;
    # the original four distributions remain embedded exactly once.
    expected = base.copy()
    corrections = []
    for day in sorted(old_missing):
        close = float(prefix.loc[day, 'as_traded_close'])
        assert wiki.loc[day, 'ex-dividend'] == 0
        i = base.index.get_loc(day)
        assert abs(old_factor.iloc[i] / old_factor.iloc[i - 1] - 1) < 1e-10
        multiplier = 1 / (1 + cash[day] / close)
        prefix.loc[prefix.index < day, PRICE] *= multiplier
        expected.loc[expected.index < day, PRICE] *= multiplier
        corrections.append({'date': str(day.date()), 'old_cash': 0, 'issuer_cash': cash[day],
                            'pre_ex_multiplier': multiplier})
    assert_frame_equal(prefix.loc[base.index], expected, check_exact=True)
    assert_frame_equal(prefix.loc[base.index, NOMINAL], base[NOMINAL], check_exact=True)
    assert_frame_equal(prefix.loc[[ANCHOR]], base.loc[[ANCHOR]], check_exact=True)

    # New cash changes the tail factor from its vendor-observed event date;
    # do not normalize the old prefix again or add separate cash entitlements.
    tail = raw.loc[(raw.index > ANCHOR) & (raw.index <= END)].copy()
    cal = xcals.get_calendar('XNYS', start=base.index.min(), end=END)
    sessions = lambda a, b: cal.sessions_in_range(a, b).tz_localize(None)
    assert len(tail) == 571 and tail.index.equals(sessions(ANCHOR, END)[1:])
    factor, factors = float(old_factor.loc[ANCHOR]), []
    for day, quote in tail.iterrows():
        factor *= 1 + cash.get(day, 0) / quote.Close
        factors.append(factor)
    f = pd.Series(factors, index=tail.index)
    extra = pd.DataFrame({**{k: tail[k.title()] * f for k in PRICE},
        'volume': tail.Volume, 'as_traded_close': tail.Close, 'dollar_volume': tail.Close * tail.Volume,
        'adjusted': True,
        'source': 'SheepB v1 Yahoo/yfinance whole OHLCV; issuer cash amounts, vendor event dates, fixed WIKI forward return convention',
        'downloaded_at': pd.Series(pd.NaT, index=tail.index, dtype=base.downloaded_at.dtype)})[base.columns].astype(base.dtypes.to_dict())
    joined = pd.concat([prefix, extra]).sort_index()
    assert len(joined) == 4218 and joined.index.equals(sessions(base.index.min(), END))
    required = joined.loc[START:END]
    assert len(required) == 1902 and required.index.equals(sessions(START, END))
    assert np.isfinite(joined[PRICE + NOMINAL]).all().all() and joined[PRICE + NOMINAL].gt(0).all().all()
    assert joined.high.ge(joined[['open', 'close', 'low']].max(axis=1)).all()
    assert joined.low.le(joined[['open', 'close', 'high']].min(axis=1)).all()
    c = pd.Series(cash).reindex(joined.index).fillna(0)
    error = (joined.close.pct_change() - ((joined.as_traded_close + c) / joined.as_traded_close.shift(1) - 1)).abs().max()
    assert error < 1e-10
    output = OUT / 'ADS-repaired-through-2020-07-02.candidate.parquet'
    final = joined.rename_axis('date').reset_index()
    final.to_parquet(output, index=False)
    assert_frame_equal(pd.read_parquet(output), final, check_exact=True)
    audit = {'status': 'WORK_CANDIDATE_REQUIRES_INDEPENDENT_REVIEW', 'approved_for_application': False,
        'candidate': {'path': str(output), 'sha256': sha(output), 'rows': len(final), 'tail_rows': 571},
        'baseline_sha256': sources['canonical']['sha256'], 'source_inputs': sources,
        'issuer_ledger_sha256': sha(ledger_path), 'prefix_corrections': corrections,
        'normalization': 'Keep 2018-03-27 anchor unchanged; two missing old cash events alone change pre-ex adjusted OHLC; nine tail events advance the factor from each vendor date without renormalizing old prefix.',
        'original_four_cash_events_retained_once': True, 'nominal_fields_unchanged': True,
        'new_row_download_times_unknown_NaT': True, 'maximum_return_identity_error': float(error),
        'required_window': ['2012-12-12', '2020-07-02'], 'required_sessions': 1902,
        'first_normal_post_removal_nominal_open': float(tail.loc[END, 'Open']),
        'event_date_grade': 'Vendor-observed dates retained; only 2017-02-13 has an explicit secondary ex-date in this packet; no primary ex-date claim.',
        'payment_grade': '2020 two amounts have issuer declarations; actual payment not separately obtained.',
        'ordinary_cash_actions_added': 0, 'source_end_is_not_terminal': True,
        'older_prefix_not_newly_certified': True, 'repo_changed': False, 'network_requests': 0}
    (OUT / 'build-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
