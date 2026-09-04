# S&P 500 historical-membership reference spot check

- Source: [`fja05680/sp500`](https://github.com/fja05680/sp500)
- Upstream commit: `c31ac3cc56f28cf9a02b4e694eff7ceab596a0ff`
- Source file: `S&P 500 Historical Components & Changes (Updated).csv`
- Local file: `data/reference/sp500_history.csv`
- SHA-256: `39a9202c9ef69a74c0ff07e2113ad41fb6da7c8c5b6cd9541f0185fb4391e717`
- Snapshot coverage in this copy: 1996-01-02 through 2026-06-30

The check compares five rows from the upstream
`sp500_changes_since_2019.csv` ledger with the membership snapshot immediately
before the effective date and the snapshot on the effective date. Every added
ticker must move from absent to present; every removed ticker must move from
present to absent.

| Effective date | Previous snapshot | Added | Removed | Result |
|---|---|---|---|---|
| 2019-01-18 | 2019-01-11 | TFX | PCG | PASS |
| 2020-12-21 | 2020-11-17 | TSLA | AIV | PASS |
| 2022-06-21 | 2022-06-09 | ON, KDP | IPGP, UA, UAA | PASS |
| 2023-12-18 | 2023-10-18 | UBER, JBL, BLDR | SEE, ALK, SEDG | PASS |
| 2024-06-24 | 2024-05-08 | GDDY, CRWD, KKR | ILMN, CMA, RHI | PASS |

This is a source-integrity spot check, not an independent audit of S&P Dow
Jones Indices announcements. CHK-02 will use the reference only as specified,
never as the strategy's selection universe.

