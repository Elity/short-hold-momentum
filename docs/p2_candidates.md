# P2 development-period candidate set

Baseline: V00 (`20260904-220347-109e68bf`), Sharpe 0.385, CAGR 4.75%,
MaxDD -24.51%, annual turnover 261.57%, average exposure 64.47%.

All candidates are one-factor-at-a-time changes from V00 and use only the
2005–2018 development period. The set is closed before any P2 run. The runner
applies and validates the single preregistered `params.yaml` change at runtime,
so the baseline configuration file remains frozen.

All three batches are approved under the owner delegation recorded in ADR-002.

| Batch | ID | Parameter | V00 | Candidate | Hash |
|---:|---|---|---:|---:|---|
| 1 | V01 | `signal.top_n` | 15 | 10 | `3e1707dd` |
| 1 | V02 | `signal.top_n` | 15 | 20 | `f6a1a45c` |
| 1 | V03 | `signal.skip_trading_days` | 21 | 0 | `bf0ab3bd` |
| 1 | V04 | `signal.lookback_trading_days` | 252 | 126 | `2064365d` |
| 1 | V05 | `risk.trend_filter.off_exposure` | 0.0 | 0.5 | `73a4c3cd` |
| 2 | V06 | `risk.trend_filter.sma_days` | 200 | 100 | `7405237b` |
| 2 | V07 | `risk.vol_target.target_annual_vol` | 0.15 | 0.10 | `9d06d7ca` |
| 2 | V08 | `risk.vol_target.target_annual_vol` | 0.15 | 0.20 | `a073556a` |
| 2 | V09 | `eligibility.min_adv_usd` | 10,000,000 | 5,000,000 | `d87fb494` |
| 2 | V10 | `eligibility.min_adv_usd` | 10,000,000 | 20,000,000 | `d4f7d97d` |
| 3 | V11 | `eligibility.min_price_usd` | 5.0 | 10.0 | `77db835a` |

The suggested rebalance-frequency variant is deferred. It changes
`config/dates.yaml`, requires HC-03, and the current specification's
`params_hash` excludes that value, so it cannot yet consume the variant budget
correctly.
