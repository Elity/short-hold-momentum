from pathlib import Path

import pandas as pd
import pytest

from shm.service import app
from shm.service.store import ServiceStore


def test_failed_run_cannot_be_replayed_after_a_newer_market_close(
    tmp_path: Path, monkeypatch
) -> None:
    store = ServiceStore(tmp_path / "service.sqlite3")
    store.initialize()
    run_id = store.create_run(
        trigger="scheduled",
        scheduled_for="2026-09-18",
        market_session="2026-09-17",
    )
    store.finish_run(run_id, "failed", error="network")
    service = app.RunService(
        store,
        tmp_path,
        timezone_name="Asia/Shanghai",
        retry_attempts=3,
        retry_delay_seconds=0,
    )
    monkeypatch.setattr(
        app,
        "latest_completed_session",
        lambda: pd.Timestamp("2026-09-18"),
    )

    with pytest.raises(ValueError, match="stale"):
        service.retry_failed(run_id)


@pytest.mark.parametrize('failed', [False, True])
def test_personal_prices_update_after_strategy_finishes(tmp_path, monkeypatch, failed):
    from types import SimpleNamespace
    store=ServiceStore(tmp_path/'service.sqlite3');store.initialize()
    run_id=store.create_run(trigger='manual',scheduled_for=None,market_session='2026-09-04')
    service=app.RunService(store,tmp_path,timezone_name='Asia/Shanghai',retry_attempts=1,retry_delay_seconds=0)
    calls=[]
    def strategy(*args,**kwargs):
        if failed:
            raise RuntimeError('strategy failure')
        return SimpleNamespace(summary='complete')
    def personal():
        assert store.get_run(run_id).status==('failed' if failed else 'success')
        calls.append('updated')
    monkeypatch.setattr(app,'run_daily_workflow',strategy)
    service.personal=SimpleNamespace(enabled=True,refresh_after_strategy=personal)
    service._active_run_id=run_id
    service._execute(run_id)
    assert calls==['updated'] and service._active_run_id is None
