# ADR-006 — Freeze V04 after OOS validation

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Inputs: the three OOS reports for V04, V08, and V02

## Decision

Freeze V04 (`params_hash` `2064365d`) as the P2 winner. V04 was ranked first
before any OOS read and passed KR2 with Sharpe 0.926 versus SPY 0.900 and
MaxDD -15.11% versus SPY -33.72%. V08 also passed, but V04 keeps the higher
Sharpe and shallower drawdown. V02 failed the strict Sharpe comparison.

The exact parameter snapshot is stored in `config/params.frozen.yaml`. Any
future change to that file starts a new version and requires a new ADR.

## Boundaries

- The three recorded OOS unlocks are exhausted; no further OOS rerun is
  permitted under SPEC-SHM-001 v0.2.
- WARN_SURVIVORSHIP and WARN_ONE_YEAR_WONDER remain visible in the winning
  report and must be considered during forward paper validation.
- This decision authorizes research progression only. It does not authorize
  live orders or real-money trading.
