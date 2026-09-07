# Short-Hold Momentum

An auditable research implementation of `SPEC-SHM-001` for a long-only,
fixed-universe US equity momentum strategy. This repository is engineering
infrastructure, not investment advice.

## Current phase

### Verified S&P 500 expansion (v0.4)

The cross-industry profiles are `S500-C0` through `S500-C4`. Their trading rules
are unchanged; only the universe policy changes. Current membership comes from
dated State Street SPY equity holdings cross-checked against Wikipedia, with
CIK/security identities, source hashes and immutable change snapshots. Both
source and verification age must be no more than one completed trading session;
stale or conflicting evidence prohibits new risk. This is a verified daily
public snapshot, not a real-time licensed index feed.

```bash
uv run --no-sync shm sp500-refresh --repo-root .
uv run --no-sync shm market-refresh-sp500 --repo-root .
uv run --no-sync shm research-v04 --repo-root .
```

The enabled `config/sp500.yaml` routes daily downloads through one serial,
rate-limited queue instead of the legacy downloader. Existing current caches
need no request; overlap checks, archived repairs, persistent provider-call
budgets and global 429/Retry-After pauses prevent retry storms. The previous
V04's required prices share this queue. Current source and price completeness
are separate gates shown on the dashboard.

The new historical study uses historical members, never today's winners
retroactively. Incomplete membership or corrupted historical quotes makes
results inconclusive and blocks winner/account creation. v0.2/v0.3 records and
accounts remain separately accessible. See `docs/spec-v0.4.md` and ADR-012.

Detailed parquet/decision traces, raw cache backups and queue state are local
artifacts rather than source files; published reports retain snapshot hashes
and the reproducible commands. Container upgrades add missing versioned assets
without replacing existing account evidence or the SQLite schedule.

### Fixed-rule trend exits (v0.3)

SPEC v0.3 adds a separate, closed C0–C4 study and version-isolated paper runtime.
Its objective is net CAGR above SPY and a smaller maximum drawdown at both
10 and 25 bps costs. A 10% drawdown triggers a review, not forced liquidation;
there is no maximum holding-age exit. See `docs/spec-v0.3.md` and ADR-011.

```bash
uv run --no-sync shm research-v03 --repo-root .
```

This reads the existing adjusted-price caches through 2026-09-04 and records
**known-history research**, never a fresh OOS test. It preserves the old OOS
ledger. Results are in `reports/v03/selection.json` and its referenced report.
Only a candidate meeting both cost-scenario gates creates
`config/v03/winner.json`; no qualifying candidate means no new account.

For a frozen winner, replace `C3` below with its actual id:

```bash
uv run --no-sync shm paper init-v03 --strategy-id C3 --repo-root .
uv run --no-sync shm paper daily-decision --strategy-id C3 --repo-root .
uv run --no-sync shm paper status-v03 --strategy-id C3 --repo-root .
```

The existing daily service automatically initializes and advances a frozen
winner. Independent 10/25 bps books, daily decisions, monthly reports and 10%
drawdown reviews live under `paper/v03/<candidate>/`. No historical dates can
be backfilled as timely forward decisions. The dashboard defaults to V04 and
also exposes C0–C4, clearly separating historical screening from forward
performance. A candidate without a paper account has no displayed account NAV.
The next-open fills and model costs do not establish broker execution costs.

### Preserved v0.2 baseline

P2 research has passed KR2. The three frozen OOS candidates were run in the
precommitted order, exhausting the `3/3` OOS budget: V04 and V08 passed, while
V02 missed the strict SPY Sharpe comparison. V04 (`params_hash` `2064365d`) is
frozen in `config/params.frozen.yaml`; detailed evidence is in
`docs/p2_development_results.md`.

The P3 technical deliverables and the P4 local paper workflow are implemented.
P4 starts from the $100,000 all-cash snapshot dated 2026-09-05 and remains at
`0/3` completed rebalance/fill cycles and `0/3` monthly reports; the first
eligible signal date is 2026-09-17. Check the machine-readable state with
`uv run shm paper status --repo-root .` and follow
`docs/p4_operator_runbook.md` for manual operation.

Gate is not available yet. It still requires the genuine forward P4 evidence,
owner-authored `docs/why/P1.md` through `P4.md`, resolution of ADR-010's
deterministic zero-bps execution-cost limitation, and an owner-created
`config/live.yaml`.

## Bootstrap

```bash
uv sync --locked
uv run shm config validate --config-dir config
uv run shm config validate --config-dir config --require-universe
uv run shm data update
uv run pytest
```

The project is pinned to Python 3.12 because the open-source vectorbt/numba
stack does not yet support every Python 3.13 combination consistently.

## Container service

The published image is `ghcr.io/elity/short-hold-momentum:latest`. It runs a
small dashboard and a persistent scheduler around the existing P4 commands.
All mutable repository artifacts and the SQLite run database live under
`/var/lib/shm`, so replacing the container does not discard paper evidence or
run history.

```bash
mkdir -p runtime
docker compose up -d
```

The dashboard is exposed on port `9022` by default. Override deployment values
without editing the compose file:

```bash
SHM_WEB_PORT=9081 SHM_DATA_DIR=/srv/short-hold-momentum docker compose up -d
```

The dashboard shows total assets, cash, current positions, weighted cost,
unrealized and realized P&L, an equity curve with an equal-start SPY reference,
trade history, saved monthly/option reports, and the next rebalance date.
It reads the existing paper ledger; there are no demo balances in the service.
Missing prices or cost evidence are shown as unavailable instead of zero.

Run history shows the last 90 days of successful, failed and active runs,
with the actual step output and retry attempts. New runs also record steps
skipped because they are not due. Older database history is retained.
The daily check time can be changed in the page and is stored in SQLite.
Each run makes up to three attempts with a five-minute delay.
The preserved V04 stock strategy still makes decisions only on its 20-session rebalance
dates and simulates execution at the next session's open after that session
has closed. The page refreshes its read-only data every 30 seconds.

Dashboard test cases and browser acceptance commands are documented in
`docs/dashboard_acceptance.md`. Browser tests use a temporary isolated account
and never start its scheduler:

```bash
npm ci
npx playwright install chromium
npm run test:browser
```

Forward evidence remains date-safe: a failed run can be retried only while its
recorded XNYS session is still the latest completed session. After a newer
market close, use **Run now** to reconcile the current session; the service
will not backfill a missed ticket, fill, or option overlay with later data.

## Owner checkpoint

The frozen universe came directly from the owner. Changes to
`config/universe.yaml` remain owner-only. Validate it with:

```bash
uv run shm config validate --config-dir config --require-universe
```

V00 was run from commit `c6059f4`:

```bash
uv run shm backtest run --prereg experiments/prereg/V00.md
```

The generated report is `reports/20260904-220347-109e68bf.md`.

After freezing an OOS candidate and prediction, refresh the cache and run the
audited sample-out evaluation explicitly:

```bash
uv run shm data update --through-oos
uv run shm backtest run --prereg experiments/prereg/V04.md \
  --unlock-oos --reason "Run frozen P2 candidate V04 under ADR-002"
```

Each OOS invocation consumes one of the three unlock records in
`experiments/oos_unlocks.jsonl` and reports the KR2 result separately from the
run-quality status.
