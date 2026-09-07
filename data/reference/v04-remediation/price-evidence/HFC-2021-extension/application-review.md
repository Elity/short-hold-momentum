# HFC application review

The root review accepts the bounded repair documented in
`data/reference/v04-remediation/price-evidence/HFC-2021-extension/report.md` for the next fixed research snapshot.
It restores member-period coverage and explicitly identifies legacy missing
rows and cash-dividend corrections. The original source and intermediate
variant are retained. No ordinary-dividend cash transaction, terminal event,
new candidate, new parameter or new cost assumption is introduced.

The promoted candidate has 4,503 complete XNYS dates through 2021-08-19.
Independent application checks confirm all old nominal Close, Volume and
dollar-volume fields unchanged, exactly 856 appended tail dates plus the
missing 2017-11-08 date, and zero physical OHLCV failures. Adjusted prices
change only according to the explicit dividend corrections in the audit.

This approval does not assert perfect old daily prices, independently verified
venue-level volumes, or a complete official corporate-action calendar. Keep
all source grades, dated-capture dependencies, quote conflicts and inference
conditions in the original report. Global unresolved research gates remain
unchanged. The scope remains already-observed historical research.

Repository-relative original: `data/research/v04/prices/HFC.parquet`
SHA-256: `8e32b35e068f736fc1c6719ab85979d5a2717dc8a1a4bca90a4d2cf2eff06b54`

Repository-relative promoted price: `data/research/v04/prices/HFC-through-2021-08-19-dividend-repaired.parquet`
SHA-256: `c59827215d323fb4e2cf9d467f4e06fda7ea07b04c02aab9056c386cda869233`

The following repository-relative paths bind every copied source, proposal and
audit file, including relocated work-only artifacts, to this review:

- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-JacksonCrow-source.csv`: `ba6ec25dec06336d613fd61b7bf404486f209ad36cf51bc5521c03f35b440901`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-SheepB-source.parquet`: `196aea2aefc53bc736c9d8008cbc77142cfae321f8b0192d64d6be2669d1b0bc`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-WIKI-source.parquet`: `e20be066f5a4537478a899d7af9c2d934009f2ba758bb819dce8d7a293da0f05`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-original.parquet`: `8e32b35e068f736fc1c6719ab85979d5a2717dc8a1a4bca90a4d2cf2eff06b54`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-tail-plus-prefix-repairs.candidate.parquet`: `c59827215d323fb4e2cf9d467f4e06fda7ea07b04c02aab9056c386cda869233`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/HFC-tail-prefix-unchanged.candidate.parquet`: `ed6e10cb4eb218e8c7f4afacf6794b0b177a1b972557f8a39fd8aa266a1d4413`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/added-tail-raw-and-factor.csv`: `d26eb13aa0760d8a47951ac24aa88f5e1464a6647faadf0632fe3e2d1714a1fc`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/audit.json`: `382304eb34e7283a17ead42a0ac8feea9358dc8a5a4a671f8e05a02707529a30`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/build_hfc_extension.py`: `4e85117772e7f87472481e6f749c68bd1f2d6d0b59bdb384b17f6e98f0036317`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/dividend-return-validation.json`: `3e7ae0ac5a42b9ad026eeea26f4a361a2037da8c4aa5816548b6b1a8c3c64b6d`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/manifest-proposal.json`: `1e626f1b6164d75935321f358fcf45ccae7fe9f8ada811b4b3b708bc6ca87b3a`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/missing-session-source-observation.csv`: `7fd0343067075f27f6538ed0edf81bfcaccc1adc058334211d11f5e72df0192a`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/missing-session-two-snapshot-neighbors.csv`: `a1baafd82a565eafb76dc24bf156f124ba43dc1f9c156a4c5b60c2bad2e5d791`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/old-final-six-months-factor-audit.csv`: `448bd3ea5fc6348157d1464d785430a5dae8dab1d04559dc4ec652b0e14a7820`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/old-final-six-months-factor-steps.csv`: `35bb65c635582633ce7c320b93bfa02e3a10790d302e84949ecd08f77c157bd4`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/prefix-dividend-repair.json`: `fb76bb8f7c619fe26db800ba35333bf9cef6b86115cb9db688321f3bd4306909`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-2020-10K.source.json`: `6f1c16545b745276b42d673c8d5afe2b4c5c0466f4f6902d1f8b33998ca2ee42`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-2020-10K.txt`: `ccea6d49491e8a74fc7f5a93627417cda0d65d13bc614b58d675e70e17996876`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-2021-10K.source.json`: `0fc237aafdd380d7218732c473709486e56c6061cf4a857ad42b90cc4f99b655`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-2021-10K.txt`: `3209153513837893c1effa1bd2e0aa51c610b6ead218b70027e0319864cafa9f`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-request-06.unavailable.json`: `57e075daec6583b7d937930e8b9bb0a2f107f8c6a2f3ee62098ed6e0d87fb723`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/HFC-request-07.unavailable.json`: `835fe760b977fcfa74d2f90e818bea68b1a3e51dbb6dddd382f70a24e80304e6`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/request-01-dividend-history.json`: `9bc942daea138acdce6c4a15c98b2d87442c0382641d4c1dc03eece39c4f93ba`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/request-02-misdirected-excluded.json`: `cd91a70b8219996f4166e07084cb5f7e5485c7e0a70f92ef09ba69404a59ba77`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/request-03-2021-annual-search.json`: `f1a2199525b69238c1bc99b2e954b046dd8ea9e28759b54d5b2358532e9b52c3`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-evidence/request-08-2018-dividend-declaration.json`: `09310aeb345384d68059856866cb38ac59b3b9854dda894195f9a12216f5433b`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/primary-excerpts.json`: `a6e3c0300d411d8bbb54c60c7e5e7857fbee9598f15e78cfe25ad7f477b090b4`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/raw-and-canonical-row-audit.csv`: `f2239177d9be5152526a92162152fd222a8a85c2a34280871c732b938c15992d`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/report.md`: `fbbd3c52ab9254e9d98ce9d1dbebd1845c4448ce780668b03827951e648d3b4b`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/session-coverage-and-260-window.csv`: `b3c21beeae99b9f4d65694ed42a0c49a1da5fb5cb67b5b70e05dbeb7af3d5c20`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/tail-dividend-events.csv`: `79932d163420f62580131ba568a8ac87c6bb02121efc4ba98c25bc169bd794c6`.
- `data/reference/v04-remediation/price-evidence/HFC-2021-extension/tail-vendor-factor-steps.csv`: `d0287a84ad48602e5971b51868d3268d3d6e497dc131479bd540d3aa75a9704c`.
