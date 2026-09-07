# ADR-015: Reviewed extreme prices and inherited ATR stops

Date: 2026-09-07

Status: Implemented under the owner's standing authorization to investigate,
repair, validate and deploy the SHM paper system autonomously. This changes data
verification and fixes an existing exit rule; it adds no strategy candidate or
parameter search.

## Problem

The historical price check flags held returns larger than 50%. That is useful
for detecting a wrong security or a split-unit error, but a real market crash is
not a bad quote. APA's March 9, 2020 close-to-close loss is corroborated by two
dated Yahoo captures with matching nominal OHLCV and contemporary oil-crash
reporting. The two captures share an upstream source; they are not independent
vendors. Deleting this observation or its loss would bias the research.

A separate bug appeared during successor-security warmup. After a merger, an
existing ATR stop can be validly carried to the successor's units even though
the successor has fewer than 20 true ranges. The close evaluator previously
checked the inherited stop only when a new ATR was available.

## Decision

Keep the raw 50% observation threshold and every return unchanged. A v0.4
manifest review may identify exactly one ticker, date, quote window and expected
return, bound to the actual loaded price file and evidence SHA-256. The return
comparison uses fixed absolute tolerance 1e-10, no relative tolerance. A stale,
missing or mismatched review does not approve the event. Rejected registrations
and all original large observations remain in the result payload.

Only an exactly matched, reviewed market move is excluded from the unverified
bad-price subset used by `HOLDING_PRICE_JUMPS`. The report and detailed warnings
retain `VERIFIED_LARGE_MARKET_MOVE` and the full loss. Other data, signal and
performance gates are unaffected; default v0.3 review behavior is unchanged.

Check an existing ATR trailing stop against the current close even when today's
ATR cannot be computed. In that situation do not move the stop, invent an ATR,
or enable buying. Retain the missing-ATR warning and new-risk restriction.
Execute any resulting exit at the next available opening price, including gaps.

## Verification and limits

Focused tests cover preservation of the loss and warning, stale input/evidence,
inactive price sources, wrong ticker/date/quote window/return, and no review.
The inherited-stop regression uses short successor history and verifies a
next-open sale below the stop. A missing signal still fails `SIGNAL_DATA`.

These repairs do not establish full historical data coverage, a research winner
or readiness to fund an S500 simulation. S500-C0 through C4, cutoff 2026-09-04,
10/25 bps costs and winner selection remain frozen. The study must be rerun on
the updated snapshot; existing reports and old V04 records remain preserved.
