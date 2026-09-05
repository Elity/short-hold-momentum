# Short-Hold Momentum

An auditable research implementation of `SPEC-SHM-001` for a long-only,
fixed-universe US equity momentum strategy. This repository is engineering
infrastructure, not investment advice.

## Current phase

P1 baseline V00 completed on 2026-09-04 for the owner-approved 84-symbol
universe, including MSFT. The result is `INCONCLUSIVE`; the owner-authored
`docs/why/P1.md` remains the final P1 checkpoint before P2.

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
