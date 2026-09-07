"""Derive personal close snapshots from the shared nominal-price cache."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from .domain import digest, encoded, stamp, NY
from .store import now
from .valuation import value_state


def close_marks(root, symbols, day):
    from .comparison import cached_prices
    root, day = Path(root), pd.Timestamp(day).normalize()
    at = xcals.get_calendar('XNYS').session_close(day).isoformat()
    state_path = root/'data/market_refresh/state.json'
    refresh = json.loads(state_path.read_text()) if state_path.exists() else {}
    marks = {}
    for symbol in sorted(set(symbols)):
        if refresh.get('tickers', {}).get(symbol, {}).get('needs_full_refresh'):
            continue
        try:
            frame = cached_prices(root, symbol)
            if day not in frame.index or 'as_traded_close' not in frame:
                continue
            price = Decimal(str(frame.loc[day, 'as_traded_close']))
            if price.is_finite() and price > 0:
                marks[symbol] = {'price': str(price), 'source': '系统收盘价', 'at': at, 'basis': 'nominal'}
        except (OSError, ValueError, KeyError):
            continue
    return {'at': at, 'marks': marks, 'date': str(day.date())}


def automatic_close(store, root, day=None):
    from shm.service.workflow import latest_completed_session
    day = pd.Timestamp(day if day is not None else latest_completed_session()).normalize()
    at = xcals.get_calendar('XNYS').session_close(day).isoformat()
    # The transaction also prevents concurrent page requests from duplicating a snapshot.
    with store.connection(True) as db:
        current = store._account(db)
        if not current or stamp(at) <= stamp(current['account']['at']):
            return None
        existing = list(db.execute('SELECT * FROM valuations WHERE valid=1 ORDER BY id DESC'))
        for row in existing:
            result = json.loads(row['result'])
            if result.get('origin') != 'automatic_close' and stamp(row['at']).astimezone(NY).date() == day.date() and stamp(row['at']) >= stamp(at):
                return result  # A user's same-close source choice takes precedence.
        state = store.replay(db, current['account'], until=at)
        symbols = {l['instrument']['symbol'] for l in state['lots'] if l['instrument']['kind'] == 'equity'}
        quote = close_marks(root, symbols, day)
        payload = {'at': at, 'marks': quote['marks'], 'source': 'unselected', 'flows_complete': True,
                   'coverage': '按已录入的交易、现金流水和当日收盘价自动计算',
                   'reason': '系统按持仓账本计算；券商对账可另行补充'}
        result = value_state(state, payload)
        if result['ledger_nav'] is not None:
            payload['source'] = result['source'] = 'ledger'
            result['nav'] = result['ledger_nav']
        result.update(origin='automatic_close', snapshot_hash=digest({'payload': payload, 'result': result}), version=current['version'])
        for row in existing:
            previous = json.loads(row['result'])
            if previous.get('origin') == 'automatic_close' and stamp(row['at']) == stamp(at):
                if previous.get('snapshot_hash') == result['snapshot_hash']:
                    return previous
                db.execute('UPDATE valuations SET valid=0 WHERE id=?', (row['id'],))
        result['id'] = db.execute('INSERT INTO valuations(at,payload,result,version,created_at) VALUES(?,?,?,?,?)',
                                 (at, encoded(payload), encoded(result), current['version'], now())).lastrowid
        return result
