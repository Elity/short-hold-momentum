"""Read-only XEC source and calendar preflight; no candidate price output."""
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
import exchange_calendars as xcals

WORK=Path('/Users/fighting/Documents/Codex/2026-09-06/co-2/work')
REPO=Path('/Users/fighting/code/short-hold-momentum')
OUT=WORK/'v04-xec-extension-preflight'
paths={'canonical':REPO/'data/research/v04/prices/XEC.parquet',
       'wiki':WORK/'v04-remediation-archive/prices/XEC.parquet',
       'sheepb':WORK/'v04-source-options-next/sheepb-extracted/XEC.parquet'}
def read(path,date):
    df=pd.read_parquet(path);df[date]=pd.to_datetime(df[date]);return df.set_index(date).sort_index()
c=read(paths['canonical'],'date');w=read(paths['wiki'],'date');y=read(paths['sheepb'],'Date')
calendar=xcals.get_calendar('XNYS',start='2002-01-01',end='2026-09-04')
def sessions(start,end):return calendar.sessions_in_range(start,end).tz_localize(None)
manifest_path=REPO/'data/reference/v04-remediation/manifest.json'
manifest=json.loads(manifest_path.read_text())
backlog_path=REPO/'data/reference/v04-remediation/historical-coverage-backlog.json'
backlog=json.loads(backlog_path.read_text());member=next(r for rs in backlog['groups'].values() for r in rs if r['ticker']=='XEC')
sel=json.loads((REPO/'reports/v04/selection.json').read_text());study=REPO/'reports/v04'/sel['run_id']
decisions=json.loads((study/'S500-C0-10.decisions.json').read_text())
rb=[d for d in decisions if d['diagnostics']['rebalance']]
first_removed=member['first_nonmember_after_final_period']
last_member=member['last_member_session']
next_rebalance=next(d for d in rb if d['signal_date']>=first_removed)
source_end=c.index.max();start=calendar.next_session(source_end).tz_localize(None)
required_exit=next_rebalance['execution_date']
segments={'member_tail':(str(start.date()),last_member),
          'through_first_regular_exit':(str(start.date()),required_exit),
          'full_available_tail':(str(start.date()),str(y.index.max().date()))}
def audit_frame(df,cols):
    o,h,l,cl,v=[df[k].astype(float) for k in cols]
    finite=np.isfinite(df[list(cols)]).all(axis=1)
    basic=(o>0)&(h>0)&(l>0)&(cl>0)&(v>=0)&finite&(h>=l)
    physical=basic&(h>=pd.concat([o,cl],axis=1).max(axis=1))&(l<=pd.concat([o,cl],axis=1).min(axis=1))
    return {'rows':len(df),'duplicates':int(df.index.duplicated().sum()),
            'invalid_basic_dates':df.index[~basic].strftime('%Y-%m-%d').tolist(),
            'physical_conflict_dates':df.index[basic&~physical].strftime('%Y-%m-%d').tolist(),
            'zero_volume_dates':df.index[v==0].strftime('%Y-%m-%d').tolist()}
audits={}
for name,(a,b) in segments.items():
    d=y.loc[a:b];expected=sessions(a,b)
    audits[name]={**audit_frame(d,['Open','High','Low','Close','Volume']),
                  'start':a,'end':b,'expected_sessions':len(expected),
                  'missing_expected_sessions':expected.difference(d.index).strftime('%Y-%m-%d').tolist(),
                  'extra_non_sessions':d.index.difference(expected).strftime('%Y-%m-%d').tolist(),
                  'rebalance_dates':[r['signal_date'] for r in rb if a<=r['signal_date']<=b]}

common=w.index.intersection(y.index)
comparison=pd.DataFrame(index=common)
stats={}
for a,b in [('open','Open'),('high','High'),('low','Low'),('close','Close'),('volume','Volume')]:
    comparison['wiki_'+a]=w.loc[common,a];comparison['sheepb_'+a]=y.loc[common,b]
    ratio=y.loc[common,b]/w.loc[common,a];err=(ratio-1).abs()
    comparison[a+'_relative_difference']=ratio-1
    stats[a]={'overlap':len(common),'median_ratio':float(ratio.median()),
              'median_absolute_relative_error':float(err.median()),'p99_absolute_relative_error':float(err.quantile(.99)),
              'max_absolute_relative_error':float(err.max()),'over_1bp_rows':int((err>1e-4).sum())}
comparison.to_csv(OUT/'wiki-sheepb-overlap.csv',index_label='date')
price_err=comparison[[x+'_relative_difference' for x in ['open','high','low','close']]].abs().max(axis=1)
comparison.loc[price_err.nlargest(10).index].to_csv(OUT/'top10-overlap-price-differences.csv',index_label='date')

wf=w.adj_close/w.close;wr=wf/wf.shift(1)
yf=y['Adj Close']/y.Close;yr=yf/yf.shift(1)
events=pd.DataFrame({'wiki_dividend':w['ex-dividend'],'wiki_split_ratio':w.split_ratio,
                     'wiki_close':w.close,'wiki_factor_ratio':wr,
                     'wiki_formula_ratio':1+w['ex-dividend']/w.close})
events=events[(events.wiki_dividend.ne(0))|((events.wiki_factor_ratio-1).abs()>1e-5)|events.wiki_split_ratio.ne(1)]
events['wiki_formula_residual']=events.wiki_factor_ratio-events.wiki_formula_ratio
events['sheepb_factor_ratio']=yr.reindex(events.index)
events['sheepb_implied_cash_diagnostic_only']=y.Close.shift(1).reindex(events.index)*(1-1/events.sheepb_factor_ratio)
events.to_csv(OUT/'wiki-recorded-events-and-factor-crosscheck.csv',index_label='date')
ysteps=pd.DataFrame({'source_Close':y.Close,'previous_source_Close':y.Close.shift(1),
                    'source_Adj_Close':y['Adj Close'],'factor_ratio':yr,
                    'implied_cash_diagnostic_only_NOT_APPROVED':y.Close.shift(1)*(1-1/yr)})
ysteps=ysteps[(ysteps.factor_ratio-1).abs()>1e-5]
ysteps['event_in_wiki_cash_column']=w['ex-dividend'].reindex(ysteps.index)
ysteps['within_member_tail']=ysteps.index.to_series().between(start,last_member)
ysteps['within_normal_exit_tail']=ysteps.index.to_series().between(start,required_exit)
ysteps['cash_approved']=False
ysteps.to_csv(OUT/'sheepb-factor-steps-DIAGNOSTIC-NOT-DIVIDEND-EVIDENCE.csv',index_label='date')

wiki_expected=sessions(c.index.min(),c.index.max())
prefix_missing=wiki_expected.difference(c.index)
prefix_y_rows=y.reindex(prefix_missing)
prefix_y_rows.to_csv(OUT/'sheepb-rows-on-existing-prefix-gaps.csv',index_label='date')
source_bad=audit_frame(w,['open','high','low','close','volume'])
canonical_bad=audit_frame(c,['open','high','low','close','volume'])
bad_dates=pd.DatetimeIndex(pd.to_datetime(sorted(set(source_bad['physical_conflict_dates']+canonical_bad['physical_conflict_dates']+source_bad['invalid_basic_dates']))))
pd.concat({'wiki':w.reindex(bad_dates),'sheepb':y.reindex(bad_dates),'canonical':c.reindex(bad_dates)},axis=1).to_csv(OUT/'existing-prefix-conflicting-rows.csv',index_label='date')

# Calendar-only what-if: append all source rows, with and without filling the
# known prefix gap. No OHLCV is repaired or output as an approved candidate.
joined_dates=c.index.union(y.loc[start:required_exit].index)
needed_member=sessions(member['first_member_session'],last_member)
calendar_full=sessions(c.index.min(),required_exit)
calendar_only={}
for mode,ds in [('tail_only_keep_prefix_gaps',joined_dates),('tail_plus_source_prefix_dates',joined_dates.union(prefix_missing))]:
    good=pd.Series(calendar_full.isin(ds),index=calendar_full).rolling(260,min_periods=260).sum().eq(260)
    calendar_only[mode]={'member_sessions_without_260_observed_dates':int((~good.reindex(needed_member)).sum()),
                         'member_rebalance_dates_without_260_observed_dates':[d['signal_date'] for d in rb if member['first_member_session']<=d['signal_date']<=last_member and not good.get(pd.Timestamp(d['signal_date']),False)],
                         'note':'Date count only; ignores identity, physical OHLCV defects and corporate-action correctness.'}

paths_current=[]
for candidate in range(5):
    for bps in [10,25]:
        tag=f'S500-C{candidate}-{bps}'
        tx=pd.read_csv(study/f'{tag}.transactions.csv');tx=tx[tx.ticker=='XEC']
        daily=pd.read_parquet(study/f'{tag}.daily.parquet',columns=['weight_XEC']);owned=daily.weight_XEC>1e-12
        paths_current.append({'path':tag,'trades':len(tx),'first_trade':None if tx.empty else tx.execution_date.min(),
                              'last_trade':None if tx.empty else tx.execution_date.max(),
                              'held_sessions_after_existing_end':int((owned&(daily.index>source_end)).sum()),
                              'held_sessions_after_member_end':int((owned&(daily.index>pd.Timestamp(last_member))).sum())})

canonical_compare={}
for ca,wi in [('open','adj_open'),('high','adj_high'),('low','adj_low'),('close','adj_close'),('volume','adj_volume'),('as_traded_close','close')]:
    canonical_compare[ca]=bool(c[ca].equals(w[wi]))
canonical_compare['dollar_volume']=bool(np.allclose(c.dollar_volume,w.close*w.volume,rtol=0,atol=1e-6))
result={'network_requests':0,'repo_mutated':False,'canonical_candidate_written':False,
        'run_id':sel['run_id'],'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'inputs':{k:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()},
        'identity_status':'SOURCE_NAMES_MATCH_CIMAREX_NO_LOCAL_PRIMARY_CIK_OR_COMMON_SHARE_BRIDGE_FOUND',
        'member':member,'existing_source_end':str(source_end.date()),
        'normal_first_post_removal_rebalance':{k:next_rebalance[k] for k in ['signal_date','execution_date']},
        'normal_exit_caveat':'Schedule anchor, not proof of a repaired counterfactual path exit. Existing truncated-source paths do not own XEC at this boundary.',
        'segments':audits,'overlap_stats':stats,
        'canonical_equals_wiki_fields':canonical_compare,
        'wiki_prefix_audit':source_bad,'canonical_prefix_audit':canonical_bad,
        'prefix_missing_sessions':prefix_missing.strftime('%Y-%m-%d').tolist(),
        'prefix_nonunit_split_rows':w.loc[w.split_ratio!=1,['split_ratio']].reset_index().astype(str).to_dict('records'),
        'wiki_dividend_count':int(w['ex-dividend'].ne(0).sum()),
        'wiki_recorded_event_formula_conflicts':events[events.wiki_formula_residual.abs()>1e-5].reset_index().astype(str).to_dict('records'),
        'sheepb_step_count':len(ysteps),'sheepb_step_count_member_tail':int(ysteps.within_member_tail.sum()),
        'sheepb_step_count_normal_exit_tail':int(ysteps.within_normal_exit_tail.sum()),
        'calendar_only_260_windows':calendar_only,'actual_current_paths':paths_current,
        'source_cutoff_is_not_terminal_event':True}
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('segments',{k:{x:v[x] for x in ['rows','expected_sessions','missing_expected_sessions','invalid_basic_dates','physical_conflict_dates']} for k,v in audits.items()})
print('prefixmissing',result['prefix_missing_sessions'],'physical',source_bad['physical_conflict_dates'],'canonical',canonical_bad['physical_conflict_dates'])
print('overlap',stats)
print('lastWikiEvents',events.tail(6).round(7).to_string())
print('tailFactorSteps',ysteps.loc[start:].round(7).to_string())
print('260dateonly',calendar_only)
print('path lasttrades',[(x['path'],x['last_trade']) for x in paths_current])
