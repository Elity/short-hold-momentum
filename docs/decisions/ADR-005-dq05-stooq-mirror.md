# ADR-005 — Use a static Stooq mirror for DQ-05

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Trigger: Stooq's CSV endpoint now returns a JavaScript proof-of-work page to
  non-browser clients, so the automated DQ-05 request no longer returns CSV.

## Decision

Use the public `tousheng4/multiagent-market` raw GitHub copy of Stooq's adjusted
SPY daily history for DQ-05. Compare the latest three complete calendar years
present in both the primary Yahoo cache and the mirror. A partial latest year is
not eligible for comparison.

## Impact

- The check remains a comparison against a free source independent of the
  primary Yahoo download path.
- Fewer than three complete common years, an unavailable mirror, or any annual
  return difference above one percentage point remains `INCONCLUSIVE`.
- The source is read-only and contains no credentials or paid dependency.
