# P2 development-period results

The V01-V11 closed set was evaluated against the rules written in each prereg
before any OOS data was read. Run `status` and hypothesis `verdict` are separate:
all runs remain `INCONCLUSIVE` because CHK-02 coverage was 69% and CHK-07 could
not reach its second source, while the verdict below applies only the frozen
hypothesis threshold to the recorded 10 bps metrics.

| ID | Sharpe | CAGR | MaxDD | Turnover | Verdict | OOS |
|---|---:|---:|---:|---:|---|---|
| V01 | 0.295 | 3.39% | -26.53% | 286.65% | Refuted | No |
| V02 | 0.432 | 5.38% | -22.40% | 237.98% | Supported | Selected 3 |
| V03 | 0.369 | 4.46% | -22.31% | 260.53% | Inconclusive | No |
| V04 | 0.531 | 7.05% | -24.65% | 318.34% | Supported | Selected 1 |
| V05 | 0.404 | 5.16% | -26.61% | 261.54% | Inconclusive | No |
| V06 | 0.313 | 3.55% | -25.31% | 283.04% | Refuted | No |
| V07 | 0.346 | 3.12% | -18.56% | 196.19% | Supported | No; same parameter axis as V08 |
| V08 | 0.449 | 6.46% | -25.18% | 263.33% | Supported | Selected 2 |
| V09 | 0.409 | 5.13% | -25.61% | 266.61% | Inconclusive | No |
| V10 | 0.397 | 4.91% | -24.39% | 260.75% | Inconclusive | No |
| V11 | 0.314 | 3.62% | -23.94% | 266.52% | Refuted | No |

## Frozen OOS selection

1. V04 is the only development candidate whose 10 bps Sharpe already exceeds
   SPY while its absolute MaxDD is smaller.
2. V08 is the strongest return-oriented reserve and represents the higher-vol
   side of the volatility-target axis.
3. V02 is the diversification reserve with the shallowest drawdown of the
   remaining non-volatility candidates.

V07 is not selected because V08 already represents the same parameter key and
has materially higher Sharpe and CAGR. The selection order and predictions are
frozen before the first OOS unlock.

ADR-004 records why the generated report/log verdict fields were corrected
after the batch without changing metrics, checks, status, or candidate order.

## OOS results

All three candidates used the frozen 2019-01-01 through 2026-09-04 interval,
10 bps default cost, the same universe hash, and snapshot `24442fa7d1a43680`.
The three audited unlocks exhaust the P2 OOS budget.

| Rank | ID | Sharpe | SPY Sharpe | CAGR | MaxDD | Status | KR2 |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | V04 | 0.926 | 0.900 | 14.03% | -15.11% | WARN | PASS |
| 2 | V08 | 0.911 | 0.900 | 17.00% | -16.87% | WARN | PASS |
| 3 | V02 | 0.893 | 0.900 | 13.21% | -12.89% | WARN | FAIL |

V04 is frozen as the P2 winner. It preserves the pre-OOS priority order and
has the highest OOS Sharpe and shallower drawdown than V08. V08 also passes KR2
but is not selected for the frozen production parameters. V02 misses KR2 only
because its Sharpe is 0.007 below SPY.

The WARN status is not hidden: V04 and V08 trigger survivorship and one-year
dependency warnings; V02 triggers the one-year warning. CHK-07 passes using the
latest three complete common SPY years, and PIT coverage is 92.07%.
