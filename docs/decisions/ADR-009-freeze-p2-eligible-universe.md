# ADR-009 — Freeze the P2 eligible universe for paper validation

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Inputs: V04 (`params_hash` `2064365d`) and the 2005-01-01 through
  2018-12-31 development-period data-quality results

## Decision

Freeze the 48 active owner-universe tickers that passed P2 development-period
DQ-03 and DQ-04 in `config/p2_eligible.frozen.yaml`. The file records both the
winning parameter hash and the byte hash of `config/universe.yaml`; paper runs
must reject a mismatch instead of silently changing the tested model.

Paper mode applies current 260-session price, ADV, and history checks only
inside this frozen 48-ticker set. It does not rerun development-period DQ on
recent data and does not add any of the 36 development-ineligible tickers back
to the candidate set.

## Consequences

- `config/universe.yaml` remains owner-controlled and unchanged.
- A future owner universe or frozen-parameter change requires regenerating the
  derived list and recording a new decision.
- This preserves the P2 model definition while still allowing a ticker to fail
  current paper eligibility because its recent data, price, or liquidity is
  insufficient.
- This decision authorizes paper ticket generation only; it adds no live-order
  endpoint.
