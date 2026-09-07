import json
from decimal import Decimal as D

import pandas as pd
import pytest

from shm.personal.api import PrivateAPI
from shm.personal.market import automatic_close
from shm.personal.store import PortfolioStore
from shm.personal.valuation import valuations, valuation, personal_curve
from test_personal import account, STOCK, OPT, event, leg
from shm.personal.domain import apply, initial, positions


def opened(tmp_path, *, options=False):
    store=PortfolioStore(tmp_path/'portfolio.sqlite3');store.initialize()
    positions=[{'instrument':STOCK,'quantity':'100','mark':'100','mark_at':'2026-07-31T20:00:00Z','source':'broker','original_cost':'90'}]
    if options:
        positions.append({'instrument':OPT,'quantity':'1','mark':'2','source':'broker'})
    store.save_account({'version':0,'account':account(cash='90000',broker_nav='100200' if options else '100000',positions=positions)})
    return store


def prices(root, days):
    path=root/'data/raw/prices/MSFT.parquet';path.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame([{'date':day,'close':price/2,'as_traded_close':price} for day,price in days]).to_parquet(path,index=False)


def commit(store, at, item):
    request={'version':store.account()['version'],'event':event(item,at=at)}
    request.update(preview_hash=store.preview(request)['preview_hash'],idempotency_key='event-'+at)
    return store.commit(request)


def test_opening_account_is_first_snapshot_without_duplicate_database_entry(tmp_path):
    store=opened(tmp_path)
    v=valuations(store)[0]
    assert v['origin']=='opening' and v['nav']==D('100000')
    assert v['reconciliation']=='matched' and v['holdings'][0]['value']==D('10000')
    assert v['holdings'][0]['price_at']=='2026-07-31T20:00:00Z'
    assert automatic_close(store,tmp_path,'2026-08-03') is None
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM valuations').fetchone()[0]==0


@pytest.mark.parametrize('at,zone',[('2026-08-04T22:00:00+08:00','Asia/Shanghai'),('2026-08-04T14:00:00Z','UTC')])
def test_local_and_utc_trade_instants_follow_the_same_market_time(at,zone):
    a=account()
    trade=leg('BUY',instrument=STOCK,quantity='10',price='110',fee='0')
    state,_=apply(initial(a),a,event(trade,at=at,timezone=zone))
    expected,_=apply(initial(a),a,event(trade))
    assert state['cash']==expected['cash'] and positions(state)==positions(expected)


def test_automatic_nominal_prices_cashflows_restart_and_close_boundary(tmp_path):
    store=opened(tmp_path)
    prices(tmp_path,[('2026-08-04',110),('2026-08-05',110)])
    v=automatic_close(store,tmp_path,'2026-08-04')
    assert v['nav']==D('101000') and v['reconciliation']=='unavailable'
    assert v['holdings'][0]['value']==D('11000')
    automatic_close(PortfolioStore(store.path),tmp_path,'2026-08-04')
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM valuations').fetchone()[0]==1
    commit(store,'2026-08-05T08:00:00-04:00',{'kind':'cash','action':'DEPOSIT','amount':'5000','fee':'0','note':'deposit'})
    assert D(automatic_close(store,tmp_path,'2026-08-05')['nav'])==D('106000')
    curve,_=personal_curve(store)
    assert curve[-1]['index']==D('101') and curve[-1]['return']==0
    commit(store,'2026-08-05T17:00:00-04:00',leg('SELL',instrument=STOCK,quantity='10',price='112',fee='1'))
    assert D(automatic_close(store,tmp_path,'2026-08-05')['nav'])==D('106000')
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM valuations').fetchone()[0]==2


@pytest.mark.parametrize('problem',['stale','missing_option','pending_action','repair_pending'])
def test_incomplete_data_does_not_create_known_account_value(tmp_path,problem):
    store=opened(tmp_path,options=problem=='missing_option')
    prices(tmp_path,[('2026-08-03' if problem=='stale' else '2026-08-04',110)])
    if problem=='pending_action':
        commit(store,'2026-08-04T10:00:00-04:00',{'kind':'corporate_action','action':'PENDING','instrument':STOCK,'fee':'0','evidence':'split awaiting confirmation'})
    if problem=='repair_pending':
        path=tmp_path/'data/market_refresh/state.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'tickers':{'MSFT':{'needs_full_refresh':True}}}))
    v=automatic_close(store,tmp_path,'2026-08-04')
    assert v['nav'] is None and v['attribution']=='partial'
    assert personal_curve(store)[0][-1]['index'] is None


def test_manual_same_instant_source_is_retained_and_repair_is_versioned(tmp_path):
    store=opened(tmp_path)
    missing=automatic_close(store,tmp_path,'2026-08-04')
    prices(tmp_path,[('2026-08-04',110)])
    complete=automatic_close(store,tmp_path,'2026-08-04')
    assert missing['nav'] is None and complete['nav']==D('101000')
    manual={'version':1,'at':'2026-08-05T04:00:00+08:00','marks':{'MSFT':{'price':'111','source':'broker','basis':'nominal','at':'2026-08-04T20:00:00Z'}},
            'broker_nav':'101100','source':'broker','flows_complete':True,'coverage':'broker close'}
    preview=valuation(store,manual)
    valuation(store,{**manual,'preview_hash':preview['preview_hash']},save=True)
    assert automatic_close(store,tmp_path,'2026-08-04')['source']=='broker'
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM valuations').fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM valuations WHERE valid=0').fetchone()[0]==1


def test_personal_refresh_only_requests_held_symbols_and_shared_budget(tmp_path,monkeypatch):
    from shm.service import workflow
    from shm.data import market_refresh
    store=opened(tmp_path);calls=[]
    prices(tmp_path,[('2026-08-03',100)])
    (tmp_path/'data/raw/prices/MSFT.parquet').write_bytes(b'corrupt cache')
    monkeypatch.setattr(workflow,'latest_completed_session',lambda now=None:pd.Timestamp('2026-08-04'))
    def refresh(root,symbols,**kwargs):
        calls.append((symbols,kwargs));prices(root,[('2026-08-04',110)])
        return {'requested':1,'missing':[],'next_retry':None}
    monkeypatch.setattr(market_refresh,'refresh_market_cache',refresh)
    api=PrivateAPI(store,tmp_path,public_url='https://shm.test',gateway_token='a'*32,enabled=True,verified=True)
    assert api.refresh_after_strategy()['marks']['MSFT']['price']=='110'
    assert calls[0][0]=={'MSFT'} and calls[0][1]['daily_budget']==600
    assert calls[0][1]['held_tickers']=={'MSFT'}
    assert calls[0][1]['require_point_in_time_eligibility']
    assert any(v.get('origin')=='automatic_close' and v['nav']=='101000' for v in valuations(store))
