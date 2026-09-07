import json
from datetime import datetime

import pytest
import yaml

from shm.paper.v03 import _hash, init_paper_v03, paper_v03_status, run_paper_v03, report_paper_v03
from shm.service.dashboard import build_dashboard
from shm.service.store import ServiceStore
from shm.v04.profiles import candidate_config
from test_v03_paper import paper_repo, SIGNAL, FILL, _now


@pytest.fixture
def observation_repo(paper_repo, monkeypatch):
    import shm.universe.sp500 as sources

    config = candidate_config("S500-C3")
    folder = paper_repo / "config/v04"
    folder.mkdir()
    (folder / "observation.json").write_text(json.dumps({
        "spec_version": "0.4", "strategy_id": "S500-C3", "account_mode": "observation",
        "historically_qualified": False, "config": config, "params_hash": _hash(config),
        "cost_bps": [10, 25], "frozen_at": "2026-09-06T12:00:00Z",
    }))
    symbols = yaml.safe_load((paper_repo / "config/universe.yaml").read_text())["tickers"]
    monkeypatch.setattr(sources, "load_sp500_snapshot", lambda root: {"members": [{"symbol": t} for t in symbols]})
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": True})
    (paper_repo / "data/market_refresh").mkdir()
    return paper_repo


def initialize(root):
    return init_paper_v03(root, "S500-C3", as_of="2026-09-04", now="2026-09-06T23:00:00Z",
                          account_mode="observation")


def market(root, date):
    (root / "data/market_refresh/latest.json").write_text(json.dumps({
        "date": date, "complete": True, "require_point_in_time_eligibility": True,
    }))


def test_observation_requires_explicit_authority_without_creating_or_changing_winner(observation_repo):
    root = observation_repo
    original = (root / "paper/accounts/2026-09-05.json").read_bytes()
    with pytest.raises(ValueError, match="frozen"):
        init_paper_v03(root, "S500-C3", now="2026-09-06T23:00:00Z")
    status = initialize(root)
    assert status["account_mode"] == "observation" and status["historical_qualification"] == "UNVALIDATED"
    assert status["first_signal_date"] == SIGNAL and status["forward_start"] is None
    assert all(book["equity"] == 100000 for book in status["books"].values())
    manifest = root / "paper/v04/S500-C3/manifest.json"
    original_manifest = manifest.read_bytes()
    initialize(root)
    assert manifest.read_bytes() == original_manifest
    assert "winner" not in json.loads(original_manifest)
    assert not (root / "config/v04/winner.json").exists()
    assert (root / "paper/accounts/2026-09-05.json").read_bytes() == original
    with pytest.raises(ValueError, match="authorization"):
        init_paper_v03(root, "S500-C4", now="2026-09-06T23:00:00Z", account_mode="observation")
    definition_path = root / "config/v04/observation.json"
    definition = json.loads(definition_path.read_text())
    definition["config"]["base_candidate"]["target_vol"] = 0.25
    definition["params_hash"] = _hash(definition["config"])
    definition_path.write_text(json.dumps(definition))
    with pytest.raises(ValueError, match="differs"):
        paper_v03_status(root, "S500-C3")


@pytest.mark.parametrize("source_current", [True, False])
def test_observation_executes_shared_cost_books_or_blocks_stale_source_and_replays_once(observation_repo, monkeypatch, source_current):
    import shm.universe.sp500 as sources

    root = observation_repo
    initialize(root)
    market(root, SIGNAL)
    signal = run_paper_v03(root, "S500-C3", as_of=SIGNAL, now=_now(SIGNAL))
    assert signal["account_mode"] == "observation"
    assert signal["books"]["10"]["decision"]["target_weights"]
    assert not signal["books"]["10"]["state"]["positions"]
    market(root, FILL)
    monkeypatch.setattr(sources, "sp500_status", lambda *a, **kw: {"allow_new_risk": source_current})
    filled = run_paper_v03(root, "S500-C3", as_of=FILL, now=_now(FILL))
    for book in filled["books"].values():
        assert bool(book["execution"]["transactions"]) == source_current
        assert bool(book["state"]["positions"]) == source_current
        if not source_current:
            assert any(e.get("reason") == "MISSING_VERIFIED_SP500_UNIVERSE" for e in book["execution"]["events"])
    if source_current:
        assert filled["books"]["25"]["execution"]["cost"] > filled["books"]["10"]["execution"]["cost"] > 0
    path = root / f"paper/v04/S500-C3/days/{FILL}.json"
    committed = path.read_bytes()
    (path.parent.parent / "state.json").unlink()
    assert run_paper_v03(root, "S500-C3", as_of=FILL, now=_now(FILL)) == filled
    assert path.read_bytes() == committed
    assert paper_v03_status(root, "S500-C3")["historical_qualification"] == "UNVALIDATED"
    report = report_paper_v03(root, "S500-C3", "2026-09", now="2026-10-01T00:00:00Z")
    assert report["account_mode"] == "observation" and report["historical_qualification"] == "UNVALIDATED"
    assert not report["complete"]  # Missing days must not become completed forward evidence.


def test_observation_dashboard_shows_real_cash_and_retains_inconclusive_history(observation_repo):
    root = observation_repo
    initialize(root)
    folder = root / "reports/v04"
    folder.mkdir(parents=True)
    history = {"status": "INCONCLUSIVE", "winner": None, "candidates": []}
    (folder / "selection.json").write_text(json.dumps(history))
    store = ServiceStore(root / "service.sqlite3")
    store.initialize()
    dashboard = build_dashboard(root, store, "Asia/Shanghai", strategy_id="S500-C3",
                                now=datetime.fromisoformat("2026-09-06T23:00:00+00:00"))
    assert dashboard["account"]["total"] == 100000
    assert dashboard["strategy"]["account_mode"] == "observation"
    assert dashboard["strategy"]["historical_screen"] == history
    assert dashboard["strategy"]["performance_verdict"] == "AWAITING_FIRST_SIGNAL"
    assert dashboard["progress"]["next"] == SIGNAL
    assert not dashboard["trades"] and not dashboard["holdings"]
