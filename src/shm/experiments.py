from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import yaml


MAX_P2_VARIANTS = 20
MAX_OOS_UNLOCKS = 3

REQUIRED_RUN_FIELDS = {
    "run_id",
    "timestamp",
    "mode",
    "phase",
    "git_sha",
    "params_hash",
    "params",
    "universe_hash",
    "snapshot_id",
    "period",
    "oos_used",
    "variant_index",
    "prereg",
    "hypothesis",
    "expected",
    "results",
    "results_stress",
    "benchmark",
    "checks",
    "status",
    "verdict",
    "report",
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def compute_params_hash(params: dict[str, Any], default_cost_bps: float) -> str:
    payload = {
        "signal": params["signal"],
        "eligibility": params["eligibility"],
        "risk": params["risk"],
        "execution": params["execution"],
        "costs.default": default_cost_bps,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()[:8]


def compute_file_hash(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply_prereg_ofat(params: dict[str, Any], difference: str) -> dict[str, Any]:
    try:
        path, change = difference.split(":", 1)
        old_text, new_text = change.split("→", 1)
    except ValueError as error:
        raise ValueError("P2 preregistration must contain one OFAT change") from error

    keys = [part.strip() for part in path.strip().split(".")]
    if len(keys) < 2 or keys[0] not in {"signal", "eligibility", "risk", "execution"}:
        raise ValueError("P2 OFAT change must target a params.yaml field")

    updated = deepcopy(params)
    target: dict[str, Any] = updated
    for key in keys[:-1]:
        value = target.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"unknown P2 OFAT field: {path.strip()}")
        target = value

    field = keys[-1]
    if field not in target:
        raise ValueError(f"unknown P2 OFAT field: {path.strip()}")
    old_value = yaml.safe_load(old_text.strip())
    if target[field] != old_value:
        raise ValueError(
            f"P2 OFAT baseline mismatch for {path.strip()}: "
            f"expected {target[field]!r}, prereg says {old_value!r}"
        )
    target[field] = yaml.safe_load(new_text.strip())
    return updated


def validate_universe_hash(record: dict[str, Any], universe_path: Path | str) -> None:
    expected = compute_file_hash(universe_path)
    if record.get("universe_hash") != expected:
        raise ValueError("run record universe_hash does not match the file on disk")


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    return [json.loads(line) for line in source.read_text().splitlines() if line.strip()]


def validate_hypothesis(hypothesis: str) -> None:
    if not hypothesis.strip():
        raise ValueError("hypothesis must be non-empty")


def assert_data_access(
    *,
    mode: Literal["backtest", "paper"],
    requested_end: date,
    oos_start: date,
    unlock_oos: bool = False,
    reason: str | None = None,
) -> None:
    if mode == "paper" or requested_end < oos_start:
        return
    if not unlock_oos:
        raise PermissionError("out-of-sample data is locked; use --unlock-oos with a reason")
    if reason is None or not reason.strip():
        raise ValueError("--unlock-oos requires a non-empty reason")


def record_oos_unlock(
    path: Path | str,
    *,
    run_id: str,
    variant_index: int,
    reason: str,
    predicted: str,
    approved_by: str,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    if not reason.strip() or not predicted.strip() or not approved_by.strip():
        raise ValueError("reason, predicted, and approved_by are required")
    destination = Path(path)
    existing = read_jsonl(destination)
    for record in existing:
        if record.get("run_id") != run_id:
            continue
        expected = {
            "variant_index": variant_index,
            "reason": reason,
            "predicted": predicted,
            "approved_by": approved_by,
        }
        if all(record.get(key) == value for key, value in expected.items()):
            return record
        raise ValueError(f"conflicting OOS unlock record for run_id {run_id}")
    if len(existing) >= MAX_OOS_UNLOCKS:
        raise RuntimeError("out-of-sample unlock budget exhausted (3/3)")
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
        "run_id": run_id,
        "variant_index": variant_index,
        "reason": reason,
        "predicted": predicted,
        "approved_by": approved_by,
    }
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def validate_oos_unlock(
    path: Path | str, *, run_id: str, reason: str
) -> dict[str, Any]:
    for record in reversed(read_jsonl(path)):
        if record.get("run_id") == run_id and record.get("reason") == reason:
            return record
    raise PermissionError("OOS access requires a matching persisted unlock record")


def validate_oos_prereg(prereg: dict[str, str]) -> str:
    if prereg.get("是否使用样本外", "").strip().casefold() not in {"是", "yes", "true"}:
        raise PermissionError("preregistration is not selected for OOS use")
    prediction = prereg.get("样本外预测", "").strip()
    if not prediction:
        raise ValueError("OOS preregistration requires a non-empty prediction")
    return prediction


def load_development_run(
    path: Path | str,
    *,
    prereg: str,
    params_hash: str,
) -> dict[str, Any]:
    records = [
        row
        for row in read_jsonl(path)
        if row.get("prereg") == prereg and not row.get("oos_used", False)
    ]
    if not records:
        raise ValueError("OOS requires an existing development run for this preregistration")
    matching = [row for row in records if row.get("params_hash") == params_hash]
    if not matching:
        raise ValueError("current parameters do not match the recorded development run")
    record = matching[-1]
    if record.get("variant_index") is None:
        raise ValueError("development run is missing variant_index")
    return record


def reserve_variant(
    log_path: Path | str,
    *,
    params_hash: str,
    phase: str,
) -> int:
    if phase != "P2":
        return 0
    records = [row for row in read_jsonl(log_path) if row.get("phase") == "P2"]
    first_indexes = {
        row["params_hash"]: int(row["variant_index"])
        for row in records
        if row.get("params_hash") and row.get("variant_index") is not None
    }
    if params_hash in first_indexes:
        return first_indexes[params_hash]
    if len(first_indexes) >= MAX_P2_VARIANTS:
        raise RuntimeError("P2 variant budget exhausted (20/20)")
    return len(first_indexes) + 1


def append_run_log(path: Path | str, record: dict[str, Any]) -> None:
    missing = REQUIRED_RUN_FIELDS - record.keys()
    if missing:
        raise ValueError(f"run record missing fields: {', '.join(sorted(missing))}")
    validate_hypothesis(str(record["hypothesis"]))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def load_approved_prereg(path: Path | str) -> dict[str, str]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("- ") and "：" in line:
            key, value = line[2:].split("：", 1)
            fields[key.strip()] = value.strip()
    approval = fields.get("owner 批准", "")
    if not approval.lower().startswith("[x]"):
        raise PermissionError(f"preregistration is not owner-approved: {source}")
    hypothesis = fields.get("假设（一句话，可证伪）", "")
    validate_hypothesis(hypothesis)
    return fields
