# ADR-016 — Fixed-rule observation account before historical qualification

- Status: Accepted for implementation,2026-09-07.
- Authority: After discussion of an explicitly unvalidated observation account,
  the owner instructed: “那你奔着能让模拟账户启动的目标去执行吧，有两个条件：1. 不要过拟合 2. 不要拉长战线导致偏离核心目标越来越远”.

Allow one explicitly configured S500-C3 observation account to start without a
historically qualifying winner. C3 is the already preregistered profit-protection
hypothesis from the owner-approved v0.3 plan; it is not selected from historical
performance rankings. Freeze its existing configuration,10/25bps model costs and
calendar. No parameter search,new candidate,data repair or historical rerun is
part of this change.

The launch definition lives in `config/v04/observation.json`,never `winner.json`.
The independent100k paper ledger retains `account_mode=observation` and an
immutable authorization hash. Qualified-account initialization still requires
the original winner file. An observation account cannot silently become a
qualified account or replace an existing ledger.

Initialize now in cash; make the first trading decision on the next fixed
selection date after authorization,then simulate the next actual opening.
No retrospective signal or fill is created. Until that date the account exists
and daily automation records its waiting state. Current expected first signal
is2026-09-17,possible first modeled opening2026-09-18,subject to the unchanged
market,eligibility and source-quality checks.

Historical research remains INCONCLUSIVE and its evidence files remain intact.
Observation permission is not historical qualification. Current constituent and
price freshness,nominal eligibility,budget,long-only limits,ATR exits,pending
orders,model costs and missing-data behavior remain unchanged. Daily automation
processes the observation ledger and creates complete-month reports once its
forward observation period begins. No option execution or live brokerage is
added;option premiums remain outside account returns.

The dashboard and monthly reports explicitly label the account as observation,
not historically qualified. Short-period cumulative and same-period SPY results
remain separate from historical diagnostics. Three cycles/three monthly reports
measure operation;12-month forward evaluation retains its original definition
and never retroactively changes historical qualification.

This supersedes only the historical-winner prerequisite for explicitly authorized
observation simulation. It does not weaken research promotion or authorize live
trading. Existing V04 accounts,other configurations and OOS records remain intact.
