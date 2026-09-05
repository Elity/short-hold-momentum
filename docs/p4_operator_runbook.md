# P4 paper operator runbook

This workflow is offline and never submits an order. The owner must first pick
Alpaca paper or an existing broker's simulation account and export its latest
confirmed state to a local JSON file that is not committed:

```json
{
  "mode": "paper",
  "cash": 100000.0,
  "positions": {
    "HPQ": 50
  }
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
are identical; it will not overwrite a changed ticket.

The ticket is a draft. Submit it manually in the chosen simulation account or
through a separately reviewed paper-only adapter. On the next XNYS session,
record confirmed fills in `paper/fills/YYYY-MM-DD.csv` using:

```text
ticker,qty,fill_price,fill_time,official_open
```

An optional trailing `commission` column is supported. Never infer fills from
the ticket. Update the next account snapshot only from confirmed fills, then use
the paper accounting and monthly-report APIs in `shm.paper` for cost and
paper-versus-model attribution.

The forward-test start is the first real paper-account snapshot. Do not backfill
it to the P2 OOS period. Three completed rebalance/fill cycles and three observed
monthly reports are still required before P4 can pass.
