# JWN application review

The root review accepts the bounded repair documented in
`data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/report.md` for the next fixed research snapshot.
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

Repository-relative original: `data/research/v04/prices/JWN.parquet`
SHA-256: `1e01003047228373f09124d26372dfd64a6452e25c291eed7ca10307a726ab4c`

Repository-relative promoted price: `data/research/v04/prices/JWN-through-2021-08-19-dividend-repaired.parquet`
SHA-256: `06e1a93159d3bb81a7d1599ae3441cdc4dd602d6e40155b711f63ee9ef44ed91`

The following repository-relative paths bind every copied source, proposal and
audit file, including relocated work-only artifacts, to this review:

- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/01-jwn-submissions.body.json`: `b96917abe9b24a32dec6a0eb3eb08e7d03cb0747ae8d8b9bc213089a5e9576e3`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/01-jwn-submissions.meta.json`: `56f8206fd0d87d791dc78a49f56b32fdd90987ab34b51c9a51580e8b1972b659`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/02-jwn-2018-dividends-search.json`: `6def8f6aeeb8efb174a2022f4832c891659671abd503b4ab989d8b4cbbd33303`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/03-jwn-2019-dividends-search.json`: `ff8ffd83311d4b3f45a9fda922cc795ff36f4acc7c2b9d28e02f4c9e44ccbd56`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/04-jwn-issuer-dividends-direct.json`: `42afa4c18b132b1751ee2c3e52c44dae21e1488c1ebe56fa32f8868634565a2c`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/04-jwn-issuer-dividends-direct.txt`: `3510a345507a0a7270f344910cb84605760ab5711f886b80f1394833117551e5`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/05-jwn-2019-10k-direct.json`: `e4c6b59c03df1d4b516fed0fba1cdb80ca88ae099becb2829aef5668aae58a21`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/05-jwn-2019-10k-direct.txt`: `807bfdbde3a0596c25c276405903778239b20c81b59a5a64f77b45256fd27e7c`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/06-jwn-2020-10k-direct.json`: `08ae49178a2bbf1b90855c20b92fafb9068b8cc8c9ca534cd1bf49dd01a49fd6`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/06-jwn-2020-10k-direct.txt`: `585809468f8364290896c564009a0fdc6f8ba37a644ba2974dc3ee2b06b5fe97`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/07-jwn-2021q2-direct.json`: `59e3b85e2d44725dee8fd6353f8f9ea3930be882b3970257e6601e8060fc566f`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/07-jwn-2021q2-direct.txt`: `fdbdbcd605fff71f119a7b28f6c51f1c91e17d28f88ce6dd20a15bf007d33b40`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/08-jwn-2021q2-raw.meta.json`: `11a25055c7222fe53ac8b3099770c120d7b71b81eb4920179e2bdfcd0d597a6f`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/ADS-all-factor-events-observed.csv`: `b89304053d43e831160221f3252e94064a147a0ae00554870caeb7f2ca5e0ed2`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/ADS-factor-events-observed.csv`: `f959ad301ecd7e65d94dafb632525e61d47e907f02c97a47b0c91e03f3702765`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-IEX-original.csv`: `3a60a156b5e7362c0d9934adcf3a3fd687c1d0b589957550336064547c2cbccb`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-all-factor-events-observed.csv`: `80854ab4bdad1e053c67403a65c265f3e296d400bf7a86aef8c647c7867f1b1a`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/2017-11-08-source-whole-row.csv`: `94f85a8480785484fcf170f588cb2870c087f5da3c054a83574d6625c9560118`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/JWN-tail-plus-prefix-repairs.candidate.parquet`: `06e1a93159d3bb81a7d1599ae3441cdc4dd602d6e40155b711f63ee9ef44ed91`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/JWN-tail-prefix-unchanged.candidate.parquet`: `d87df3f51bb002ed2d01360b1b69e8b0541913f2d9e1939b1fd1bc17f7e7c71f`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/added-tail-rows.csv`: `8eed59931054fdf2ad96b3ed63f7d201119f286303d1dc0bbb2f44c1bb3da6c8`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/audit.json`: `ff920b9b34b7ed603bc25c8fb4f6a60314d647cda3db12834fd02e5a400ee76d`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/dividend-events.csv`: `7aa202a7db7b80b5163aec12b94eeb473f04230d12a7aa431858a6d22194d37f`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/manifest-proposal.json`: `98a9bb74cbd8fcab100d6a399f57977f0e5df42acb3ee3ab88cabdf7b60084c4`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/prefix-dividend-repairs.json`: `47ab43354ddd5fc931d3fcf05d36bf7eae020548fe4e7baf5207bd7ac603bac7`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/report.md`: `73695bcdbabb567bcde3a59c48ff0ae898f8e2229e995c458eea50029e832bc1`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-extension/source-excerpts.json`: `86abefe7718344907f412d8bda16dde0c76a2c494128e652b005b5987a08646a`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/JWN-factor-events-observed.csv`: `1597c1918a6097111c61150ef6455f6043953ad1220c2b80fd67d6120a5106fa`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/build_jwn_extension.py`: `708dbdae25cba3f23942ae65ca51da329f2da7cbfe9f3d38edd62471a164cd17`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/initial-local-triage.json`: `0701eb26d3d4746d03f862ac94a27890913dfaf229c61bfcada4db2454dcead9`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/prefix-and-event-triage.json`: `1bbbd62536a700c141348223bf8c35f03f0273bc27e2eab63fc4975ef34b289a`.
- `data/reference/v04-remediation/price-evidence/ADS-JWN-next/request-ledger.json`: `6e87c2d88584d504356fcc592bcbd724532cb1864d1fbce5b4e208939f492efe`.
