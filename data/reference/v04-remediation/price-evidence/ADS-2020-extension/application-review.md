# ADS finite member-history repair application review

Accept the independently reviewed 4,218-row candidate for historical Alliance
Data Systems Corporation common stock (CIK0001101215, NYSE ADS, $.01 par).
The needed 2012-12-12 through2020-07-02 window contains1,902 complete XNYS
sessions. Retain the3,646 old rows and their exact nominal Close, Volume and
dollar turnover. Restore2017-11-08 using one whole IEX row and append571 whole
SheepB OHLCV rows. The retained older prefix has not been newly certified.

Two issuer-supported ordinary cash amounts were omitted from the old source:
2017-11-13 $.52 and2018-02-13 $.57. Keep the2018-03-27 adjustment anchor fixed;
only pre-ex adjusted OHLC is multiplied by1/(1+cash/nominal ex-date Close) for
these two events. The original four $.52 distributions remain embedded once.
Nine tail distributions advance the factor from their saved vendor dates via
f_t=f_previous*(P_t+D_t)/P_t. No second old-prefix normalization and no separate
cash entitlements are added. This is the existing total-return convention,
not a claim about a broker's actual cash-payment or reinvestment time.

Issuer-document support covers all15 per-share amounts.2016Q4 and all2017
quarters are$.52;2018 quarters$.57;2019 quarters$.63;2020Q1$.63 andQ2$.21.
The2017/2019 annual reports were obtained as indexed EDGAR Online mirrors;
2020Q2 has indexed SEC8-K and issuer-release declaration evidence. Exact
ex-dates retain the vendor-observation evidence grade; only2017-02-13 has an
explicit secondary ex-date in this packet. No primary ex-date census is
claimed, and2019-09-03 is not silently moved.2020Q1/Q2 actual payment was not
separately obtained; those two amount decisions rely on issuer declarations
plus the archived event observations. These limits remain visible.

The same ordinary share identity is supported by the issuer materials.
Eight2016/2017 quarterly High/Low ranges and four nominal Close anchors through
2020-02-20 agree at reported cent precision. This supports the nominal scale,
not every daily price, volume or corporate action in2012-2020. Old WIKI/SheepB
disagreements are retained, including2017-05-17 Open,2014-08-01 Close and
2017-12-27 Volume. Unknown new-row download times remain NaT. Later2021
spinoff/2022 rename are outside this finite window; no global ADS-to-BFH alias
or continuing-company corporate action is introduced.

2020-07-02 is the next opening after the first scheduled post-removal signal,
not a legal termination or forced liquidation. The frozen five candidate/two
cost research paths must confirm actual held marks and fills stay inside the
available window after applying this input. No decision is based on whether
ADS happened to trade or improved historical performance.

Keep all five global unresolved entries, ten corporate actions, other prices,
membership, aliases, candidate parameters, costs and cutoff. Preserve V04
accounts/configuration and OOS history. This known-history data repair does
not close global gates, select a winner or launch an account. Earlier packet
pending/application-false fields are retained as stage records; this review
and the independent candidate decision approve only the stated finite scope.

Retained source and review hashes:

- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/source-inputs/canonical.parquet`: `9f05d12e7246535b97874c42650e86566fea49de8e8058672fa73d1990ad4455`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/source-inputs/iex.csv`: `b4569e912defe1d4caa45edbb26765bf0f36750513d8fed18c972eea7c7b25de`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/source-inputs/sheepb.parquet`: `173d8919cbfe7d86a62b8f3795c9a106036c5a97d12283934e5147607bdd13d9`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/source-inputs/wiki.parquet`: `89b9ebd7f9e2ff9aabb86c15bc11d2add682f73f7eaf54aa2bb05fe323a5ff62`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/ADS-IEX-provenance.json`: `9c107e46950b70d3c2ee1aeb09391645998d9f704897263684caeb29380cf169`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/ADS-IEX.source.csv`: `b4569e912defe1d4caa45edbb26765bf0f36750513d8fed18c972eea7c7b25de`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/ADS-factor-event-observations.csv`: `c2adfe891107bb4e9d2ce51b6fcac8b857b2119114a8ae1004f7facf08b22223`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/audit.json`: `e246ff5309ca5f01fffa3888a065019315db5b748abf7e4dc1cdfceb11aee5f8`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/boundary-observations.csv`: `f861129353c5acbed408d5bbd72d6e2a620cc7b638658f563dba1e2e4f2b354d`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/iex-missing-day-and-neighbors.csv`: `c4756177877f335d1b04cf39514caf58560d677a010128ad33657977ad28fadb`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/largest-observed-source-differences.csv`: `713e14e842717eb66e960fb36d634b48539b14b7bc55190d5a9bdf0be073e87e`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/member-signal-window-date-coverage.csv`: `9b1d182d3f006590f90c2baa38c4f5addecae9df02ed5d472a76576216587ede`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/preflight.py`: `ff93bc0cf21de1281fde30b3cfaed36e6894c9398e049393580fea676c7307c4`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/report.md`: `bca3ba305f5c17f4b9ad8eb9dd50d367facd562cc6d966683b15e94db2d0d477`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/sheepb-factor-observations.csv`: `60e35d81072ec670e3a502edcece4c2db002685b7bb3100c294a1961ae8d01fa`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/sheepb-missing-day-and-neighbors.csv`: `a53507eb183725473f22cc95907fbb347009f393fee1c4c03e356d457b1b71b4`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/sheepb-preserved-tail-observations.csv`: `b29d133cb0de49b8a5382bae9e21a1a57730f89e97507c762e0d71c3e068ff9e`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/source-index.json`: `b9a06772bd094d2a3005823c0bfe1d657f55e4db5e37203fd3a7d21184489fef`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/wiki-factor-observations.csv`: `6f0f145e3c60bfb0fed88cee0cd98ca96dc0f85044205698cedb2122ddddfed8`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/wiki-recorded-actions-in-required-window.csv`: `0e46ec3cd02fe8a4b2739e2a403bf95d2cb3a4818b617749c413381c69f5447e`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-bounded-preflight/wiki-sheepb-all-overlap-observations.csv`: `35eb732a142bda93d0d0413516f850d7a66934bdd21ffc6a6df5d4ee63033939`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-canonical/ADS-repaired-through-2020-07-02.candidate.parquet`: `ff8ee755db4e74b7e127b1147f4cd41e1c9977fb774796faf9a637c9dd384438`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-canonical/build-audit.json`: `3f9fece99d2293b84c43c53cce92d7a493ce9e6c546125bc9b2bcf07b6078f30`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-canonical/build_ads.py`: `616af09b0e7b9895159c0d027f50c38ad5b9e255b1f9df329c5773ac6845f12c`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/input-hashes.json`: `c459f3cc7847e7986185cb31bd9e8e0d9e95eec65e8182d7dfcfe67bdadca519`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/preliminary-source-review.json`: `40359e3753ef824b367b1a2dc98915c7a39ecb5bb78504c0767c9965e8e87d05`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/report.md`: `f56f9f00e63d71df6bf9d7e5cf1832f1ea6b1aa4175795e827b275860c2f8353`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/review.json`: `9e72df7a9cdb62065df958136c6740ca97a09c0652a60fca94eb8fef7262d3b1`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/review.py`: `d9e3cad9f43d1cb8b2bc448af18a98828b51d131947a01f4853efa4602ce452d`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/reviewed-fifteen-event-steps.csv`: `3766b00d4e14706b75837866f58b6f3394844767add28c37cf7991ea8261147c`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-independent-review/source-excerpt-checks.json`: `6eaf8e8da75d15f9f79774bfc2c2c5946dddd1637366992f8cbce5227360fb46`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/01-2017-annual-search.json`: `590e9d8b275883d8735ed4ec8c0a4022c10a60a9d2107e51ad7672bdeb93ac08`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/02-2019-annual-search.json`: `59796a23fb14fcfb43867b5e0f0cc3b3297f2fd897c7ae034731e5b6a4a4f54c`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/03-2020-q2-search.json`: `5133c0417a44df9358fd0050d3d101df539b1e628d281add336231e7657bef39`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/04-2020-half-year-search.json`: `6340dc6d3befc1c02dac63f27c9fb333b33b097a639f9ba531c00d24c4a82f44`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2017-01-26-dividend.issuer-repost.indexed.txt`: `0e0f1f2ef014dbba54d153d87657b1709380fbb0e70bf6b112c43003e9506ca1`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2017-01-26-dividend.secondary.indexed.txt`: `a974461bd45b71f91c79b33bd79162274680dbd3df0f175cf4894804dfe9b6b5`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2017-10K.edgar-online.indexed.txt`: `82a4a43de124839320cce7b76e0cfcc4265dbef6d0cccaf8ed7bcae4c82ee3e0`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2018-01-25-results.SEC-indexed.txt`: `ba69219bef918b8e948ec53a760db8123c75191aade162080b5a33e4f4d82cab`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2019-04-25-dividend.issuer-release.indexed.txt`: `a3250d3f232c820f739888d368f156951592b16794b6b4fc2b8256f74d3d0ab8`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2019-10K.edgar-online.indexed.txt`: `02c11d849501b4f366b7cb3a8046c1969bd6a77c6d72dd465544a730d3e7f48e`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2020-04-23-dividend.SEC-indexed.txt`: `5c9878792cac4d24ce9f8b23373fbca61fe048df4b94824eb0712983e8a69925`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/2020-04-23-dividend.issuer-release.indexed.txt`: `87c81690aace0d532ceb222413c4b3037ce36b8c1ddf40947b2054d0fb9bcb9d`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/assemble_evidence.py`: `a77d03189d1c674102cbf8c264c2e5a9622eeced09430ec5d752dafc580a855f`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/dividend-ledger.csv`: `a138bc6356c45cfab7db2375e0d2e7279ff599b4b69f5464ea69604532f86e45`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/dividend-ledger.json`: `f21ad921d2fbc3c57110cb030d279871175c8b143b6f066589e9734acdd1a927`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/excluded-and-insufficient-results.json`: `3a5f2689acd3ad97adba5df3691cbe7d9b0844315208adfc3ba8651d2fe21222`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/final-validation.json`: `21992964750b2ab2d1893fa739532b9ea8dcf3c23d17cec54a783c9c9af22bc1`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/issuer-and-date-excerpts.json`: `be018fb6630441f88c4842f60e33565781b72c2178b06ac9cdd2c852fc3de359`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/report.md`: `4f2ba2f793e14377623b074f2ed7af82d55be5e500014ca501e9dabcb4172d98`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/request-status.json`: `022a7d58b5cc1235625a51f5d112530d74f7ea51134c366d5fbb2f98760b9a84`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/source-index.json`: `1495b0f57a517510219e5b7c9ec68faa31a1384d7da967fac31c725f7795800b`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/summary.json`: `b6ed6aa95053b2eee25f6876fee023baaeaa41894c59b5b30a24f6fdff18988d`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/2016-2017-quarter-price-check.csv`: `fadeb0327db25958bd4cff9c0f61fbd8e473c3acab75fa8f02f1cbb367de9e72`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/checks.json`: `b127b1a951d2e7747efd35e35a35f5ccba01ddd917752a4fd8e552b7569c499f`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/four-nominal-price-anchors.csv`: `fd1d0ea358a8e6ab86b126c7362dff6f6d874a9fde7aef27c3ace523877c8d5e`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/primary-unit-excerpts.json`: `f5401174dd757629935f1e69056ec5f4d10ef2e00fd31407839b1cdd328832c6`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/report.md`: `661392e7afe5c6a2423c3c3f53e1f250491af8937846f905ca2f522f4421d4e1`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/review_units.py`: `b7fa62dc56f7c747cf4d3aada9979ac6e20c5fc8733884091700d48aeb235348`.
- `data/reference/v04-remediation/price-evidence/ADS-2020-extension/v04-ads-primary-followup/unit-identity-review/source-index.json`: `06563a9ca72132a9febfa2811892960cd559813aaa864a0d2c1ba995dc3da994`.

Promoted price: `data/research/v04/prices/ADS-repaired-through-2020-07-02.parquet`; SHA-256 `ff8ee755db4e74b7e127b1147f4cd41e1c9977fb774796faf9a637c9dd384438`.
