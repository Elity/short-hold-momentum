# FL application review

The root review accepts the bounded repair documented in
`data/reference/v04-remediation/price-evidence/FL-2021-extension/report.md` for the next fixed research snapshot.
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

Repository-relative original: `data/research/v04/prices/FL.parquet`
SHA-256: `8e74d578db3db6d7bf02452e4965f15f30e22986d0321ef86d8bce78907de7e4`

Repository-relative promoted price: `data/research/v04/prices/FL-history-repaired-through-2021-08-19.parquet`
SHA-256: `33946ddd8eac2b907e4e82f75b5177d08fa3cb405e8e46c7fafc646fb9fd8a2f`

The following repository-relative paths bind every copied source, proposal and
audit file, including relocated work-only artifacts, to this review:

- `data/reference/v04-remediation/price-evidence/FL-2021-extension/01-dividend-discovery.json`: `cc55aefb07e5d212feb558bdb9c368472dadbdb1aa42b7d53400f8e8bd1b1ded`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/02-sec-filings.json`: `79ce8e8c6041c7720d0c388ab3e327ff987fd7273c2f6da117c4b52762a88cbd`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/03-issuer-dividends.json`: `d62292db5b9d8d0cf1a6d20c0c8660541f8b97c4fbb3347f8c1e59dae4eb1378`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/04-FL-2020-10K.html`: `46847ca89f9563fd48436dab17674163fafd4f700e18bc0023f32ae886016439`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/05-FL-2021-10K.html`: `c531152c94c893b04661889fea41a17fcb72de2d6902f5eb97483e8f7e327410`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/06-issuer-annual.json`: `99e9ae74b506e3cb16420a321ad9fad26d4161850eb7c2d49c37a642cc4db2a3`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/07-issuer-2021-dividend.json`: `a857e46ae93354e44b286bfb54df3f57ef4e7fd14a22e1e910c85b7c3a556743`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/08-issuer-2020-dividend.json`: `da7fb64c9cbbcd9252e880e0d3bac78cf8a6adaaa4ea81987e41f80fd2fb5b56`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/09-issuer-2020-annual.pdf`: `96f87144b12cb476652a08d023e698611bb2db7f9c82de30ac5bc9d485f53b52`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/09-issuer-2020-annual.txt`: `fca378735f195cd6792fcbfcd58a0cf413cabb2dd3ba0d41183c00fd22aa3358`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/11-issuer-jan2018.json`: `7910d81b7d5def887326d4ab36a19f819e2352207b39157382a7be430e37deb7`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/12-issuer-apr2019.json`: `1b3480f2d72d3a8fcb2e79da43adfc67d4e659a30d68e431649cae086afb92f4`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/FL-extended-prefix-unchanged.parquet`: `0d3d3e45f7a71bef2bed16d538ec22807ec8f6457bdacdd98796dca1ff220307`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/FL-history-repaired-through-2021-08-19.parquet`: `33946ddd8eac2b907e4e82f75b5177d08fa3cb405e8e46c7fafc646fb9fd8a2f`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/IEX-FL.csv`: `fb58716cd2188dcdbea9fbfd5b1dc9d883f2a5d18586830587b8d1f6d4c576e7`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/audit.json`: `a2ade38ccedc4e43a3f28777127c6bc9fb8f12d97e46a1b07d8479c397a29044`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/build_candidate.py`: `e1b00a54ca25c0a39e6922f9435345c61abfb8c824b17a7111eccc409fa33e38`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/fetch_filings.py`: `07f3a91fa58b3b294340e4cba1d411146044df144b10d0faa739ea1c0aa8e791`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/fetch_issuer_reports.py`: `13c5315cd7e7e637d318b11782bbc6036bdb86938c67169e77a55a660c1c907f`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/filings-retrieval.json`: `a90ad9a390b87619433f6a7229ee72ec9fb7fb2ee724249d10815ddddb9573a1`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/issuer-reports-retrieval.json`: `a47e33cf524ce8150804243ffa93b36b47f214f2ff5f7b580a627f5b42535efc`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/largest-retained-quote-differences.json`: `b4ed748aad01e36f6c173dc410e74b8dc83f3d43cbcbdc8bb4db70b9fe99bed0`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/manifest-proposal.json`: `66539c8124ffc5e1bb2d8b498291322bdd31d702491d36dfc116216443b34834`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-annual-excerpts.json`: `bcb03a5bad58fddff76e29cbc72a39a9405371673090839e32ab2cf47bcc86df`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/01-search.json`: `08fd8ff2286c622622b712ca48eedc1c02f67aecea078c92409311d49c4d109f`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/02-search.json`: `33bca84489b4e7b469ea55dd62c23c422df94c4deb1dc2a17e842ce850385127`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/03-FL-2021Q2-normalized.txt`: `994f9e1a36b57330d10ec0f5138beae17bb63e11851fef258a0b676a874c3d00`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/03-FL-2021Q2-retrieval.json`: `adde13d8a36f54bdfa59ca6e5456dd3b444a471109ff16840712f3363b03f65c`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/03-FL-2021Q2.body`: `a06ac2f937c9973c593ab91537e7feba6fbd4ce61c3060a90e00a81018785827`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/03-FL-2021Q2.txt`: `0f5b0a2ea9fc277c3027981ce905e3162423a14ef0c04a06bc2989bd7fce04d1`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/2017Q4-company-release-prnewswire-indexed.txt`: `1787cfee26a76b1bf4da61f7d42a28714abe0047ca742553f50fa98410da4778`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/2017Q4-issuer-dividend-indexed.txt`: `85532cd0da4f234105180f0e0b38f2fffaf7ac8c607fb8887af90bb13277f4cb`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/2021Q2-equity-excerpt.txt`: `58c3c54506fecc9a9f814f6cd3de3de7bbaf5c50029a573780b2567dba0ffd42`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/2021Q2-issuer-indexed-1.txt`: `512b13607ff6fe9137c48bdbc2e6920e1fdb6ef6f125c2631b8d20b015a7c2ed`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/2021Q2-issuer-indexed-2.txt`: `a5f6ab24ecd6b54c499c6e9a183f6849543ae86614b77adacd06afc37f52f1e0`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/facts.json`: `cf275ffc25f171a0ecba9840225e4ccbbd0852019b5055cdd2479408eff07377`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/report.md`: `40e52398c3e5d30ca3bd4727fa331109a5be94d245ca57323827852eaa7fec9f`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/primary-followup/request-log.json`: `d5ad0c9ea0635e92f68c5a6b17f01d32ed32fc4c1006d6bf73ac0723f2a0b824`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/report.md`: `d47f7cb652a7c607aa6111808e1740d49edeb1ef254c0b1921c539f6aefa7ddc`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/retained-2017-05-19-review.json`: `2d5018eb1ac33c485d3a22324d9941c678452bff51916a0552cfee9cbec8fc63`.
- `data/reference/v04-remediation/price-evidence/FL-2021-extension/write_report.py`: `715b3c4e796745ddd6a51620206599b1f2987e6b94082233b3de3d45374279d7`.
