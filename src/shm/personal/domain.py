"""Deterministic personal ledger. Money crosses the API as decimal strings."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

ZERO = Decimal('0')
NY = ZoneInfo('America/New_York')


class Invalid(ValueError):
    pass


class Conflict(Invalid):
    pass


def dec(value, field='amount', *, positive=False, nonnegative=False):
    if not isinstance(value, (str, Decimal)):
        raise Invalid(f'{field}: 必须使用十进制字符串')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise Invalid(f'{field}: 无效数值') from None
    if not result.is_finite() or (positive and result <= 0) or (nonnegative and result < 0):
        raise Invalid(f'{field}: 数值范围无效')
    return result


def encoded(value):
    return json.dumps(value, default=lambda x: str(x) if isinstance(x, Decimal) else None,
                      sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def stamp(value, *, future=False):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise Invalid('时间必须含时区偏移，例如 2026-09-04T16:00:00-04:00') from None
    if not future and result > datetime.now(timezone.utc):
        raise Invalid('不能录入未来事件')
    return result


def instrument(raw):
    kind = raw.get('kind', 'equity')
    symbol = str(raw.get('symbol', '')).upper().strip()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-^]{0,15}', symbol):
        raise Invalid('证券代码无效')
    item = {'kind': kind, 'symbol': symbol}
    if kind == 'equity':
        item.update(key=symbol, multiplier='1')
        return item
    if kind != 'option':
        raise Invalid('证券类型须为 equity 或 option')
    try:
        expiry = date.fromisoformat(raw['expiry'])
    except (ValueError, KeyError):
        raise Invalid('期权到期日无效') from None
    right = raw.get('right', '').upper()
    settlement = raw.get('settlement', 'physical')
    if right not in ('C', 'P') or settlement not in ('physical', 'cash'):
        raise Invalid('期权类型或结算方式无效')
    strike = dec(raw.get('strike'), '行权价', positive=True)
    mult = dec(raw.get('multiplier', '100'), '乘数', positive=True)
    if mult != mult.to_integral_value():
        raise Invalid('乘数须为整数')
    adjusted = bool(raw.get('adjusted', False))
    series = str(raw.get('series', 'standard'))
    if adjusted and series == 'standard':
        raise Invalid('调整合约须提供独立 series 标识')
    code = raw.get('occ', '').replace(' ', '').upper()
    if code:
        match = re.fullmatch(r'([A-Z0-9.]+)(\d{6})([CP])(\d{8})', code)
        if not match or match[1] != symbol or match[2] != expiry.strftime('%y%m%d') or match[3] != right or Decimal(match[4])/1000 != strike:
            raise Invalid('合约代码与标的、到期日、方向或行权价不一致')
    item.update(expiry=str(expiry), right=right, strike=str(strike), multiplier=str(mult),
                settlement=settlement, adjusted=adjusted, series=series, occ=code)
    item['key'] = f'{symbol}:{expiry}:{right}:{strike.normalize()}:{mult}:{settlement}:{series}'
    return item


def quantity(value, item, *, signed=False):
    q = dec(value, '数量', positive=not signed)
    if q == 0 or (item['kind'] == 'option' and q != q.to_integral_value()):
        raise Invalid('期权张数须为非零整数；普通数量须非零')
    return q


def positions(state):
    result = {}
    for lot in state['lots']:
        k = lot['instrument']['key']
        result[k] = result.get(k, ZERO) + lot['quantity']
    return {k: v for k, v in result.items() if v != 0}


def obligation(state):
    # Gross physical delivery amount, deliberately not margin or maximum loss.
    return sum((abs(l['quantity']) * dec(l['instrument']['strike']) * dec(l['instrument']['multiplier'])
                for l in state['lots'] if l['instrument']['kind'] == 'option' and l['quantity'] < 0
                and l['instrument']['settlement'] == 'physical' and not l['instrument']['adjusted']), ZERO)


def initial(account):
    if account.get('currency') != 'USD' or account.get('type') not in ('cash', 'margin') or not account.get('name', '').strip():
        raise Invalid('须填写账户名称、USD 和 cash/margin 类型')
    start = stamp(account.get('at'))
    cash = dec(account.get('cash'), '净现金')
    if cash < 0 and (account['type'] == 'cash' or not account.get('confirm_financing')):
        raise Invalid('负现金须为保证金账户并确认融资事实')
    state = {'cash': cash, 'lots': [], 'realized': [], 'flows': [], 'expenses': [], 'issues': [],
             'receivable': dec(account.get('receivable', '0'), '应收', nonnegative=True),
             'payable': dec(account.get('payable', '0'), '应付', nonnegative=True)}
    if (state['receivable'] or state['payable']) and not account.get('balance_note'):
        raise Invalid('应收应付须填写依据')
    total = cash + state['receivable'] - state['payable']
    seen = set()
    for idx, entry in enumerate(account.get('positions', [])):
        ins = instrument(entry['instrument'])
        q = quantity(entry['quantity'], ins, signed=True)
        if ins['key'] in seen:
            raise Invalid('期初相同证券请合并为一行')
        seen.add(ins['key'])
        if q < 0 and ins['kind'] == 'equity' and account['type'] != 'margin':
            raise Invalid('股票空头须使用保证金账户')
        mark = dec(entry.get('mark'), '期初单位估值', nonnegative=True)
        if entry.get('mark_at') and stamp(entry['mark_at']) > start:
            raise Invalid('股价时间不得晚于开始记录时间')
        if not entry.get('source'):
            raise Invalid('期初估值须填写来源')
        actual = entry.get('original_cost')
        actual = dec(actual, '原始单位成本', nonnegative=True) * abs(q) * dec(ins['multiplier']) if actual not in (None, '') else None
        opened = entry.get('original_opened_at') or None
        if opened and stamp(opened) > start:
            raise Invalid('原建仓日期不得晚于期初')
        total += q * mark * dec(ins['multiplier'])
        state['lots'].append({'id': f'opening:{idx}', 'instrument': ins, 'quantity': q,
                              'basis': abs(q)*mark*dec(ins['multiplier']), 'actual_basis': actual,
                              'opened_at': opened, 'observed_at': account['at'], 'links': []})
    nav = dec(account.get('broker_nav'), '券商净资产', positive=True)
    if abs(total-nav) > max(Decimal('1'), abs(nav)*Decimal('.0001')):
        raise Invalid(f'期初对账差额 {total-nav}；检查每股/每张权利金及遗漏持仓、应收应付')
    return state


def _close(state, ins, count, sign, proceeds, fee, at, link, *, transfer=False):
    available = sum((abs(l['quantity']) for l in state['lots'] if l['instrument']['key'] == ins['key'] and l['quantity']*sign > 0), ZERO)
    if available < count:
        raise Invalid(f"{ins['key']}: 可平数量 {available}，本次请求 {count}")
    left, basis, actual, known = count, ZERO, ZERO, True
    pieces = []
    for lot in state['lots']:
        if left == 0 or lot['instrument']['key'] != ins['key'] or lot['quantity']*sign <= 0:
            continue
        take = min(abs(lot['quantity']), left)
        fraction = take / abs(lot['quantity'])
        part = lot['basis'] * fraction
        basis += part
        if lot['actual_basis'] is None:
            known = False
        else:
            a = lot['actual_basis'] * fraction
            actual += a
            lot['actual_basis'] -= a
        pieces.append({'lot_id': lot['id'], 'quantity': str(take), 'opened_at': lot['opened_at']})
        lot['basis'] -= part
        lot['quantity'] -= take*sign
        left -= take
    state['lots'] = [l for l in state['lots'] if l['quantity']]
    if not transfer:
        state['realized'].append({'event': link, 'instrument': ins['key'], 'at': at, 'quantity': count,
                                  'observation_pnl': sign*(proceeds-basis)-fee,
                                  'actual_pnl': sign*(proceeds-actual)-fee if known else None, 'pieces': pieces})
    return basis, actual if known else None


def _open(state, ins, q, basis, actual, at, link, suffix=''):
    if any(l['instrument']['key'] == ins['key'] and l['quantity']*q < 0 for l in state['lots']):
        raise Invalid('不能通过开仓静默改变现有方向；请先显式平仓')
    state['lots'].append({'id': link+suffix, 'instrument': ins, 'quantity': q, 'basis': basis,
                          'actual_basis': actual, 'opened_at': at, 'observed_at': at, 'links': [link]})


def apply(state, account, event, link='preview'):
    state = copy.deepcopy(state)
    at = event.get('at')
    moment = stamp(at).astimezone(NY)
    if moment < stamp(account['at']):
        raise Invalid('事件不得早于账户起点')
    # Inputs may use the user's local zone or UTC; trading-date rules remain New York based.
    before = positions(state)
    before_cash, before_obligation = state['cash'], obligation(state)
    legs = event.get('legs', [])
    if not legs:
        raise Invalid('至少填写一个事件或交易腿')
    if len(legs) > 50:
        raise Invalid('单次组合最多 50 腿')
    # All ordinary close legs share the inventory existing before the batch.
    closing = {}
    for leg in legs:
        if leg.get('action') in ('SELL', 'BUY_TO_COVER', 'STC', 'BTC', 'EXERCISE', 'ASSIGN', 'EXPIRE', 'SETTLE'):
            ins = instrument(leg['instrument'])
            q = quantity(leg['quantity'], ins)
            closing[ins['key']] = closing.get(ins['key'], ZERO)+q
    for key, q in closing.items():
        if q > abs(before.get(key, ZERO)):
            raise Invalid(f'{key}: 组合累计平仓 {q} 超过原持仓 {abs(before.get(key, ZERO))}')
    for idx, leg in enumerate(legs):
        kind = leg.get('kind', 'trade')
        fee = dec(leg.get('fee'), '总费用', nonnegative=True)
        action = leg.get('action')
        if kind == 'cash':
            amount = dec(leg.get('amount'), '金额', nonnegative=True)
            signs = {'DEPOSIT': 1, 'WITHDRAW': -1, 'DIVIDEND': 1, 'INTEREST': 1, 'FINANCING_INTEREST': -1, 'FEE': -1, 'RECEIVABLE_SETTLED': 1, 'PAYABLE_SETTLED': -1}
            if action not in signs or not leg.get('note'):
                raise Invalid('现金类型无效或缺少说明')
            tax = dec(leg.get('tax', '0'), '分红扣税', nonnegative=True)
            if (action != 'DIVIDEND' and tax) or tax > amount:
                raise Invalid('扣税须对应分红且不大于税前金额')
            if action in ('RECEIVABLE_SETTLED','PAYABLE_SETTLED'):
                balance = 'receivable' if action=='RECEIVABLE_SETTLED' else 'payable'
                if amount > state[balance]:
                    raise Invalid('结清金额超过已记账的应收或应付余额')
                state[balance] -= amount
            change = signs[action]*amount-tax-fee
            state['cash'] += change
            if action in ('DEPOSIT', 'WITHDRAW'):
                state['flows'].append({'at': at, 'amount': signs[action]*amount, 'event': link})
            state['expenses'].append({'at': at, 'action': action, 'fee': fee, 'tax': tax,
                                      'financing_interest': amount if action == 'FINANCING_INTEREST' else ZERO})
            continue
        ins = instrument(leg['instrument'])
        if kind == 'corporate_action':
            if not leg.get('evidence'):
                raise Invalid('公司行动须提供可核对依据')
            if action == 'PENDING':
                state['issues'].append({'event': link, 'instrument': ins['key'], 'evidence': leg['evidence']})
            elif action == 'SPLIT' and ins['kind'] == 'equity':
                ratio = dec(leg.get('ratio'), '拆股比例', positive=True)
                for lot in state['lots']:
                    if lot['instrument']['key'] == ins['key']:
                        lot['quantity'] *= ratio
                state['issues'] = [x for x in state['issues'] if x['instrument'] != ins['key']]
            elif action == 'EXCHANGE':
                target = instrument(leg['target'])
                ratio = dec(leg.get('ratio'), '换股比例', positive=True)
                for lot in state['lots']:
                    if lot['instrument']['key'] == ins['key']:
                        new_q = lot['quantity']*ratio
                        quantity(str(new_q), target, signed=True)
                        lot['instrument'], lot['quantity'] = target, new_q
                state['issues'] = [x for x in state['issues'] if x['instrument'] != ins['key']]
            else:
                raise Invalid('公司行动支持待核、已确认拆股或换股；现金补价须另录现金事件')
            state['cash'] -= fee
            continue
        q = quantity(leg.get('quantity'), ins)
        mult = dec(ins['multiplier'])
        if kind == 'trade':
            price = dec(leg.get('price'), '成交价/每股权利金', nonnegative=True)
            if ins['kind'] == 'option' and date.fromisoformat(ins['expiry']) < moment.astimezone(NY).date():
                raise Invalid('成交日期晚于期权到期日')
            choices = ('BUY', 'SELL', 'SELL_SHORT', 'BUY_TO_COVER') if ins['kind'] == 'equity' else ('BTO', 'STO', 'STC', 'BTC')
            if action not in choices:
                raise Invalid('方向与证券类型不一致')
            if action == 'SELL_SHORT' and account['type'] != 'margin':
                raise Invalid('股票卖空须为保证金账户')
            buy = action in ('BUY', 'BUY_TO_COVER', 'BTO', 'BTC')
            value = price*q*mult
            state['cash'] += (-value if buy else value)-fee
            if action in ('BUY', 'BTO', 'SELL_SHORT', 'STO'):
                basis = value+fee if buy else value-fee
                _open(state, ins, q if buy else -q, basis, basis, at, link, f':{idx}')
            else:
                _close(state, ins, q, -1 if buy else 1, value, fee, at, link)
        elif kind == 'lifecycle':
            if ins['kind'] != 'option' or not leg.get('evidence'):
                raise Invalid('期权事件须填写合约及确认依据')
            held = positions(state).get(ins['key'], ZERO)
            sign = 1 if held > 0 else -1
            if action == 'EXPIRE':
                if moment.astimezone(NY).date() < date.fromisoformat(ins['expiry']):
                    raise Invalid('未到期不得确认失效')
                _close(state, ins, q, sign, ZERO, fee, at, link)
                state['cash'] -= fee
            elif action == 'SETTLE':
                if ins['settlement'] != 'cash':
                    raise Invalid('该合约不是现金结算合约')
                amount = dec(leg.get('settlement_amount'), '有符号结算总额')
                if amount*sign < 0:
                    raise Invalid('结算方向与持仓方向不一致')
                _close(state, ins, q, sign, abs(amount), fee, at, link)
                state['cash'] += amount-fee
            elif action in ('EXERCISE', 'ASSIGN'):
                if ins['settlement'] != 'physical' or ins['adjusted']:
                    raise Invalid('调整合约或非实物合约不能自动交割，请先核对标准交付内容')
                if (action == 'EXERCISE') != (sign == 1):
                    raise Invalid('行权对应多头，指派对应空头')
                premium, actual = _close(state, ins, q, sign, ZERO, ZERO, at, link, transfer=True)
                shares = q*mult
                strike_value = dec(ins['strike'])*shares
                buy_stock = (ins['right'] == 'C') == (sign == 1)
                # Call exercise + premium; Put assignment - premium. Sale inverse.
                effective = strike_value + sign*premium + fee if buy_stock else strike_value-sign*premium-fee
                actual_eff = (strike_value+sign*actual+fee if buy_stock else strike_value-sign*actual-fee) if actual is not None else None
                state['cash'] += (-strike_value if buy_stock else strike_value)-fee
                stock = instrument({'symbol': ins['symbol']})
                existing = positions(state).get(stock['key'], ZERO)
                close_q = min(shares, abs(existing)) if existing*(1 if buy_stock else -1) < 0 else ZERO
                if close_q:
                    # Effective premium includes lifecycle fee; no second fee.
                    _close(state, stock, close_q, -1 if buy_stock else 1, effective*close_q/shares, ZERO, at, link)
                    if actual_eff is None:
                        state['realized'][-1]['actual_pnl'] = None
                    else:
                        # Correct actual result for transferred premium from an opening position.
                        r = state['realized'][-1]
                        if r['actual_pnl'] is not None:
                            r['actual_pnl'] += (-1 if buy_stock else 1)*(actual_eff-effective)*close_q/shares
                remaining = shares-close_q
                if remaining:
                    if not buy_stock and account['type'] != 'margin':
                        raise Invalid('交割会产生股票空头，现金账户须先核对真实持仓')
                    _open(state, stock, remaining*(1 if buy_stock else -1), effective*remaining/shares,
                          actual_eff*remaining/shares if actual_eff is not None else None, at, link, f':delivery:{idx}')
            else:
                raise Invalid('未知期权生命周期事件')
        else:
            raise Invalid('未知事件类型')
        state['expenses'].append({'at': at, 'action': action, 'fee': fee, 'tax': ZERO, 'financing_interest': ZERO})
    if state['cash'] < 0:
        if account['type'] == 'cash':
            raise Invalid('现金账户本次记账后现金为负；请核对入金或更正账户类型')
        if not event.get('confirm_financing'):
            raise Invalid('负现金须确认实际融资事实')
    return state, {'before': before, 'after': positions(state), 'cash_before': before_cash,
                   'cash_change': state['cash']-before_cash, 'cash_after': state['cash'],
                   'delivery_change': obligation(state)-before_obligation,
                   'delivery_total': obligation(state), 'warnings': ['交割总额为空头期权按行权价计算的名义金额；多头行权属于权利，不计为空头义务。该金额不是最大亏损或券商保证金'],
                   'issues': state['issues']}
