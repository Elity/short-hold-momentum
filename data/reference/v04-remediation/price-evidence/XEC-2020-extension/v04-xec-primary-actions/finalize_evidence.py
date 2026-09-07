"""Package the bounded XEC evidence pass without network or repository writes."""
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
PRIMARY = OUT / 'primary-evidence'
PRE = WORK / 'v04-xec-extension-preflight'


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')


req1 = json.loads((PRIMARY / 'request-01-2019-annual-search.json').read_text())
note = next(r for r in req1['webResults'] if '/1168054/' in r['url'])
(PRIMARY / 'XEC-2019-Q2-capital-stock-R13.txt').write_text(note['content'] + '\n')
req4 = json.loads((PRIMARY / 'request-04-issuer-dividend-releases.json').read_text())
secondary = next(r for r in req4['webResults'] if 'a2-finance.com/en/' in r['url'])
(PRIMARY / 'XEC-secondary-A2-history.txt').write_text(secondary['content'] + '\n')
marketlog = next(r for r in req4['webResults'] if 'marketlog.com/symbol/xec' in r['url'])
(PRIMARY / 'XEC-secondary-Marketlog-history.txt').write_text(marketlog['content'] + '\n')

rows = [
    ('2017-09-14', .16, None, None, None, None),
    ('2017-11-14', .08, .08, '2017-09-01', '2017-11-15', '2017-12-01'),
    ('2018-02-14', .08, .08, '2017-12-08', '2018-02-15', '2018-03-01'),
    ('2018-05-14', .16, .16, '2018-02-23', '2018-05-15', '2018-06-01'),
    ('2018-08-14', .16, .16, '2018-05-11', '2018-08-15', '2018-08-31'),
    ('2018-11-14', .18, .18, '2018-08-30', '2018-11-15', '2018-11-30'),
    ('2019-02-14', .18, .18, '2018-12-06', '2019-02-15', '2019-03-01'),
    ('2019-05-14', .20, .20, '2019-02-20', '2019-05-15', '2019-05-31'),
    ('2019-08-14', .20, .20, '2019-05-09', '2019-08-15', '2019-08-30'),
    ('2019-11-14', .20, .20, '2019-08-30', '2019-11-15', '2019-11-29'),
    ('2020-02-13', .20, .20, '2019-12-06', '2020-02-14', '2020-02-28'),
]
events = pd.DataFrame(rows, columns=['candidate_ex_date', 'candidate_cash_usd', 'secondary_cash_usd',
                                   'secondary_declared_date', 'secondary_record_date', 'secondary_pay_date'])
steps = pd.read_csv(PRE / 'sheepb-factor-steps-DIAGNOSTIC-NOT-DIVIDEND-EVIDENCE.csv')
events = events.merge(steps[['date', 'implied_cash_diagnostic_only_NOT_APPROVED']],
    left_on='candidate_ex_date', right_on='date', how='left').drop(columns='date')
events['primary_cash_usd'] = None
events['primary_record_date'] = None
events['primary_payment_window'] = None
events['primary_ex_date_explicit'] = False
events['status'] = 'SECONDARY_AND_FACTOR_CORROBORATED_PRIMARY_AMOUNT_PENDING'
events.loc[events.candidate_ex_date.eq('2017-09-14'), 'status'] = 'WIKI_CONFLICT_NO_SECONDARY_OR_FACTOR_SUPPORT_PRIMARY_ADJUDICATION_PENDING'
idx = events.candidate_ex_date.eq('2019-08-14')
events.loc[idx, 'primary_cash_usd'] = .20
events.loc[idx, 'primary_record_date'] = '2019-08-15'
events.loc[idx, 'primary_payment_window'] = 'on or before 2019-08-30'
events.loc[idx, 'status'] = 'PRIMARY_AMOUNT_RECORD_PAYMENT_WINDOW_VERIFIED_EXDATE_SECONDARY_AND_FACTOR'
events['applied'] = False
events.to_csv(OUT / 'eleven-event-evidence-levels.csv', index=False)
assert len(events) == 11
assert events.primary_cash_usd.notna().sum() == 1
assert events.secondary_cash_usd.notna().sum() == 10
assert '2017-09-14' not in secondary['content']
assert all(s in secondary['content'] for s in events.loc[events.secondary_cash_usd.notna(), 'candidate_ex_date'])

annual = (PRIMARY / 'XEC-2018-10K.txt').read_text()
excerpts = []
for term in ['Our $0.01 par value common stock', 'The closing price of Cimarex stock', 'At January 31, 2019']:
    found = re.search(re.escape(term), annual)
    if found:
        excerpts.append({'term': term, 'source': 'XEC 2018 10-K, Item5 page34',
                         'quote': annual[max(0, found.start()-80):found.end()+430]})
excerpts.append({'term': '2019Q2 common dividend and separate preferred shares',
                 'source': note['url'], 'quote': note['content']})
dump('primary-excerpts.json', excerpts)
sheepb = pd.read_parquet(WORK / 'v04-source-options-next/sheepb-extracted/XEC.parquet')
sheepb['Date'] = pd.to_datetime(sheepb.Date)
anchor = sheepb.loc[sheepb.Date.eq('2019-01-31')].iloc[0]
nominal_anchor_error = abs(float(anchor.Close) - 75.34)
assert nominal_anchor_error < .00001

audit = {
    'status': 'PARTIAL_PRIMARY_EVIDENCE_NOT_READY_FOR_ALL_EVENT_APPROVAL',
    'window': {'start': '2018-03-28', 'end': '2020-03-10', 'tail_sessions_preflight': 491},
    'identity': {'issuer': 'Cimarex Energy Co.', 'CIK': '0001168054', 'ticker': 'XEC',
        'security': 'NYSE ordinary common stock, USD 0.01 par value',
        'primary_evidence': '2018 10-K Item5 and 2019Q2 capital-stock note'},
    'source_dates': {'2018_10K_accession': '0001168054-19-000006',
        '2018_10K_url': 'https://www.sec.gov/Archives/edgar/data/1168054/000116805419000006/a12311810kxec.htm',
        '2019_Q2_accession': '0001168054-19-000017', '2019_Q2_capital_stock_url': note['url'],
        '2017_full_year_10K_located': False, '2019_full_year_10K_located': False},
    'events': events.astype(object).where(pd.notna(events), None).to_dict('records'),
    'event_counts': {'candidates': 11, 'primary_amount_verified': 1,
        'secondary_plus_factor_with_primary_amount_pending': 9, 'WIKI_conflict_pending_primary': 1},
    '2017_09_14': {'WIKI_amount': .16, 'SheepB_factor_step_cash_supported': False,
        'A2_secondary_event_present': False, 'Marketlog_secondary_event_present': False,
        'interpretation': 'Strong suspect of an extra WIKI dividend; absence from sources is not sufficient primary proof to remove it in this pass.',
        'removal_approved': False},
    'tail_cash_total_from_secondary_and_factor_candidates': 1.48,
    'tail_total_fully_primary_verified': False,
    'dates_hierarchy': {'2019_08_14_event': 'Primary amount USD0.20 and record Aug15/pay on-or-before Aug30; exact ex-date Aug14 comes from source factor and secondary history.',
        'other_nine_real_step_events': 'Amounts, declared/record/pay dates from secondary A2/Marketlog; exact ex-dates additionally corroborated by SheepB factor steps.',
        '2017_09_14': 'Only WIKI event field/factor; no confirming secondary entry or SheepB step.'},
    'nominal_units': {'supported_price_anchor_date': '2019-01-31', 'primary_NYSE_close': 75.34,
        'SheepB_Close': float(anchor.Close), 'absolute_difference': nominal_anchor_error,
        'common_shares_2019_01_31': 95755298, 'common_shares_2019_06_30_approximately': 101500000,
        'status': 'Common-share dollar scale supported at overlapping anchor; full 2017-2020-03-10 split ledger not yet verified.'},
    'preferred_and_acquisition_limit': {
        'actual_observation': '2019Q2 note says 62500 SeriesA 8.125% convertible preferred shares issued with Resolute acquisition; ordinary common shares remain separately described.',
        'do_not_apply_to_XEC_common': ['USD20.31 preferred dividends', 'preferred USD1000 liquidation preference', '8.0421 common shares plus USD471.40 preferred conversion option'],
        'ordinary_holder_forced_exchange_verified': False,
        'interpretation': 'Nothing in the retrieved preferred-stock terms is a forced exchange of old ordinary XEC shares. This limited note is not a complete negative ledger for all old common-share actions.'},
    'capture_limitations': ['2018 10-K Browse capture has 126413 characters, ends within MD&A, and omits numerical tables; it does not include full cash dividend or share-equity notes.',
        '2018 Item5 confirms cash dividends in each quarter but gives no amounts in the captured text.',
        'Initial searches returned unrelated CIKs, explicitly excluded; no conclusions use Comerica, Occidental, Bruker, Antero, General Mills or Chimera.',
        'CIMXP preferred security results are excluded from ordinary XEC dividends.',
        'A2 and Marketlog may share upstream history; they are corroborating secondary pages, not proven independent vendors.',
        'StreetInsider omits some dates and conflicts on old 2016 rows outside scope; it is not used alone as a complete ledger.'],
    'next_primary_evidence_needed': [
        'Complete 2017 cash-dividend table or common-stock note/declarations, to adjudicate the extra Sep14 USD0.16 and confirm Nov14 USD0.08.',
        '2017-12-08 declaration for the Feb14 2018 USD0.08 event and 2018 capital-stock notes/quarterly declarations for the USD0.16/USD0.18 steps.',
        'Actual fiscal2019 common dividend note and 2019-12-06 declaration for Feb13 2020 USD0.20; do not confuse filing-year2019 10-K with fiscal2019.',
        'Bounded common-share capital rollforward around Resolute acquisition; separate new preferred issuance from old common holders.'
    ],
    'new_public_requests_used': 4, 'new_public_request_limit': 4,
    'new_quote_provider_calls': 0, 'request_denials_or_bypasses': 0,
    'network_calls_by_this_script': 0, 'repo_or_manifest_modified': False,
    'canonical_candidate_generated': False, 'no_2021_merger_extension': True,
}
dump('audit.json', audit)
print(json.dumps({'status': audit['status'], 'counts': audit['event_counts'], 'nominal_anchor': audit['nominal_units']}, indent=2))
