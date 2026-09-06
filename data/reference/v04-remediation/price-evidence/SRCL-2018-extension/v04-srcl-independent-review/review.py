"""Independent, zero-network review of one fixed SRCL data candidate."""
from pathlib import Path
import hashlib
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
SRC = OUT.parent / 'v04-srcl-bounded'
REPO = Path('/Users/fighting/code/short-hold-momentum')
CANDIDATE = SRC / 'SRCL-through-2018-12-28.candidate.parquet'
EXPECTED_SHA = 'f3c6c3325c4d582a89905183ec0f16c14f84c511928c68c2e0afe8492d2102bd'
CANONICAL = REPO / 'data/research/v04/prices/SRCL.parquet'
START, END, TAIL_START, GAP = [pd.Timestamp(s) for s in ['2007-11-12', '2018-12-28', '2018-03-28', '2017-11-08']]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False) + '\n')


def indexed(path, date_col='date'):
    f = pd.read_csv(path) if path.suffix == '.csv' else pd.read_parquet(path)
    f.index = pd.DatetimeIndex(pd.to_datetime(f[date_col])).tz_localize(None).normalize()
    return f.drop(columns=[date_col]).sort_index()


def equal_fields(a, b, columns):
    return {c: bool((a[c].eq(b[c]) | (a[c].isna() & b[c].isna())).all()) for c in columns}


source_index = load(SRC / 'source-index.json')
sources = {item['file']: {'expected': item['sha256'], 'actual': sha(SRC / item['file'])} for item in source_index}
before = {str(CANDIDATE): sha(CANDIDATE), str(CANONICAL): sha(CANONICAL),
          **{str(SRC / x): item['actual'] for x, item in sources.items()}}
build = load(SRC / 'build-audit.json')
old = indexed(SRC / 'SRCL-current-override.original.parquet')
current = indexed(CANONICAL)
c = indexed(CANDIDATE)
wiki = indexed(SRC / 'SRCL-WIKI.raw-source.parquet')
sheep = indexed(SRC / 'SRCL-SheepB.raw-source.parquet', 'Date')
iex = indexed(SRC / 'SRCL-IEX.source.csv')
required = c.loc[START:END]
tail = c.loc[TAIL_START:END]
new_dates = c.index.difference(old.index)
calendar = xcals.get_calendar('XNYS', start=START - pd.Timedelta(days=10), end=END + pd.Timedelta(days=10))
expected = calendar.sessions_in_range(START, END).tz_localize(None)
expected_tail = calendar.sessions_in_range(TAIL_START, END).tz_localize(None)
expected_new = expected_tail.union(pd.DatetimeIndex([GAP]))
numeric = ['open', 'high', 'low', 'close', 'volume', 'as_traded_close', 'dollar_volume']
old_fields = equal_fields(old, c.reindex(old.index), old.columns)
checks = {
    'candidate_hash_matches_declared_fixed_artifact': sha(CANDIDATE) == EXPECTED_SHA == build['candidate_sha256'],
    'source_index_hashes_match': all(x['expected'] == x['actual'] for x in sources.values()),
    'baseline_copy_is_unchanged_current_override': sha(CANONICAL) == sha(SRC / 'SRCL-current-override.original.parquet') == build['baseline_sha256'],
    'all_original_rows_retained': old.index.isin(c.index).all().item(),
    'same_column_set': list(c.columns) == list(old.columns),
    'all_original_fields_preserved_exactly': all(old_fields.values()),
    'new_dates_exactly_one_gap_plus_191_tail': new_dates.equals(expected_new),
    'required_calendar_complete_no_extra': required.index.equals(expected),
    'tail_calendar_complete_no_extra': tail.index.equals(expected_tail),
    'dates_unique': not c.index.has_duplicates,
    'candidate_ends_at_bound': c.index.max() == END,
    'candidate_contains_expected_3838_rows': len(c) == 3838 and len(required) == 2802 and len(tail) == 191,
    'finite_required_numeric_fields': bool(np.isfinite(required[numeric].to_numpy()).all()),
    'positive_required_prices': bool(required[['open', 'high', 'low', 'close', 'as_traded_close']].gt(0).all().all()),
    'nonnegative_volume_and_dollar_volume': bool(required[['volume', 'dollar_volume']].ge(0).all().all()),
    'required_ohlc_internally_coherent': bool((required.high.ge(required[['open', 'close', 'low']].max(axis=1)) & required.low.le(required[['open', 'close', 'high']].min(axis=1))).all()),
    'new_rows_downloaded_at_left_unknown': bool(c.loc[new_dates, 'downloaded_at'].isna().all()),
    'all_rows_adjusted_flag_true': bool(c.adjusted.eq(True).all()),
    'required_window_close_is_nominal': bool(required.close.eq(required.as_traded_close).all()),
    'required_WIKI_no_recorded_cash_events': bool(wiki.loc[START:, 'ex-dividend'].eq(0).all()),
    'required_WIKI_no_recorded_split_events': bool(wiki.loc[START:, 'split_ratio'].eq(1).all()),
    'required_SheepB_adjusted_equals_close': bool(sheep.loc[START:END, 'Adj Close'].eq(sheep.loc[START:END, 'Close']).all()),
}
tail_mapping = {c: c.title() for c in ['open', 'high', 'low', 'close', 'volume']}
tail_fields = {field: bool(tail[field].eq(sheep.loc[expected_tail, src]).all()) for field, src in tail_mapping.items()}
gap_fields = {field: bool(c.loc[GAP, field] == iex.loc[GAP, field]) for field in ['open', 'high', 'low', 'close', 'volume']}
checks.update({
    'tail_is_whole_original_SheepB_OHLCV': all(tail_fields.values()),
    'gap_is_whole_original_IEX_OHLCV': all(gap_fields.values()),
    'new_rows_nominal_close_equals_selected_source_close': bool(c.loc[new_dates, 'as_traded_close'].eq(c.loc[new_dates, 'close']).all()),
    'new_rows_dollar_volume_is_nominal_close_times_source_shares': bool(c.loc[new_dates, 'dollar_volume'].eq(c.loc[new_dates, 'as_traded_close'] * c.loc[new_dates, 'volume']).all()),
    'no_new_ordinary_cash_credit_proposed': build['ordinary_cash_credits_created'] == 0,
    'no_new_corporate_action_proposed': build['corporate_actions_created'] == 0,
})
new_observations = c.loc[new_dates].copy()
new_observations.to_csv(OUT / 'reviewed-new-rows.csv', index_label='date')
source_evidence = load(OUT / 'source-evidence-review.json')
checks['issuer_source_text_hash_bound'] = source_evidence['filing_content']['sha256'] == sha(SRC / '2018-10K.edgar-online.indexed.txt')
checks['exact_Stericycle_SEC_identity'] = source_evidence['SEC_direct_identity']['cik'] == '0000861878' and source_evidence['SEC_direct_identity']['name'] == 'STERICYCLE INC'
checks['issuer_2016_2018_common_cash_policy_confirmed'] = 'We did not declare or pay any cash dividends on our common stock during 2018, 2017 or 2016.' in source_evidence['filing_content']['common_stock_identity_and_cash_dividends_excerpt']
checks['preferred_conversion_not_treated_as_common_distribution'] = 'Series A Mandatory Convertible Preferred Stock' in source_evidence['filing_content']['preferred_conversion_excerpt'] and checks['no_new_corporate_action_proposed'] and checks['no_new_ordinary_cash_credit_proposed']

after = {p: sha(p) for p in before}
checks['all_reviewed_inputs_unchanged_during_review'] = before == after
summary = {
    'decision': 'APPROVE_BOUNDED_APPLICATION' if all(checks.values()) else 'DO_NOT_APPLY',
    'candidate_path': str(CANDIDATE), 'candidate_sha256': EXPECTED_SHA,
    'scope': {'required_start': str(START.date()), 'required_end': str(END.date()),
        'candidate_first_preserved': str(c.index.min().date()), 'candidate_rows': len(c),
        'required_rows': len(required), 'unchanged_original_rows': len(old), 'new_whole_row_count': len(new_dates),
        'one_restored_date': str(GAP.date()), 'tail_start': str(TAIL_START.date()), 'tail_rows': len(tail)},
    'checks': checks, 'failed_checks': [name for name, passed in checks.items() if not passed],
    'all_old_columns_exact': old_fields, 'IEX_whole_row_fields': gap_fields, 'SheepB_whole_tail_fields': tail_fields,
    'IEX_gap_row': {field: float(c.loc[GAP, field]) for field in numeric},
    'source_evidence': source_evidence,
    'inherited_source_differences': {'not_modified_or_adjudicated': True,
        'examples': {'2017-06-08_open': {'WIKI': float(wiki.loc['2017-06-08', 'open']), 'SheepB': float(sheep.loc['2017-06-08', 'Open'])},
                     '2017-06-23_volume': {'WIKI': float(wiki.loc['2017-06-23', 'volume']), 'SheepB': float(sheep.loc['2017-06-23', 'Volume'])}},
        'interpretation': 'These are existing vendor disagreements in unchanged rows, not evidence authorizing replacement of the old prefix. No new acceptance tolerance is introduced.'},
    'specific_conflict_blocking_this_bounded_application': None if all(checks.values()) else [name for name, passed in checks.items() if not passed],
    'review_limits': ['Bounded data application only, not global PRICE_REPAIR_EVIDENCE closure.',
        '2007-2015 retains existing WIKI evidence; no newly obtained complete issuer split/dividend/spinoff census.',
        'New issuer text confirms no common cash dividends for2016-2018; preferred dividends/conversion do not accrue to existing common holdings.',
        'The 191-day tail is vendor archive evidence with source-scale corroboration, not issuer/exchange-certified daily quotes.',
        'Performance graph numeric values are absent from retained source text; no invented comparison was made.',
        'Actual holdings/executions/receivables must be checked in the original ten fixed candidate/cost paths after application; no automatic forced Dec28 sale is introduced.',
        'No later acquisition lifecycle or source expansion is approved.'],
    'constraints': {'new_network_requests': 0, 'backtests_run': 0, 'repo_writes': 0, 'producer_files_written': 0,
        'new_acceptance_standards': 0},
}
dump('review.json', summary)
dump('input-hashes.json', {'before': before, 'after': after, 'unchanged': before == after})
print(json.dumps({'decision': summary['decision'], 'candidate_sha256': EXPECTED_SHA,
    'failed_checks': summary['failed_checks'], 'scope': summary['scope']}, indent=2))
