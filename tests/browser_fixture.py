"""Start an isolated populated dashboard for browser acceptance; no scheduler."""
import json
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

from shm.service import app
from shm.service.dashboard import build_dashboard
from test_service_dashboard import NOW, seed_dashboard


with tempfile.TemporaryDirectory(prefix="shm-dashboard-test-") as directory:
    root = Path(directory)
    store = seed_dashboard(root)
    app.build_dashboard = lambda path, database, timezone: build_dashboard(
        path, database, timezone, now=NOW
    )
    service = app.RunService(
        store, root, timezone_name="Asia/Shanghai", retry_attempts=3, retry_delay_seconds=0
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), app._handler(service))
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
