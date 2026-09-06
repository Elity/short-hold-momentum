# Owner phase notes

`P1.md` through `P4.md` are written by the owner at the corresponding human
checkpoints. Agent-generated substitutes do not satisfy the specification.

ADR-001 allowed work to continue without `P1.md`, and ADR-002 delegated phase
transitions and approvals. Neither decision removes the Gate requirement for
all four owner-authored notes.

## What each note must answer

- `P1.md`: What the system does, why its signal/risk/execution design is
  reasonable, and what the V00 result means. Use the V00 report under
  `reports/` as evidence.
- `P2.md`: Which registered hypotheses were supported, refuted, or remained
  inconclusive; why V04 was frozen; and what the three OOS results do and do
  not prove. Use `docs/p2_development_results.md`.
- `P3.md`: Why most holdings cannot support a covered call at the intended
  account size, why the option overlay remains optional, and which risks or
  approximations the owner accepts. Use `docs/options_overlay_rulebook.md` and
  `reports/20260905-p3-options-dry-run.md`.
- `P4.md`: After three genuine cycles and three monthly reports, explain the
  observed paper/model gap, execution costs, skipped positions, and whether
  ADR-010's deterministic official-open simulation is acceptable for Gate.
  Do not write this conclusion before the forward evidence exists.

Each file should be roughly one page in the owner's own words. It may link to
repository evidence, but copying an agent-generated summary does not satisfy
the learning checkpoint.

## Agent-prepared review drafts

At the owner's request, review drafts are available under `docs/why/drafts/`:

- `P1.md`: system design, design rationale, and the V00 baseline.
- `P2.md`: the closed V01-V11 experiment set, frozen V04 decision, and OOS
  evidence boundaries.
- `P3.md`: option-overlay feasibility, optionality, risks, and accepted
  engineering approximations.

These drafts deliberately live outside the final `docs/why/P1.md` through
`P3.md` paths, so the automated Gate audit cannot mistake them for completed
owner checkpoints. The owner must review the cited evidence, rewrite or add
their own reasoning, and then save the final versions at those required paths.
`P4.md` is not drafted before three genuine forward cycles and three monthly
reports exist.
