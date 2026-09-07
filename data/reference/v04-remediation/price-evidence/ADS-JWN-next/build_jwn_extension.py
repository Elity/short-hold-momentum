from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil
import numpy as np
import pandas as pd
import exchange_calendars as xcals

BASE=Path(__file__).resolve().parent
OUT=BASE/'JWN-extension';OUT.mkdir(exist_ok=True)
ROOT=Path('/Users/fighting/code/short-hold-momentum')
SOURCE=BASE.parent/'sheepb-extracted/JWN.parquet'
ARCHIVE=BASE.parents[1]/'v04-remediation-archive/prices/JWN.parquet'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
D=lambda t:str(pd.Timestamp(t).date())
manifest=json.loads((ROOT/'data/reference/v04-remediation/manifest.json').read_text())
entry=manifest['price_overrides']['JWN'];old_path=ROOT/entry['path'];old_sha=sha(old_path)
old=pd.read_parquet(old_path).sort_values('date').reset_index(drop=True)
source=pd.read_parquet(SOURCE);source['date']=pd.to_datetime(source.Date);source=source.sort_values('date').reset_index(drop=True)
raw=pd.read_parquet(ARCHIVE);raw['date']=pd.to_datetime(raw.date)
# Amounts and dates are transcribed from the published table, never inferred from price factors.
events=[
 ('2017-11-15','2017-11-24','2017-11-27','2017-12-12'),
 ('2018-02-21','2018-03-02','2018-03-05','2018-03-20'),
 ('2018-05-08','2018-05-17','2018-05-18','2018-06-04'),
 ('2018-08-22','2018-08-31','2018-09-04','2018-09-19'),
 ('2018-11-14','2018-11-23','2018-11-26','2018-12-11'),
 ('2019-02-27','2019-03-08','2019-03-11','2019-03-26'),
 ('2019-05-23','2019-05-31','2019-06-03','2019-06-18'),
 ('2019-08-20','2019-08-29','2019-08-30','2019-09-16'),
 ('2019-11-21','2019-11-27','2019-11-29','2019-12-16'),
 ('2020-02-27','2020-03-09','2020-03-10','2020-03-25')]
records=[]
table=(BASE/'04-jwn-issuer-dividends-direct.txt').read_text()
for declaration,ex,record,payment in events:
    date=pd.Timestamp(ex)
    compact=f'{date.month}/{date.day}/{date.year}'
    assert compact in table
    records.append({'declaration_date':declaration,'ex_date':ex,'record_date':record,'payment_date':payment,
                    'cash_per_nominal_share':.37,'currency':'USD',
                    'scope':'prefix_missing_dividend' if date<=old.date.max() else 'extension_dividend',
                    'amount_source':'Published Mergent table hosted by Nordstrom, corroborated by SEC quarterly/annual dividend disclosures and saved issuer releases',
                    'ex_date_source':'Mergent historical table on issuer website; date agrees with source adjustment-factor event',
                    'date_source_grade':'ISSUER_HOSTED_THIRD_PARTY_TABLE_NOT_INDIVIDUAL_SEC_EXDATE_ANNOUNCEMENT',
                    'amount_not_inferred_from_factor':True})
e=pd.DataFrame(records);e.to_csv(OUT/'dividend-events.csv',index=False)
amounts={pd.Timestamp(row['ex_date']):row['cash_per_nominal_share'] for row in records}
anchor=old.iloc[-1];anchor_factor=float(anchor.close/anchor.as_traded_close)
# Validate the canonical frozen-WIKI convention on the last already recorded dividend.
known_date=pd.Timestamp('2017-08-24');known=raw.loc[raw.date.eq(known_date)].iloc[0];prior=raw.loc[raw.date.lt(known_date)].iloc[-1]
observed=(prior.adj_close/prior.close)/(known.adj_close/known.close)
expected=float(known.close/(known.close+known['ex-dividend']))
assert abs(observed-expected)<1e-12
# Extend the frozen anchor forward under the canonical WIKI total-return rule.
tail=source.loc[source.date.gt(old.date.max())].copy();factor=anchor_factor;factors=[];factor_events=[]
for row in tail.itertuples():
    cash=amounts.get(row.date,0.)
    if cash:
        factor*=float((row.Close+cash)/row.Close)
        factor_events.append({'ex_date':D(row.date),'cash':cash,'nominal_ex_close':float(row.Close),'factor_after':factor})
    factors.append(factor)
tail['canonical_factor']=factors
imported_at=pd.Timestamp.fromtimestamp(SOURCE.stat().st_mtime,tz='UTC')
def frame_from(rows, factors, label):
    f=pd.DataFrame({'date':rows.date,'open':rows.Open*factors,'high':rows.High*factors,'low':rows.Low*factors,
                    'close':rows.Close*factors,'volume':rows.Volume,'as_traded_close':rows.Close,
                    'dollar_volume':rows.Close*rows.Volume,'adjusted':True,'source':label,'downloaded_at':imported_at})
    f['date']=pd.to_datetime(f.date).astype(old.date.dtype)
    f['downloaded_at']=pd.to_datetime(f.downloaded_at,utc=True).astype(old.downloaded_at.dtype)
    return f[list(old.columns)]
new=frame_from(tail,tail.canonical_factor,'SheepB stock-market-dataset-20002021 v1; nominal OHLCV with canonical WIKI dividend return factors')
variant1=pd.concat([old,new],ignore_index=True).sort_values('date').reset_index(drop=True)
pd.testing.assert_frame_equal(variant1.loc[variant1.date.le(old.date.max())].reset_index(drop=True),old)
# The original WIKI also lacks 2017-11-08; its entire supplied row has an independent local IEX cross-check.
calendar=xcals.get_calendar('XNYS',start=old.date.min(),end=source.date.max())
missing_prefix=calendar.sessions[(calendar.sessions>=old.date.min())&(calendar.sessions<=old.date.max())].difference(old.date)
assert missing_prefix.tolist()==[pd.Timestamp('2017-11-08')]
gap_rows=source.loc[source.date.isin(missing_prefix)].copy()
iex=pd.read_csv(BASE/'JWN-IEX-original.csv');iex['date']=pd.to_datetime(iex.date)
gap_comparison=[]
for row in gap_rows.itertuples():
    ref=iex.loc[iex.date.eq(row.date)].iloc[0]
    cmp={col:float(abs(getattr(row,col.title())-ref[col])/ref[col]) for col in ['open','high','low','close']}
    assert max(cmp.values())<.0001
    gap_comparison.append({'date':D(row.date),'sheepb_full_row':{k:v for k,v in source.loc[source.date.eq(row.date)].iloc[0].to_dict().items() if k != 'date'},
                           'iex_ohlcv':{k:float(ref[k]) for k in ['open','high','low','close','volume']},
                           'relative_ohlc_differences':cmp,'relative_volume_difference':float(abs(row.Volume-ref.volume)/ref.volume)})
# Adjacent old rows share the same frozen factor; no interpolation of price or volume is used.
gap_factors=[]
for date in gap_rows.date:
    before=old.loc[old.date.lt(date)].iloc[-1];after=old.loc[old.date.gt(date)].iloc[0]
    f_before=float(before.close/before.as_traded_close);f_after=float(after.close/after.as_traded_close)
    assert abs(f_before-f_after)<1e-12 and date not in amounts
    gap_factors.append(f_before)
gaps=frame_from(gap_rows,np.array(gap_factors),'SheepB v1 full 2017-11-08 row; independently compared with existing Cam Nugent IEX archive')
variant2=pd.concat([variant1,gaps],ignore_index=True).sort_values('date').reset_index(drop=True)
price_columns=['open','high','low','close'];prefix_repairs=[]
for row in records:
    date=pd.Timestamp(row['ex_date'])
    if row['scope']!='prefix_missing_dividend':continue
    p_ex=float(old.loc[old.date.eq(date),'as_traded_close'].iloc[0]);multiplier=p_ex/(p_ex+row['cash_per_nominal_share'])
    mask=variant2.date.lt(date);variant2.loc[mask,price_columns]*=multiplier
    prefix_repairs.append({**row,'nominal_ex_close_from_existing_prefix':p_ex,'multiplier_for_strictly_pre_ex_adjusted_ohlc':multiplier,
                           'old_rows_changed':int(old.date.lt(date).sum()),'candidate_rows_changed':int(mask.sum())})
nonprices=[c for c in old.columns if c not in price_columns]
pd.testing.assert_frame_equal(variant2.loc[variant2.date.isin(old.date),nonprices].reset_index(drop=True),old[nonprices])
pd.testing.assert_frame_equal(variant2.loc[variant2.date.gt(old.date.max())].reset_index(drop=True),new.reset_index(drop=True))
missing1=[D(x) for x in calendar.sessions.difference(variant1.date)];missing2=[D(x) for x in calendar.sessions.difference(variant2.date)]
assert missing1==['2017-11-08'] and missing2==[]
assert len(variant2)==4503 and len(new)==856 and len(old)==3646
assert variant2.date.is_unique
assert (variant2.volume>0).all()
assert np.isfinite(variant2[price_columns+['volume','as_traded_close','dollar_volume']]).all().all()
assert not (variant2.open.gt(variant2.high+1e-6)|variant2.open.lt(variant2.low-1e-6)|variant2.close.gt(variant2.high+1e-6)|variant2.close.lt(variant2.low-1e-6)).any()
checks=[]
for row in records:
    date=pd.Timestamp(row['ex_date']);present=variant2.loc[variant2.date.eq(date)].iloc[0];before=variant2.loc[variant2.date.lt(date)].iloc[-1]
    actual=float(present.close/before.close-1)
    expected_return=float((present.as_traded_close+row['cash_per_nominal_share'])/before.as_traded_close-1)
    assert abs(actual-expected_return)<1e-12
    checks.append({'ex_date':row['ex_date'],'actual_adjusted_return':actual,'expected_nominal_plus_cash_return':expected_return,'absolute_error':abs(actual-expected_return)})
# A market provider's Adj Close is only a cross-check, not the dividend amount or canonical return source.
boundary=source.loc[source.date.eq(old.date.max())].iloc[0]
provider_rebased=tail['Adj Close']*(float(anchor.close)/float(boundary['Adj Close']))
rebased_difference=(new.close.to_numpy()/provider_rebased.to_numpy()-1)
comparison=source.merge(raw,on='date',suffixes=('_source','_wiki'))
post_split=comparison.loc[comparison.date.ge('2005-07-01')].copy();ratio_stats={};conflicts=[]
for column in ['open','high','low','close']:
    ratio=post_split[column.title()]/post_split[column]
    ratio_stats[column]={'count':len(ratio),'median':float(ratio.median()),'min':float(ratio.min()),'max':float(ratio.max()),'p99_abs_relative_difference':float(ratio.sub(1).abs().quantile(.99))}
    for i in ratio.sub(1).abs().nlargest(5).index:
        r=post_split.loc[i];conflicts.append({'date':D(r.date),'field':column,'source':float(r[column.title()]),'wiki':float(r[column]),'ratio':float(ratio.loc[i])})
vol_rel=(post_split.Volume-post_split.volume).abs()/post_split.volume
v1path=OUT/'JWN-tail-prefix-unchanged.candidate.parquet';v2path=OUT/'JWN-tail-plus-prefix-repairs.candidate.parquet'
variant1.to_parquet(v1path,index=False);variant2.to_parquet(v2path,index=False)
pd.testing.assert_frame_equal(pd.read_parquet(v1path).iloc[:len(old)],old)
readback=pd.read_parquet(v2path);pd.testing.assert_frame_equal(readback,variant2)
assert sha(old_path)==old_sha
new.to_csv(OUT/'added-tail-rows.csv',index=False);pd.DataFrame(prefix_repairs).to_json(OUT/'prefix-dividend-repairs.json',orient='records',indent=2)
source.loc[source.date.isin(missing_prefix)].to_csv(OUT/'2017-11-08-source-whole-row.csv',index=False)
audit={
 'status':'CORRECTED_CANDIDATE_READY_FOR_ROOT_REVIEW_GLOBAL_GATE_UNCHANGED','preferred_candidate':v2path.name,
 'variant1':{'path':v1path.name,'sha256':sha(v1path),'rows':len(variant1),'old_prefix_exactly_preserved':True,'new_rows':len(new),'missing_sessions':missing1,'apply_ready':False,'known_unfixed_dividend_dates':['2017-11-24','2018-03-02']},
 'variant2':{'path':v2path.name,'sha256':sha(v2path),'rows':len(variant2),'first':D(variant2.date.min()),'last':D(variant2.date.max()),'missing_sessions':missing2,'new_tail_rows':len(new),'added_prefix_whole_rows':len(gaps),'apply_ready':True,'old_non_price_fields_exactly_preserved':True,'prefix_adjusted_ohlc_repairs':prefix_repairs},
 'selection_reason':'JWN has eight post-cutoff dividend-factor events versus fourteen for ADS through the same source endpoint, and SEC explicitly confirms suspension beginning Q2 2020. Selection is evidence-completeness-based, not return-based.',
 'identity':{'issuer':'Nordstrom, Inc.','cik':'0000072333','security_class':'Common stock, without par value','exchange':'New York Stock Exchange','ticker':'JWN','source_identity':'Local SheepB Name JWN / Company Name Nordstrom; post-2005 nominal overlap with frozen WIKI supports continuity.'},
 'inputs':{'runtime_prefix':str(old_path),'runtime_prefix_sha256':old_sha,'raw_wiki_archive':str(ARCHIVE),'raw_wiki_archive_sha256':sha(ARCHIVE),'sheepb_file':str(SOURCE),'sheepb_file_sha256':sha(SOURCE),'sheepb_archive_sha256':'22f61a91843c579577a1757bd31653fd998ba8054723da3d4b41d994cda46373','local_iex_csv':str(BASE/'JWN-IEX-original.csv'),'local_iex_csv_sha256':sha(BASE/'JWN-IEX-original.csv')},
 'dividend_evidence':{'events':records,'tail_count':8,'prefix_missing_count':2,'amounts_never_inferred_from_factors':True,'date_grade':'Issuer-hosted Mergent history, independently matching vendor adjustment dates; not all dates are individual SEC announcements.','primary_amount_support':'SEC 2020 10-K gives all four 2019 quarters at 0.37 and 2020 Q1 at 0.37; SEC 2019 10-K gives 2017/2018/2019 annual totals 1.48; issuer May/Aug 2018 releases and 2018 Q1/Q2 filings corroborate 0.37 installments.','suspension_support':'SEC 2020 10-K says cash dividends suspended from Q2 2020, consistent with no further Mergent records or factor events through 2021-08-19.','2021q2_limit':'Browse result is truncated before financial statements; final direct SEC request returned 403 and was not retried.'},
 'split_and_unit_evidence':{'last_wiki_split':'2005-07-01 2:1','issuer_hosted_table_last_split':'2005-07-01 1:2 display convention','split_table_grade':'Mergent third-party data hosted by issuer, not a separately retrieved split announcement','post_split_overlap_ratios':ratio_stats,'no_nonunit_scale_observed_after_2005':True,'condition':'Source Close is split-adjusted. Since the full post-2005 source overlaps old nominal OHLC at unit scale, no later non-unit cumulative split rescaling is observed. Tail alone uses Close as nominal; earlier split-adjusted source prices never replace the historical raw prefix.'},
 'return_convention':{'known_wiki_dividend_test_date':'2017-08-24','known_wiki_dividend':float(known['ex-dividend']),'observed_backward_factor':float(observed),'expected_Pex_over_Pex_plus_D':expected,'absolute_error':abs(float(observed)-expected),'tail_anchor_date':D(anchor.date),'tail_anchor_factor':anchor_factor,'tail_formula':'f_t=f_previous*(P_ex+D)/P_ex on verified ex-dates; unchanged otherwise','prefix_formula':'multiply adjusted OHLC strictly before each missing ex-date by P_ex/(P_ex+D)','prefix_anchor_unchanged':True,'last_canonical_factor':float(new.iloc[-1].close/new.iloc[-1].as_traded_close),'event_return_checks':checks,'max_relative_difference_from_constant_rebased_provider_adj_close':float(np.max(np.abs(rebased_difference))),'dividend_cash_events_added':0},
 'prefix_missing_row_crosscheck':gap_comparison,'preserved_old_provider_conflicts':conflicts,
 'volume_basis':{'source':'Unscaled reported number of shares from frozen SheepB/yfinance; no K/M parsing','venue_scope':'not independently established','overlap_median_abs_relative_difference':float(vol_rel.median()),'overlap_p99_abs_relative_difference':float(vol_rel.quantile(.99)),'old_volume_and_dollar_volume_unchanged':True,'new_dollar_volume':'source Close * source Volume; never multiplied by return factor'},
 'tests':{'calendar_complete':True,'duplicates':0,'new_or_repaired_ohlcv_physical_conflicts':0,'old_original_file_unchanged':True,'all_ten_cash_return_identities_verified':True,'parquet_readback_verified':True,'backtest_run':False},
 'remaining_scope':'Closes the JWN required membership price tail through 2020-06-19 and provides exit quotes through 2021-08-19; does not provide the later life through JWN 2025 termination or remove global PRICE_REPAIR_EVIDENCE.',
 'main_repo_modified':False,'new_primary_requests_used':8}
(OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'variant1':audit['variant1'],'variant2':{k:v for k,v in audit['variant2'].items() if k!='prefix_adjusted_ohlc_repairs'},'prefix_repairs':prefix_repairs,'last_factor':audit['return_convention']['last_canonical_factor'],'max_rebased_provider_difference':audit['return_convention']['max_relative_difference_from_constant_rebased_provider_adj_close']},ensure_ascii=False,indent=2))
