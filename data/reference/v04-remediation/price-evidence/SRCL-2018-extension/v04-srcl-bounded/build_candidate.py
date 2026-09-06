"""Build a work-only SRCL candidate from preserved local whole-source rows."""
import hashlib
import json
import re
import shutil
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parent
REPO = Path('/Users/fighting/code/short-hold-momentum')
FIRST, LAST = '2007-11-12', '2018-12-28'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name, value): (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
def flat(text): return re.sub(r'\s+',' ',text)

request_status=json.loads((OUT/'request-status.json').read_text())
assert request_status['new_public_requests_started']==4
assert all(r['status'] in ('returned','failed') for r in request_status['requests'])
submissions=json.loads((OUT/'01-sec-submissions.body.json').read_text())
assert submissions['name']=='STERICYCLE INC' and submissions['cik']=='0000861878'
recent=submissions['filings']['recent']
position=recent['accessionNumber'].index('0001564590-19-005500')
assert recent['reportDate'][position]=='2018-12-31'
assert recent['primaryDocument'][position]=='srcl-10k_20181231.htm'

response=json.loads((OUT/'04-dividend-annual-search.json').read_text())['result']
if 'webResults' not in response:response=json.loads(response['content'][0]['text'])
source_index=[]
mirrors=[
 ('2018-10K.edgar-online.indexed.txt','content.edgar-online.com',
  'Issuer 2018 SEC filing content mirrored by EDGAR Online, obtained through search index; original SEC HTML attempt returned403. Indexed text is partial, not a full-file download.'),
 ('2018-annual-cover.eproxymaterials.indexed.txt','eproxymaterials.com',
  'Partial indexed annual-report text from proxy-material host, not downloaded original PDF; cover identity and class only; aggregate market value is not a per-share price anchor.'),
 ('2017-10K-cover.getfilings.indexed.txt','getfilings.com',
  'Partial indexed third-party mirror of 2017 issuer annual filing; common and preferred classes are distinct; no 2017 dividend-policy passage returned here.'),
]
for filename,domain,grade in mirrors:
    row=next(r for r in response['webResults'] if domain in r['url'])
    path=OUT/filename
    path.write_text(row['content'])
    source_index.append(dict(file=filename,url=row['url'],source_grade=grade,
                             request_number=4,sha256=sha(path),characters=len(row['content'])))
source_index.append(dict(file='01-sec-submissions.body.json',
                         url='https://data.sec.gov/submissions/CIK0000861878.json',
                         source_grade='Direct SEC submissions JSON, issuer identity and filing accession metadata',
                         request_number=1,sha256=sha(OUT/'01-sec-submissions.body.json')))
annual=flat((OUT/'2018-10K.edgar-online.indexed.txt').read_text())
excerpts=[
 ('common_class','Common stock, par value $.01 per share Nasdaq Global Select Market'),
 ('symbol','The Company’s common stock is listed on the Nasdaq Global Select Market under the ticker symbol "SRCL."'),
 ('common_cash_policy_2016_2018','We did not declare or pay any cash dividends on our common stock during 2018, 2017 or 2016.'),
 ('preferred_conversion_not_common_distribution','Finally, in September 2018, our Series A Mandatory Convertible Preferred Stock (“Series A Preferred Stock”) was converted, in accordance with the terms of issue, into a total of 4.7 million shares of our common stock'),
]
for _,quote in excerpts:assert quote in annual,quote
save('issuer-excerpts.json',[dict(id=name,source_file='2018-10K.edgar-online.indexed.txt',
                                 quote=quote,whitespace_normalized=True) for name,quote in excerpts])

originals={
 'SRCL-current-override.original.parquet': REPO/'data/research/v04/prices/SRCL.parquet',
 'SRCL-WIKI.raw-source.parquet': WORK/'v04-remediation-archive/prices/SRCL.parquet',
 'SRCL-SheepB.raw-source.parquet': WORK/'v04-source-options-next/sheepb-extracted/SRCL.parquet',
 'SheepB-dataset-metadata.original.json': WORK/'v04-source-options-next/04-sheepb-metadata.body',
 'SheepB-download.original.json': WORK/'v04-source-options-next/sheepb-2021-download.json',
}
for filename,path in originals.items():
    shutil.copyfile(path,OUT/filename)
    assert sha(path)==sha(OUT/filename)
    source_index.append(dict(file=filename,original_path=str(path),
                             source_grade='Existing local original; no new network request',
                             request_number=None,sha256=sha(path)))
for filename,grade in [('SRCL-IEX.source.csv','Public Cam Nugent sandp500 archive, original IEX whole-source observations; independent upstream from SheepB Yahoo'),
                       ('IEX-getSandP.source.py','Original archive acquisition script explicitly calls pandas_datareader iex; retained as provenance, never executed'),
                       ('SRCL-IEX-missing-day-evidence.json','Locally extracted source-member and ZIP hashes plus adjacent observations')]:
    source_index.append(dict(file=filename,source_grade=grade,request_number=None,sha256=sha(OUT/filename)))
save('source-index.json',source_index)

baseline=pd.read_parquet(OUT/'SRCL-current-override.original.parquet').sort_values('date').reset_index(drop=True)
source=pd.read_parquet(OUT/'SRCL-SheepB.raw-source.parquet').set_index('Date').sort_index()
source.index=pd.to_datetime(source.index)
tail=source.loc['2018-03-28':LAST]
assert len(tail)==191
assert np.array_equal(tail['Adj Close'].to_numpy(),tail['Close'].to_numpy())
iex=pd.read_csv(OUT/'SRCL-IEX.source.csv',parse_dates=['date']).set_index('date')
hole=iex.loc[pd.Timestamp('2017-11-08')]
assert not baseline.date.eq(pd.Timestamp('2017-11-08')).any()

new=[]
for day,row in tail.iterrows():
    new.append(dict(date=day,open=float(row['Open']),high=float(row['High']),
                    low=float(row['Low']),close=float(row['Close']),volume=float(row['Volume']),
                    as_traded_close=float(row['Close']),
                    dollar_volume=float(row['Close'])*float(row['Volume']),adjusted=True,
                    source='SheepB v1 Yahoo archive; SRCL bounded nominal whole row, reviewed zero common cash 2016-2018',
                    downloaded_at=pd.NaT))
new.append(dict(date=pd.Timestamp('2017-11-08'),**{k:float(hole[k]) for k in ('open','high','low','close','volume')},
                as_traded_close=float(hole['close']),dollar_volume=float(hole['close'])*float(hole['volume']),
                adjusted=True,source='Cam Nugent sandp500 v4 IEX archive; SRCL 2017-11-08 whole-row restoration, factor1',
                downloaded_at=pd.NaT))
addition=pd.DataFrame(new,columns=baseline.columns)
addition['downloaded_at']=pd.Series(pd.NaT,index=addition.index,dtype=baseline['downloaded_at'].dtype)
candidate=pd.concat([baseline,addition],ignore_index=True).sort_values('date').reset_index(drop=True)
assert len(candidate)==len(baseline)+192 and not candidate.date.duplicated().any()
retained=candidate.set_index('date').loc[baseline.date].reset_index()
pd.testing.assert_frame_equal(retained,baseline,check_exact=True)
window=candidate.loc[candidate.date.between(FIRST,LAST)].set_index('date')
calendar=xc.get_calendar('XNYS',start=FIRST,end=LAST)
expected=calendar.sessions_in_range(FIRST,LAST).tz_localize(None)
assert window.index.equals(expected) and len(window)==2802
assert window[['open','high','low','close','volume']].notna().all().all()
assert np.isfinite(window[['open','high','low','close','volume']]).all().all()
bad=(window[['open','high','low','close']].le(0).any(axis=1)|window.volume.lt(0)
     |window.high.lt(window[['open','low','close']].max(axis=1))
     |window.low.gt(window[['open','high','close']].min(axis=1)))
assert not bad.any()
assert window.close.eq(window.as_traded_close).all()
candidate_path=OUT/'SRCL-through-2018-12-28.candidate.parquet'
candidate.to_parquet(candidate_path,index=False)
pd.testing.assert_frame_equal(pd.read_parquet(candidate_path),candidate,check_exact=True)
addition.sort_values('date').to_csv(OUT/'new-whole-source-rows.csv',index=False)

limitations=[
 'Only 2016, 2017 and 2018 common cash-dividend absence is explicitly supported by the newly returned issuer filing content; no new 2007-2015 primary action certification was obtained.',
 'No independent complete split/spinoff census was obtained. Unchanging vendor factors, raw/adjusted unit ratios and independent IEX overlap support the bounded same-unit interpretation; they are not themselves proof of no corporate action.',
 'No exact issuer/exchange per-share historical price anchor was obtained in this four-request budget. The accurately dated IEX whole row is a public independent-vendor quote anchor, not an issuer price statement.',
 'Annual-report cover aggregate nonaffiliate market value is not divided by later total shares to fabricate a per-share price.',
 'WIKI/SheepB historical quote and volume differences remain disclosed in source-preflight; all existing rows are retained exactly, not averaged or silently replaced.',
 'The 2018 preferred-to-common conversion is not a cash dividend or stock split entitlement for existing ordinary common holders. Preferred dividends are not credited to this strategy.',
 'New-row downloaded_at is unavailable and stored as NaT; original metadata remains unchanged. Source publication/retrieval provenance is in the preserved source index.',
 'The 2003-2007 older prefix is retained unchanged for compatibility, but new evidence review targets only 2007-11-12 through 2018-12-28.',
 'This is a work-only candidate pending independent review; no manifest, account, strategy parameter or global evidence gate is changed.'
]
audit=dict(status='WORK_ONLY_CANDIDATE_PENDING_INDEPENDENT_REVIEW',
           research_key='SRCL',legal_issuer='Stericycle, Inc.',cik='0000861878',
           source_request_budget=4,new_public_requests_started=4,
           successful_public_responses=3,failed_direct_SEC_HTML_attempts=1,
           candidate_path=str(candidate_path),candidate_sha256=sha(candidate_path),
           baseline_sha256=sha(OUT/'SRCL-current-override.original.parquet'),
           first=str(candidate.date.min().date()),last=str(candidate.date.max().date()),rows=len(candidate),
           required_window=[FIRST,LAST],required_window_rows=len(window),
           all_original_rows_all_columns_preserved_exactly=True,original_rows=len(baseline),
           appended_tail_rows=191,restored_whole_row_date='2017-11-08',
           restored_row_source='IEX whole row; no fields selected from SheepB',
           ordinary_cash_credits_created=0,corporate_actions_created=0,
           required_window_missing_sessions=[],required_window_invalid_ohlcv_rows=0,
           required_window_adjusted_to_nominal_ratio=1.0,
           issuer_common_cash_dividend_policy_years=[2016,2017,2018],
           zero_vendor_factor_events_not_treated_as_independent_action_proof=True,
           original_old_quote_conflicts_resolved=False,limits=limitations,
           approved_for_application=False,repo_modified=False)
save('build-audit.json',audit)
print(json.dumps({k:audit[k] for k in ('status','candidate_path','candidate_sha256','rows','required_window_rows','original_rows','appended_tail_rows')},indent=2))
