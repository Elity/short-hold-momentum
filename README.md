# Short-Hold Momentum

An auditable research implementation of `SPEC-SHM-001` for a long-only,
fixed-universe US equity momentum strategy. This repository is engineering
infrastructure, not investment advice.

## Current phase

P2 out-of-sample preparation. The closed development set V01-V11 is complete;
V04, V08, and V02 were selected in that order before any OOS data was read.
All development runs are `INCONCLUSIVE` on data-quality evidence, while their
separate hypothesis verdicts are recorded in `docs/p2_development_results.md`.
The owner waived `docs/why/P1.md` in ADR-001, and ADR-002 delegates the
remaining checkpoints and repository commits to the agent.

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
