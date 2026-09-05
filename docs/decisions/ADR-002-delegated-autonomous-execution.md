# ADR-002 — Delegate project execution and checkpoints

- Status: Accepted
- Date: 2026-09-05
- Owner instruction: “后面都不需要我批准了吧，无论是阶段结束还是需要 commit，都授权你自己执行到底”

## Decision

The owner delegates future phase transitions, experiment-batch approvals,
repository staging, and commits for this project to the agent. The agent may
continue through the remaining specification without pausing solely for an
owner approval or commit action.

## Boundaries

- The delegation applies only to `/Users/fighting/code/short-hold-momentum`.
- Experiment preregistration, variant limits, OOS unlock records, and audit
  trails remain mandatory.
- The delegation does not permit paid services, secrets in the repository,
  live brokerage orders, or real-money trading. INV-09 remains unchanged.
- Material deviations must still be recorded transparently in an ADR.
