# ADR-012 — Verified current S&P 500 universe and fixed-rule expansion study

- Status: Accepted by owner request on 2026-09-06.
- Spec: ../spec-v0.4.md
- Owner request: adjust the stock universe before deployment; ensure the latest S&P 500 constituents.

Use daily issuer SPY equity holdings cross-checked with the public S&P 500 constituent table for forward membership. Save dated, hashed snapshots, identities and changes; prohibit new risk on stale or conflicting sources. This is verified daily public information, not a real-time licensed index feed.

Research uses historical membership and unchanged C0-C4 rules. Current-list survivorship shortcuts and polluted historical prices cannot qualify a strategy. Keep all v0.2/v0.3 evidence and accounts intact. Deploy data and display capabilities even if research has no qualifying winner; never invent a winner or start an unqualified account.

The source code and immutable image publication needed for this explicitly authorized NAS deployment are in scope. Preserve the live SQLite 07:30 schedule, take a stopped-service backup, and retain the previous immutable image for rollback. No real-money orders are authorized.
