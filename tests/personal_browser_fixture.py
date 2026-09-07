"""Disposable local acceptance service; never uses NAS data or a real AI key."""
import json
import signal
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from cryptography.fernet import Fernet
from shm.service import app
from shm.service.dashboard import build_dashboard
from shm.personal.store import PortfolioStore
from shm.personal.api import PrivateAPI
from shm.personal.ai import AIService
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
    key=root/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
    def fake(settings,key,messages,param,**kwargs):
        if kwargs.get('test'):
            return {'text':'OK','usage':{'completion_tokens':1}}
        return {'text':json.dumps({'title':'样本有限的账户复盘','summary':'基于当前录入证据，先补齐账目。','limitations':['本地验收模型样例'], 'facts':[{'evidence_id':'window.start','value':json.loads(messages[-1]['content'])['start']}], 'suggestions':[]}), 'usage':{'completion_tokens':50}}
    ai=AIService(personal,root,key_path=key,caller=fake)
    service=app.RunService(legacy,root,timezone_name='Asia/Shanghai',retry_attempts=1,retry_delay_seconds=0)
    service.personal=PrivateAPI(personal,root,public_url='https://shm.test',gateway_token='fixture-gateway-token-32-characters',enabled=True,verified=True,ai=ai)
    ai.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),app._handler(service))
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'directory':directory}),flush=True)
    try:server.serve_forever()
    finally:service.stop();server.server_close()
