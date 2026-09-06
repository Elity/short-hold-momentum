# Investment dashboard acceptance

The dashboard reads the existing paper account, tickets, fills, price caches,
reports and SQLite run database. It does not change stock selection or the
20-session rebalance schedule. Dates in fixtures are synthetic and are never
copied into the NAS runtime.

| Case | Coverage | Expected result |
| --- | --- | --- |
| D01 | Initial cash account | No invented positions, fills, daily return or monthly report |
| D02 | Buy, partial sell and commissions | Weighted cost, realized P&L, unrealized P&L and total assets reconcile |
| D03 | Price freshness | Future prices excluded; missing latest close produces unknown values and a visible warning |
| D04 | Ledger mismatch | Incomplete cost basis is marked unavailable rather than guessed |
| D05 | Reports | Saved monthly and option reports can be opened; arbitrary filesystem paths cannot |
| D06 | Run history | Actual success/failure/skip steps, timestamps, attempts and output are visible |
| D07 | Schedule settings | A valid HH:MM persists in SQLite; invalid/cross-origin writes are rejected |
| D08 | Browser with populated ledger | Navigation, chart, position/trade details, filters, export and reports work |
| D09 | Browser safety and layout | Report/log text cannot execute HTML; desktop and narrow mobile pages fit |
| D10 | NAS acceptance | Open the deployed URL, compare UI with live API, inspect actual logs and save/reload/restore schedule |

Run backend tests with `uv run pytest`. Run the isolated browser cases with
`npm ci`, `npx playwright install chromium`, and `npm run test:browser`.
The browser fixture starts an HTTP server without starting a scheduler.

For deployed acceptance:

```sh
SHM_BROWSER_URL=http://192.168.2.3:9022 \
SHM_TEST_SETTINGS=1 npm run test:browser
```

The schedule acceptance case restores the original time in a `finally` block.
It never triggers trades or populates the real account with fixture data.
Set `SHM_BROWSER_ARTIFACTS` to choose the screenshot and result directory.

Run history defaults to the last 90 days in the UI. Existing database history
is retained; the dashboard does not delete trading evidence.
