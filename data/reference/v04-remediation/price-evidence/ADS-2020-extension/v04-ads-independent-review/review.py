"""Independent zero-network audit of one ADS source ledger and fixed candidate."""
from pathlib import Path
import hashlib
import json
import re

import exchange_calendars as xcals
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
EVIDENCE = WORK / 'v04-ads-primary-followup'
BUILD = WORK / 'v04-ads-canonical'
PRE = WORK / 'v04-ads-bounded-preflight'
REPO = Path('/Users/fighting/code/short-hold-momentum')
CANDIDATE = BUILD / 'ADS-repaired-through-2020-07-02.candidate.parquet'
CANDIDATE_SHA = 'ff8ee755db4e74b7e127b1147f4cd41e1c9977fb774796faf9a637c9dd384438'
LEDGER_SHA = 'f21ad921d2fbc3c57110cb030d279871175c8b143b6f066589e9734acdd1a927'
START, ANCHOR, END, GAP = map(pd.Timestamp, ['2012-12-12', '2018-03-27', '2020-07-02', '2017-11-08'])
PRICE = ['open', 'high', 'low', 'close']
NOMINAL = ['as_traded_close', 'volume', 'dollar_volume']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str, allow_nan=False) + '\n')


def frame(path, date='date'):
    f = pd.read_csv(path) if Path(path).suffix == '.csv' else pd.read_parquet(path)
    f[date] = pd.to_datetime(f[date])
    return f.set_index(date).sort_index()


def normalize(text):
    return re.sub(r'\s+', ' ', text.replace('\u200b', ' ')).strip()


def exactly(a, b):
    return bool((a.eq(b) | (a.isna() & b.isna())).all().all())


sources = {x['source']: x for x in read(PRE / 'source-index.json') if x['source'] in ['wiki', 'canonical', 'sheepb', 'iex']}
issuer_sources = {x['source_id']: x for x in read(EVIDENCE / 'source-index.json')}
inputs = [CANDIDATE, EVIDENCE / 'dividend-ledger.json', EVIDENCE / 'source-index.json', EVIDENCE / 'issuer-and-date-excerpts.json',
          *[Path(x['path']) for x in sources.values()], *[EVIDENCE / x['file'] for x in issuer_sources.values()]]
before = {str(p): sha(p) for p in inputs}
base = frame(Path(sources['canonical']['path']))
wiki = frame(Path(sources['wiki']['path']))
sheep = frame(Path(sources['sheepb']['path']), 'Date')
iex = frame(Path(sources['iex']['path']))
c = frame(CANDIDATE)
ledger = read(EVIDENCE / 'dividend-ledger.json')
cash = pd.Series({pd.Timestamp(e['source_observed_date']): float(e['issuer_confirmed_amount']) for e in ledger})
roles = pd.Series({pd.Timestamp(e['source_observed_date']): e['event_role'] for e in ledger})
old_missing = pd.Series({pd.Timestamp('2017-11-13'): .52, pd.Timestamp('2018-02-13'): .57})
expected_amounts = [.52] * 5 + [.57] * 4 + [.63] * 5 + [.21]
dates_from_preflight = pd.DatetimeIndex(pd.read_csv(PRE / 'ADS-factor-event-observations.csv').date)
texts = {sid: normalize((EVIDENCE / x['file']).read_text()) for sid, x in issuer_sources.items()}
excerpts = read(EVIDENCE / 'issuer-and-date-excerpts.json')
quote_checks = [{'id': x['id'], 'source_id': x['source_id'], 'matches': normalize(x['quote']) in texts[x['source_id']]} for x in excerpts]

checks = {
    'fixed_candidate_hash': sha(CANDIDATE) == CANDIDATE_SHA,
    'fixed_ledger_hash': sha(EVIDENCE / 'dividend-ledger.json') == LEDGER_SHA,
    'all_raw_source_hashes_match': all(sha(x['path']) == x['sha256'] for x in sources.values()),
    'all_issuer_source_hashes_match': all(sha(EVIDENCE / x['file']) == x['sha256'] for x in issuer_sources.values()),
    'all_issuer_excerpts_match_saved_content': len(quote_checks) == 13 and all(x['matches'] for x in quote_checks),
    'fifteen_dates_and_amounts_match_supported_schedule': len(ledger) == 15 and cash.index.equals(dates_from_preflight) and cash.tolist() == expected_amounts,
    'event_roles_are_four_old_two_missing_nine_tail': roles.value_counts().to_dict() == {'tail_event': 9, 'old_WIKI_recorded_cash': 4, 'old_prefix_unrecorded_event': 2},
    'all_amounts_supported_by_source_ids_not_factors': all(e['amount_source_ids'] and not e['amount_inferred_from_factor'] for e in ledger),
    '2017_11_13_is_0_52': cash[pd.Timestamp('2017-11-13')] == .52 and 'Fourth quarter 0.52 28.7' in texts['P17M'],
    'issuer_identity_common_stock_consistent': all('ALLIANCE DATA SYSTEMS CORPORATION' in texts[sid] and '31-1429215' in texts[sid] for sid in ['P17M', 'P19M']) and 'ADS' in texts['P20Q2_SEC'],
    'primary_ex_date_not_overclaimed': all(e['primary_ex_date'] is None and not e['primary_ex_date_explicitly_verified'] for e in ledger),
    'actual_payment_vs_declaration_grade_preserved': sum(e['actual_paid_per_share_quarter_supported'] for e in ledger) == 13 and all(not e['actual_paid_per_share_quarter_supported'] and 'DECLARATION_ONLY' in e['issuer_amount_evidence_scope'] for e in ledger if e['source_observed_date'].startswith('2020')),
}

# Date-role consistency check only; supplier dates remain supplier-grade.
dated = []
cal = xcals.get_calendar('XNYS', start='2003-09-01', end='2020-07-10')
all_dates = cal.sessions_in_range('2003-10-01', END).tz_localize(None)
for e in ledger:
    if e['issuer_record_date'] is None:
        continue
    day, record = pd.Timestamp(e['source_observed_date']), pd.Timestamp(e['issuer_record_date'])
    sessions = cal.sessions_in_range(day, record).tz_localize(None)
    expected_gap = 2 if day < pd.Timestamp('2017-09-05') else 1
    dated.append({'date': str(day.date()), 'record': str(record.date()),
        'declaration': e['issuer_declaration_date'], 'payment': e['issuer_payment_date'],
        'record_minus_observed_session_count': len(sessions) - 1, 'historical_normal_ex_offset': expected_gap,
        'consistent': bool(len(sessions) - 1 == expected_gap and pd.Timestamp(e['issuer_declaration_date']) < day < pd.Timestamp(e['issuer_payment_date']))})
checks['all_eight_dated_declarations_consistent_with_observed_order'] = len(dated) == 8 and all(x['consistent'] for x in dated)

# Preserve original metadata and nominal observations.  Only the two dated
# multiplicative corrections may alter old adjusted OHLC; tail cash is forward.
old_c = c.reindex(base.index)
non_price = [col for col in base.columns if col not in PRICE]
multiplier = pd.Series(1.0, index=base.index)
for day, amount in old_missing.items():
    multiplier.loc[multiplier.index < day] *= base.loc[day, 'as_traded_close'] / (base.loc[day, 'as_traded_close'] + amount)
expected_old = base[PRICE].mul(multiplier, axis=0)
checks.update({
    'same_original_columns': list(c.columns) == list(base.columns),
    'all_original_dates_retained': bool(base.index.isin(c.index).all()),
    'all_original_non_price_fields_exact': exactly(old_c[non_price], base[non_price]),
    'all_original_nominal_fields_exact': exactly(old_c[NOMINAL], base[NOMINAL]),
    'old_adjusted_OHLC_only_two_missing_cash_corrections': bool(np.allclose(old_c[PRICE], expected_old, rtol=1e-12, atol=1e-10)),
    '2018_03_27_anchor_all_fields_exact': exactly(c.loc[[ANCHOR]], base.loc[[ANCHOR]]),
    'old_rows_from_second_event_onward_all_fields_exact': exactly(c.reindex(base.loc[pd.Timestamp('2018-02-13'):].index), base.loc[pd.Timestamp('2018-02-13'):]),
    'old_four_recorded_amounts_match_and_not_reapplied': wiki.loc[wiki['ex-dividend'].ne(0), 'ex-dividend'].to_dict() == cash.loc[roles.eq('old_WIKI_recorded_cash')].to_dict(),
})
tail = c.loc[c.index > ANCHOR]
tail_dates = cal.sessions_in_range(ANCHOR, END).tz_localize(None)[1:]
new_dates = c.index.difference(base.index)
required_dates = cal.sessions_in_range(START, END).tz_localize(None)
checks.update({
    'full_candidate_calendar_4218_unique_rows': len(c) == 4218 and not c.index.has_duplicates and c.index.equals(all_dates),
    'required_calendar_1902_rows_complete': c.loc[START:END].index.equals(required_dates) and len(required_dates) == 1902,
    'new_dates_only_gap_plus_571_tail': new_dates.equals(tail_dates.union(pd.DatetimeIndex([GAP]))) and len(tail) == 571,
    'all_fields_finite_positive_and_OHLC_coherent': bool(np.isfinite(c[PRICE + NOMINAL]).all().all() and c[PRICE + NOMINAL].gt(0).all().all() and c.high.ge(c[['open', 'close', 'low']].max(axis=1)).all() and c.low.le(c[['open', 'close', 'high']].min(axis=1)).all()),
    'new_download_timestamps_unknown': bool(c.loc[new_dates, 'downloaded_at'].isna().all()),
})
tail_cash = cash.loc[roles.eq('tail_event')].reindex(tail_dates).fillna(0.0)
tail_nominal = sheep.loc[tail_dates]
expected_factor = (1 + tail_cash / tail_nominal.Close).cumprod()
actual_factor = tail.close / tail.as_traded_close
tail_fields = {col: bool(np.allclose(tail[col], tail_nominal[col.title()] * expected_factor, rtol=1e-12, atol=1e-10)) for col in PRICE}
gap_factor = (base.close / base.as_traded_close).loc[:GAP].iloc[-1]
gap_factor *= np.prod([base.loc[day, 'as_traded_close'] / (base.loc[day, 'as_traded_close'] + amount) for day, amount in old_missing.items() if GAP < day])
gap_fields = {col: bool(np.isclose(c.loc[GAP, col], iex.loc[GAP, col] * gap_factor, rtol=1e-12, atol=1e-10)) for col in PRICE}
checks.update({
    'tail_only_nine_forward_factors_from_one_anchor': bool(np.allclose(actual_factor, expected_factor, rtol=1e-12, atol=1e-12)) and float(actual_factor.iloc[0]) == 1.0,
    'tail_adjusted_fields_from_whole_SheepB_OHLC': all(tail_fields.values()),
    'tail_nominal_fields_whole_SheepB_exact': bool(tail.as_traded_close.eq(tail_nominal.Close).all() and tail.volume.eq(tail_nominal.Volume).all() and tail.dollar_volume.eq(tail_nominal.Close * tail_nominal.Volume).all()),
    'gap_adjusted_fields_from_whole_IEX_OHLC': all(gap_fields.values()),
    'gap_nominal_fields_whole_IEX_exact': c.loc[GAP, 'as_traded_close'] == iex.loc[GAP, 'close'] and c.loc[GAP, 'volume'] == iex.loc[GAP, 'volume'] and c.loc[GAP, 'dollar_volume'] == iex.loc[GAP, 'close'] * iex.loc[GAP, 'volume'],
})

# The price-ratio check is independent of the construction path: the adjustment
# carries each supported cash amount once in the stock total-return convention.
daily_cash = cash.reindex(c.index).fillna(0)
economic_ratio = (c.as_traded_close + daily_cash) / c.as_traded_close.shift(1)
output_ratio = c.close / c.close.shift(1)
max_return_error = float((output_ratio - economic_ratio).abs().max())
checks['all_day_cash_total_return_identity_no_double_count'] = max_return_error < 1e-10

source_summary = read(OUT / 'preliminary-source-review.json')
checks['eight_nominal_anchor_comparisons_are_nonempty_and_pass'] = len(source_summary['nominal_anchor_checks']) == 8 and all(x['matches_reported_cent'] for x in source_summary['nominal_anchor_checks'])
after = {p: sha(p) for p in before}
checks['all_bound_inputs_unchanged_during_audit'] = before == after
checks = {name: bool(passed) for name, passed in checks.items()}

event_rows = []
for day, amount in cash.items():
    i = c.index.get_loc(day)
    event_rows.append({'date': str(day.date()), 'role': roles.loc[day], 'issuer_amount': float(amount),
        'nominal_close': float(c.loc[day, 'as_traded_close']), 'expected_factor_step': float(1 + amount / c.loc[day, 'as_traded_close']),
        'observed_factor_step': float((c.close / c.as_traded_close).iloc[i] / (c.close / c.as_traded_close).iloc[i - 1]),
        'total_return_identity_error': float(abs(output_ratio.loc[day] - economic_ratio.loc[day]))})
pd.DataFrame(event_rows).to_csv(OUT / 'reviewed-fifteen-event-steps.csv', index=False)
dump('source-excerpt-checks.json', quote_checks)
dump('input-hashes.json', {'before': before, 'after': after, 'unchanged': before == after})
result = {'decision': 'APPROVE_BOUNDED_APPLICATION' if all(checks.values()) else 'DO_NOT_APPLY',
    'candidate_path': str(CANDIDATE), 'candidate_sha256': CANDIDATE_SHA, 'issuer_ledger_sha256': LEDGER_SHA,
    'required_window': [str(START.date()), str(END.date())], 'candidate_rows': len(c), 'required_rows': len(required_dates),
    'checks': checks, 'failed_checks': [k for k, v in checks.items() if not v],
    'cash_amount_sum': float(cash.sum()), 'cash_reconstruction_max_return_identity_error': max_return_error,
    'fixed_anchor': str(ANCHOR.date()), 'tail_factor_start': float(actual_factor.iloc[0]), 'tail_factor_end': float(actual_factor.iloc[-1]),
    'old_prefix_price_correction_values': sorted(multiplier.unique().tolist()),
    'gap_corrected_factor': float(gap_factor), 'gap_adjusted_field_checks': gap_fields, 'tail_adjusted_field_checks': tail_fields,
    'dated_declaration_consistency': dated, 'nominal_anchor_checks': source_summary['nominal_anchor_checks'],
    'source_assessment': 'Issuer amounts plus retained vendor-date grades and independent nominal-price anchors are sufficient for this bounded data application. No specific date/amount/unit contradiction was found. This does not certify issuer ex-dates,2020 actual payment,or a complete corporate-action census.',
    'retained_limits': ['All15 primary ex-dates are unverified; only2017-02-13 has a secondary explicit ex-date in this packet.',
        'Thirteen quarterly paid per-share amounts are supported;2020 two amounts only have issuer declarations and stated payable dates.',
        'Vendor factor changes supply event-date observations, never primary cash amounts.2019-09-03 remains unchanged.',
        'Original four WIKI distributions remain embedded once; no separate cash credit,receivable,or terminal action is approved.',
        'Older2003-2012 rows retain nominal data and receive only the same two later-event unit corrections; their source evidence is not newly certified.',
        'Post-2020-07-02 acquisition/spinoff history is outside scope.',
        'Global gates, frozen strategy parameters, account branches and cost models are unchanged. Actual ten fixed paths must be checked after application.'],
    'constraints': {'new_network_requests': 0, 'repo_writes': 0, 'producer_files_written': 0, 'backtests_run': 0}}
dump('review.json', result)
print(json.dumps({'decision': result['decision'], 'failed_checks': result['failed_checks'], 'check_count': len(checks),
    'candidate_sha256': CANDIDATE_SHA, 'tail_factor_start': result['tail_factor_start'], 'tail_factor_end': result['tail_factor_end'],
    'max_return_error': max_return_error}, indent=2))
