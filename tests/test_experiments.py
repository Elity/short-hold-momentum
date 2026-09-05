import json
from datetime import date

import pytest

from shm.experiments import (
    apply_prereg_ofat,
    append_run_log,
    assert_data_access,
    compute_file_hash,
    compute_params_hash,
    load_approved_prereg,
    load_development_run,
    record_oos_unlock,
    reserve_variant,
    validate_oos_prereg,
    validate_universe_hash,
)


def test_prereg_ofat_applies_one_existing_params_change() -> None:
    params = {
        "signal": {"top_n": 15},
        "eligibility": {},
        "risk": {"trend_filter": {"off_exposure": 0.0}},
        "execution": {},
    }

    updated = apply_prereg_ofat(params, "signal.top_n: 15 → 10")

    assert params["signal"]["top_n"] == 15
    assert updated["signal"]["top_n"] == 10
    with pytest.raises(ValueError, match="baseline mismatch"):
        apply_prereg_ofat(params, "signal.top_n: 20 → 10")


def test_oos_lock_and_fourth_unlock_are_rejected(tmp_path) -> None:
    with pytest.raises(PermissionError, match="out-of-sample data is locked"):
        assert_data_access(
            mode="backtest",
            requested_end=date(2019, 1, 2),
            oos_start=date(2019, 1, 1),
        )

    log = tmp_path / "oos_unlocks.jsonl"
    for index in range(3):
        record_oos_unlock(
            log,
            run_id=f"run-{index}",
            variant_index=index,
            reason="Owner approved the planned OOS check.",
            predicted="Sharpe should remain above SPY.",
            approved_by="owner",
        )
    with pytest.raises(RuntimeError, match="3/3"):
        record_oos_unlock(
            log,
            run_id="run-4",
            variant_index=4,
            reason="Another check.",
            predicted="No change.",
            approved_by="owner",
        )


def test_oos_prereg_and_development_identity_are_required(tmp_path) -> None:
    prediction = "Sharpe remains above SPY."
    assert validate_oos_prereg(
        {"是否使用样本外": "是", "样本外预测": prediction}
    ) == prediction
    with pytest.raises(PermissionError, match="not selected"):
        validate_oos_prereg({"是否使用样本外": "否", "样本外预测": prediction})
    with pytest.raises(ValueError, match="non-empty prediction"):
        validate_oos_prereg({"是否使用样本外": "是"})

    log = tmp_path / "log.jsonl"
    records = [
        {
            "prereg": "experiments/prereg/V04.md",
            "params_hash": "2064365d",
            "variant_index": 4,
            "oos_used": False,
        },
        {
            "prereg": "experiments/prereg/V04.md",
            "params_hash": "2064365d",
            "variant_index": 4,
            "oos_used": True,
        },
    ]
    log.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    development = load_development_run(
        log,
        prereg="experiments/prereg/V04.md",
        params_hash="2064365d",
    )
    assert development["variant_index"] == 4
    with pytest.raises(ValueError, match="do not match"):
        load_development_run(
            log,
            prereg="experiments/prereg/V04.md",
            params_hash="different",
        )


def test_empty_hypothesis_stops_run_logging(tmp_path) -> None:
    with pytest.raises(ValueError, match="hypothesis must be non-empty"):
        append_run_log(
            tmp_path / "log.jsonl",
            {
                "run_id": "r",
                "timestamp": "2026-09-04T00:00:00Z",
                "mode": "backtest",
                "phase": "P1",
                "git_sha": "abc",
                "params_hash": "12345678",
                "params": {},
                "universe_hash": "u",
                "snapshot_id": "s",
                "period": {},
                "oos_used": False,
                "variant_index": 0,
                "prereg": "V00.md",
                "hypothesis": " ",
                "expected": "none",
                "results": {},
                "results_stress": {},
                "benchmark": {},
                "checks": {},
                "status": "FAIL",
                "verdict": "unable",
                "report": "report.md",
            },
        )


def test_twenty_first_distinct_variant_is_rejected(tmp_path) -> None:
    log = tmp_path / "log.jsonl"
    rows = [
        f'{{"phase":"P2","params_hash":"hash-{index}","variant_index":{index + 1}}}'
        for index in range(20)
    ]
    log.write_text("\n".join(rows) + "\n")
    assert reserve_variant(log, params_hash="hash-0", phase="P2") == 1
    with pytest.raises(RuntimeError, match="20/20"):
        reserve_variant(log, params_hash="new-hash", phase="P2")


def test_file_hash_matches_disk_bytes(tmp_path) -> None:
    universe = tmp_path / "universe.yaml"
    universe.write_bytes(b"tickers: [AAPL]\n")
    assert compute_file_hash(universe) == "fd32d700edde95732fc8d2dc356514e76c75caf1c3d1188ddaae0000fdefca0d"
    validate_universe_hash({"universe_hash": compute_file_hash(universe)}, universe)
    with pytest.raises(ValueError, match="does not match"):
        validate_universe_hash({"universe_hash": "wrong"}, universe)


def test_params_hash_is_deterministic() -> None:
    params = {
        "signal": {"top_n": 15},
        "eligibility": {"min_price_usd": 5},
        "risk": {"trend_filter": True},
        "execution": {"fill": "next_open"},
    }
    first = compute_params_hash(params, 10)
    second = compute_params_hash(dict(reversed(list(params.items()))), 10)
    assert first == second


def test_unapproved_preregistration_is_rejected(tmp_path) -> None:
    prereg = tmp_path / "V00.md"
    prereg.write_text(
        "# V00\n- 假设（一句话，可证伪）：Baseline completes.\n- owner 批准：[ ] 日期：\n"
    )
    with pytest.raises(PermissionError, match="not owner-approved"):
        load_approved_prereg(prereg)
