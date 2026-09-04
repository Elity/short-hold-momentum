# P1 data preflight — 2026-09-04

## Owner universe

- Frozen tickers supplied by owner: 84
- Active after the owner's approval to include `MSFT`: 84
- Benchmark added separately: `SPY`
- Core download failures after cache replay: 0 / 85 (84 owner tickers + `SPY`)
- Development-period cache range: 2003-12-19 through 2018-12-31

Nine owner tickers have no observations in the development period because
their public listings begin after 2018: `APP`, `BILL`, `CRWD`, `DDOG`, `NET`,
`PATH`, `PLTR`, `SNOW`, and `ZM`. They remain frozen in the owner universe and
are automatically ineligible during the development backtest.

Across the 177 scheduled development-period rebalances, the owner universe has
29–47 eligible stocks. Four rebalance dates are below the configured minimum of
30, so V00 will be `INCONCLUSIVE` unless the owner changes the frozen universe.
This is an expected status, not a runtime failure.

## CHK-02 point-in-time reference

- Unique S&P 500 symbols observed during 2005–2018: 826
- Additional PIT symbols requested from yfinance: 781
- Technical download failures after cache replay: 0
- Parquet files currently available across core and PIT symbols: 547
- Mean PIT membership coverage on the 177 rebalance dates: 69.02%

Coverage is measured point-in-time: a member counts only when its cache has a
price on that rebalance date. Because coverage is below the required 80%,
CHK-02 will report `INCONCLUSIVE`. The missing history is concentrated in
delisted and renamed symbols that Yahoo no longer serves under their historical
identifiers.
