# ADR-010 — Use a local paper account with $100,000 initial cash

- Status: Accepted
- Date: 2026-09-05
- Owner instruction: “给定十万美金初始值，然后你模拟持仓”

## Decision

Start P4 with a repository-local, paper-only account ledger at $100,000 cash
and no positions. The forward-test start is 2026-09-05. The first eligible
signal remains the canonical 2026-09-17 rebalance; the simulator must not enter
positions early.

For this local simulation, stock tickets are filled in full at the next XNYS
session's official opening price with zero commission. The fill is generated
only after that session is complete and only from the local daily cache. No
broker endpoint, credential, live order, margin, or real money is permitted.

## Consequences

- The local account can validate signal timing, whole-share rounding, cash,
  holdings, and forward model/account divergence.
- A zero-slippage official-open fill is a deterministic simulation assumption,
  not observed broker execution. Its 0 bps result cannot satisfy the original
  P4 requirement to measure real paper-broker execution cost for Gate.
- Gate remains unavailable until the owner separately accepts this limitation
  or supplies genuine paper-broker fills, the required phase notes, and
  `config/live.yaml`.
