# ADR-008 — Apply an execution-quality floor to CSP quotes

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Trigger: The first delayed-chain dry run selected a CIEN put with bid 0 and
  ask 1.00 because SPEC-SHM-001 specifies liquidity limits only for CC.

## Decision

Apply the existing CC execution-quality limits to CSP selection as well:

- bid must be at least $0.10; and
- `(ask - bid) / mid` must be at most 20%.

All original CSP constraints remain in force: absolute delta at most 0.25,
100% cash coverage, one contract per candidate, and aggregate CSP notional at
most 20% of portfolio equity.

## Consequences

The overlay skips a candidate instead of proposing a zero-premium or very wide
paper order. This is a forward-looking execution safeguard prompted by an
observed free-chain quote, not a historical optimization, and it changes no P2
result or OOS budget.
