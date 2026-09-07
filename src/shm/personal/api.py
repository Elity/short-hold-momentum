"""Authenticated adapter. Existing public dashboard never reads the private database."""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from .domain import Invalid, Conflict, encoded, instrument, stamp
from .store import PortfolioStore
from .valuation import valuation, valuations
from .comparison import compare, cached_prices
from .ai import AIService
from .market import automatic_close, close_marks

PREFIXES = ('/api/personal/', '/api/ai/')


def private_path(path):
    return path.startswith(PREFIXES) or path == '/api/comparison'


class PrivateAPI:
    def __init__(self, store, root, *, public_url='', gateway_token='', enabled=False, verified=False, key_path=None, ai=None):
        self.store, self.root = store, Path(root)
        self.public_url = public_url.rstrip('/')
        self.gateway_token = gateway_token
        u = urlparse(self.public_url)
        self.enabled = bool(enabled and verified and u.scheme=='https' and u.netloc and not u.username and not u.password and not u.query and not u.fragment and not u.path and len(gateway_token)>=32)
        self.ai = ai or AIService(store, root, key_path=key_path)

    @classmethod
    def from_environment(cls, db_path, root):
        # Do not create/read the private DB at all when not configured.
        if os.environ.get('SHM_PRIVATE_ENABLED') != '1':
            return None
        token_path = os.environ.get('SHM_GATEWAY_TOKEN_FILE')
        try:
            token = Path(token_path).read_text().strip() if token_path and Path(token_path).is_file() else ''
        except (OSError, UnicodeError):
            token = ''
        store = PortfolioStore(os.environ.get('SHM_PORTFOLIO_DB_PATH',str(Path(db_path).with_name('portfolio.sqlite3'))))
        api = cls(store,root,public_url=os.environ.get('SHM_PUBLIC_URL',''),gateway_token=token,enabled=True,
                  verified=os.environ.get('SHM_GATEWAY_VERIFIED')=='1',key_path=os.environ.get('SHM_AI_MASTER_KEY_FILE'))
        if api.enabled:
            store.initialize()
        return api

    def authorized(self, headers, method):
        if not self.enabled:
            return False
        token = headers.get('X-SHM-Gateway-Token','')
        if not hmac.compare_digest(token.encode(),self.gateway_token.encode()):
            return False
        if method != 'GET' and headers.get('Origin') != self.public_url:
            return False
        return True

    def dispatch(self, method, path, query, payload=None):
        p = payload or {}
        q = lambda name,default: query.get(name,[default])[-1]
        if path == '/api/personal/account':
            return self.store.account() if method=='GET' else self.store.save_account(p)
        if path == '/api/personal/events/preview' and method=='POST':
            return self.store.preview(p)
        if path == '/api/personal/events':
            return self.store.events() if method=='GET' else self.store.commit(p)
        if path == '/api/personal/valuations':
            if method == 'GET':
                automatic_close(self.store, self.root)
                return valuations(self.store)
            return valuation(self.store,p,save=bool(p.get('save')))
        if path == '/api/personal/quotes' and method=='GET':
            return self.quotes(q('symbol', None), q('at', None))
        if path == '/api/personal/quotes/refresh' and method=='POST':
            return self.refresh_quotes(p.get('symbol'))
        if path == '/api/comparison' and method=='GET':
            automatic_close(self.store, self.root)
            return compare(self.store,self.root,strategy_id=q('strategy_id','S500-C3'),cost_bps=int(q('cost_bps','10')),start=q('start',None),end=q('end',None))
        if path == '/api/ai/settings':
            return self.ai.settings() if method=='GET' else self.ai.save_settings(p)
        if path == '/api/ai/test' and method=='POST':
            return self.ai.test()
        if path == '/api/ai/reports':
            return self.ai.reports() if method=='GET' else self.ai.create(p)
        if path == '/api/ai/suggestions':
            return self.ai.suggestions() if method=='GET' else self.ai.update_suggestion(p)
        raise Invalid('未知私人接口或方法')

    def quotes(self, symbol=None, at=None):
        current = self.store.account()
        if symbol:
            symbols = {instrument({'kind': 'equity', 'symbol': symbol})['symbol']}
        elif current['account']:
            symbols = {l['instrument']['symbol'] for l in current['state']['lots'] if l['instrument']['kind']=='equity'}
        else:
            return {'marks':{}}
        from shm.service.workflow import latest_completed_session
        day = latest_completed_session(stamp(at) if at else None)
        return {**close_marks(self.root, symbols, day), 'note': '正股 / ETF 使用最近完成交易日收盘价；期权需补充券商报价。'}

    def refresh_after_strategy(self):
        if not self.enabled:
            return
        return self.refresh_quotes()

    def refresh_quotes(self, symbol=None):
        account = self.store.account()
        if symbol:
            symbols = {instrument({'kind':'equity', 'symbol':symbol})['symbol']}
        elif account['account']:
            symbols = {l['instrument']['symbol'] for l in account['state']['lots'] if l['instrument']['kind']=='equity'}
        else:
            return {'marks': {}, 'note': '尚未建立账户'}
        from shm.data.market_refresh import refresh_market_cache
        from shm.service.workflow import latest_completed_session
        import pandas as pd
        if len(symbols)>100:
            raise Invalid('个人账户持有标的超过首版单次刷新上限 100')
        day = latest_completed_session()
        history_start = day-pd.Timedelta(days=550)
        for ticker in symbols | {'SPY'}:
            try:
                frame = cached_prices(self.root, ticker)
            except (OSError, ValueError):
                continue  # The shared downloader repairs corrupt caches.
            if not frame.empty:
                history_start = min(history_start, frame.index.min())
        # Uses the same provider lock, ticker cache and 600-call counter, after the strategy finishes.
        summary = refresh_market_cache(self.root, symbols, as_of=day, held_tickers=symbols, daily_budget=600,
                                       history_start=str(history_start.date()), require_point_in_time_eligibility=True,
                                       summary_namespace='personal')
        automatic_close(self.store, self.root, day)
        return {**self.quotes(symbol), 'requested': summary['requested'], 'missing': summary['missing'], 'next_retry': summary['next_retry']}
