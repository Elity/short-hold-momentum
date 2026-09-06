# ADR-011 — v0.3 known-history research and independent paper validation

- Status: Accepted by owner request, 2026-09-06
- Authority: Owner explicitly requested implementation of SPEC-SHM-001 v0.3.
- Spec: ../spec-v0.3.md

The objective is net CAGR above SPY and a smaller absolute maximum drawdown. A 10% drawdown raises a review event rather than forcing liquidation. Continuous holdings have no fixed age limit.

Preserve V04, its 48-name derived universe, existing paper ledger, and all three historical OOS unlocks. v0.3 uses the unchanged owner universe with contemporaneous 260-session eligibility. It has a separate closed set C0–C4 and a separate known-history research ledger. Permission to review data through 2026-09-04 does not create fresh out-of-sample evidence or reset any old budget.

This version supersedes the v0.2 month holding claim, relative-Sharpe-only gate, fixed development-period eligibility for the new version, and mandatory 10% liquidation. It also supersedes the missing-price liquidation assumption only for v0.3: no synthetic previous-close liquidation is permitted.

Only a qualifying candidate may be frozen and initialized in the independent paper account. A no-winner result is a valid completed research outcome. No live brokerage order is authorized. The local next-open model with 10/25 bps costs remains simulated execution, not observed broker cost evidence.
