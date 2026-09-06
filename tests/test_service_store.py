from datetime import UTC, datetime

from shm.service.store import ServiceStore


def test_store_persists_settings_runs_and_steps(tmp_path) -> None:
    store = ServiceStore(tmp_path / "service.sqlite3")
    store.initialize()
    assert store.get_setting("daily_time") == "05:30"
    store.set_setting("daily_time", "06:10")

    run_id = store.create_run(
        trigger="scheduled",
        scheduled_for="2026-09-06",
        market_session="2026-09-04",
    )
    store.mark_running(run_id)
    attempt = store.increment_attempt(run_id)
    now = datetime.now(UTC)
    store.add_step(
        run_id=run_id,
        attempt=attempt,
        name="paper-status",
        status="success",
        started_at=now,
        finished_at=now,
        output="ok",
    )
    store.finish_run(run_id, "success", summary="done")

    run = store.get_run(run_id)
    assert run is not None
    assert (store.get_setting("daily_time"), run.status, run.attempts, run.summary) == (
        "06:10",
        "success",
        1,
        "done",
    )
    assert store.find_scheduled_run("2026-09-06").id == run_id
    assert store.list_steps(run_id)[0].output == "ok"


def test_store_marks_interrupted_runs_failed(tmp_path) -> None:
    store = ServiceStore(tmp_path / "service.sqlite3")
    store.initialize()
    run_id = store.create_run(
        trigger="manual",
        scheduled_for=None,
        market_session="2026-09-04",
    )
    store.mark_running(run_id)

    store.mark_interrupted_runs()

    run = store.get_run(run_id)
    assert run is not None
    assert run.status == "failed"
