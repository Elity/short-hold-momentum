"""Audit existing archives and propose one whole-row replacement; never apply it."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import pandas as pd
import exchange_calendars as xc

OUT = Path(__file__).resolve().parent
WORK = OUT.parents[1]
REPO = Path('/Users/fighting/code/short-hold-momentum')
DAY = pd.Timestamp('2016-11-25')
FIELDS = ['open', 'high', 'low', 'close', 'volume']
FILES = {
    'IEX': WORK / 'v04-corporate-actions-next/ATVI-independent-extracted.source.csv',
    'JacksonCrow': WORK / 'v04-source-options-next/ATVI-jackson-source.csv',
    'SheepB': WORK / 'v04-source-options-next/sheepb-extracted/ATVI.parquet',
    'WIKI': WORK / 'v04-remediation-archive/prices/ATVI.parquet',
    'current_2020': REPO / 'data/research/v04/prices/ATVI-through-2020-04-01.parquet',
    'IEX_metadata': WORK / 'v04-corporate-actions-next/ATVI-kaggle-metadata.source.json',
    'JacksonCrow_metadata': WORK / 'v04-source-options-next/03-jacksoncrow-metadata.body',
    'SheepB_metadata': WORK / 'v04-source-options-next/04-sheepb-metadata.body',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


input_hashes = {key: {'path': str(path), 'sha256': sha(path)} for key, path in FILES.items()}
cal = xc.get_calendar('XNYS', start='2016-10-01', end='2016-12-31')
i = cal.sessions.get_loc(DAY)
dates = cal.sessions[i-10:i+11]
frames = {}
for name in ['IEX', 'JacksonCrow', 'SheepB', 'WIKI', 'current_2020']:
    path = FILES[name]
    frame = pd.read_parquet(path) if path.suffix == '.parquet' else pd.read_csv(path)
    frame.columns = [c.lower() for c in frame.columns]
    frame['date'] = pd.to_datetime(frame['date'])
    frames[name] = frame.set_index('date').reindex(dates)
    assert frames[name][FIELDS].notna().all().all()

selected = frames['IEX'].loc[DAY]
old = frames['current_2020'].loc[DAY]
assert old['open'] < old['low'] and frames['WIKI'].loc[DAY, 'open'] == 36.52
assert selected['low'] <= min(selected['open'], selected['close']) <= max(selected['open'], selected['close']) <= selected['high']
assert selected['close'] == old['as_traded_close']
factor = float(old['close'] / old['as_traded_close'])
factor_window = frames['current_2020']['close'] / frames['current_2020']['as_traded_close']
assert np.allclose(factor_window, factor, rtol=0, atol=1e-12)
comparison, stats = [], {}
for name, frame in frames.items():
    if name == 'current_2020':
        continue
    for day, row in frame.iterrows():
        comparison.append({'provider': name, 'date': str(day.date()),
                           **{f: float(row[f]) for f in FIELDS},
                           **{f + '_delta_vs_IEX': float(row[f] - frames['IEX'].loc[day, f]) for f in FIELDS}})
    delta = frame[FIELDS] - frames['IEX'][FIELDS]
    neighbors = delta.drop(DAY)
    bad = neighbors[FIELDS[:4]].abs().gt(.011).any(axis=1)
    stats[name] = {'target': {f: float(frame.at[DAY, f]) for f in FIELDS},
                   'target_max_abs_OHLC_delta_vs_IEX': float(delta.loc[DAY, FIELDS[:4]].abs().max()),
                   'target_volume_delta_vs_IEX': float(delta.at[DAY, 'volume']),
                   'neighbor_sessions': 20, 'neighbor_all_OHLC_within_0_011': int((~bad).sum()),
                   'neighbor_price_conflict_dates': neighbors.index[bad].strftime('%Y-%m-%d').tolist(),
                   'neighbor_max_abs_OHLC_delta': {f: float(neighbors[f].abs().max()) for f in FIELDS[:4]},
                   'neighbor_max_abs_relative_volume_delta': float((neighbors['volume'] / frames['IEX'].drop(DAY)['volume']).abs().max())}
pd.DataFrame(comparison).to_csv(OUT / 'provider-target-and-20-neighbors.csv', index=False)
factor_window.rename('canonical_factor').to_csv(OUT / 'current-canonical-factor-window.csv')
patch = {'date': '2016-11-25', **{f: float(selected[f] * factor) for f in FIELDS[:4]},
         'volume': float(selected['volume']), 'as_traded_close': float(selected['close']),
         'dollar_volume': float(selected['close'] * selected['volume']), 'adjusted': True,
         'source': 'IEX via Cam Nugent Kaggle sandp500 v4 (2018-02-10); whole 2016-11-25 OHLCV row, existing WIKI canonical adjustment factor preserved',
         'downloaded_at': datetime.now(timezone.utc).isoformat()}
assert patch['close'] == old['close'] and patch['volume'] == old['volume']
assert patch['as_traded_close'] == old['as_traded_close'] and patch['dollar_volume'] == old['dollar_volume']
assert patch['low'] <= min(patch['open'], patch['close']) <= max(patch['open'], patch['close']) <= patch['high']
pd.DataFrame([patch]).to_csv(OUT / 'ATVI-2016-11-25.patch.csv', index=False)
original = {key: (str(value) if isinstance(value, pd.Timestamp) else value) for key, value in old.to_dict().items()}
original['date'] = '2016-11-25'
save('original-row.json', original)
audit = {
    'status': 'VERIFIED_SINGLE_ROW_REPAIR_PROPOSAL_NOT_APPLIED', 'ticker': 'ATVI', 'date': '2016-11-25',
    'problem': 'Old WIKI nominal open 36.52 is below its low 37.20; preserved current adjusted open 36.301143... is below low 36.977068.... This predates the 2020 extension.',
    'source_choice': 'Entire IEX OHLCV row; no provider mixing. IEX is the selected vendor. JacksonCrow and SheepB are two archived Yahoo/yfinance snapshots, not two independent vendors.',
    'nominal_ohlcv': {f: float(selected[f]) for f in FIELDS}, 'canonical_factor': factor,
    'canonical_factor_range_in_21_sessions': [float(factor_window.min()), float(factor_window.max())],
    'normalization': 'Multiply every selected IEX nominal OHLC field by old canonical close / old as_traded_close. Preserve IEX share volume and nominal close*volume. Never import either newer Yahoo Adj Close scale.',
    'neighbor_window': [str(dates[0].date()), str(dates[-1].date())],
    'neighbor_definition': '10 XNYS sessions before + target + 10 XNYS sessions after',
    'source_comparisons': stats,
    'unchanged_existing_numerics': ['close', 'volume', 'as_traded_close', 'dollar_volume'],
    'material_numeric_change': {'open_before': float(old['open']), 'open_after': patch['open']},
    'source_limits': ['IEX volume is a reported integer share count; exact consolidation scope is not independently established.',
                      'Yahoo-derived target volume is 19 shares lower than IEX, a 0.000593% difference. Use all IEX fields together.',
                      'Old WIKI 2016-11-30 open differs from IEX/Yahoo by 0.05 while remaining internally consistent; record it without widening this repair.'],
    'input_hashes': input_hashes, 'network_requests': 0, 'main_manifest_modified': False,
    'current_or_2021_candidate_modified': False,
    'application_preconditions': ['Locate the 2016-11-25 row in the final 2021 candidate; require its preserved original fields and canonical factor to match this audit.',
                                 'Replace this entire one row only, preserving the final candidate schema and timestamp dtype.',
                                 'Update candidate and evidence hashes in a new manifest entry; do not retain a claim that every preexisting row is unchanged after this explicit repair.']}
save('audit.json', audit)
save('repair-proposal.json', {'status': 'PROPOSAL_ONLY', 'ticker': 'ATVI', 'date': '2016-11-25',
     'operation': 'replace_one_whole_row_in_final_2021_candidate_after_original_row_check',
     'expected_original_row_file': str(OUT / 'original-row.json'),
     'expected_original_row_sha256': sha(OUT / 'original-row.json'), 'canonical_factor': factor,
     'replacement_row': patch, 'selected_source_path': str(FILES['IEX']), 'selected_source_sha256': sha(FILES['IEX']),
     'audit_path': str(OUT / 'audit.json'), 'audit_sha256': sha(OUT / 'audit.json'),
     'manifest_instruction': 'Append a dated whole-row repair entry, update the final candidate hash and invalid-row audit; do not replace unrelated history.'})
(OUT / 'report.md').write_text(f'''# ATVI 2016-11-25 whole-row repair proposal

The selected complete IEX row is O37.45 / H37.58 / L37.20 / C37.22 / V3,206,319. JacksonCrow and SheepB both report the same OHLC to float precision and V3,206,300. They are two Yahoo/yfinance archive captures, not two independent vendors.

Across the 10 XNYS sessions before and after the date (2016-11-10 to 2016-12-09), both Yahoo captures agree with IEX on all OHLC within $0.011 on 20/20 neighboring sessions. Their largest relative volume difference from IEX is about 0.00917%. The target volume differs by only 19 shares; the entire IEX row is used without mixing fields.

Old WIKI is the outlier: nominal open36.52 is below low37.20. The bad value was already in the preserved old prefix. Current adjusted open={old['open']:.12f}, low={old['low']:.12f}. Using the existing constant canonical factor {factor:.15f}, the replacement adjusted open is {patch['open']:.12f}. Close, volume, as_traded_close and dollar_volume remain exactly unchanged. Newer Yahoo Adj Close fields are not imported.

The 2016-11-30 WIKI open also differs by $0.05 from IEX/Yahoo but is internally valid. That supplier difference is retained as evidence and is not part of this proposed repair.

Files: repair-proposal.json, audit.json, original-row.json, ATVI-2016-11-25.patch.csv, provider-target-and-20-neighbors.csv, and current-canonical-factor-window.csv. Root should verify that the final 2021 candidate still contains the original row/factor, then replace only this complete row and refresh hashes. No main manifest or candidate was modified, and no network requests were made.
''')
assert all(sha(FILES[key]) == record['sha256'] for key,record in input_hashes.items())
print(json.dumps({'nominal_ohlcv':audit['nominal_ohlcv'],'factor':factor,'open_before':float(old['open']),
                  'open_after':patch['open'],'close_unchanged':True,'Yahoo_neighbors_matching':'20/20',
                  'network_requests':0,'main_and_candidate_unchanged':True},indent=2))
