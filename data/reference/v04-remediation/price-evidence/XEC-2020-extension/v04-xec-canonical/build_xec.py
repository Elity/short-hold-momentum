"""Work-only XEC candidate. Requires a verified ledger; never fetches or applies data."""
from pathlib import Path
import argparse
import hashlib
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

OUT = Path(__file__).parent
PREFLIGHT = OUT.parent / 'v04-xec-extension-preflight'
ANCHOR, END = pd.Timestamp('2018-03-27'), pd.Timestamp('2020-03-10')
PRICE = ['open', 'high', 'low', 'close']
NOMINAL = ['as_traded_close', 'volume', 'dollar_volume']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', required=True, type=Path)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text())
    assert ledger['status'] == 'VERIFIED_FOR_WORK_BUILD', 'Ledger is not verified; no candidate written.'
    assert ledger['ticker'] == 'XEC'
    assert all(ledger.get(k) for k in ('snapshot_time', 'issuer_cik', 'identity_and_units_evidence', 'normal_exit_quote_evidence'))
    stamp = pd.Timestamp(ledger['snapshot_time'])
    assert stamp.tzinfo is not None
    events = {pd.Timestamp(e['ex_date']): e for e in ledger['events']}
    assert len(events) == len(ledger['events'])
    assert all(e['status'] == 'confirmed' and e.get('evidence') and
               type(e['cash']) in (float, int) and np.isfinite(e['cash']) and e['cash'] >= 0
               for e in events.values()), 'Every cash decision needs a confirmed amount, including explicit zero.'
    needs = json.loads((PREFLIGHT / 'minimum-external-evidence.json').read_text())['items']
    required = {pd.Timestamp(d) for item in needs if item['id'] in
                ('XEC_PREFIX_DIVIDEND_CONFLICTS', 'XEC_TAIL_DIVIDENDS_8') for d in item['dates']}
    assert required <= events.keys(), 'All 3 disputed prefix dates and 8 tail dates need explicit decisions.'
    preflight = json.loads((PREFLIGHT / 'audit.json').read_text())
    paths = {k: Path(preflight['inputs'][k]['path']) for k in ('canonical', 'sheepb')}
    for key, path in paths.items():
        assert sha(path) == preflight['inputs'][key]['sha256'], f'Changed input: {key}'
    base = pd.read_parquet(paths['canonical']).set_index('date').sort_index()
    raw = pd.read_parquet(paths['sheepb'])
    raw['Date'] = pd.to_datetime(raw.Date)
    raw = raw.set_index('Date').sort_index()
    assert len(base) == 3646 and base.index.max() == ANCHOR and base.index.is_unique and raw.index.is_unique
    assert all(base.index.min() <= d <= END for d in events)
    assert raw.Name.eq('XEC').all() and raw['Company Name'].eq('Cimarex Energy').all()
    iex_path = PREFLIGHT / 'XEC-IEX-existing-archive.csv'
    iex_meta = json.loads((PREFLIGHT / 'iex-existing-local-source.json').read_text())
    assert sha(iex_path) == iex_meta['member_sha256']
    iex = pd.read_csv(iex_path, parse_dates=['date']).set_index('date')
    assert iex.Name.eq('XEC').all()
    recorded = pd.read_csv(PREFLIGHT / 'wiki-recorded-events-and-factor-crosscheck.csv', parse_dates=['date']).set_index('date')
    assert recorded.wiki_split_ratio.eq(1).all() and not preflight['prefix_nonunit_split_rows']
    old_cash = recorded.wiki_dividend.to_dict()
    old_factor = base.close / base.as_traded_close
    prefix = base.copy()

    # Whole IEX row replacement: original nominal C/V/turnover must stay exact.
    repair_day = pd.Timestamp('2015-08-28')
    quote = iex.loc[repair_day]
    assert quote.close == base.loc[repair_day, 'as_traded_close']
    assert quote.volume == base.loc[repair_day, 'volume']
    assert abs(quote.close * quote.volume - base.loc[repair_day, 'dollar_volume']) < 1e-8
    prefix.loc[repair_day, PRICE] = quote[PRICE].to_numpy(dtype=float) * old_factor.loc[repair_day]
    prefix.loc[repair_day, ['source', 'downloaded_at']] = ['IEX whole 2015-08-28 row; retained legacy factor before ledger corrections', stamp]

    # Whole missing IEX day; carry the verified unchanged old neighboring basis.
    missing = pd.Timestamp('2017-11-08')
    assert missing not in base.index
    before = old_factor.loc[old_factor.index < missing].iloc[-1]
    after = old_factor.loc[old_factor.index > missing].iloc[0]
    assert abs(before - after) < 1e-10
    quote = iex.loc[missing]
    row = base.iloc[0].copy()
    row[PRICE] = quote[PRICE].to_numpy(dtype=float) * before
    row[NOMINAL] = [float(quote.close), float(quote.volume), float(quote.close * quote.volume)]
    row['source'], row['downloaded_at'] = 'IEX whole missing 2017-11-08 row; old neighboring factor then ledger corrections', stamp
    prefix.loc[missing] = row
    prefix = prefix.sort_index().astype(base.dtypes.to_dict())

    # Hold the March 27 anchor fixed. Change only pre-ex price units for each
    # approved old-event decision; never derive the verified amount from factors.
    expected = base.copy()
    corrections = []
    for day, e in sorted(events.items()):
        if day > ANCHOR:
            continue
        close = float(prefix.loc[day, 'as_traded_close'])
        prior_cash = float(old_cash.get(day, 0.0))
        q_old, q_new = 1 + prior_cash / close, 1 + e['cash'] / close
        if day in base.index:
            i = base.index.get_loc(day)
            assert i > 0 and abs(old_factor.iloc[i] / old_factor.iloc[i - 1] - q_old) < 1e-10
        multiplier = q_old / q_new
        prefix.loc[prefix.index < day, PRICE] *= multiplier
        expected.loc[expected.index < day, PRICE] *= multiplier
        corrections.append({'ex_date': str(day.date()), 'source_recorded_cash': prior_cash,
                            'verified_cash': e['cash'], 'pre_ex_multiplier': multiplier})
    retained = base.index.difference([repair_day])
    assert_frame_equal(prefix.loc[retained], expected.loc[retained], check_exact=True)
    assert np.array_equal(prefix.loc[base.index, NOMINAL].to_numpy(), base[NOMINAL].to_numpy())
    assert_frame_equal(prefix.loc[[ANCHOR]], base.loc[[ANCHOR]], check_exact=True)

    tail = raw.loc[(raw.index > ANCHOR) & (raw.index <= END)].copy()
    cal = xcals.get_calendar('XNYS', start=base.index.min(), end=END)
    assert len(tail) == 491 and tail.index.equals(cal.sessions_in_range(ANCHOR, END)[1:].tz_localize(None))
    factor, factors = float(prefix.loc[ANCHOR, 'close'] / prefix.loc[ANCHOR, 'as_traded_close']), []
    for day, quote in tail.iterrows():
        factor *= 1 + events.get(day, {}).get('cash', 0.0) / quote.Close
        factors.append(factor)
    f = pd.Series(factors, index=tail.index)
    extra = pd.DataFrame({**{k: tail[k.title()] * f for k in PRICE},
        'volume': tail.Volume, 'as_traded_close': tail.Close, 'dollar_volume': tail.Close * tail.Volume,
        'adjusted': True, 'source': 'SheepB v1 Yahoo/yfinance whole OHLCV; verified ledger and fixed WIKI return convention',
        'downloaded_at': stamp})[base.columns].astype(base.dtypes.to_dict())
    joined = pd.concat([prefix, extra]).sort_index()
    assert len(joined) == 4138 and joined.index.equals(cal.sessions_in_range(base.index.min(), END).tz_localize(None))
    assert np.isfinite(joined[PRICE + NOMINAL]).all().all() and joined[PRICE + NOMINAL].gt(0).all().all()
    assert joined.high.ge(joined[['open', 'close', 'low']].max(axis=1)).all()
    assert joined.low.le(joined[['open', 'close', 'high']].min(axis=1)).all()
    cash = pd.Series({**old_cash, **{d: e['cash'] for d, e in events.items()}}).reindex(joined.index).fillna(0)
    error = (joined.close.pct_change() - ((joined.as_traded_close + cash) / joined.as_traded_close.shift(1) - 1)).abs().max()
    assert error < 1e-10
    output = OUT / 'XEC-repaired-through-2020-03-10.candidate.parquet'
    final = joined.rename_axis('date').reset_index()
    final.to_parquet(output, index=False)
    assert_frame_equal(pd.read_parquet(output), final, check_exact=True)
    for key, path in paths.items():
        assert sha(path) == preflight['inputs'][key]['sha256']
    audit = {'status': 'WORK_CANDIDATE_REQUIRES_ROOT_REVIEW', 'approved_for_application': False,
        'candidate': {'path': str(output), 'sha256': sha(output), 'rows': len(final), 'tail_rows': 491},
        'ledger_sha256': sha(args.ledger), 'preflight_sha256': sha(PREFLIGHT / 'audit.json'),
        'source_cash_table_sha256': sha(PREFLIGHT / 'wiki-recorded-events-and-factor-crosscheck.csv'),
        'source_inputs': preflight['inputs'], 'iex_sha256': sha(iex_path), 'prefix_corrections': corrections,
        'old_nominal_fields_unchanged': True, 'anchor_unchanged': True, 'maximum_return_identity_error': float(error),
        'first_normal_post_removal_open': float(tail.loc[END, 'Open']), 'no_ordinary_cash_actions': True,
        'aliases_changed': False, 'repo_changed': False, 'network_requests': 0,
        'source_end_is_not_terminal': True, 'post_repair_path_exit_still_requires_research_review': True}
    (OUT / 'build-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit['candidate'], indent=2))


if __name__ == '__main__':
    main()
