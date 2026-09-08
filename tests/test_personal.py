from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import json

import pytest
from cryptography.fernet import Fernet

from shm.personal.domain import Invalid, Conflict, initial, instrument, apply, positions
from shm.personal.store import PortfolioStore
from shm.personal.valuation import value_state, interval_return, valuation
from shm.personal.ai import AIService, ReportError, validate_report
from shm.personal.api import PrivateAPI

AT='2026-08-03T16:00:00-04:00'
TRADE='2026-08-04T10:00:00-04:00'
OPT={'kind':'option','symbol':'MSFT','expiry':'2026-08-21','right':'P','strike':'190','multiplier':'100','settlement':'physical'}
STOCK={'kind':'equity','symbol':'MSFT'}


def account(**kwargs):
    return {'name':'私人测试','currency':'USD','type':'cash','at':AT,'cash':'100000','broker_nav':'100000','positions':[],**kwargs}


def leg(action='STO', **kwargs):
    return {'kind':'trade','instrument':OPT,'action':action,'quantity':'1','price':'2.10','fee':'0.65',**kwargs}


def event(*legs, **kwargs):
    return {'at':TRADE,'timezone':'America/New_York','legs':list(legs),**kwargs}


def test_put_premium_liability_and_assignment_fifo():
    a=account()
    state,summary=apply(initial(a),a,event(leg()))
    assert summary['cash_change']==D('209.35')
    mark={instrument(OPT)['key']:{'price':'2.10','source':'broker','at':TRADE}}
    v=value_state(state,{'at':TRADE,'marks':mark})
    assert v['ledger_nav']==D('99999.35')
    state,summary=apply(state,a,event(leg(kind='lifecycle',action='ASSIGN',fee='1',evidence='券商成交单')))
    assert positions(state)=={'MSFT':D('100')}
    assert state['cash']==D('81208.35')
    assert state['lots'][0]['basis']==D('18791.65')
    assert state['realized']==[]
    state,_=apply(state,a,event(leg('SELL',instrument=STOCK,quantity='50',price='200',fee='1')))
    assert state['realized'][0]['actual_pnl']==D('603.175')


def test_combo_aggregate_closing_and_credit():
    a=account()
    state,_=apply(initial(a),a,event(leg()))
    with pytest.raises(Invalid,match='组合累计平仓'):
        apply(state,a,event(leg('BTC'),leg('BTC')))
    state,summary=apply(initial(a),a,event(leg(),leg('BTO',instrument={**OPT,'strike':'185'},price='1.10')))
    assert summary['cash_change']==D('98.70')
    assert summary['delivery_total']==19000  # long Put is a right, not another short delivery obligation
    state2,summary=apply(state,a,event(leg()))
    assert positions(state2)[instrument(OPT)['key']]==-2
    assert summary['delivery_change']==19000


@pytest.mark.parametrize('right,action,premium_expected', [('C','EXERCISE','19211.65'),('P','ASSIGN','18791.65')])
def test_delivery_buy_basis(right,action,premium_expected):
    a=account()
    ins={**OPT,'right':right}
    state,_=apply(initial(a),a,event(leg('BTO' if action=='EXERCISE' else 'STO',instrument=ins)))
    state,_=apply(state,a,event(leg(action,kind='lifecycle',instrument=ins,fee='1',evidence='broker')))
    assert state['lots'][0]['basis']==D(premium_expected)
    assert state['realized']==[]


def test_expiry_cash_settlement_and_stock_short_are_explicit():
    a=account()
    state,_=apply(initial(a),a,event(leg()))
    with pytest.raises(Invalid,match='未到期'):
        apply(state,a,event(leg('EXPIRE',kind='lifecycle',evidence='broker')))
    state,_=apply(state,a,event(leg('EXPIRE',kind='lifecycle',evidence='broker',fee='0'),at='2026-08-21T17:00:00-04:00'))
    assert state['realized'][0]['actual_pnl']==D('209.35')
    a=account(type='margin')
    state,_=apply(initial(a),a,event(leg('SELL_SHORT',instrument=STOCK,price='100',quantity='10')))
    with pytest.raises(Invalid):
        apply(state,a,event(leg('SELL',instrument=STOCK,price='100',quantity='1')))
    cash_opt={**OPT,'settlement':'cash'}
    state,_=apply(initial(a),a,event(leg('STO',instrument=cash_opt)))
    state,_=apply(state,a,event(leg('SETTLE',kind='lifecycle',instrument=cash_opt,settlement_amount='-100',fee='1',evidence='broker')))
    assert not state['lots']
    assert state['cash']==D('100108.35')


def test_marks_broker_nav_missing_and_difference():
    a=account()
    state,_=apply(initial(a),a,event(leg()))
    v=value_state(state,{'at':TRADE,'broker_nav':'112840','source':'broker','flows_complete':True,'reason':'采用券商','marks':{}})
    assert v['nav']==D('112840') and v['ledger_nav'] is None and v['difference'] is None
    assert v['attribution']=='partial' and v['reconciliation']=='unavailable'
    v=value_state(initial(a),{'at':TRADE,'broker_nav':'120000','source':'ledger','flows_complete':True,'reason':'待核'})
    assert v['difference']==-20000 and v['reconciliation']=='difference'


def test_cash_flows_and_financing():
    r,method=interval_return(AT,'2026-08-04T16:00:00-04:00','100000','110000',[{'at':'2026-08-04T16:00:00-04:00','amount':'10000'}])
    assert r==0
    r,method=interval_return(AT,'2026-08-04T16:00:00-04:00','100000','111100',[{'at':'2026-08-04T08:00:00-04:00','amount':'10000'}])
    assert r==D('.01')
    a=account(type='margin')
    state,_=apply(initial(a),a,event({'kind':'cash','action':'FINANCING_INTEREST','amount':'100','fee':'0','note':'利息'}))
    assert state['cash']==99900
    with pytest.raises(Invalid,match='负'):
        apply(initial(account()),account(),event(leg('BUY',instrument=STOCK,quantity='1001',price='100')))


def test_account_unknown_cost_split_and_nonfinite():
    a=account(cash='90000',positions=[{'instrument':STOCK,'quantity':'100','mark':'100','source':'broker'}])
    state=initial(a)
    assert state['lots'][0]['actual_basis'] is None
    state,_=apply(state,a,event({'kind':'corporate_action','action':'SPLIT','instrument':STOCK,'ratio':'2','fee':'0','evidence':'公告'}))
    assert positions(state)['MSFT']==200 and state['lots'][0]['basis']==10000
    for bad in ('NaN','Infinity','-1'):
        with pytest.raises(Invalid):
            apply(initial(account()),account(),event(leg(price=bad)))
    with pytest.raises(Invalid):
        instrument({**OPT,'occ':'MSFT260821C00190000'})


def test_atomic_preview_restart_idempotency_and_revision(tmp_path):
    store=PortfolioStore(tmp_path/'portfolio.sqlite3');store.initialize()
    store.save_account({'account':account(),'version':0})
    req={'version':1,'event':event(leg())}
    preview=store.preview(req)
    assert store.events()==[]
    req.update(preview_hash=preview['preview_hash'],idempotency_key='first-submit')
    result=store.commit(req)
    assert result['version']==2
    again=PortfolioStore(store.path)
    assert again.commit(req)==json.loads(json.dumps(result,default=str))
    with pytest.raises(Conflict):
        again.commit({**req,'confirm_duplicate':True})
    with pytest.raises(Conflict):
        again.preview({'version':1,'event':event(leg())})
    revision={'version':2,'event':event(leg(price='3')),'replaces':1,'reason':'价格录错'}
    preview=again.preview(revision)
    again.commit({**revision,'preview_hash':preview['preview_hash'],'idempotency_key':'revision-key'})
    rows=again.events()
    assert len(rows)==2 and rows[1]['reversed_by']==2
    assert again.account()['state']['cash']==D('100299.35')


def test_valuation_revision_invalidates_history(tmp_path):
    s=PortfolioStore(tmp_path/'portfolio.sqlite3');s.initialize();s.save_account({'account':account(),'version':0})
    p={'version':1,'at':TRADE,'broker_nav':'100000','source':'ledger','flows_complete':True,'coverage':'全部已录事件'}
    pre=valuation(s,p)
    result=valuation(s,{**p,'preview_hash':pre['preview_hash']},save=True)
    req={'version':1,'event':event(leg())};pre=s.preview(req)
    s.commit({**req,'preview_hash':pre['preview_hash'],'idempotency_key':'test-key-one'})
    with s.connection() as db:
        assert db.execute('SELECT valid FROM valuations').fetchone()[0]==0


def test_ai_encryption_test_invalidation_and_evidence(tmp_path):
    s=PortfolioStore(tmp_path/'portfolio.sqlite3');s.initialize()
    key=tmp_path/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
    calls=[]
    def caller(settings,secret,messages,param,**kwargs):
        calls.append((secret,messages,param))
        return {'unsupported_parameter':True} if param=='max_completion_tokens' else {'text':'OK','usage':{}}
    ai=AIService(s,tmp_path,key_path=key,caller=caller)
    ai.save_settings({'base_url':'https://example.com/v1','model':'model-a','key':'never-expose-this'})
    assert 'never-expose-this' not in json.dumps(ai.settings())
    assert 'never-expose-this' not in s.path.read_bytes().decode(errors='ignore')
    assert ai.test()['compatibility']=='max_tokens'
    assert all('个人' not in json.dumps(c[1]) for c in calls)
    ai.save_settings({'model':'model-b'})
    assert not ai.settings()['tested']
    with pytest.raises(ReportError):
        validate_report({'title':'结论','summary':'x','limitations':[], 'facts':[{'evidence_id':'fake','value':2}],'suggestions':[]},{'real':{'value':2}})


def test_ai_http_diagnostics_persist_without_provider_body_or_key(tmp_path, monkeypatch, capsys):
    import io
    import urllib.error
    from email.message import Message
    from shm.personal import ai as module
    store=PortfolioStore(tmp_path/'portfolio.sqlite3');store.initialize()
    master=tmp_path/'key';master.write_bytes(Fernet.generate_key());master.chmod(0o600)
    ai=AIService(store,tmp_path,key_path=master)
    secret='secret-must-never-leak'
    ai.save_settings({'base_url':'https://example.com/v1','model':'test-model','key':secret})
    failed=True
    class Opener:
        def open(self, request, timeout):
            assert request.get_header('User-agent') == module.USER_AGENT
            assert request.get_header('Authorization') == 'Bearer '+secret
            assert json.loads(request.data)['max_completion_tokens'] == 128
            if failed:
                headers=Message();headers['Server']='cloudflare';headers['CF-Ray']='abc123-AMS'
                headers['X-Request-ID']=secret
                raise urllib.error.HTTPError(request.full_url,403,'Forbidden',headers,
                    io.BytesIO(('error code: 1010\n'+secret+' provider-private-body').encode()))
            return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]}).encode())
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(ReportError,match='Cloudflare.*1010.*abc123-AMS'):
        ai.test()
    restarted=AIService(PortfolioStore(store.path),tmp_path,key_path=master)
    status=restarted.settings()
    assert status['has_key'] and not status['tested']
    assert status['last_test']['details']['http_status']==403
    logs=capsys.readouterr().err
    assert 'ai_connection_test' in logs and 'abc123-AMS' in logs
    for content in (logs,json.dumps(status),store.path.read_bytes().decode(errors='ignore')):
        assert secret not in content and 'provider-private-body' not in content
    failed=False
    assert restarted.test()['tested']
    assert restarted.settings()['last_test']['status']=='success'
    assert 'success' in capsys.readouterr().err
    restarted.save_settings({'model':'another-model'})
    assert restarted.settings()['last_test'] is None
    assert restarted.settings()['has_key']


def test_gateway_disabled_direct_and_forged_headers(tmp_path):
    s=PortfolioStore(tmp_path/'p.sqlite3')
    p=PrivateAPI(s,tmp_path,public_url='https://shm.example.com',gateway_token='a'*32,enabled=True,verified=True)
    assert not p.authorized({},'GET')
    assert not p.authorized({'X-Authenticated-User':'admin'},'GET')
    assert not p.authorized({'X-SHM-Gateway-Token':'fake'},'GET')
    assert p.authorized({'X-SHM-Gateway-Token':'a'*32},'GET')
    assert not p.authorized({'X-SHM-Gateway-Token':'a'*32,'Origin':'https://evil.example'},'POST')
    assert p.authorized({'X-SHM-Gateway-Token':'a'*32,'Origin':'https://shm.example.com'},'POST')
    p=PrivateAPI(s,tmp_path,public_url='http://host',gateway_token='a'*32,enabled=True,verified=True)
    assert not p.enabled


def test_comparison_same_start_fee_and_missing_day(tmp_path,monkeypatch):
    import pandas as pd
    from shm.personal import comparison
    s=PortfolioStore(tmp_path/'p.sqlite3');s.initialize();s.save_account({'account':account(),'version':0})
    for at,nav in [('2026-08-04T16:00:00-04:00','101000'),('2026-08-06T16:00:00-04:00','102000')]:
        p={'version':1,'at':at,'broker_nav':nav,'source':'broker','flows_complete':True,'coverage':'全量','reason':'券商已确认'}
        pre=valuation(s,p);valuation(s,{**p,'preview_hash':pre['preview_hash']},save=True)
    folder=tmp_path/'data/raw/prices';folder.mkdir(parents=True)
    pd.DataFrame({'date':pd.date_range('2026-08-03','2026-08-06'),'close':[100,101,102,103]}).to_parquet(folder/'SPY.parquet')
    monkeypatch.setattr(comparison,'_build_v03_portfolio',lambda *a,**k:{'chart':[]})
    result=comparison.compare(s,tmp_path)
    assert result['simulation_status']=='waiting'
    assert result['rows'][0]['spy']==D('100')/D('1.001')
    assert result['rows'][2]['personal'] is None
    assert result['rows'][-1]['personal']==102
    assert result['metrics']['personal']['max_drawdown'] is None
    assert not result['complete']


@pytest.mark.parametrize('opening', ['2026-09-05T12:00:00-04:00', '2026-09-07T02:09:33-04:00'])
def test_comparison_waits_for_first_close_after_non_session_opening(tmp_path, monkeypatch, opening):
    import pandas as pd
    from shm.personal import comparison
    s=PortfolioStore(tmp_path/'p.sqlite3');s.initialize()
    s.save_account({'account':account(at=opening),'version':0})
    monkeypatch.setattr(comparison,'latest_completed_session',lambda:pd.Timestamp('2026-09-04'))
    result=comparison.compare(s,tmp_path)
    assert result['rows']==[] and not result['complete']
    assert result['warnings']==['等待首份收盘估值；日线 SPY 无法比较盘中期初']


def test_comparison_accepts_single_completed_close(tmp_path, monkeypatch):
    import pandas as pd
    from shm.personal import comparison
    s=PortfolioStore(tmp_path/'p.sqlite3');s.initialize()
    s.save_account({'account':account(at='2026-09-04T16:00:00-04:00'),'version':0})
    monkeypatch.setattr(comparison,'latest_completed_session',lambda:pd.Timestamp('2026-09-04'))
    monkeypatch.setattr(comparison,'_build_v03_portfolio',lambda *a,**k:{'chart':[]})
    monkeypatch.setattr(comparison,'cached_prices',lambda *a:pd.DataFrame({'close':[100]},index=pd.to_datetime(['2026-09-04'])))
    result=comparison.compare(s,tmp_path)
    assert len(result['rows'])==1 and result['complete']
    assert result['rows'][0]['personal']==100
    assert result['rows'][0]['spy']==D('100')/D('1.001')


def test_after_close_cash_flow_before_snapshot_and_intraday_dietz():
    r,method=interval_return(AT,'2026-08-04T17:00:00-04:00','100000','110000',[{'at':'2026-08-04T16:30:00-04:00','amount':'10000'}])
    assert r==0 and method=='TWR_cash_flow_timing'
    r,method=interval_return(AT,'2026-08-04T16:00:00-04:00','100000','111000',[{'at':'2026-08-04T12:00:00-04:00','amount':'10000'}])
    assert 'Dietz' in method and r>0


def test_report_failure_budget_and_legacy_isolation(tmp_path,monkeypatch):
    from shm.personal import ai as module
    s=PortfolioStore(tmp_path/'p.sqlite3');s.initialize();s.save_account({'account':account(),'version':0})
    key=tmp_path/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
    calls=[]
    def caller(*args,**kwargs):
        calls.append(1)
        if kwargs.get('test'):return {'text':'OK','usage':{}}
        raise ReportError('temporary',True)
    ai=AIService(s,tmp_path,key_path=key,caller=caller)
    ai.save_settings({'base_url':'https://test.invalid/v1','model':'test','key':'fake','manual_limit':2})
    ai.test()
    monkeypatch.setattr(ai,'evidence',lambda *args:{'subject':'personal','start':'2026-08-03','end':'2026-08-04','strategy_id':'S500-C3','cost_bps':10,'template_version':'test','ledger_version':1,'source_version':'v1','evidence':{},'limited':True})
    request={'subject':'personal','start':'2026-08-03','end':'2026-08-04'}
    ai.create(request);assert ai.run_one()
    assert ai.reports()[0]['status']=='failed'
    assert len(calls)==3  # harmless connection test + two counted report attempts
    with pytest.raises(Invalid,match='额度'):
        ai.create(request)
    assert s.account()['version']==1 and s.account()['state']['cash']==100000


def test_report_disabled_before_worker_sends(tmp_path,monkeypatch):
    s=PortfolioStore(tmp_path/'p.sqlite3');s.initialize()
    key=tmp_path/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
    calls=[]
    def caller(*a,**k):calls.append(1);return {'text':'OK','usage':{}}
    ai=AIService(s,tmp_path,key_path=key,caller=caller)
    ai.save_settings({'base_url':'https://test.invalid/v1','model':'test','key':'fake','automatic':True});ai.test()
    monkeypatch.setattr(ai,'evidence',lambda *args:{'subject':'personal','start':'2026-08-03','end':'2026-08-04','strategy_id':'S500-C3','cost_bps':10,'template_version':'test','source_version':'v1','evidence':{}})
    ai.create({'subject':'personal','start':'2026-08-03','end':'2026-08-04'},'automatic')
    ai.save_settings({'automatic':False});ai.run_one()
    assert len(calls)==1 and ai.reports()[0]['status']=='failed'


def test_receivable_settlement_and_unconfirmed_expiry():
    a=account(cash='99000',receivable='1000',balance_note='已确认应收')
    state,_=apply(initial(a),a,event({'kind':'cash','action':'RECEIVABLE_SETTLED','amount':'1000','fee':'0','note':'到账'}))
    assert state['cash']==100000 and state['receivable']==0 and state['flows']==[]
    a=account();state,_=apply(initial(a),a,event(leg()))
    at='2026-08-24T16:00:00-04:00'
    v=value_state(state,{'at':at,'marks':{instrument(OPT)['key']:{'price':'0','source':'broker','at':at}}})
    assert v['ledger_nav'] is None and '到期事件待确认' in v['missing'][0]
