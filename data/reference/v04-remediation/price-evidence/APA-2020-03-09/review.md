# APA 2020-03-09: reviewed real market loss

The close-to-close loss of -53.864734116116% is retained in full. No quote,
trade, strategy rule, return or 50% observation threshold is changed. This record
marks only this exact hash-pinned observation as reviewed; every other large move
still requires its own evidence. It does not clear other correctness/data gates.

## Evidence and reproducible comparison

The archived Yahoo capture in Kaggle `sheepb/stock-market-dataset-20002021`,
version 1 (updated 2021-08-25), independently preserves an older capture date,
but shares the Yahoo upstream with the current 2026 cache. It is **not a second
independent vendor**. Archive and extraction hashes are recorded in `audit.json`.
Nominal current OHLC is reconstructed using each day's stored
`close / as_traded_close` factor. All eight OHLC values agree within floating-point
precision (less than 1e-10 dollars), and both volumes agree exactly:

| Date | Open | High | Low | Close | Volume |
|---|---:|---:|---:|---:|---:|
| 2020-03-06 | 23.42 | 23.51 | 20.22 | 20.70 | 10,198,100 |
| 2020-03-09 | 13.42 | 13.70 | 9.32 | 9.55 | 28,073,200 |

The as-traded unit is continuous across these two dates. The stored adjusted
return is -0.5386473411611574; numerical rounding of the nominal closes is
not used to replace it. Source rows and exact comparisons are kept beside this
report. The raw cache SHA-256 is `1036439f6901350d93828680c6623dec06df0efb3ff2f7f8bcd26bfee67a02b1`.

The contemporaneous Schaeffers article reports APA down 41.06% to $12.20 at
midday on March 9; Reuters/Nasdaq describes the oil-price-war selloff. Their
captured contents corroborate the economic event, not the exact closing bar.
These sources and the two agreeing dated captures support treating the observed
loss as a real market extreme. This is not an official exhaustive corporate-
action ledger or an exchange-certified OHLCV record.

## Review decision

Register only `APA / 2020-03-09 / close_to_close` against the exact input and
this evidence hash. The raw >50% observation, loss and visible
`VERIFIED_LARGE_MARKET_MOVE` warning remain. A changed input hash, evidence hash,
quote window, ticker, date or return invalidates this registration. Reviewed
market losses do not independently fail the bad-price gate; unreviewed moves
continue to fail it. The historical data is already observed research, not OOS.

## Supporting file hashes

- `2021-capture.csv`: `658c7fdf6a66f1a0a5b95374524471b8518b91ceaa7ab30bb76f86bf3a4b77b2`
- `APA-nasdaq-reuters-market-context.source.json`: `130a44a73c947fbe0baff3f4a9a109f301cfa470731ef88a7d7242c03191ddd0`
- `APA-schaeffers-contemporaneous-intraday.source.json`: `f74a1596fea1e1d8922813788f0c5895d189431dda627d0f2f6a93ae301ef73b`
- `archive-download.json`: `ca52947426ff0ddd9e673a10e63ccca8cd5aa338dfe616b1262b994347ce8c95`
- `audit.json`: `0b58d16334a3fb6f6572dbf5468b190d57106519781cad29c1181a81c3d7c87a`
- `current-capture.csv`: `2bff0f84e6745313b295210bbc308b1057ad7555a44c1198548292f643922d41`
