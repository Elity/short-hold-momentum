# Short-Hold Momentum

An auditable research implementation of `SPEC-SHM-001` for a long-only,
fixed-universe US equity momentum strategy. This repository is engineering
infrastructure, not investment advice.

## Current phase

P2 research has passed KR2. The three frozen OOS candidates were run in the
precommitted order, exhausting the `3/3` OOS budget: V04 and V08 passed, while
V02 missed the strict SPY Sharpe comparison. V04 (`params_hash` `2064365d`) is
frozen in `config/params.frozen.yaml`; detailed evidence is in
`docs/p2_development_results.md`.

The P3 technical deliverables and the P4 local paper workflow are implemented.
P4 starts from the $100,000 all-cash snapshot dated 2026-09-05 and remains at
`0/3` completed rebalance/fill cycles and `0/3` monthly reports; the first
eligible signal date is 2026-09-17. Check the machine-readable state with
`uv run shm paper status --repo-root .` and follow
`docs/p4_operator_runbook.md` for manual operation.

Gate is not available yet. It still requires the genuine forward P4 evidence,
owner-authored `docs/why/P1.md` through `P4.md`, resolution of ADR-010's
deterministic zero-bps execution-cost limitation, and an owner-created
`config/live.yaml`.

## Bootstrap

```bash
uv sync --locked
uv run shm config validate --config-dir config
uv run shm config validate --config-dir config --require-universe
uv run shm data update
uv run pytest
```

The project is pinned to Python 3.12 because the open-source vectorbt/numba
stack does not yet support every Python 3.13 combination consistently.

## Container service

The published image is `ghcr.io/elity/short-hold-momentum:latest`. It runs a
small dashboard and a persistent scheduler around the existing P4 commands.
All mutable repository artifacts and the SQLite run database live under
`/var/lib/shm`, so replacing the container does not discard paper evidence or
run history.

```bash
mkdir -p runtime
docker compose up -d
```

The dashboard is exposed on port `9022` by default. Override deployment values
without editing the compose file:

```bash
SHM_WEB_PORT=9081 SHM_DATA_DIR=/srv/short-hold-momentum docker compose up -d
```

The page shows P4 counters, successful and failed runs, per-step output, and
the next daily schedule. The daily time can be changed in the page and is
stored in SQLite. Automatic and manual runs retry transient failures three
times with a five-minute delay.

Forward evidence remains date-safe: a failed run can be retried only while its
recorded XNYS session is still the latest completed session. After a newer
market close, use **Run now** to reconcile the current session; the service
will not backfill a missed ticket, fill, or option overlay with later data.

## Owner checkpoint

The frozen universe came directly from the owner. Changes to
`config/universe.yaml` remain owner-only. Validate it with:

```bash
uv run shm config validate --config-dir config --require-universe
```

V00 was run from commit `c6059f4`:

```bash
uv run shm backtest run --prereg experiments/prereg/V00.md
```

The generated report is `reports/20260904-220347-109e68bf.md`.

After freezing an OOS candidate and prediction, refresh the cache and run the
audited sample-out evaluation explicitly:

```bash
uv run shm data update --through-oos
uv run shm backtest run --prereg experiments/prereg/V04.md \
  --unlock-oos --reason "Run frozen P2 candidate V04 under ADR-002"
```

Each OOS invocation consumes one of the three unlock records in
`experiments/oos_unlocks.jsonl` and reports the KR2 result separately from the
run-quality status.
