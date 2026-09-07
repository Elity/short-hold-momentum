from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import exchange_calendars as xcals
import pandas as pd

from .domain import Invalid, NY, dec, stamp
from .valuation import personal_curve
from shm.service.dashboard import build_portfolio, _build_v03_portfolio
from shm.service.workflow import latest_completed_session
from shm.v04.profiles import STRATEGY_IDS


def cached_prices(root, symbol):
    path = root / 'data/raw/prices' / f'{symbol}.parquet'
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame['date'] = pd.to_datetime(frame['date']).dt.tz_localize(None).dt.normalize()
    return frame.set_index('date').sort_index()


def compare(store, root, *, strategy_id='S500-C3', cost_bps=10, start=None, end=None):
    if strategy_id not in ('V04', *STRATEGY_IDS) or cost_bps not in (10, 25):
        raise Invalid('无效策略或成本情景')
    curve, _ = personal_curve(store)
    result = {'rows': [], 'strategy_id': strategy_id, 'cost_bps': cost_bps,
              'simulation_status': 'waiting', 'complete': False, 'metrics': {},
              'cost_note': '个人：实际费用、利息及扣税；模拟：模型成本；SPY：含息总回报，首日买入成本，末日估值',
              'warnings': []}
    if not curve:
        return result
    cutoff = latest_completed_session()
    # Daily cache supports only completed session closes, never an invented intraday benchmark.
    calendar = xcals.get_calendar('XNYS', start=curve[0]['date'], end=max(str(cutoff.date()), curve[-1]['date']))
    daily = {}
    for p in curve:
        day = pd.Timestamp(p['date'])
        if day in calendar.sessions and stamp(p['at']) >= calendar.session_close(day).to_pydatetime():
            daily[p['date']] = p
    if not daily:
        result['warnings'].append('等待首份收盘估值；日线 SPY 无法比较盘中期初')
        return result
    valid = [d for d,p in daily.items() if p['index'] is not None]
    if not valid:
        result['warnings'].append('个人估值或资金流不完整')
        return result
    beginning = max(min(valid), start or min(valid))
    ending = min(max(daily), str(cutoff.date()), end or str(cutoff.date()))
    try:
        sim = build_portfolio(root) if strategy_id == 'V04' else _build_v03_portfolio(root, strategy_id, cost_bps, datetime.now(timezone.utc))
    except (OSError, ValueError, KeyError):
        sim = {'chart': []}
    simulation = {p['date']: p['equity'] for p in sim['chart'] if p['equity'] is not None}
    # A single initialized-cash row is not forward evidence.
    if len(simulation) > 1:
        beginning = max(beginning, min(simulation))
        ending = min(ending, max(simulation))
        result['simulation_status'] = 'forward'
    else:
        simulation = {}
    spy = cached_prices(root, 'SPY')
    if spy.empty or 'close' not in spy:
        result['warnings'].append('SPY 总回报价缺失')
        return result
    common = sorted(d for d in daily if beginning <= d <= ending and daily[d]['index'] is not None and pd.Timestamp(d) in spy.index and (not simulation or d in simulation))
    if not common:
        result['warnings'].append('尚无共同可比较收盘起点')
        return result
    beginning = common[0]
    pbase = dec(str(daily[beginning]['index']))
    spybase = dec(str(spy.loc[pd.Timestamp(beginning), 'close']), positive=True)
    sbase = dec(str(simulation[beginning])) if simulation else None
    # Paying bps on purchased notional reduces initial wealth by 1/(1+cost).
    invest = Decimal('100')/(1+Decimal(cost_bps)/10000)
    for day in calendar.sessions_in_range(beginning, ending):
        d = str(day.date())
        p = daily.get(d)
        pv = dec(str(p['index']))/pbase*100 if p and p['index'] is not None else None
        sv = dec(str(simulation[d]))/sbase*100 if simulation and d in simulation and sbase and sbase>0 else None
        bv = invest*dec(str(spy.loc[day,'close']))/spybase if day in spy.index and pd.notna(spy.loc[day,'close']) else None
        result['rows'].append({'date': d, 'personal': pv, 'simulation': sv, 'spy': bv, 'method': p['method'] if p else 'missing'})
    result.update(start=beginning, end=ending)
    required = ['personal','spy']+(['simulation'] if simulation else [])
    result['complete'] = bool(result['rows']) and all(r[k] is not None for r in result['rows'] for k in required)
    for key in required:
        vals = [r[key] for r in result['rows']]
        complete = all(v is not None for v in vals)
        peak, dd = Decimal('100'), Decimal('0')
        for v in vals:
            if v is not None:
                peak = max(peak, v)
                dd = min(dd, v/peak-1)
        result['metrics'][key] = {'cumulative_return': vals[-1]/100-1 if vals[-1] is not None else None,
                                  'max_drawdown': dd if complete else None, 'complete': complete}
    if not result['complete']:
        result['warnings'].append('区间内部存在缺值；曲线断开，不提供完整区间最大回撤或排名')
    if any('Dietz' in r['method'] for r in result['rows']):
        result['warnings'].append('盘中资金流缺少即时估值，部分收益使用 Modified Dietz 近似')
    return result
