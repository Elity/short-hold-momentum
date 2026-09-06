"""Compare supplied issuer-filing mirror excerpts with existing vendor observations."""
from pathlib import Path
import hashlib,json,re
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

W=Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work')
B=W/'v04-ads-primary-followup';O=B/'unit-identity-review'
R=Path('/Users/fighting/code/short-hold-momentum')
sources={};index=[];excerpts=[]
def track(path,grade):
    index.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'grade':grade})
def clean(text):return re.sub(r'\s+',' ',text.replace('\u200b','')).strip()
for year in (2017,2019):
    path=B/f'{year}-10K.edgar-online.indexed.txt'
    track(path,'issuer_10K_mirror_search_index_text_not_direct_SEC_download_partial_body')
    s=clean(path.read_text());sources[year]=s
    patterns=[('identity',r'Commission file number.{0,850}'),
              ('market_information',r'Our common stock is listed.{0,1400}'),
              ('June_price_anchor',r'.{0,160}closing price.{0,500}'),
              ('holder_price_anchor',r'Holders As of.{0,450}')]
    if year==2017:
        patterns += [('stockholders_equity_rollforward',r'CONSOLIDATED STATEMENTS OF STOCKHOLDERS’ EQUIT Y.{0,2050}'),
                     ('balance_sheet_share_units',r'Common stock, \$0\.01 par value; authorized.{0,900}')]
    for key,pattern in patterns:
        match=re.search(pattern,s,re.I)
        assert match,(year,key)
        excerpts.append({'year':year,'key':key,'source_path':str(path),'normalized_excerpt':match.group(0)})

frames={}
for name,grade in [('2020-04-23-dividend.SEC-indexed.txt','SEC_8K_index_text_not_direct_download'),
                   ('2020-04-23-dividend.issuer-release.indexed.txt','issuer_PRNewswire_release_index_text')]:
    path=B/name;track(path,grade);s=clean(path.read_text())
    for key,pattern in [('identity',r'ALLIANCE DATA SYSTEMS CORPORATION.{0,1750}'),
                        ('common_cash_declaration',r'.{0,150}declared a quarterly cash dividend.{0,430}')]:
        match=re.search(pattern,s,re.I)
        assert match,(name,key)
        excerpts.append({'year':2020,'key':key,'source_path':str(path),'normalized_excerpt':match.group(0)})
for name,path in {'wiki':W/'v04-remediation-archive/prices/ADS.parquet',
                  'sheepb':W/'v04-source-options-next/sheepb-extracted/ADS.parquet',
                  'canonical':R/'data/research/v04/prices/ADS.parquet'}.items():
    track(path,'existing_price_observations_not_modified')
    f=pd.read_parquet(path).rename(columns={'Date':'date','High':'high','Low':'low','Close':'close','Adj Close':'adj_close'})
    f['date']=pd.to_datetime(f.date);frames[name]=f

quarter_values={2017:[(251.19,214.68),(266.25,232.81),(265.68,209.00),(254.79,215.37)],
                2016:[(275.94,176.63),(227.34,185.02),(239.72,191.59),(241.69,197.69)]}
def cents(value):return float(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
qrows=[]
for year,values in quarter_values.items():
    for q,(high,low) in enumerate(values,1):
        for source in ('wiki','sheepb'):
            f=frames[source];f=f[(f.date.dt.year==year)&(f.date.dt.quarter==q)]
            h,l=float(f.high.max()),float(f.low.min())
            qrows.append({'year':year,'quarter':q,'source':source,'issuer_high':high,'issuer_low':low,
                          'raw_high':h,'raw_low':l,'high_matches_at_reported_cent_precision':cents(h)==high,
                          'low_matches_at_reported_cent_precision':cents(l)==low,
                          'basis':'NYSE composite per-share high/low; raw daily High max / Low min, not adjusted or close extrema'})
pd.DataFrame(qrows).to_csv(O/'2016-2017-quarter-price-check.csv',index=False)
arows=[]
for day,value,filing in [('2017-06-30',256.69,2017),('2018-02-21',239.59,2017),('2019-06-28',140.13,2019),('2020-02-20',103.06,2019)]:
    for name,f in frames.items():
        f=f[f.date==day]
        if f.empty:continue
        row=f.iloc[0];raw=float(row.as_traded_close if name=='canonical' else row.close)
        adjusted=float(row.close if name=='canonical' else row.adj_close)
        arows.append({'date':day,'issuer_close':value,'filing_year':filing,'source':name,
                      'nominal_close':raw,'adjusted_close':adjusted,'nominal_absolute_difference':raw-value,
                      'matches_at_reported_cent_precision':cents(raw)==value})
pd.DataFrame(arows).to_csv(O/'four-nominal-price-anchors.csv',index=False)
for name,obj in [('source-index.json',index),('primary-unit-excerpts.json',excerpts),('checks.json',{
    'network_requests':0,'repo_changes':0,'candidate_created':False,
    'reviewed_filings':['2017_10K_partial_mirror','2019_10K_partial_mirror','2020-04-23_8K_and_issuer_declaration'],'quarter_checks':len(qrows),
    'all_quarter_extremes_match_reported_cent_precision':all(r['high_matches_at_reported_cent_precision'] and r['low_matches_at_reported_cent_precision'] for r in qrows),
    'nominal_price_anchor_comparisons':len(arows),'all_nominal_anchors_match_reported_cent_precision':all(r['matches_at_reported_cent_precision'] for r in arows),
    'scope_limit':'identity, nominal prices, ordinary-common-stock unit context; not all daily bars or all historical actions certified',
    'source_limit':'2017 and 2019 supplied mirror/index bodies are partial; no missing-word negative conclusion about all splits'})]:
    (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'quarter_comparisons':len(qrows),'anchors':arows},ensure_ascii=False,indent=2))
