"""Bounded source-only audit. Never builds or writes applicable price inputs."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import exchange_calendars as xcals
from shm.v04.history import load_membership

R=Path('/Users/fighting/code/short-hold-momentum')
W=Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work')
O=W/'v04-ads-bounded-preflight'
START,END='2012-12-12','2020-07-02'
OLD_END='2018-03-27'
manifest=json.loads((R/'data/reference/v04-remediation/manifest.json').read_text())
scope=next(x for x in json.loads((W/'v04-archive-closure-plan/next-minimum-scope.json').read_text()) if x['ticker']=='ADS')
iex_meta=json.loads((O/'ADS-IEX-provenance.json').read_text())
paths={'wiki':W/'v04-remediation-archive/prices/ADS.parquet',
       'canonical':R/manifest['price_overrides']['ADS']['path'],
       'sheepb':Path(scope['source_path']), 'iex':O/'ADS-IEX.source.csv'}
expected={'wiki':manifest['price_overrides']['ADS']['source_archive_sha256'],
          'canonical':manifest['price_overrides']['ADS']['sha256'],
          'sheepb':scope['source_sha256'],'iex':iex_meta['member_sha256']}
source_index=[]
frames={}
for key,path in paths.items():
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest==expected[key],path
    source_index.append({'source':key,'path':str(path),'sha256':digest,'matches_expected':True})
    f=pd.read_csv(path) if key=='iex' else pd.read_parquet(path)
    f=f.rename(columns={'Date':'date','Open':'open','High':'high','Low':'low','Close':'close','Adj Close':'adj_close','Volume':'volume'})
    f['date']=pd.to_datetime(f.date)
    frames[key]=f.loc[f.date.between(START,END)].set_index('date').sort_index()
wiki,canon,sheep,iex=[frames[k] for k in ('wiki','canonical','sheepb','iex')]
cal=xcals.get_calendar('XNYS',start=START,end='2020-07-16')
dates=cal.sessions_in_range(START,END).tz_localize(None)
tail=sheep.loc['2018-03-28':END]

def structure(f,expected_dates):
    finite=np.isfinite(f[['open','high','low','close','volume']]).all(axis=1)
    good=finite & f[['open','high','low','close','volume']].gt(0).all(axis=1)
    good &= f.high.ge(f[['open','close','low']].max(axis=1)) & f.low.le(f[['open','close','high']].min(axis=1))
    return {'rows':len(f),'first':str(f.index.min().date()),'last':str(f.index.max().date()),
            'missing_sessions':[str(x.date()) for x in expected_dates.difference(f.index)],
            'extra_sessions':[str(x.date()) for x in f.index.difference(expected_dates)],
            'duplicate_dates':int(f.index.duplicated().sum()),'bad_ohlcv_rows':int((~good).sum())}

overlap=wiki.index.intersection(sheep.index)
comparison=pd.DataFrame(index=overlap)
stats={}
top=[]
for c in ('open','high','low','close','volume'):
    a,b=wiki.loc[overlap,c],sheep.loc[overlap,c]
    relative=(b/a-1).abs()
    comparison['wiki_'+c]=a; comparison['sheepb_'+c]=b; comparison[c+'_absolute_relative_difference']=relative
    stats[c]={'rows':len(relative),'median':float(relative.median()),'p99':float(relative.quantile(.99)),
              'maximum':float(relative.max()),'observed_count_above_1bp':int(relative.gt(.0001).sum())}
    for d in relative.nlargest(5).index:
        top.append({'field':c,'date':str(d.date()),'wiki':float(a.loc[d]),'sheepb':float(b.loc[d]),'absolute_relative_difference':float(relative.loc[d])})
comparison.reset_index().to_csv(O/'wiki-sheepb-all-overlap-observations.csv',index=False)
pd.DataFrame(top).to_csv(O/'largest-observed-source-differences.csv',index=False)
factors=[]
for name,f in [('wiki',wiki),('sheepb',sheep)]:
    factor=f.adj_close/f.close
    fobs=pd.DataFrame({'source':name,'factor':factor,'factor_step':factor/factor.shift(1)})
    if name=='wiki':
        fobs['ex_dividend_vendor_field']=f['ex-dividend'];fobs['split_ratio_vendor_field']=f.split_ratio
        fobs['adjusted_volume_over_volume']=f.adj_volume/f.volume
    fobs.reset_index().to_csv(O/f'{name}-factor-observations.csv',index=False)
    factors.append({'source':name,'factor_min':float(factor.min()),'factor_max':float(factor.max()),
                    'factor_step_count_above_1bp':int((factor/factor.shift(1)-1).abs().gt(.0001).sum()),
                    'interpretation':'vendor observation only; zero steps do not establish no distributions or splits'})
actions=wiki.loc[wiki['ex-dividend'].ne(0)|wiki.split_ratio.ne(1)]
actions.reset_index().to_csv(O/'wiki-recorded-actions-in-required-window.csv',index=False)
tail.reset_index().to_csv(O/'sheepb-preserved-tail-observations.csv',index=False)
sheep.loc['2017-11-06':'2017-11-10'].reset_index().to_csv(O/'sheepb-missing-day-and-neighbors.csv',index=False)
iex.loc['2017-11-06':'2017-11-10'].reset_index().to_csv(O/'iex-missing-day-and-neighbors.csv',index=False)
boundary_dates=pd.to_datetime(['2017-11-07','2017-11-08','2017-11-09','2017-11-10','2017-11-13','2017-11-14','2018-02-12','2018-02-13','2018-02-14','2018-03-27','2018-03-28','2020-06-03','2020-06-19','2020-06-22','2020-07-01','2020-07-02'])
boundaries=[]
for name,f in frames.items():
    for d in boundary_dates.intersection(f.index):
        row={'source':name,'date':str(d.date())}
        row.update({c:float(f.at[d,c]) for c in ('open','high','low','close','volume')})
        boundaries.append(row)
pd.DataFrame(boundaries).to_csv(O/'boundary-observations.csv',index=False)
gap=pd.Timestamp('2017-11-08')
gap_comparison={c:{'iex':float(iex.at[gap,c]),'sheepb':float(sheep.at[gap,c]),
                   'sheepb_minus_iex':float(sheep.at[gap,c]-iex.at[gap,c])} for c in ('open','high','low','close','volume')}
current_matches={c:bool(np.array_equal(canon[c],wiki['adj_'+c])) for c in ('open','high','low','close','volume')}
current_matches['as_traded_close']=bool(np.array_equal(canon.as_traded_close,wiki.close))
current_matches['dollar_volume']=bool(np.array_equal(canon.dollar_volume,wiki.close*wiki.volume))
selection_path=R/'reports/v04/selection.json'
selection=json.loads(selection_path.read_text())
schedule=pd.DatetimeIndex([x['date'] for x in selection['price_coverage']['rebalance_dates']])
h,_,_=load_membership(R)
mh=h.set_index('date').members
membership=mh.reindex(mh.index.union(dates)).sort_index().ffill().reindex(dates)
member_signals=[d for d in schedule.intersection(dates) if 'ADS' in membership[d]]
coverage=[]
for d in member_signals:
    required=dates[max(0,dates.get_loc(d)-259):dates.get_loc(d)+1]
    old_missing=required.difference(wiki.index)
    local_missing=required.difference(sheep.index)
    coverage.append({'date':str(d.date()),'current_260_complete':len(required)==260 and len(old_missing)==0,
                     'current_missing_count':len(old_missing),'local_sheepb_260_dates_complete':len(required)==260 and len(local_missing)==0,
                     '2017_11_08_inside_window':gap in required,'interpretation':'calendar availability only, not approved eligibility or ranking'})
pd.DataFrame(coverage).to_csv(O/'member-signal-window-date-coverage.csv',index=False)
audit={'status':'SOURCE_PREFLIGHT_ONLY_NOT_APPROVED_FOR_APPLICATION','network_requests':0,'repository_writes':0,
       'scope':{'start':START,'end':END,'expected_XNYS_sessions':len(dates),'study_reference':selection['run_id']},
       'structure':{'wiki_existing_prefix':structure(wiki,dates[dates<=OLD_END]),'canonical_existing_prefix':structure(canon,dates[dates<=OLD_END]),
                    'sheepb_required_window':structure(sheep,dates),'sheepb_needed_tail':structure(tail,dates[dates>OLD_END])},
       'source_company_labels':{'wiki':manifest['price_overrides']['ADS']['source_name'],'sheepb':list(sheep['Company Name'].unique()),
                                'interpretation':'source labels are not independent issuer identity evidence'},
       'current_canonical_matches_WIKI_exactly':current_matches,'WIKI_nonzero_cash_fields':int(wiki['ex-dividend'].ne(0).sum()),
       'WIKI_nonunit_split_fields':int(wiki.split_ratio.ne(1).sum()),'factor_observations':factors,
       'overlap_relative_difference':stats,'2017_11_08':gap_comparison,
       'coverage':{'member_signal_count':len(coverage),'current_dates_complete_260':sum(x['current_260_complete'] for x in coverage),
                   'local_sheepb_dates_complete_260':sum(x['local_sheepb_260_dates_complete'] for x in coverage),
                   'member_signals_whose_260_window_includes_gap':sum(x['2017_11_08_inside_window'] for x in coverage)},
       'not_proven':['issuer identity and common-share basis','no dividend/split/spinoff merely from zero source fields',
                     'which conflicting overlap source is economically correct','actual path closure after approved application'],
       'not_performed':['web request','applicable price construction','repository or strategy changes','cross-sectional rerun']}
for path in [W/'v04-source-options-next/sheepb-2021-download.json',W/'v04-source-options-next/sheepb-extraction.json',
             O/'ADS-IEX-provenance.json',W/'v04-archive-closure-plan/next-minimum-scope.json']:
    source_index.append({'source':'existing_provenance','path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
for name,obj in [('audit.json',audit),('source-index.json',source_index)]:
    (O/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
sf=sheep.adj_close/sheep.close
wf=wiki.adj_close/wiki.close
event_rows=[]
for day in sf[(sf/sf.shift(1)-1).abs().gt(.0001)].index:
    present=day in wiki.index
    event_rows.append({'date':str(day.date()),'period':'tail' if day>pd.Timestamp(OLD_END) else 'old_prefix',
                       'sheepb_factor':sf.loc[day],'sheepb_factor_step':sf.loc[day]/sf.shift(1).loc[day],
                       'wiki_ex_dividend_observed':wiki.at[day,'ex-dividend'] if present else None,
                       'wiki_split_ratio_observed':wiki.at[day,'split_ratio'] if present else None,
                       'wiki_factor':wf.loc[day] if present else None,
                       'wiki_factor_step':wf.loc[day]/wf.shift(1).loc[day] if present else None,
                       'issuer_confirmed_amount':None,
                       'interpretation':'factor change is date/scale observation; cash amount not inferred'})
pd.DataFrame(event_rows).to_csv(O/'ADS-factor-event-observations.csv',index=False)
print(json.dumps(audit,ensure_ascii=False,indent=2))
