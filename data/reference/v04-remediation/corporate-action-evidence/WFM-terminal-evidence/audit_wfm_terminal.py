"""Work-only WFM terminal event audit. No downloads and no runtime-input writes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd
import numpy as np
import exchange_calendars as xcals

BASE = Path(__file__).resolve().parent
REPO = Path('/Users/fighting/code/short-hold-momentum')
ARCHIVE = BASE.parent.parent / 'v04-remediation-archive/prices/WFM.parquet'
RESEARCH = REPO / 'data/research/v04/prices/WFM.parquet'
ADR = REPO / 'docs/decisions/ADR-014-corporate-actions-and-security-identity.md'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(name, value):
    (BASE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

inputs = {str(p): digest(p) for p in [ARCHIVE, RESEARCH, ADR]}
archive = pd.read_parquet(ARCHIVE).copy()
research = pd.read_parquet(RESEARCH).copy()
for frame in [archive, research]:
    frame['date'] = pd.to_datetime(frame['date'])
    frame.sort_values('date', inplace=True)
    assert not frame['date'].duplicated().any()

archive.set_index('date', inplace=True)
research.set_index('date', inplace=True)
window = archive.loc['2017-06-20':].copy()
window['price_adjustment_factor'] = window['adj_close'] / window['close']
window['terminal_session_status'] = 'OBSERVED_BEFORE_DISPUTED_TERMINAL_DATE'
window.loc[pd.Timestamp('2017-08-28'), 'terminal_session_status'] = 'DISPUTED_DO_NOT_ASSUME_EXECUTABLE_OR_DELETE'
window.to_csv(BASE / 'WFM-terminal-window.csv', float_format='%.15g')

ex = pd.Timestamp('2017-06-28')
prev = archive.loc['2017-06-27']
today = archive.loc[ex]
dividend = float(today['ex-dividend'])
observed_factor = float(prev.adj_close / prev.close)
exact_total_return_factor = float(today.close / (today.close + dividend))
cash_total_return = float((today.close + dividend) / prev.close - 1)
adjusted_return = float(today.adj_close / prev.adj_close - 1)
assert dividend == 0.18
assert abs(observed_factor - exact_total_return_factor) < 1e-12
assert abs(adjusted_return - cash_total_return) < 1e-12
assert (archive.loc[ex:, 'ex-dividend'].iloc[1:] == 0).all()
assert np.allclose(archive.loc[ex:, 'close'], archive.loc[ex:, 'adj_close'], rtol=0, atol=1e-10)
common = research.index.intersection(archive.index)
max_close_error = float((research.loc[common, 'close'] - archive.loc[common, 'adj_close']).abs().max())
max_nominal_error = float((research.loc[common, 'as_traded_close'] - archive.loc[common, 'close']).abs().max())
assert max_close_error < 1e-10
assert max_nominal_error < 1e-10

dividend_audit = {
    'ordinary_dividend_amount_usd': 0.18,
    'declaration_date': '2017-06-07',
    'record_date': '2017-06-30',
    'payment_date': '2017-07-11',
    'ex_date': '2017-06-28',
    'ex_date_evidence': 'Local archive plus dividendhistory.org and DividendMax; date not literally in the captured SEC declaration table.',
    'sec_fiscal_2017_declared_dividends_usd': [0.14, 0.14, 0.18],
    'sec_fiscal_2017_declared_total_usd': 0.46,
    'previous_raw_close': float(prev.close),
    'previous_adjusted_close': float(prev.adj_close),
    'ex_date_raw_close': float(today.close),
    'ex_date_adjusted_close': float(today.adj_close),
    'observed_previous_adjustment_factor': observed_factor,
    'factor_formula_observed': 'C_ex / (C_ex + D)',
    'factor_formula_value': exact_total_return_factor,
    'factor_formula_absolute_error': abs(observed_factor - exact_total_return_factor),
    'adjusted_close_ex_day_return': adjusted_return,
    'cash_inclusive_raw_ex_day_return': cash_total_return,
    'same_basis_previous_close_discount_formula_not_used': float(1 - dividend / prev.close),
    'factor_is_one_from_ex_date_to_archive_end': True,
    'research_rows_compared': len(common),
    'research_close_vs_archive_adjusted_max_abs_error': max_close_error,
    'research_nominal_vs_archive_raw_max_abs_error': max_nominal_error,
    'raw_price_treatment': 'Raw OHLC do not separately credit ordinary dividends; a raw-price strategy needs a separate dividend ledger.',
    'current_research_price_treatment': 'Current research close uses archive adjusted close; this ordinary dividend is already represented in total return.',
    'terminal_cash_per_actual_share_usd': 42.0,
    'additional_ordinary_dividend_at_merger_usd': 0.0,
    'double_count_guard': 'Do not add 0.18 to the 42.00 merger consideration or pay it again on top of adjusted-price P&L.',
    'scope_limit': 'This verifies the final 2017 ordinary dividend, not every historical WFM action or a broker payment ledger.'
}
dump('WFM-dividend-audit.json', dividend_audit)

cal = xcals.get_calendar('XNYS')
sessions = cal.sessions_in_range('2017-08-25', '2017-09-08')
sessions = [pd.Timestamp(t).date().isoformat() for t in sessions]
def fifth_after(effective):
    later = [d for d in sessions if d > effective]
    return later[4], later[:5]

alternatives = []
for last, effective, premise in [
    ('2017-08-25', '2017-08-28', 'Only if the issuer-requested pre-open halt is confirmed and the 2017-08-28 archive row is not an executable strategy daily bar.'),
    ('2017-08-28', '2017-08-29', 'Only if a genuine executable 2017-08-28 session is confirmed; Nasdaq lists marketplace suspension effective 2017-08-29.')
]:
    settlement, counted = fifth_after(effective)
    alternatives.append({
        'apply': False,
        'premise_required': premise,
        'last_trading_session': last,
        'effective_session': effective,
        'cash_settlement_session': settlement,
        'counted_XNYS_sessions_after_effective': counted,
        'legal_completion_date_unchanged': '2017-08-28',
        'settlement_is_model_not_observed': True
    })

proposal = {
    'status': 'UNVERIFIED_TERMINAL_SESSION',
    'manifest_ready': False,
    'eligible_for_freeze': False,
    'runtime_inputs_modified': False,
    'reason': 'Nasdaq ECA2017-10 is more direct operational evidence than the issuer SEC 8-K request and supports retaining the nonzero-volume 2017-08-28 archive row. Recommend 2017-08-29 effective-session mapping for review; exact intraday cutoff and executability of the disputed daily bar remain unverified.',
    'confirmed_terms': {
        'source_ticker': 'WFM',
        'source_issuer': 'Whole Foods Market, Inc.',
        'source_CIK': '0000865436',
        'source_CUSIP': '966837106',
        'acquirer': 'Amazon.com, Inc.',
        'cash_per_actual_common_share_usd': 42.0,
        'legal_completion_date': '2017-08-28',
        'merger_agreement_date': '2017-06-15',
        'ordinary_share_default': 'Cash without interest; excludes company/acquirer-owned shares and dissenting owners described in the 8-K.',
        'last_confirmed_pre_dispute_observed_session': '2017-08-25',
        'last_trading_session': None,
        'exact_halt_timestamp': None,
        'issuer_requested_halt': 'prior to market open on 2017-08-28',
        'nasdaq_marketplace_suspension_effective_date': '2017-08-29'
    },
    'proposed_action_incomplete_do_not_load': {
        'action_id': 'WFM_CASH_2017-08-28',
        'source_ticker': 'WFM',
        'known_date': '2017-08-28',
        'last_trading_session': None,
        'effective_session': None,
        'cash_per_share': 42.0,
        'cash_settlement_session': None,
        'evidence': str(BASE / 'WFM-findings.md'),
        'source_price_treatment': 'terminal_before_action_pending_cutoff_verification'
    },
    'cash_settlement_status': 'MODEL_SELECTED_BUT_EFFECTIVE_SESSION_UNRESOLVED',
    'settlement_policy': {
        'rule': 'fifth_XNYS_session_after_effective',
        'model_only': True,
        'policy_path': str(ADR),
        'policy_sha256': inputs[str(ADR)],
        'cash_entitlement_legal_date': '2017-08-28',
        'cash_available_before_model_release': False,
        'actual_broker_posting_date': None,
        'apply_by_default': False
    },
    'conditional_alternatives_not_candidates': alternatives,
    'recommended_alternative_for_review': {
        'last_trading_session': '2017-08-28',
        'effective_session': '2017-08-29',
        'cash_settlement_session': '2017-09-06',
        'automatic_application_authorized_by_packet': False,
        'reason': 'The exchange directly lists August 29 as marketplace suspension effective date; issuer August 28 wording is only a request. The archive records nonzero August 28 volume. Prefer preservation pending regular-session/intraday cutoff verification.',
        'exact_quote_and_timestamp_evidence': str(BASE / 'WFM-exact-source-quotes.json')
    },
    'price_window_proposal': {
        'trim_applied': False,
        'last_valid_session': None,
        'disputed_row': '2017-08-28',
        'treatment_pending_review': 'Keep original immutable; flag disputed tail so it cannot silently supply an assumed executable open. Do not fabricate replacement OHLC or auto-trim on legal date alone.'
    },
    'ordinary_dividend_treatment': dividend_audit['double_count_guard'],
    'equity_unit_conversion': 'At the event actual_shares = adjusted_quantity * (last_valid_adjusted_close / last_valid_as_traded_close). Both possible terminal rows have factor 1. Cash receivable = actual_shares * 42.00; do not record a sale and a cash merger payment for the same shares.',
    'additional_unknowns': [
        'Whether the 2017-08-28 archive volume consists of executable regular-session trades, pre-market prints, corrections, or a vendor terminal artifact.',
        'The exact intraday legal effective time and exact trading halt timestamp.',
        'Actual broker cash posting date.'
    ],
    'external_queries_used': 3,
    'external_query_limit': 3,
    'input_hashes': inputs
}
dump('WFM-action-proposal.json', proposal)

sources = []
for p in sorted(BASE.glob('*.txt')):
    sources.append({'path': str(p), 'sha256': digest(p), 'source_url': p.read_text().splitlines()[0].removeprefix('URL: '), 'capture': 'Search_MCP extracted content; see corresponding saved search JSON, not original raw HTML.'})
dump('WFM-sources.json', {'sources': sources, 'search_json_hashes': {p.name: digest(p) for p in sorted(BASE.glob('search-*.json'))}, 'external_queries_used': 3})

report = '''# WFM terminal-event evidence — work only

Status: **UNVERIFIED_TERMINAL_SESSION**. No price data, source code, or runtime manifest was modified. This packet is not eligible to freeze a winner.

## Confirmed legal terms

The issuer's SEC 8-K, dated August 28, 2017, states that Amazon completed the acquisition on **2017-08-28**, and each eligible outstanding ordinary share “was converted into the right to receive **$42.00 in cash, without interest**.” Whole Foods survived as Amazon's wholly owned subsidiary; WFM ordinary equity ceased under the merger. The default ordinary-share terms exclude specified company/acquirer-owned shares and dissenting shareholders. Employee stock awards in the same 8-K are not exchange-traded option settlement evidence.

SEC source: https://www.sec.gov/Archives/edgar/data/865436/000114420417045261/v474128_8k.htm

## The last executable session is unresolved

The 8-K says the company “is requesting” Nasdaq to “suspend trading ... **prior to market open on August 28, 2017**.” That is a request, not a completed exchange halt timestamp.

Nasdaq's own updated Equity Corporate Actions Alert ECA2017-10 says **“The merger became effective today, August 28, 2017.”** Its table states **“Marketplace Effective Date for Suspension:  August 29, 2017”**. The exchange's marketplace suspension field is **more direct operational evidence than the issuer's request**; these statements should not be treated as two equally authoritative final halt records. Prefer the exchange date when forming the work-only proposal.

The Nasdaq title explicitly contains **(UPDATED)**. Its visible header is **Thursday, August 24, 2017** and Search_MCP `lastUpdatedAt` is `2017-08-24T00:00:00.0000000`; the body itself refers to August 28 as today. The exact revision timestamp is therefore **not supplied**. The search crawler timestamp (`2025-02-15T11:12:00.0000000Z`) is not an event or update date. The SEC document is dated August 28; no separate last-updated timestamp is provided. `WFM-exact-source-quotes.json` preserves both verbatim excerpts, URLs, and date metadata.

Nasdaq source: https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2017-10

The local archive's last two observations are:

| Date | Open | High | Low | Close | Volume |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2017-08-25 | 41.99 | 42.00 | 41.99 | 41.99 | 4,268,652 |
| 2017-08-28 | 41.99 | 41.99 | 41.99 | 41.99 | 760,065 |

The final row's nonzero volume corroborates August 28 market activity, consistent with Nasdaq's August 29 suspension date. **Recommendation: preserve August 28 and prefer August 29 as the effective session in the review proposal. Do not crop the archive at August 25 merely from the issuer request.** The constant OHLC still does not establish a normal executable daily session or the precise intraday halt. The packet keeps automatic application disabled until that narrower issue is resolved; it does not claim the archive is contaminated. The exact verified last trading session and halt timestamp remain null, alongside populated recommended dates for review.

## Final ordinary dividend is already in adjusted prices

The SEC 2017 annual report lists the final ordinary dividend as declared **2017-06-07**, amount **$0.18**, record date **2017-06-30**, payment date **2017-07-11**. Its fiscal-2017 table lists three dividends, $0.14 + $0.14 + $0.18 = $0.46, with no later ordinary dividend in that table. The archive's June 28 ex-date is crosschecked by DividendHistory and DividendMax; the captured SEC table does not itself quote the ex-date.

SEC source: https://www.sec.gov/Archives/edgar/data/865436/000086543617000238/wfm10k2017.htm

On June 27 the archive raw close is 42.56 and adjusted close is 42.379448503417. On June 28 raw and adjusted close are both 42.25, with ex-dividend 0.18. The prior-day factor is **0.9957577185953242**, matching **42.25 / (42.25 + 0.18)** to less than 1e-12. The adjusted ex-day return therefore equals **(42.25 + 0.18) / 42.56 - 1**. This is the archive's observed total-return convention; it is not the different approximation `1 - dividend / prior_close`.

The research close matches the archive adjusted close, while `as_traded_close` matches raw close. From June 28 through the archive tail the price factor is 1. Consequently the $0.18 ordinary dividend is already in adjusted-price performance. **The terminal cash event is $42.00, not $42.18**; do not separately pay the ordinary dividend again or both liquidate and redeem the same shares. Raw OHLC alone do not separately credit dividend cash; a raw-price accounting model would need its own dividend ledger. This audit does not certify all historical WFM adjustments.

## ADR-014 cash release is a model date

ADR-014 selects release on the **fifth XNYS session strictly after the effective session**. Cash is receivable and part of NAV at the event, but is unavailable for new purchases until release. This is not a claim about any investor's actual broker posting date.

The cutoff evidence produces a preferred mapping and an alternative requiring stronger confirmation; these are date interpretations, not strategy candidates:

| Condition requiring confirmation | Last tradable session | Effective session | Model cash release |
| --- | --- | --- | --- |
| Issuer-requested pre-open suspension actually prevented the August 28 strategy session | 2017-08-25 | 2017-08-28 | 2017-09-05 |
| August 28 was an executable session and August 29 is the first unavailable session | 2017-08-28 | 2017-08-29 | 2017-09-06 |

Both retain **2017-08-28 as the confirmed legal merger date**. September 4 was a market holiday. **The recommended review mapping is last session August 28, effective session August 29, model release September 6**, because Nasdaq is the direct marketplace source. Neither mapping is applied. The verified/automatic action fields remain null, while `recommended_alternative_for_review` contains the preferred dates and limitations. No broker posting date is claimed and no cash may silently release merely from this work-only proposal.

## Reproducibility and focused checks

`audit_wfm_terminal.py` reads only the two existing WFM parquet files and ADR-014. It records their hashes, the evidence hashes, the final dividend arithmetic, the archive/research field mapping, the terminal observations, and both calendar mappings. It makes no external requests and asserts the inputs remain unchanged. The task used exactly three external searches and performed no broad historical-price search.
'''
(BASE / 'WFM-findings.md').write_text(report)
assert {str(p): digest(p) for p in [ARCHIVE, RESEARCH, ADR]} == inputs
outputs = {p.name: digest(p) for p in sorted(BASE.iterdir()) if p.is_file() and p.name != 'WFM-audit-result.json'}
dump('WFM-audit-result.json', {
    'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': ['ordinary dividend arithmetic', 'research-to-archive close mapping', 'research nominal-to-archive raw mapping', 'no post-June-28 dividend adjustment', 'ADR-014 calendar mappings', 'runtime input hashes unchanged'],
    'status': proposal['status'],
    'manifest_ready': False,
    'runtime_inputs_modified': False,
    'input_hashes': inputs,
    'output_hashes': outputs
})
print(json.dumps({'status': proposal['status'], 'manifest_ready': False, 'research_rows_compared': len(common), 'adjustment_factor': observed_factor, 'conditional_settlement_dates': [a['cash_settlement_session'] for a in alternatives], 'input_hashes_unchanged': True}, indent=2))
