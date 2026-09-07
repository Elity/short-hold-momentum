"""Start an isolated populated dashboard for browser acceptance; no scheduler."""
import json
import signal
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from shm.service import app
from shm.service.dashboard import build_dashboard
from shm.paper.v03 import init_paper_v03
from shm.universe.sp500 import refresh_sp500_universe
from test_service_dashboard import NOW, seed_dashboard
from test_sp500_universe import source_documents

def terminate_fixture(_signum, _frame):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, terminate_fixture)


with tempfile.TemporaryDirectory(prefix="shm-dashboard-test-") as directory:
    root = Path(directory)
    store = seed_dashboard(root)
    source = source_documents(date="16-Oct-2026")
    refresh_sp500_universe(root, as_of="2026-10-16", now=NOW, fetcher=source.__getitem__)
    selection = root / "reports/v04/selection.json"
    selection.parent.mkdir(parents=True)
    selection.write_text(json.dumps({
        "spec_version": "0.4", "evidence": "known_history", "metrics_valid": False,
        "winner": None, "status": "INCONCLUSIVE", "period": {"start": "2006-01-01", "end": "2026-09-04"},
        "candidates": [{"strategy_id": "S500-C3", "qualified": False, "metrics_valid": False,
                        "metrics_10": {"cagr": 0.3, "maxdd": -0.1},
                        "metrics_25": {"cagr": 0.28, "maxdd": -0.12},
                        "benchmark_25": {"cagr": 0.1, "maxdd": -0.3},
                        "warnings": ["Synthetic invalid-price fixture: performance must remain unavailable"]}],
    }))
    init_paper_v03(root, "S500-C3", as_of="2026-10-16", now=NOW, account_mode="observation")
    app.build_dashboard = lambda path, database, timezone, **kwargs: build_dashboard(
        path, database, timezone, now=NOW, **kwargs
    )
    service = app.RunService(
        store, root, timezone_name="Asia/Shanghai", retry_attempts=3, retry_delay_seconds=0
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), app._handler(service))
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "directory":directory}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
