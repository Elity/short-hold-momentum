# TWTR application review

The root review accepts the proposal in `evidence.md` for the frozen v0.4
research inputs. The original proposal and its work-directory-relative audit
paths are retained as provenance. The following repository-relative application
map resolves the promoted files; the raw CSV is now included with the evidence:

- `candidate_path`: `data/research/v04/prices/TWTR-history-repaired.parquet`; SHA-256 `82f441e0b680ecb153c110caf2bae516e38a89e2fa2480dad983ec7c39eebe4e`.
- `downloaded_source_path`: `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/downloaded-source.csv`; SHA-256 `db416326855cad38b07d6830718c599822b2389741d1042179003d5194966631`.
- `original_runtime_path`: `data/research/v04/prices/TWTR.parquet`; SHA-256 `bb765a9fa4587292625ceb4efdf376e67c3d40b1ac2cd85a93fbfa37f952710c`.

The 1,102 original WIKI rows remain unchanged. The complete 2,259-session series
ends at the observed 2022-10-27 quote; the registered cash event is processed on
2022-10-28. Default consideration is $54.20 per actual share. Cash becomes usable
on 2022-11-04 under the unchanged ADR014 model, not observed brokerage timing.
No artificial October 28 price or duplicate cash return is introduced.

The whole-row 2021-05-05 repair comes from a separately dated archive. Both that
archive and the newer main source share Yahoo upstream; this is not independent
vendor confirmation. Identity, primary-source dividend policy and interim
accounts, nominal-unit overlap, the conditional July-October dividend inference,
and the absence of a separate exchange last-trade notice retain the limitations
stated in `evidence.md` and the primary supplement. None of these conclusions
clears unrelated historical coverage or identity issues.

The following supporting-file hashes bind the relocated proposal and primary
evidence to this review:

- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/2021-05-05-independent-neighbors.csv`: `c73daa9e09479eb9168d0f97c53cbe1a5240330c5362a15aaeee9e0898f415ee`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/2021-05-05-independent-row-audit.json`: `7ab9f923aa8f3e01f7c28e15aac71cbdb4f5a26fcd20b36586b601141702aec9`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/audit.json`: `9dac5e411a5fd73a6ff898ee004c846f27184acf5a102ac436098e3862eae7df`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/downloaded-source.csv`: `db416326855cad38b07d6830718c599822b2389741d1042179003d5194966631`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/evidence.md`: `518fd6b70078611b8766df77756f10177278028988c89733bd9bb762c9546d95`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/manifest-proposal.json`: `fbba7e77783ebe0c6a67179f551e7fc62b19dea1f58f6c4cabb07f78b0ae05ad`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/new-pre2018-gap-row.csv`: `8d0a8cffee7b4b6c4ee4e6176efa09b8d6e32cb072bd6c6a2229d72ecd54756d`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/source-conflicting-row-not-applied.csv`: `58167b6942020a3edf434f8f08cd75817c93dc2d0b4cdd019448e109bc19c51f`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-repair-proposal/source-zero-volume-not-applied.csv`: `32d849a4575c50883e94883276a48efa4bb581bc5fadd3205f4b5c8d5ceea464`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/01-closing-search.json`: `7428022628e78158edcbe52c35765e0387978d2892fe4c4cd76deff75eb222fb`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/02-ipo-dividend-search.json`: `eb570201372da6a7651c9e510cf698e4817561b90b4ecfdf2cb50eab038c4d19`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/03-dividend-latest-search.json`: `ded3419352ec89b239b0f4bc66451a1fdcb62d7160b0dd756beed93cb3a269e6`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/04-annual-dividend-search.json`: `b66a2bef96c6a400bb1aa4a17f812c2f049a2828e3aaa3d0dcd67f6335efb66b`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/05-2021-10k-direct.json`: `234d824b8a2ffeb95455794decc6454095ee1417567edbd1d17032cd4cf1ec06`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/05-2021-10k-direct.txt`: `41b9f70d2206458f9c9ffc715224490541ce141dddfad1a9387a5e8d09f83e39`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/06-submissions.body.json`: `dc3a049042821da59e68c7354e8e769f17c71087f56d47160d4854486ad8f815`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/06-submissions.meta.json`: `08e995d73728bd41461c3d551cec7904953f38254fa3e743f22d3ebe2be6e79f`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/07-2022-q2-direct.json`: `176db58f76f3594044eb3200b16c90adbd1108062d0c77dd1396adf3a723d587`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/07-2022-q2-direct.txt`: `5c62c43481db6139f0f21bac57ab3bfe2365535954c5bf267454c211e444f627`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/08-merger-proxy-direct.json`: `5bf503292bf63da79b4c64f4d02a523468bb101d99347b4a222ed282f498dc7c`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/08-merger-proxy-direct.txt`: `9bc9472707407803e4d3667b4b6463ae982ef3ee41acd689ef988c64972ee248`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/direct-file-request-ledger.json`: `5c3374999d0da2a1fca8a10905c6c37e0ed238d1ad9f7fee3678d6434ffb3317`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/dividend-and-unit-supplement.json`: `74564d502b1019d00eb6b039e31c661297b74305723e44e1b5a4a0f25b045131`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/dividend-and-unit-supplement.md`: `e8abba9e55684af3cd03536a306a9703c40b02fdf19c542866391a845591406e`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/findings.md`: `baaced818e65bd563bd1a951383e855a85b14272409c82feedb4ac8b7450237b`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/nominal-unit-reasoning.md`: `36a00d06135ccb15aa0bceebb1608c1c63f7f68032a0002c4063eaea86bc907b`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/primary-excerpts-and-terms.json`: `5d7b27b2c33e83b1b5cd3312efa9b07b2fd5422856a14541bf7790039e6d4df1`.
- `data/reference/v04-remediation/corporate-action-evidence/TWTR-primary-evidence/request-ledger.json`: `d20b2e62f6f287a6682f26ea328f6005bb1be0614cd1432610f0bfab0734029f`.
