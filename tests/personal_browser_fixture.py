"""Disposable local acceptance service; never uses NAS data or a real AI key."""
import json
import signal
import tempfile
import pandas as pd
from pathlib import Path
from http.server import ThreadingHTTPServer
from cryptography.fernet import Fernet
from shm.service import app, workflow
from shm.data import market_refresh
from shm.service.dashboard import build_dashboard
from shm.personal.store import PortfolioStore
from shm.personal.api import PrivateAPI
from shm.personal.ai import AIService, ReportError
from test_service_dashboard import seed_dashboard, NOW

def terminate_fixture(_signum, _frame):
    # Unwind TemporaryDirectory on test failure as well as success.
    raise SystemExit(0)


signal.signal(signal.SIGTERM, terminate_fixture)

with tempfile.TemporaryDirectory(prefix='shm-personal-acceptance-') as directory:
    root=Path(directory)
    legacy=seed_dashboard(root)
    app.build_dashboard=lambda path,store,tz,**kwargs:build_dashboard(path,store,tz,now=NOW,**kwargs)
    personal=PortfolioStore(root/'portfolio.sqlite3');personal.initialize()
    close_day=pd.Timestamp('2026-08-03')
    real_session=workflow.latest_completed_session
    workflow.latest_completed_session=lambda now=None:real_session(now) if now is not None else close_day
    price_path=root/'data/raw/prices/MSFT.parquet';price_path.parent.mkdir(parents=True,exist_ok=True)
    def seed_prices():
        pd.DataFrame([{'date':'2026-08-03','close':50.0,'as_traded_close':100.0},
                      {'date':'2026-08-04','close':55.0,'as_traded_close':110.0}]).to_parquet(price_path,index=False)
    seed_prices()
    def refresh_prices(root,symbols,**kwargs):
        assert symbols=={'MSFT'} and kwargs['daily_budget']==600
        seed_prices()
        return {'requested':0,'missing':[],'next_retry':None}
    market_refresh.refresh_market_cache=refresh_prices
    class AcceptanceAPI(PrivateAPI):
        def refresh_quotes(self,symbol=None):
            global close_day
            close_day=pd.Timestamp('2026-08-04')
            return super().refresh_quotes(symbol)

    key=root/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
    def fake(settings,key,messages,param,**kwargs):
        if kwargs.get('test'):
            if settings['model']=='provider-denied':
                raise ReportError('上游接口 HTTP 403：Cloudflare 拒绝了请求（错误码 1010）；请求编号 fixture-ray')
            return {'text':'OK','usage':{'completion_tokens':1}}
        return {'text':json.dumps({'title':'样本有限的账户复盘','summary':'基于当前录入证据，先补齐账目。','limitations':['本地验收模型样例'], 'facts':[{'evidence_id':'window.start','value':json.loads(messages[-1]['content'])['start']}], 'suggestions':[]}), 'usage':{'completion_tokens':50}}
    ai=AIService(personal,root,key_path=key,caller=fake)
    service=app.RunService(legacy,root,timezone_name='Asia/Shanghai',retry_attempts=1,retry_delay_seconds=0)
    service.personal=AcceptanceAPI(personal,root,public_url='https://shm.test',gateway_token='fixture-gateway-token-32-characters',enabled=True,verified=True,ai=ai)
    ai.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),app._handler(service))
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'directory':directory}),flush=True)
    try:server.serve_forever()
    finally:service.stop();server.server_close()
