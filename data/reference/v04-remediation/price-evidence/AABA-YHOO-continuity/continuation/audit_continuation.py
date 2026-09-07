"""Local evidence reconciliation and independent review of the AABA diagnostic join."""
from pathlib import Path
import hashlib
import json
import textwrap

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
PRIMARY = OUT / 'primary-evidence/2017-NCSR-main.txt'
CANDIDATE = WORK / 'v04-aaba-canonical/AABA-YHOO-through-2017-12-29.diagnostic.parquet'
WIKI = WORK / 'v04-aaba-identity/YHOO-WIKI-source.parquet'
TAIL = WORK / 'v04-aaba-tail-candidate/AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet'
URL = 'https://www.sec.gov/Archives/edgar/data/1011006/000119312518058471/d434197dncsr.htm'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + '\n')


text = PRIMARY.read_text()
sections = [
    ('Cash flows', '13', 'ALTABA INC. CONSOLIDATED STATEMENT OF CASH FLOWS', 'ALTABA INC. CONSOLIDATED STATEMENT OF CHANGES IN NET ASSETS'),
    ('Changes in net assets', '14', 'ALTABA INC. CONSOLIDATED STATEMENT OF CHANGES IN NET ASSETS', 'ALTABA INC. FINANCIAL HIGHLIGHTS'),
    ('Financial highlights', '15', 'ALTABA INC. FINANCIAL HIGHLIGHTS', 'ALTABA INC. NOTES TO CONSOLIDATED FINANCIAL STATEMENTS'),
    ('Capital share transactions', '34-35', 'Note 14 Capital Share Transactions', 'Note 15 Distributions'),
    ('Distributions policy', '35', 'Note 15 Distributions', 'Note 16 Principal Risks'),
]
excerpts = []
for title, page, begin, end in sections:
    start = text.index(begin)
    stop = text.index(end, start + len(begin))
    quote = text[start:stop]
    excerpts.append({'section': title, 'printed_page': page, 'start_character': start, 'end_character': stop,
                     'quote': quote, 'url': URL})
assert all(term in text for term in ['68,799', '8,432,186', '62,485,919', '824,921,315', '32.85', '69.85'])
assert text.find('Report of Independent Registered Public Accounting Firm', 200000) > 0
prior_period_start = text.index('CONSOLIDATED FINANCIAL STATEMENTS For the Period from January 1, 2017', 200000)
assert prior_period_start > max(e['end_character'] for e in excerpts)
dump('primary-excerpts.json', excerpts)
lines = ['# Altaba 2017 H2 primary excerpts', '', f'Source: {URL}', '']
for item in excerpts:
    lines += [f"## {item['section']} — printed page {item['printed_page']}", '',
              textwrap.fill(item['quote'], width=120, replace_whitespace=True), '']
(OUT / 'primary-excerpts.md').write_text('\n'.join(lines))

fund_reconciliation = {
    'reporting_period': ['2017-06-16', '2017-12-31'], 'units': 'USD thousands',
    'net_assets_beginning': 50201124, 'net_increase_from_operations': 20648182,
    'common_share_issuance_proceeds': 68799, 'common_share_repurchases': -8432186,
    'reported_net_assets_end': 62485919, 'reported_net_cash_from_operations': 8363787,
    'reported_net_cash_used_in_financing': -8363387, 'reported_net_change_in_cash': 400,
}
fund_reconciliation['net_asset_bridge_residual'] = 62485919 - (50201124 + 20648182 + 68799 - 8432186)
fund_reconciliation['financing_bridge_residual'] = -8363387 - (68799 - 8432186)
fund_reconciliation['cash_change_bridge_residual'] = 400 - (8363787 - 8363387)
assert all(fund_reconciliation[k] == 0 for k in ['net_asset_bridge_residual', 'financing_bridge_residual', 'cash_change_bridge_residual'])
fund_reconciliation['interpretation'] = 'Audited statements account for reported capital cash flows through share issuance and repurchases, with no shareholder distribution line or unexplained residual. This is affirmative statement reconciliation, not inference from a missing CSV dividend column.'
fund_reconciliation['precision_limit'] = 'Financial statement dollar amounts are reported in thousands; zero means no reported shareholder distribution, not a claim of an independently queried exhaustive exchange action feed.'
dump('financial-statement-reconciliation.json', fund_reconciliation)

candidate = pd.read_parquet(CANDIDATE)
wiki = pd.read_parquet(WIKI).loc[lambda d: d.date >= '2003-10-01'].reset_index(drop=True)
raw = pd.read_parquet(TAIL).reset_index(drop=True)
prefix = candidate.loc[candidate.date <= '2017-06-16'].reset_index(drop=True)
tail = candidate.loc[candidate.date >= '2017-06-19'].reset_index(drop=True)
assert len(candidate) == 3588 and len(prefix) == 3452 and len(tail) == 136
checks = {}
for col in ['open', 'high', 'low', 'close', 'volume']:
    checks[f'prefix_{col}_equals_WIKI_adjusted'] = bool(np.array_equal(prefix[col], wiki['adj_' + col]))
    checks[f'tail_{col}_equals_unscaled_Google'] = bool(np.array_equal(tail[col], raw[col.title()]))
checks['prefix_nominal_close_equals_WIKI_raw'] = bool(np.array_equal(prefix.as_traded_close, wiki.close))
checks['prefix_dollar_volume_equals_raw_close_times_raw_volume'] = bool(np.array_equal(prefix.dollar_volume, wiki.close * wiki.volume))
checks['tail_nominal_close_equals_Google_Close'] = bool(np.array_equal(tail.as_traded_close, raw.Close))
checks['tail_dollar_volume_equals_raw_close_times_raw_volume'] = bool(np.array_equal(tail.dollar_volume, raw.Close * raw.Volume))
checks['terminal_WIKI_factor_equals_one'] = bool(prefix.close.iloc[-1] / prefix.as_traded_close.iloc[-1] == 1)
cal = xc.get_calendar('XNYS', start='2003-01-01', end='2018-01-31')
sessions = cal.sessions_in_range(candidate.date.min(), candidate.date.max()).tz_localize(None)
checks['all_candidate_XNYS_sessions_present'] = bool(pd.DatetimeIndex(candidate.date).equals(sessions))
checks['unique_dates'] = bool(candidate.date.is_unique)
bar = candidate[['open', 'high', 'low', 'close', 'volume']]
valid = np.isfinite(bar).all(axis=1) & (bar > 0).all(axis=1)
valid &= candidate.high.ge(candidate[['open', 'close', 'low']].max(axis=1))
valid &= candidate.low.le(candidate[['open', 'close', 'high']].min(axis=1))
checks['all_OHLCV_valid'] = bool(valid.all())
assert all(checks.values())
total_returns = candidate.close.pct_change()
nominal_returns = candidate.as_traded_close.pct_change()
return_error = (total_returns - nominal_returns).loc[candidate.date >= '2017-06-19'].abs().max()
assert return_error < 1e-12
anchors = pd.to_datetime(['2017-05-25', '2017-06-15', '2017-06-16', '2017-06-19', '2017-06-23', '2017-06-26', '2017-07-24', '2017-12-29'])
candidate.loc[candidate.date.isin(anchors)].to_csv(OUT / 'candidate-key-dates.csv', index=False)
assert candidate.loc[candidate.date.eq(pd.Timestamp('2017-06-26')), 'open'].iloc[0] == 55.38
reference_start = float(candidate.loc[candidate.date.eq(pd.Timestamp('2017-06-15')), 'close'].iloc[0])
reference_end = float(candidate.loc[candidate.date.eq(pd.Timestamp('2017-12-29')), 'close'].iloc[0])
reference_return = reference_end / reference_start - 1
assert round(reference_return * 100, 2) == 32.85
independent_review = {
    'candidate_path': str(CANDIDATE), 'candidate_sha256': sha(CANDIDATE), 'candidate_rows': len(candidate),
    'decision': 'JOIN_MATCHES_AUDITED_2017_H2_CONTINUITY_CONCLUSION', 'checks': checks,
    'tail_max_daily_return_difference_from_nominal_price_returns': float(return_error),
    'official_end_market_price': 69.85, 'candidate_end_market_price': reference_end,
    'official_market_total_return_percent': 32.85,
    'reference_prior_close_date': '2017-06-15', 'reference_prior_close': reference_start,
    'reference_price_return_percent': reference_return * 100,
    'market_return_crosscheck': 'Report period starts June 16; June 15 prior close is 52.58. 69.85 / 52.58 - 1 rounds to official 32.85%. This corroborates no additional distribution adjustment; it is not a standalone proof of the action ledger.',
    'last_WIKI_close_date': '2017-06-16', 'last_WIKI_close': 52.5892,
    'Google_same_date_close': 52.58, 'unrescaled_boundary_difference_usd': .0092,
    'first_Google_tail_open_date': '2017-06-19', 'first_Google_tail_open': 54.,
    'first_post_removal_cycle_signal_date_parent_verified': '2017-06-23',
    'next_open_for_that_cycle': '2017-06-26', 'next_open_quote': 55.38,
    'execution_limit': 'These are schedule and quote anchors, not proof that every strategy actually holds or exits AABA on June 26. Parent will validate actual fills across candidates.',
    'source_label_note': 'Candidate source currently still says action review pending; this read-only review does not modify that label or candidate bytes.',
    'candidate_modified_by_review': False, 'repo_modified_by_review': False,
}
dump('independent-candidate-review.json', independent_review)

conclusion = {
    'status': 'CONTINUITY_SUPPORTED_BY_AUDITED_FINANCIAL_STATEMENTS_AND_IDENTITY_EVIDENCE',
    'period': {'from': '2017-06-19', 'through': '2017-12-29'},
    'reported_holder_cash_distributions': {'ordinary_dividend': 0., 'special_dividend': 0., 'mandatory_cash_distribution': 0.,
        'evidence_basis': ['Audited cash flow statement p13', 'Audited changes in net assets p14', 'Financial highlights p15', 'Notes 14/15 pp34-35'],
        'interpretation': 'No shareholder distribution is reported for the audited June16-Dec31 period, and the published statements reconcile without one.'},
    'share_unit_continuity': {'continuation_factor': 1., 'mandatory_stock_exchange': False,
        'evidence_basis': 'June19 identity 8-K says shareholder action not required; audited Note14 accounts for common-share capital activity as employee option/RSU issuance and voluntary buybacks, with no split or mandatory exchange reported.'},
    'voluntary_corporate_actions': {'employee_share_issuance_approximately': 4100000,
        'repurchased_shares_approximately': 138400000, 'self_tender_shares_approximately': 64500000,
        'open_market_repurchase_shares_approximately': 73900000, 'shares_outstanding_2017_12_31': 824921315,
        'nonparticipant_holder_treatment': 'No separate cash credit or change in held units for a shareholder who neither tenders nor sells. Issuance/buyback effects are already reflected in market price.'},
    'proposed_total_return_join': {'preserve_WIKI_adjusted_prefix': True, 'prefix_last_date': '2017-06-16',
        'prefix_last_adjustment_factor': 1., 'append_Google_whole_nominal_OHLCV_from': '2017-06-19',
        'tail_adjustment_factor': 1., 'additional_cash_return': 0., 'terminal_cash_event': False,
        'nominal_price_and_dollar_volume': 'Use source Close and source Volume for tail dollar volume. Preserve WIKI raw dollar-volume values and adjusted OHLCV for prefix.'},
    'nominal_unit_support': ['Google source overlap with WIKI in 2017 has matching dollar-per-share scale',
        'SEC financial highlights end market price USD 69.85 exactly matches final raw quote',
        'Official 32.85% market total return matches the prior-close to period-end price ratio at stated precision',
        'Audited capital share activity supports unchanged share units for continuing holders'],
    'financial_statement_reconciliation': fund_reconciliation,
    'independent_candidate_review': independent_review,
    'primary_source': URL, 'primary_capture_characters': len(text),
    'capture_scope': 'Main HTML capture includes the entire Altaba June16-Dec31 financial statements, Notes1-16 and auditor report; it continues into the earlier Yahoo period but ends before that earlier period is complete.',
    'limited_capture_not_used_as_full_proof': 'request-02 .txt capture has only 11696 characters and ends in the investment schedule.',
    'qualifications': ['No independent exchange corporate-action feed was queried; conclusion is supported by complete audited period statements, identity notice, and price-return crosscheck.',
        'Issued and repurchased share counts in Note14 are approximate; do not describe them as an exact per-share rollforward.',
        'Fund dividend income from underlying holdings is not an AABA shareholder payout.',
        'Do not apply 2018 tenders or 2019 liquidation distributions backward into this 2017 source.',
        'Prior WIKI corporate actions before the reviewed period are inherited, not re-audited here.',
        'Actual strategy holding/exit path remains a separate parent-side validation.'],
    'public_requests_used': 4, 'public_request_limit': 4, 'new_price_provider_calls': 0,
    'network_calls_by_audit_script': 0, 'repo_or_manifest_modified': False,
}
dump('audit.json', conclusion)
dump('total-return-join-proposal.json', conclusion['proposed_total_return_join'])
print(json.dumps({'status': conclusion['status'], 'financial_reconciliation': fund_reconciliation,
                  'candidate_review': independent_review}, indent=2))
