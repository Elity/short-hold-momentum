# ADR-007 — Estimate missing option delta without paid data

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Trigger: yfinance option chains normally expose implied volatility but not
  contract delta, while the P3 CC and CSP rules require delta thresholds.

## Decision

Use a chain-provided delta when one exists. Otherwise estimate delta from the
same delayed chain's implied volatility with a local Black–Scholes calculation
using calendar days / 365, risk-free rate 0, and dividend yield 0 unless the
caller explicitly supplies different values.

- For covered calls, if neither delta nor usable implied volatility exists,
  apply the specification's explicit fallback and choose the lowest strike at
  least 5% out of the money, subject to the bid and spread rules.
- For cash-secured puts, do not invent an OTM fallback. Skip the candidate when
  neither chain delta nor a calculable implied-volatility delta exists.
- Among affordable CSP contracts with absolute delta at most 0.25, choose the
  highest strike, interpreted as the closest-to-money qualifying contract.
- CSP quote-quality thresholds are intentionally outside this delta decision;
  ADR-008 records the later liquidity decision prompted by the first dry run.

## Consequences

The estimate is only a deterministic contract-selection aid; it is not a
pricing model or an execution price. The delayed quote, zero-rate/zero-dividend
defaults, and model delta source must remain visible in paper tickets and P4
attribution. This decision adds no paid data and authorizes no broker call or
live order.
