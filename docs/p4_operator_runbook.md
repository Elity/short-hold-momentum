# P4 paper operator runbook

This workflow is offline and never submits an order. ADR-010 selects the local
simulator with $100,000 initial cash. Its initial tracked snapshot is
`paper/accounts/2026-09-05.json`:

```json
{
  "mode": "paper",
  "cash": 100000.0,
  "positions": {}
}
```

After the selected XNYS rebalance session has closed and the local daily caches
contain that completed date, generate the six-column ticket with:

```sh
uv run shm paper rebalance \
  --repo-root . \
  --account /absolute/path/to/paper-account.json \
  --as-of YYYY-MM-DD
```

The command loads `config/params.frozen.yaml`, verifies the P2 parameter and
universe hashes, restricts reads to the latest 260 XNYS sessions, and writes
`paper/tickets/YYYY-MM-DD.csv`. A same-date rerun is allowed only when the bytes
are identical; it will not overwrite a changed ticket. It also records the
content-addressed input snapshot in `data/snapshots/manifest.json` and appends
one idempotent `mode: paper` audit row to `experiments/log.jsonl`. That row
contains ticket diagnostics only—never a 2019-to-date performance metric.

The ticket is a draft. For the ADR-010 local simulator, wait until the next XNYS
session is complete, then fill stock MOO/OPG tickets at that session's official
open using the local cache. These fills have zero commission and are simulated,
not observed broker execution. The resulting file uses:

```text
ticker,qty,fill_price,fill_time,official_open
```

An optional trailing `commission` column is supported. Never infer fills from
an external paper broker's ticket. For local simulated fills, write the next
account snapshot with:

```sh
uv run shm paper simulate-fills \
  --repo-root . \
  --account paper/accounts/YYYY-MM-DD.json \
  --signal-date YYYY-MM-DD \
  --output-account paper/accounts/NEXT-SESSION.json
```

The command refuses to run before the next XNYS session is complete and only
accepts stock `market_on_open` / `opg` tickets. For externally confirmed fills,
use:

```sh
uv run shm paper ingest-fills \
  --repo-root . \
  --account /absolute/path/to/account-before.json \
  --tickets paper/tickets/YYYY-MM-DD.csv \
  --fills paper/fills/YYYY-MM-DD.csv \
  --output-account /absolute/path/to/account-after.json
```

The command rejects fills without a matching ticket, overfills, uncovered
sells, and any purchase that would make cash negative. It reports realized
cost against the official open and updates the next account snapshot only from
confirmed fills. After an XNYS calendar month has fully closed, generate the
forward-only paper-versus-model report with:

```sh
uv run shm paper monthly-report \
  --repo-root . \
  --month YYYY-MM
```

The report starts from `forward_test_start`, carries positions and model signals
across month boundaries, and writes `reports/paper-YYYY-MM.md`. It rejects the
current or a future month until its final XNYS session has closed, and it never
uses account snapshots, fills, or model signals before 2026-09-05.

The forward-test start is the first real paper-account snapshot. Do not backfill
it to the P2 OOS period. Three completed rebalance/fill cycles and three observed
monthly reports are still required before P4 can pass.
