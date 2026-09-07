"""Valuation provenance, cash-flow timing and comparable observation returns."""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime
import exchange_calendars as xcals
import pandas as pd

from .domain import ZERO, NY, Invalid, Conflict, dec, digest, encoded, positions, stamp
from .store import now


def value_state(state, payload):
    at = stamp(payload['at'])
    marks = payload.get('marks', {})
    total = state['cash']+state['receivable']-state['payable']
    missing, holdings = [], []
    instruments = {l['instrument']['key']: l['instrument'] for l in state['lots']}
    pending = {i['instrument'] for i in state['issues']}
    for key, q in positions(state).items():
        ins = instruments[key]
        mark = marks.get(key)
        valid = bool(mark and mark.get('source') and mark.get('at') and key not in pending)
        if valid:
            quoted = stamp(mark['at'])
            # Same-session marks only; no stale or future fill-forward.
            valid = quoted <= at and quoted.astimezone(NY).date() == at.astimezone(NY).date()
            valid = valid and not (ins['kind'] == 'equity' and mark.get('basis') != 'nominal')
        price = dec(mark['price'], '单位估值', nonnegative=True) if valid else None
        amount = q*price*dec(ins['multiplier']) if price is not None else None
        holdings.append({'instrument': ins, 'quantity': q, 'mark': price, 'value': amount})
        if amount is None:
            missing.append(key)
        else:
            total += amount
    ledger = total if not missing and not pending else None
    broker = dec(payload['broker_nav'], '券商净资产') if payload.get('broker_nav') not in (None, '') else None
    difference = ledger-broker if ledger is not None and broker is not None else None
    tolerance = max(Decimal('1'), abs(broker)*Decimal('.0001')) if broker is not None else None
    reconciliation = 'unavailable' if difference is None else 'matched' if abs(difference) <= tolerance else 'difference'
    source = payload.get('source', 'unselected')
    if source not in ('ledger', 'broker', 'unselected'):
        raise Invalid('收益来源无效')
    chosen = {'ledger': ledger, 'broker': broker, 'unselected': None}[source]
    if source != 'unselected':
        if chosen is None:
            raise Invalid('指定来源缺少估值')
        if not payload.get('flows_complete'):
            raise Invalid('采用收益来源前须确认该快照之前的入出金录入完整')
        if reconciliation != 'matched' and not payload.get('reason'):
            raise Invalid('未对账时采用指定来源须填写理由；也可暂存待核对')
    return {'at': payload['at'], 'source': source, 'nav': chosen, 'ledger_nav': ledger, 'broker_nav': broker,
            'attribution': 'partial' if missing or pending else 'complete', 'reconciliation': reconciliation,
            'difference': difference, 'tolerance': tolerance, 'missing': missing, 'holdings': holdings,
            'flows_complete': bool(payload.get('flows_complete')), 'reason': payload.get('reason', ''),
            'coverage': payload.get('coverage', ''), 'issues': state['issues']}


def valuation(store, payload, *, save=False):
    with store.connection(save) as db:
        current = store._account(db)
        if not current:
            raise Invalid('请先建账')
        if payload.get('version') != current['version']:
            raise Conflict('账本变化，请重新预览估值')
        if stamp(payload['at']) < stamp(current['account']['at']) or not payload.get('coverage'):
            raise Invalid('估值不得早于期初，并须说明覆盖时点')
        state = store.replay(db, current['account'], until=payload['at'])
        result = value_state(state, payload)
        result['preview_hash'] = digest({'payload': {k:v for k,v in payload.items() if k not in ('preview_hash','save')}, 'result': result})
        result['version'] = current['version']
        if save:
            if payload.get('preview_hash') != result['preview_hash']:
                raise Conflict('估值预览失效，请重新预览')
            result['id'] = db.execute('INSERT INTO valuations(at,payload,result,version,created_at) VALUES(?,?,?,?,?)',
                                      (payload['at'], encoded(payload), encoded(result), current['version'], now())).lastrowid
        return result


def valuations(store):
    with store.connection() as db:
        return [{**json.loads(r['result']), 'id': r['id'], 'valid': bool(r['valid'])} for r in db.execute('SELECT * FROM valuations ORDER BY id DESC')]


def interval_return(start_at, end_at, start_nav, end_nav, flows):
    begin, end = stamp(start_at), stamp(end_at)
    a, b = dec(str(start_nav)), dec(str(end_nav))
    relevant = [f for f in flows if begin < stamp(f['at']) <= end]
    if not relevant:
        denominator, numerator, method = a, b-a, 'TWR'
    else:
        c = sum((dec(str(f['amount'])) for f in relevant), ZERO)
        calendar = xcals.get_calendar('XNYS')
        end_day = pd.Timestamp(end.astimezone(NY).date())
        same_session = end_day in calendar.sessions and all(stamp(f['at']).astimezone(NY).date()==end.astimezone(NY).date() for f in relevant)
        previous_day = pd.Timestamp(begin.astimezone(NY).date())
        adjacent = same_session and previous_day in calendar.sessions and calendar.next_session(previous_day)==end_day
        before = [f for f in relevant if same_session and stamp(f['at'])<=calendar.session_open(end_day).to_pydatetime()]
        after = [f for f in relevant if same_session and stamp(f['at'])>=calendar.session_close(end_day).to_pydatetime()]
        if all(stamp(f['at']) == end for f in relevant):
            denominator, numerator, method = a, b-a-c, 'TWR_after_close'
        elif adjacent and len(before)+len(after)==len(relevant):
            denominator = a+sum((dec(str(f['amount'])) for f in before), ZERO)
            numerator, method = b-a-c, 'TWR_before_open' if before and not after else 'TWR_cash_flow_timing'
        else:
            duration = Decimal(str((end-begin).total_seconds()))
            if duration <= 0:
                raise Invalid('估值时间须递增')
            weighted = sum((dec(str(f['amount']))*Decimal(str((end-stamp(f['at'])).total_seconds()))/duration for f in relevant), ZERO)
            denominator, numerator, method = a+weighted, b-a-c, 'Modified Dietz (近似)'
    if denominator <= 0:
        return None, 'invalid_denominator'
    return numerator/denominator, method


def personal_curve(store):
    current = store.account()
    if current['account'] is None:
        return [], []
    account = current['account']
    opening = {'at': account['at'], 'nav': str(sum((l['basis']*(1 if l['quantity']>0 else -1) for l in current_opening(account)['lots']), ZERO)+dec(account['cash'])+dec(account.get('receivable','0'))-dec(account.get('payable','0'))), 'flows_complete': True, 'source': 'opening'}
    latest = {}
    for v in reversed(valuations(store)):
        latest[v['at']] = v if v['valid'] else {**v, 'nav': None}
    points = [opening]+sorted([v for v in latest.values() if stamp(v['at'])>stamp(opening['at'])], key=lambda x: stamp(x['at']))
    flows = current['state']['flows']
    index, curve, previous = Decimal('100'), [], None
    for p in points:
        valid = p['nav'] is not None and p.get('flows_complete')
        method, r = 'opening', None
        if previous and valid and previous['nav'] is not None:
            r, method = interval_return(previous['at'], p['at'], previous['nav'], p['nav'], flows)
            if r is None:
                valid = False
            elif index is not None:
                index *= 1+r
        elif previous:
            valid = False
        if not valid:
            curve.append({'at': p['at'], 'date': str(stamp(p['at']).astimezone(NY).date()), 'nav': p['nav'], 'index': None, 'return': None, 'method': 'missing', 'source': p['source']})
            continue
        curve.append({'at': p['at'], 'date': str(stamp(p['at']).astimezone(NY).date()), 'nav': p['nav'], 'index': index, 'return': r, 'method': method, 'source': p['source']})
        previous = p
    return curve, flows


def current_opening(account):
    from .domain import initial
    return initial(account)
