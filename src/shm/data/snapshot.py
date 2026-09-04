"""Content-addressed manifests for the parquet files used by a run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: str
    files: dict[str, dict[str, str]]


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path: Path, manifest_path: Path) -> str:
    data_root = manifest_path.parent.parent
    try:
        return path.resolve().relative_to(data_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def create_snapshot(
    price_paths: Mapping[str, Path | str],
    manifest_path: Path | str,
    *,
    created_at: datetime | None = None,
) -> Snapshot:
    """Hash every used parquet and append one content-addressed snapshot."""

    manifest_path = Path(manifest_path)
    files = {
        ticker.upper(): {
            "path": _relative_path(Path(path), manifest_path),
            "sha256": sha256_file(path),
        }
        for ticker, path in sorted(price_paths.items())
    }
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"))
    snapshot_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    stamp = created_at or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    snapshot = Snapshot(snapshot_id, stamp.astimezone(UTC).isoformat(), files)

    if manifest_path.exists():
        payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        payload = {"schema_version": 1, "snapshots": []}
    snapshots = payload.setdefault("snapshots", [])
    if not any(item.get("id") == snapshot.id for item in snapshots):
        snapshots.append(
            {"id": snapshot.id, "created_at": snapshot.created_at, "files": snapshot.files}
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return snapshot
