# ADR-004 — Separate run status from hypothesis verdict

- Status: Accepted under ADR-002 delegation
- Date: 2026-09-05
- Trigger: V01-V11 reports mapped every `INCONCLUSIVE` run status directly to
  an `无法判定` hypothesis verdict instead of applying the frozen prereg rule.

## Decision

Run quality status and hypothesis verdict are independent fields. Preserve all
recorded metrics, checks, and statuses. Adjudicate V01-V11 mechanically against
their preregistered thresholds, correct only the `verdict` field in the JSONL
and Markdown reports, and publish the complete calculation in
`docs/p2_development_results.md`.

Future OOS runs will calculate KR2 separately from the quality status. A KR2
pass still requires an eligible status from the specification; a favorable
metric comparison cannot override `INCONCLUSIVE` or `FAIL`.

## Impact

- No run is repeated and no additional variant budget is consumed.
- No metric, check result, status, preregistered threshold, or OOS choice is
  changed after seeing OOS data.
- V04, V08, and V02 are selected before the first OOS unlock.
