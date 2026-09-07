"""Zero-network, source-only RSH/RSHCQ preflight; no applicable candidate."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
REPO = Path('/Users/fighting/code/short-hold-momentum')
CSV = OUT / 'RSH-WIKI-source.csv'
ARCHIVE = WORK / 'v04-remediation-archive/wiki-prices.zip'
STUDY = REPO / 'reports/v04/v04-cf5a0714087194e8/selection.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


if not CSV.exists():
    with zipfile.ZipFile(ARCHIVE) as archive, archive.open('WIKI_PRICES.csv') as source, CSV.open('wb') as target:
        target.write(source.readline())
        for line in source:
            if line.startswith(b'RSH,'):
                target.write(line)
data = pd.read_csv(CSV, parse_dates=['date'])
data.to_parquet(OUT / 'RSH-WIKI-source.parquet', index=False)
assert len(data) == 8344 and data.ticker.eq('RSH').all() and data.date.is_unique
cal = xc.get_calendar('XNYS', start='1982-01-01', end='2015-12-31')
study = json.loads(STUDY.read_text())
rebalance = pd.DatetimeIndex(pd.to_datetime([x['date'] for x in study['price_coverage']['rebalance_dates']]))
first_signal = rebalance.min()
first_signal_pos = cal.sessions.get_loc(first_signal)
warmup_start = cal.sessions[first_signal_pos-260].tz_localize(None)
members = pd.read_csv(REPO / 'data/reference/sp500_history.csv', parse_dates=['date'])
member_flag = members.tickers.str.split(',').map(lambda xs: 'RSHCQ' in xs)
last_member = members.loc[member_flag, 'date'].max()
last_member_signal = rebalance[rebalance <= last_member].max()
first_after_signal = rebalance[rebalance > last_member].min()
next_open = cal.next_session(first_after_signal).tz_localize(None)
expected = cal.sessions_in_range(warmup_start, next_open).tz_localize(None)
window = data.loc[data.date.between(warmup_start, next_open)].copy()
assert warmup_start == pd.Timestamp('2003-12-19') and next_open == pd.Timestamp('2011-07-11')
assert len(window) == 1902 and pd.DatetimeIndex(window.date).equals(expected)
numeric = window[['open', 'high', 'low', 'close', 'volume']]
valid = np.isfinite(numeric).all(axis=1) & (numeric > 0).all(axis=1)
valid &= window.high.ge(window[['open', 'close', 'low']].max(axis=1))
valid &= window.low.le(window[['open', 'close', 'high']].min(axis=1))
assert valid.all()

factor = data.adj_close / data.close
observed_step = factor / factor.shift(1)
expected_step = data.split_ratio * (data.close + data['ex-dividend']) / data.close
mask = data.date.between(warmup_start, next_open)
errors = (observed_step - expected_step).abs().loc[mask]
assert errors.max() < 1e-12
ohlc_errors = {}
for c in ['open', 'high', 'low', 'close']:
    error = (window['adj_' + c] - window[c] * (window.adj_close / window.close)).abs().max()
    ohlc_errors[c] = float(error)
    assert error < 1e-10
assert window.adj_volume.eq(window.volume).all()
actions = window.loc[window['ex-dividend'].ne(0) | window.split_ratio.ne(1)].copy()
assert len(actions) == 7 and actions['ex-dividend'].eq(.25).all() and window.split_ratio.eq(1).all()
actions['observed_factor_step'] = observed_step.loc[actions.index]
actions['formula_factor_step'] = expected_step.loc[actions.index]
actions['evidence_level'] = 'WIKI observed fields and internally consistent adjustment; no issuer action proof yet'
actions.to_csv(OUT / 'required-window-vendor-cash-actions.csv', index=False)
window[['date', 'close', 'ex-dividend', 'split_ratio', 'adj_close']].assign(
    factor=(window.adj_close / window.close),
    observed_step=observed_step.loc[window.index],
    expected_step=expected_step.loc[window.index]).to_csv(OUT / 'required-window-factor-audit.csv', index=False)

coverage = pd.DataFrame({'date': expected, 'quote_present': expected.isin(data.date)})
coverage['prior_260_sessions_present'] = coverage.quote_present.shift(1).rolling(260, min_periods=260).sum().eq(260)
member_signals = rebalance[(rebalance >= first_signal) & (rebalance <= last_member)]
assert len(member_signals) == 82
assert coverage.loc[coverage.date.isin(member_signals), 'prior_260_sessions_present'].all()
coverage.to_csv(OUT / 'minimal-window-date-coverage.csv', index=False)
window.loc[window.date.isin([warmup_start, first_signal, last_member_signal, last_member, first_after_signal, next_open])].to_csv(OUT / 'boundary-observations.csv', index=False)

anchors = []
evidence_dir = REPO / 'data/reference/v04-remediation/corporate-action-evidence'
for year, day, shares, value in [(2004, '2004-09-30', 722842, 20702195), (2005, '2005-09-30', 565742, 14030402)]:
    p = evidence_dir / f'spy-{year}-membership.primary.txt'
    t = p.read_text()
    metadata = json.loads((evidence_dir / f'spy-{year}-membership.evidence.json').read_text())
    assert sha(p) == metadata['sha256']
    line = next(line for line in t.splitlines() if 'RadioShack Corp.' in line)
    row = data.loc[data.date.eq(day)].iloc[0]
    price = value / shares
    assert abs(price - row.close) < .000001 and abs(row.close * shares - value) <= .50
    anchors.append({'date': day, 'issuer_label': 'RadioShack Corp.', 'fund_common_shares': shares,
        'fund_reported_value_usd': value, 'implied_nominal_price': price, 'WIKI_raw_close': float(row.close),
        'WIKI_adjusted_close_not_nominal': float(row.adj_close), 'rounding_difference_total_usd': float(row.close * shares - value),
        'source_url': metadata['source_url'], 'source_path': str(p), 'source_sha256': metadata['sha256'], 'quote': line,
        'limit': 'Dated fund common-stock name and valuation support old issuer/nominal price scale; do not establish the RSHCQ identifier bridge.'})
dump('existing-primary-fund-price-anchors.json', anchors)

manifest = json.loads((REPO / 'data/reference/v04-remediation/manifest.json').read_text())
study_member_sessions = cal.sessions_in_range(first_signal, last_member).tz_localize(None)
future_actions = data.loc[data.date.gt(next_open) & data['ex-dividend'].ne(0), ['date', 'ex-dividend']]
audit = {
    'status': 'STRUCTURALLY_COMPLETE_BOUNDED_SOURCE_IDENTITY_NOT_APPROVED',
    'network_requests': 0, 'repo_modified': False, 'applicable_candidate_generated': False,
    'raw_archive_rows_extracted_for_inspection_only': True,
    'membership': {'key': 'RSHCQ', 'full_local_history_first': str(members.loc[member_flag, 'date'].min().date()),
        'last_member_session': str(last_member.date()), 'first_nonmember_session': '2011-07-01',
        'research_first_signal': str(first_signal.date()), 'study_period': study['period'],
        'research_member_sessions': len(study_member_sessions), 'member_rebalance_dates': len(member_signals),
        'RSH_separate_membership_label_present': bool(members.tickers.str.split(',').map(lambda xs: 'RSH' in xs).any()),
        'source_membership_date_evidence_only': True},
    'minimal_window': {'warmup_definition': '260 complete XNYS sessions strictly before first 2005-01-03 signal, plus signal date and subsequent holding/exit observations',
        'first': str(warmup_start.date()), 'last': str(next_open.date()), 'rows': len(window),
        'last_member_signal': str(last_member_signal.date()),
        'last_member_signal_next_open': str(cal.next_session(last_member_signal).date()),
        'first_post_removal_signal': str(first_after_signal.date()), 'first_post_removal_next_open': str(next_open.date()),
        'schedule_reference': str(STUDY), 'schedule_reference_run': study['run_id'],
        'actual_counterfactual_exit_not_yet_proven': True},
    'source': {'ticker': 'RSH', 'archive_company_label': 'RadioShack Corp.', 'raw_first': str(data.date.min().date()),
        'raw_last': str(data.date.max().date()), 'raw_rows': len(data), 'archive_path': str(ARCHIVE),
        'csv_path': str(CSV), 'csv_sha256': sha(CSV), 'parquet_path': str(OUT / 'RSH-WIKI-source.parquet'),
        'parquet_sha256': sha(OUT / 'RSH-WIKI-source.parquet'), 'is_only_raw_source': True},
    'structural_checks_in_minimal_window': {'expected_XNYS_sessions': len(expected), 'missing_sessions': [], 'duplicates': 0,
        'invalid_OHLCV_rows': 0, 'all_82_member_signal_prior260_windows_complete': True,
        'cash_events': 7, 'cash_sum_vendor_observed_only': 1.75, 'nonunit_splits': 0,
        'max_factor_formula_residual': float(errors.max()), 'max_OHLC_common_factor_residual': ohlc_errors,
        'adj_volume_equals_raw_volume': True},
    'adjustment_anchor': {'at_minimal_start': float(window.adj_close.iloc[0] / window.close.iloc[0]),
        'at_minimal_end': float(window.adj_close.iloc[-1] / window.close.iloc[-1]),
        'later_source_cash_observations_outside_scope': future_actions.to_dict('records'),
        'interpretation': 'Archive adjusted levels retain later cash adjustments as a common scale factor across the bounded window. Do not treat adjusted levels as nominal prices or apply these later cash events inside the 2003-2011 window. No source row is changed here.'},
    'vendor_action_dates': actions.date.dt.strftime('%Y-%m-%d').tolist(),
    'existing_primary_nominal_anchors': anchors,
    'identity_status': 'Local name and price anchors support historical RadioShack common stock, but no primary dated RSH-to-RSHCQ legal/common-share identifier bridge is present in inspected local evidence.',
    'current_manifest_alias_RSHCQ': manifest.get('aliases', {}).get('RSHCQ'),
    'current_manifest_override_RSHCQ': manifest.get('price_overrides', {}).get('RSHCQ'),
    '2015_bankruptcy_or_OTC_economic_event_needed_for_minimal_window': False,
    '2015_scope_reason': 'The first scheduled post-membership exit is July11 2011. A bounded research window and verified actual exits can end years before the 2015 source tail. A later OTC record may be useful solely to prove the historical identifier bridge, not to value a simulated 2015 liquidation.',
    'minimum_remaining_evidence': [
        'A primary issuer/SEC/exchange record identifies old RadioShack RSH ordinary common shares and the RSHCQ historical label as the same legacy security, with dated legal issuer/CIK and share-class/CUSIP context. Do not substitute a later RadioShack-branded reorganized security.',
        'Primary dividend/stock-capital disclosures covering the seven observed USD0.25 annual events and confirming the ordinary share units in the bounded period; exact ex-dates may remain separately graded if supported by dated historical records.',
        'After any approved bounded construction, actual fixed strategy paths must show that held marks and sales do not require prices beyond the chosen endpoint; this is a local path check, not another external data request.'
    ],
    'not_required_now': ['Full 2015 bankruptcy settlement valuation', 'OTC price reconstruction to equity cancellation', 'Successor-company prices', 'A terminal-cash assumption at 2015-02-02'],
}
dump('audit.json', audit)
print(json.dumps({'status': audit['status'], 'window': audit['minimal_window'], 'checks': audit['structural_checks_in_minimal_window']}, indent=2))
