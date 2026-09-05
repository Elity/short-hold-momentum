# ADR-003 — Handle unavailable t+1 opening prices

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Trigger: V04 failed because PIT holding `ANDV` had no 2018-10-02 open after its acquisition and delisting.

## Decision

Do not use t+1 availability to change the signal formed at t. At execution:

- skip a new entry when its t+1 open is unavailable and retain the allocation
  as cash;
- force an existing holding with an unavailable t+1 open to exit at its most
  recent valid close;
- record each fallback and surface its count in CHK-07.

This conservative rule keeps signal construction free of lookahead while
allowing historical-universe checks to survive mergers and delistings.
