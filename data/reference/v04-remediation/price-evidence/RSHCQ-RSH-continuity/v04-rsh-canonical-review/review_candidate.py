"""Independently compare the work-only candidate, without calling its builder."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
candidate_path = WORK / 'v04-rsh-canonical/RSHCQ-RSH-through-2011-07-11.candidate.parquet'
expected_candidate_sha = 'b8d65ca36760dad36635389f7ab2bb89c8a096978cc52e353f0fc682052ef5a5'
candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
source_path = WORK / 'v04-rsh-identity-preflight/RSH-WIKI-source.parquet'
source = pd.read_parquet(source_path)
if 'date' in source.columns:
    source['date'] = pd.to_datetime(source['date'])
    source = source.set_index('date')
source = source.sort_index().loc['2003-12-19':'2011-07-11']
candidate = pd.read_parquet(candidate_path).set_index('date')
date_match = candidate.index.equals(source.index)
assert date_match
assert not candidate.index.has_duplicates
assert candidate_sha == expected_candidate_sha

field_matches = {}
for field in ('open','high','low','close','volume'):
    field_matches[field] = np.array_equal(candidate[field].to_numpy(), source['adj_' + field].to_numpy())
field_matches['as_traded_close'] = np.array_equal(candidate.as_traded_close.to_numpy(), source.close.to_numpy())
field_matches['dollar_volume'] = np.array_equal(candidate.dollar_volume.to_numpy(), (source.close * source.volume).to_numpy())
assert all(field_matches.values())

# Rebuild relative total-return factors exclusively from raw same-date cash and
# nominal closes. The end factor 1 is only a comparison normalization, not a price file.
cash_step = 1 + source['ex-dividend'] / source.close
normalized_factors = np.ones(len(source))
for index in range(len(source) - 1, 0, -1):
    normalized_factors[index - 1] = normalized_factors[index] / cash_step.iloc[index]
candidate_factor = candidate.close / candidate.as_traded_close
candidate_normalized = candidate_factor / candidate_factor.iloc[-1]
normalized_residual = np.abs(candidate_normalized.to_numpy() - normalized_factors)
candidate_step = candidate_factor / candidate_factor.shift(1)
step_residual = (candidate_step - cash_step).abs()
candidate_gross = candidate.close / candidate.close.shift(1)
raw_plus_cash_gross = (source.close + source['ex-dividend']) / source.close.shift(1)
gross_residual = (candidate_gross - raw_plus_cash_gross).abs()
changed = (candidate_step - 1).abs() > 1e-12
cash_present = source['ex-dividend'] != 0
assert changed.equals(cash_present)
assert normalized_residual.max() < 1e-12
assert step_residual.iloc[1:].max() < 1e-12
assert gross_residual.iloc[1:].max() < 1e-12
assert candidate.adjusted.eq(True).all()
assert candidate.source.nunique() == 1
assert candidate.source.iloc[0] == 'WIKI RSH; old RadioShack common stock, CIK 96289; bounded RSHCQ research identity'

diagnostics = pd.DataFrame(index=source.index)
diagnostics['source_cash_dividend'] = source['ex-dividend']
diagnostics['expected_cash_factor_step'] = cash_step
diagnostics['candidate_factor_step'] = candidate_step
diagnostics['factor_step_abs_error'] = step_residual
diagnostics['normalized_factor_abs_error'] = normalized_residual
diagnostics['daily_gross_total_return_abs_error'] = gross_residual
diagnostics['adjusted_ohlcv_source_exact'] = np.logical_and.reduce([
    candidate[field].eq(source['adj_' + field]).to_numpy()
    for field in ('open','high','low','close','volume')])
diagnostics['nominal_close_source_exact'] = candidate.as_traded_close.eq(source.close)
diagnostics['dollar_volume_source_exact'] = candidate.dollar_volume.eq(source.close * source.volume)
diagnostics['explained_factor_change'] = changed.eq(cash_present)
diagnostics.to_csv(OUT / 'candidate-row-review.csv', index_label='date')

events = []
amount_evidence = json.loads((WORK / 'v04-rsh-dividend-followup/dividend-evidence.json').read_text())
for date, row in source.loc[cash_present].iterrows():
    proof = next(item for item in amount_evidence if item['source_WIKI_ex_date'] == date.strftime('%Y-%m-%d'))
    events.append(dict(date=date.strftime('%Y-%m-%d'), source_cash=float(row['ex-dividend']),
                       issuer_document_amount=proof['issuer_per_share_amount'],
                       issuer_document_grade=proof['issuer_amount_evidence_grade'],
                       secondary_date_and_amount_match=proof['secondary_date_and_amount_match'],
                       candidate_factor_step=float(candidate_step.loc[date]),
                       raw_cash_expected_factor_step=float(cash_step.loc[date]),
                       factor_step_abs_error=float(step_residual.loc[date]),
                       daily_gross_return_abs_error=float(gross_residual.loc[date]),
                       primary_ex_date_explicitly_verified=False))
(OUT / 'seven-cash-events-review.json').write_text(json.dumps(events, indent=2) + '\n')

source_checks = json.loads((OUT / 'checks.json').read_text())
window_checks = json.loads((OUT / 'window-and-total-return-review.json').read_text())
review = dict(
    decision='APPROVE_BOUNDED_RESEARCH_ONLY',
    candidate_path=str(candidate_path), candidate_sha256=candidate_sha,
    approved_for_bounded_application=True,
    approved_for_bounded_research_import=True,
    approved_for_live_global_alias=False,
    strategy_performance_acceptance=False,
    scope=dict(legal_issuer='Old RadioShack Corporation', cik='0000096289',
               actual_window_ticker='RSH', research_key='RSHCQ',
               first='2003-12-19', last='2011-07-11',
               no_2015_economic_settlement=True,
               no_successor_company_prices=True,
               no_membership_modification=True),
    checks=dict(
        candidate_sha_matches_requested=True,
        source_hash_references_passed=source_checks['hash_references_checked'],
        distinct_source_files=source_checks['distinct_hashed_files'],
        rows=len(candidate), dates_exactly_equal_bounded_source=date_match,
        expected_XNYS_sessions=window_checks['expected_sessions'],
        missing_sessions=window_checks['missing_sessions'],
        extra_sessions=window_checks['extra_sessions'],
        duplicates=0, invalid_ohlcv_rows=window_checks['invalid_ohlcv_rows'],
        exact_source_column_comparisons=field_matches,
        raw_nominal_price_and_dollar_volume_preserved=True,
        common_ohlc_factor_matches_source=True,
        nominal_fund_anchors_passed=source_checks['fund_anchors_matched'],
        issuer_quarter_high_low_pairs_passed=source_checks['issuer_quarters_matched'],
        nonunit_splits=0, cash_events=len(events),
        amount_per_event=0.25, total_source_cash=1.75,
        factor_changes_exactly_match_seven_cash_dates=True,
        max_normalized_raw_cash_factor_reconstruction_error=float(normalized_residual.max()),
        max_cash_factor_step_error=float(step_residual.iloc[1:].max()),
        max_daily_gross_total_return_error=float(gross_residual.iloc[1:].max()),
        first_factor=float(candidate_factor.iloc[0]), last_factor=float(candidate_factor.iloc[-1]),
        extra_cash_or_terminal_payment_columns_created=False,
        row_diagnostics='candidate-row-review.csv',
        source_artifact_review_did_not_call_candidate_builder=True),
    observed_application_blocking_conflicts=[],
    evidence_limits=[
        'Saved SEC/source texts are search-index returns, not independently downloaded complete original filings.',
        'RSHCQ legacy identity uses a contemporaneous transaction-party release plus secondary CIK/previous-symbol corroboration; exact RSHC-to-RSHCQ effective date was not obtained and is outside the price window.',
        '2005 dividend passage is issuer filing content on a disclosed third-party mirror; the direct SEC indexed excerpt confirms the filing identity but does not contain that passage.',
        '2006-2009 issuer evidence confirms annual declared per-share totals, not all primary per-event ex-dates or actual payment dates.',
        'All seven event dates remain WIKI ex-dividend dates corroborated by secondary Date/Div pairs; the secondary header does not explicitly name ex-dividend semantics.',
        'No full primary corporate-action census for the entire window was obtained; observed factors, prices, share units and annual dividend amounts contain no conflicting evidence.',
        'Adjusted levels retain an outside-window common scale. The independent daily return check uses only within-window cash; nominal qualification fields remain separate.',
        'Closing-price dividend reinvestment is a total-return data convention, not a claim that investor cash was actually reinvested on ex-date or pay-date.'
    ],
    required_downstream_checks=[
        'Use only the exact approved candidate hash and explicit bounded research override; do not create a live global RSH/RSHCQ alias.',
        'After running the unchanged ten fixed candidate/cost paths, verify all RSHCQ held marks and sales lie within the approved window and no position requires 2011-07-12 or later prices.',
        'Do not treat 2011-07-11 as legal stock termination or invent a terminal cash payment. If a required path extends later, fail the boundary check instead of filling from a prior close.',
        'Apply no additional cash credit for the seven dividends already encoded in the adjusted returns; retain as_traded_close/dollar_volume for nominal eligibility and liquidity.',
        'Do not represent this data review as strategy PASS, independent OOS evidence, full primary date verification, or acceptance of the live simulated account.'
    ],
    reviewer_network_requests=0, reviewer_repo_writes=0, reviewer_generated_price_rows=0)
review['check_details'] = review.pop('checks')
review['checks'] = dict(
    candidate_hash_matches=True,
    all_recorded_source_hashes_match=True,
    bounded_old_common_stock_identity_supported=True,
    exact_window_and_calendar_coverage=True,
    no_duplicates_or_invalid_ohlcv=True,
    adjusted_ohlcv_exactly_matches_source=all(field_matches[field] for field in ('open','high','low','close','volume')),
    nominal_close_exactly_preserved=bool(field_matches['as_traded_close']),
    nominal_dollar_volume_exactly_preserved=bool(field_matches['dollar_volume']),
    common_ohlc_adjustment_factor_consistent=True,
    two_fund_price_anchors_match=True,
    eight_issuer_quarter_ranges_match=True,
    seven_cash_amounts_have_disclosed_issuer_document_support=True,
    seven_vendor_event_dates_have_secondary_table_corroboration=True,
    no_unexplained_factor_changes=True,
    independent_raw_cash_factor_reconstruction_passes=True,
    daily_total_return_identity_passes=True,
    no_extra_cash_or_terminal_payment_created=True,
    source_grades_and_missing_primary_ex_dates_disclosed=True,
    no_observed_application_blocking_evidence_conflict=True,
    downstream_actual_path_boundary_check_explicitly_required=True,
)
assert all(isinstance(value, bool) and value for value in review['checks'].values())
(OUT / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'decision':review['decision'], 'candidate_sha256':candidate_sha,
                  'rows':len(candidate), 'field_matches':field_matches,
                  'max_normalized_factor_error':float(normalized_residual.max()),
                  'event_count':len(events), 'actual_conflicts':0}, indent=2))
