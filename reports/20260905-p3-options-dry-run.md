# P3 option overlay dry run — 2026-09-05

## Classification

This is a non-executable technical demonstration built from the frozen V04
historical model snapshot. It is not an owner brokerage account, not a P4
paper-account rebalance, and not authorization to submit an order.

## Inputs and reconstruction

- Frozen strategy: V04, `params_hash=2064365d`.
- Source snapshot: `reports/20260905-162445-2064365d.daily.parquet`, through
  2026-09-04; no new OOS unlock or backtest was run.
- Last signal / execution: 2026-08-19 / 2026-08-20.
- Next scheduled rebalance: 2026-09-17; selected standard expiration:
  2026-09-18.
- Historical model equity / cash: $273,132.34 / $203,014.24.
- The backtest uses fractional shares. For this dry run every model quantity was
  floored to a whole-share proxy and the marked value of discarded fractions
  was added to cash, producing proxy cash of $204,476.99 with unchanged equity.
- Cost bases were reconstructed from actual rebalance opens plus the 10 bps buy
  cost. Replay matched recorded transaction costs to within `1.42e-14`.
- Candidate ranks 16–20 were reconstructed from the same restricted V04 signal
  inputs and checked by reproducing the persisted top-15 holding set:
  LRCX, CIEN, TXN, ON, AAPL.
- Delayed yfinance option chains were observed at 2026-09-05T10:41:21Z.

## Result

Only HPQ reached CC coverage in the whole-share proxy (156 shares), but its
chain had no call satisfying the delta/OTM, bid, and relative-spread rules. The
other 14 holdings were below 100 shares.

One CSP passed all rules after ADR-007 and ADR-008:

| Underlying | Contract | Expiry | Strike | Bid | Ask | Delta | Delta source | Cash use | Max loss |
|---|---|---|---:|---:|---:|---:|---|---:|---:|
| LRCX | LRCX260918P00270000 | 2026-09-18 | $270.00 | $1.80 | $2.15 | -0.1043 | Black–Scholes from chain IV | $27,000.00 | $26,820.00 |

The draft is stored at
`paper/tickets/2026-09-05-options-dry-run.csv`. It is paper-only and was not
submitted anywhere.

CIEN, TXN, ON, and AAPL had no contract that simultaneously fit remaining
cash/notional, delta, bid, and spread constraints. Aggregate CSP cash usage was
$27,000.00, below both available cash and the 20% model-equity cap of
$54,626.47. Aggregate calculated maximum loss was $26,820.00.

## Gate-scale feasibility

The historical model equity is above the future Gate range. If the same
2026-09-04 weights are statically scaled to $50,000 or $100,000, the largest
HPQ position is only 28 or 57 whole shares, so neither Gate size can write a
covered call. The LRCX put also exceeds the respective 20% CSP caps. Therefore
this CSV proves the P3 calculation and selection path only; it does not prove
that the owner account can or should place an option order.

Formal P3 completion still requires the owner-authored `docs/why/P3.md` and an
account-selected current-holdings run if the owner wants the literal DoD rather
than this historical model demonstration.
