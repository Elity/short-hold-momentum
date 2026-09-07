import json
import shutil
import threading
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd
import pytest

from shm.service import app
from shm.service.dashboard import build_dashboard, build_portfolio, read_report
from shm.service.store import ServiceStore


NOW = datetime(2026, 10, 17, 0, 0, tzinfo=UTC)


def seed_dashboard(root: Path, *, populated: bool = True) -> ServiceStore:
    """An isolated ledger with fees and a partial exit; never used by the service."""
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source / "config", root / "config")
    for name in ("accounts", "tickets", "fills", "options"):
        (root / "paper" / name).mkdir(parents=True)
    (root / "reports").mkdir()
    (root / "paper/p4.yaml").write_text(
        "mode: paper\nprovider: local_offline_simulator\nforward_test_start: 2026-09-05\n"
    )
    accounts = [("2026-09-05", 10000, {})]
    if populated:
        accounts += [
            ("2026-09-18", 8998, {"AAA": 10}),
            ("2026-10-16", 9276, {"AAA": 6, "BBB": 5}),
        ]
        (root / "paper/tickets/2026-09-17.csv").write_text(
            "ticker,side,qty,order_type,time_in_force,reason\n"
            "AAA,buy,10,market_on_open,opg,Initial selection\n"
        )
        (root / "paper/tickets/2026-10-15.csv").write_text(
            "ticker,side,qty,order_type,time_in_force,reason\n"
            "AAA,sell,4,market_on_open,opg,Reduce position\n"
            "BBB,buy,5,market_on_open,opg,New selection\n"
        )
        (root / "paper/fills/2026-09-18.csv").write_text(
            "ticker,qty,fill_price,fill_time,official_open,commission\n"
            "AAA,10,100,2026-09-18T13:30:00Z,100,2\n"
        )
        (root / "paper/fills/2026-10-16.csv").write_text(
            "ticker,qty,fill_price,fill_time,official_open,commission\n"
            "AAA,4,120,2026-10-16T13:30:00Z,120,1\n"
            "BBB,5,40,2026-10-16T13:30:00Z,40,1\n"
        )
        (root / "reports/paper-2026-09.md").write_text(
            "# Paper monthly report — 2026-09\n\n## Paper vs model\n"
            "| Measure | Paper | Model | Gap |\n|---|---:|---:|---:|\n"
            "| Return | +1.00% | +1.10% | -0.10% |\n\n"
            '<script>window.__report_xss = true</script>\n'
        )
        (root / "paper/options/2026-10-16.json").write_text(json.dumps({
            "mode": "paper", "paper_only": True, "signal_date": "2026-10-15",
            "as_of": "2026-10-16", "orders": [],
            "skipped": [{"ticker": "AAA", "strategy": "CC", "reason": "insufficient shares"}],
            "summary": {"max_loss": 0, "cash_usage": 0, "csp_notional": 0},
        }))
    for date, cash, positions in accounts:
        (root / f"paper/accounts/{date}.json").write_text(json.dumps({
            "as_of": date, "cash": cash, "positions": positions, "mode": "paper",
        }))
    cache = root / "data/raw/prices"
    cache.mkdir(parents=True)
    dates = pd.to_datetime(["2026-09-04", "2026-09-18", "2026-10-15", "2026-10-16", "2026-10-19"])
    for ticker, closes in {
        "AAA": [99, 101, 124, 125, 9999], "BBB": [39, 40, 39, 38, 9999],
        "SPY": [500, 501, 520, 525, 9999],
    }.items():
        pd.DataFrame({
            "date": dates, "open": closes, "high": closes, "low": closes,
            "close": closes, "volume": [100000] * len(dates), "adjusted": True,
            "source": "test-fixture", "downloaded_at": pd.Timestamp(NOW),
        }).to_parquet(cache / f"{ticker}.parquet", index=False)
    store = ServiceStore(root / "service.sqlite3")
    store.initialize()
    for status, day in [("failed", "2026-10-15"), ("success", "2026-10-17")]:
        run_id = store.create_run(
            trigger="scheduled", scheduled_for=day, market_session="2026-10-16"
        )
        store.mark_running(run_id)
        store.increment_attempt(run_id)
        store.add_step(
            run_id=run_id, attempt=1, name="data-update", status=status,
            started_at=NOW - timedelta(seconds=30), finished_at=NOW,
            output="行情已更新" if status == "success" else '<img src=x onerror="window.__log_xss=true">',
        )
        if status == "success":
            store.add_step(
                run_id=run_id, attempt=1, name="rebalance", status="skipped",
                started_at=NOW, finished_at=NOW, output="本次没有到期调仓",
            )
        store.finish_run(run_id, status, summary=(
            "2026-10-16: fills 2026-10-16; paper status: cycles=2/3, pending=0, "
            "missed=0, monthly_reports=1/3, next_rebalance=2026-11-12"
        ) if status == "success" else "",
                         error="行情请求失败" if status == "failed" else "")
        with store._connect() as connection:
            connection.execute(
                "UPDATE runs SET created_at=?, started_at=?, finished_at=? WHERE id=?",
                ((NOW-timedelta(seconds=30)).isoformat(), (NOW-timedelta(seconds=30)).isoformat(),
                 NOW.isoformat(), run_id),
            )
    return store


def test_dashboard_reconciles_partial_sale_fees_and_excludes_future_prices(tmp_path):
    seed_dashboard(tmp_path)
    result = build_portfolio(tmp_path, now=NOW)
    account = result["account"]
    assert account["cash"] == 9276
    assert account["market"] == 940
    assert account["total"] == 10216
    assert account["unrealized"] == pytest.approx(137.8)
    assert account["realized"] == pytest.approx(78.2)
    assert account["gain"] == pytest.approx(account["unrealized"] + account["realized"])
    assert account["day"] == pytest.approx(-22)
    assert result["holdings"][0]["cost"] == pytest.approx(100.2)
    sale = next(t for t in result["trades"] if t["side"] == "sell")
    assert sale["realized_pnl"] == pytest.approx(78.2)
    assert result["chart"][-1]["date"] == "2026-10-16"
    assert result["chart"][-1]["equity"] == account["total"]
    assert result["chart"][-1]["benchmark"] == 10500
    assert not result["warnings"]


def test_dashboard_empty_account_keeps_cash_and_does_not_invent_trades(tmp_path):
    seed_dashboard(tmp_path, populated=False)
    result = build_portfolio(tmp_path, now=datetime(2026, 9, 6, tzinfo=UTC))
    assert result["account"]["total"] == 10000
    assert result["account"]["unrealized"] == 0
    assert result["trades"] == result["holdings"] == []
    assert len(result["chart"]) == 1
    assert result["account"]["day"] is None


def test_dashboard_missing_latest_price_is_unknown_not_zero(tmp_path):
    seed_dashboard(tmp_path)
    path = tmp_path / "data/raw/prices/AAA.parquet"
    prices = pd.read_parquet(path)
    prices.loc[prices.date != pd.Timestamp("2026-10-16")].to_parquet(path, index=False)
    result = build_portfolio(tmp_path, now=NOW)
    assert result["account"]["total"] is None
    assert result["account"]["unrealized"] is None
    assert result["account"]["cash"] == 9276
    assert result["chart"][-1]["equity"] is None
    assert any("缺少 2026-10-16 收盘价" in message for message in result["warnings"])


def test_dashboard_unreconciled_cost_basis_remains_unknown(tmp_path):
    seed_dashboard(tmp_path)
    path = tmp_path / "paper/accounts/2026-10-16.json"
    payload = json.loads(path.read_text())
    payload["positions"]["AAA"] = 7
    path.write_text(json.dumps(payload))
    result = build_portfolio(tmp_path, now=NOW)
    assert result["account"]["realized"] is None
    assert result["account"]["unrealized"] is None
    assert any("持仓不一致" in message for message in result["warnings"])


def test_reports_only_read_known_artifact_names(tmp_path):
    seed_dashboard(tmp_path)
    assert "Paper monthly report" in read_report(tmp_path, "monthly/2026-09")["content"]
    with pytest.raises(FileNotFoundError):
        read_report(tmp_path, "monthly/../../config/params")


def test_dashboard_http_settings_history_details_and_static_assets(tmp_path, monkeypatch):
    store = seed_dashboard(tmp_path)
    old = store.create_run(trigger="manual", scheduled_for=None, market_session="2026-01-01")
    with store._connect() as connection:
        connection.execute(
            "UPDATE runs SET created_at=? WHERE id=?",
            ((NOW-timedelta(days=100)).isoformat(), old),
        )
    monkeypatch.setattr(
        app, "build_dashboard", lambda root, database, timezone, **kwargs: build_dashboard(
            root, database, timezone, now=NOW, **kwargs
        )
    )
    service = app.RunService(
        store, tmp_path, timezone_name="Asia/Shanghai", retry_attempts=3, retry_delay_seconds=0
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), app._handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base) as response:
            page = response.read().decode()
            assert "当前持仓" in page and "/static/dashboard.js" in page
            assert "示例账户" not in page
        for asset in ("dashboard.js", "dashboard.css"):
            with urlopen(base + "/static/" + asset) as response:
                assert response.status == 200
        with urlopen(base + "/api/dashboard") as response:
            result = json.load(response)
            assert len(result["runs"]) == 2
            assert result["progress"]["next"] == "2026-11-12"
            assert result["strategy"]["id"] == "V04"
        with urlopen(base + "/api/dashboard?strategy_id=C3&cost_bps=25") as response:
            result = json.load(response)
            assert result["strategy"]["id"] == "C3"
            assert result["strategy"]["performance_verdict"] == "NOT_STARTED"
            assert result["account"]["total"] is None
            assert result["trades"] == []
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/api/dashboard?strategy_id=../V04")
        assert error.value.code == 400
        with urlopen(base + "/api/runs/1") as response:
            assert json.load(response)["steps"][0]["status"] == "failed"
        request = Request(base + "/api/settings", json.dumps({"daily_time": "08:00"}).encode(),
                          {"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            assert json.load(response)["daily_time"] == "08:00"
        assert ServiceStore(store.path).get_setting("daily_time") == "08:00"
        for value in ("25:00", "8:00"):
            request.data = json.dumps({"daily_time": value}).encode()
            with pytest.raises(HTTPError) as error:
                urlopen(request)
            assert error.value.code == 400
        request.data = json.dumps({"daily_time": "09:00"}).encode()
        request.add_header("Origin", "https://unrelated.example")
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        assert store.get_setting("daily_time") == "08:00"
        for path in ("/api/runs/9999", "/api/reports/monthly/../../config/params.yaml"):
            with pytest.raises(HTTPError) as error:
                urlopen(base + path)
            assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
