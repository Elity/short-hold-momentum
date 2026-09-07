"""S&P 500 source evidence and version isolation at the dashboard boundary."""
import json

from shm.service.dashboard import build_dashboard, list_reports, read_report
from shm.service.store import ServiceStore
from shm.universe.sp500 import refresh_sp500_universe
from test_sp500_universe import NOW, TOMORROW, source_documents


def test_sp500_dashboard_keeps_source_dates_and_failure_gate_without_inventing_account(tmp_path):
    store = ServiceStore(tmp_path / "service.sqlite3")
    store.initialize()
    missing = build_dashboard(tmp_path, store, "Asia/Shanghai", now=NOW, strategy_id="S500-C3")
    assert missing["strategy"]["version"] == "0.4"
    assert missing["account"]["total"] is None
    assert not missing["universe"]["allow_new_risk"]

    documents = source_documents()
    refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=NOW, fetcher=documents.__getitem__)
    verified = build_dashboard(tmp_path, store, "Asia/Shanghai", now=NOW, strategy_id="S500-C3", cost_bps=25)
    source = verified["universe"]
    assert source["fresh"] and source["allow_new_risk"]
    assert source["source_as_of"] == "2026-09-03"
    assert source["verified_for_session"] == "2026-09-04"
    assert source["source_age_sessions"] == 1
    assert source["security_count"] == source["company_count"] == 500
    assert len(source["source_urls"]) == 2
    assert verified["strategy"]["performance_verdict"] == "NOT_STARTED"
    assert verified["account"]["total"] is None

    def unavailable(_):
        raise TimeoutError("provider unavailable")

    refresh_sp500_universe(tmp_path, as_of="2026-09-04", now=TOMORROW, fetcher=unavailable)
    failed = build_dashboard(tmp_path, store, "Asia/Shanghai", now=TOMORROW, strategy_id="S500-C3")
    assert failed["universe"]["fresh"]
    assert not failed["universe"]["allow_new_risk"]
    assert failed["universe"]["security_count"] == 500
    assert failed["universe"]["error"] == "provider unavailable"
    assert any("暂停新增买入" in warning for warning in failed["warnings"])


def test_sp500_dashboard_uses_only_v04_research_and_reports(tmp_path):
    store = ServiceStore(tmp_path / "service.sqlite3")
    store.initialize()
    for version, strategy in (("v03", "C3"), ("v04", "S500-C3")):
        report_dir = tmp_path / "paper" / version / strategy / "reports"
        report_dir.mkdir(parents=True)
        (report_dir / "2026-09.md").write_text(strategy + " forward report")
        selection_dir = tmp_path / "reports" / version
        selection_dir.mkdir(parents=True)
        (selection_dir / "selection.json").write_text(json.dumps({
            "spec_version": "0.4" if version == "v04" else "0.3",
            "metrics_valid": False, "winner": None,
            "candidates": [{"strategy_id": strategy, "metrics_valid": False,
                            "metrics_10": {"cagr": 0.3}, "qualified": False}],
        }))
    result = build_dashboard(tmp_path, store, "Asia/Shanghai", now=NOW, strategy_id="S500-C3")
    assert result["strategy"]["historical_screen"]["spec_version"] == "0.4"
    assert not result["strategy"]["historical_screen"]["metrics_valid"]
    assert len(list_reports(tmp_path, strategy_id="S500-C3")) == 1
    assert read_report(tmp_path, "monthly/2026-09", strategy_id="S500-C3")["content"] == "S500-C3 forward report"
    assert read_report(tmp_path, "monthly/2026-09", strategy_id="C3")["content"] == "C3 forward report"
