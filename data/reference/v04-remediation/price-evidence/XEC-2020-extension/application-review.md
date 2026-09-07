# XEC bounded history application review

Accept 4,138 complete XNYS observations from 2003-10-01 through 2020-03-10:
491 appended whole-source SheepB rows, one IEX missing-day restoration on
2017-11-08, and the reviewed IEX 2015-08-28 row correcting Open below Low.
All existing nominal Close, Volume and dollar turnover remain exact.

The root accepts the source-level conclusions in
`v04-xec-primary-actions/final-eleven-event-and-unit-review.json` and the
explicit `v04-xec-canonical/ledger.verified.json`. The original March 27, 2018
price anchor is unchanged. Undo the false September 14, 2017 $0.16 event;
restore November 14, 2017 and February 14, 2018 $0.08 events. Append the
eight confirmed tail amounts using the fixed WIKI total-return recurrence.
Ordinary dividends enter adjusted returns only, with no second cash credit.

Evidence levels are explicit: issuer declarations and annual filing mirrors
support nominal cash amounts; ex-dates use corroborated published secondary
histories and source factor observations. The 2019 November event's exact
record/pay dates are secondary. The public SECInfo R36 transcription is used;
the unavailable original SEC R10 was not read. Unrelated-issuer search hits,
unavailable endpoints and malformed alternate date tables are not approval
evidence. Prior partial reports remain as dated investigation records and
are superseded only to the extent stated in the final source review.

The common-stock scale is supported by issuer identity and stock disclosures,
an official $75.34 January 31, 2019 close matching the archive, and independently
supported cash amounts matching the source scale. Preferred-stock conversion
terms are not imposed on ordinary XEC holders. Source limitations and earlier
WIKI/IEX/SheepB quote conflicts remain disclosed; no blanket vendor replacement
or claim of independently certified every-day quotes is made.

The selected end date is the first normal post-membership-removal execution
session in the frozen schedule, not a legal termination or fabricated fill.
The ensuing fixed study must verify actual holdings and exits lie within
the restored range. The real nominal 2020-03-10 opening observation is
16.559999465942383; any adjusted fill must be compared on the matching basis.

Retain all five global unresolved items, all 10 registered corporate actions,
all candidate parameters/costs/cutoff, and all original V04 account records.
This is known-history data remediation, not independent OOS or winner approval.

Original external-path inputs are also retained under source-inputs with the
same hashes; copied work scripts and source reports retain their original
provenance paths. Repository-relative evidence hashes follow.

- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/source-inputs/XEC-canonical.parquet`: `c793f0947e1e82051776936a2b68b26ccb64608d711c7acf50bfab66ef508e77`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/source-inputs/XEC-sheepb.parquet`: `d435d3385d66572e31eb22d9fb3831a0afb566eac42792762825c4107406fb1b`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/source-inputs/XEC-wiki.parquet`: `0c5531b61913909e788561ba5b37d1f146e926416bff1ea10a119c52836ef342`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/01-2018-aug-increase.json`: `778f70ab5189f7af426091643486f7ec71859fbc981a6df5cae6187afcdab48d`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/02-2018-dec-declaration.json`: `08748daf30369af448b7f87460db5a6e7508b838233db04c9821cdc10530dd6e`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/03-2019-feb-increase.json`: `7fe2274416514e36a46f9f92772ae0b48e030ea544fecc496d0fb6770085855e`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/04-2018-may-declaration.json`: `451d8cfbad46f1bc81d842432332eeb675b352a18ae6b102c04864e61941a0c0`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/05-2019-aug-declaration.json`: `ca641c3fe6e221b1177223c88164548d2724ee320ad49b2e3f8bd5911531cef5`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/06-2019-dec-declaration.json`: `908ad09cc3eadd45683bb773e08c633005ef156c7486e3037b8ae4f93070612f`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/07-2019-nov-payment.json`: `fdf061c279b23e68f87d76900ba36d3fd0dc86b2d9233ef7dd4feab04bc38501`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/08-2019-q3-capital-stock.json`: `467f08883fef8d7bb09eb6be0f7a7b38ab7f73ade96e17e1a3c645d430d460ec`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-announcement-evidence/2019-R36-quarters-transcription.txt`: `b8915aa3561dc46ebb9068e97ba48d9631d7bbb178ba1634e43a601f6563f00a`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/XEC-repaired-through-2020-03-10.candidate.parquet`: `a0593a53521087bc2c255a1706ace68aceef0c1e1fd39391fc347dd7e22e0fc5`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/build-audit.json`: `f0bd76defa9bda001cb4abfda05e1a49495711ff4d9264c632eb050abfaa1549`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/build_xec.py`: `aed9a00717f38ba828ad971b241b2cf4066f8685fe87010731dc2a8f6cb158d9`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/ledger.pending.json`: `1730347bebed0ea3a0d916a13696dc26037289bbf797d3c9807251f42b416c4d`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/ledger.verified.json`: `3fae386926c4cab0ab920065c3aa551f48cf0705a6e16d647c3d4b53eff05857`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-canonical/rebuild-plan.md`: `cd03c84640ac2fc1fb44e3cedd93f2cb09753a0688671812d8d0c732eb2dc105`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/XEC-IEX-existing-archive.csv`: `925dd82d168b5db014e908d3a70bb6cfd05e93cb0a0b1565324707dd86d466bb`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/adjustment-boundary-observations.csv`: `fed2eca1f41b6730a258af206eb18e160b87f41c3816be8ce2c0fc52116db238`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/audit.json`: `e7703ff3022d09cb5b9d64666b4adadc425dc06f2b050f320fda1f24278dc85b`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/checks.json`: `65565f0398935bfd526e8b25f9f4e2883f4acf6b00188a514be4dfb08e03d814`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/existing-prefix-conflicting-rows.csv`: `affcce234bfdd256af6d92b7559e473e512ecea60e94785af35c9bd0b315a1fb`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/iex-existing-local-source.json`: `faae452f95513b14ea3fe7fdbc95e23be47a5a0803a35ee12fecc5302f66ae9f`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/minimum-external-evidence.json`: `465e13dc3386ff281e416954dcf21f762e72417466bb8f9656f57e1768340045`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/preflight.py`: `79c84eb3603f8efcd70f9709688c180eaa9c48aecd74ed6a993e4b1c99c2db5b`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/report.md`: `7e6d00533ea32bbdb682370501db98f9f7ae39d92c7c91d9a3021f91d57246d8`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/selected-prefix-row-three-source-check.csv`: `6c17c05b8170cc2112760218e1352295c3b42d37ed2fe277808d1cbf243c4f96`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/sheepb-factor-steps-DIAGNOSTIC-NOT-DIVIDEND-EVIDENCE.csv`: `c0cb8c64d82dcfd6a2b3229d8b498e48b01b4aaf3180084f837e24afe484bb1e`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/sheepb-rows-on-existing-prefix-gaps.csv`: `75dd61be12b19ab570ef31f425422f0e47418e94af23196954c32ed6c704c4a1`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/tail-required-key-rows.csv`: `6b4030cc13c4f17e445e43f5094175c44f06b521f402d3aa6b8df60f0e57a311`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/top10-overlap-price-differences.csv`: `29950da3121aec5a73e956ce5f1d4569dcaddd0bfe4875e7000c5148c94367ff`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/wiki-recorded-events-and-factor-crosscheck.csv`: `3624a5580682cee7830c574cc53e1aa4c63d976e7e4eb66f52899078ab7715a8`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-extension-preflight/wiki-sheepb-overlap.csv`: `e9f861429a8854aa5dfbeaff23ce611e9bd0eb899a31f68b13589cdecf1817f6`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-note-followup/01-capital-stock-search.json`: `32fefa322f5bff2d63ed8311a8c90ce0a1bee955db35d6ddf8df807ef24a88cf`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-note-followup/02-FilingSummary.body`: `ee8c57c1d7c32fd5b5f7cfbe67ee58b69767d3396a8151d9e5be0e1d9722c3d4`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-note-followup/02-FilingSummary.meta.json`: `d355e4cd22167480eef1db7b2077b9d8535ce4ced5953ad46a41951987929a73`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-note-followup/03-2018-accession-dividends.json`: `2394f5a5eb2593c4537cc5d32aa82c1d0bf9df7b512553dda8ee19d31f4ff851`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-note-followup/04-issuer-dividend-passages.json`: `2658ac8da29a345e5f6eb7fcc7bc0c751f2cfb1eede6db1cf759df9539011635`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/audit.json`: `7a34609a2b29b843e57168e7ec28fc3aa924cf7bdec85335b2af21b58d6c4b7e`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/eleven-event-evidence-levels.csv`: `09261db8936564a95db257fbed2731760a543ed9a130ace7625dc90b676c89e3`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/final-cash-dividend-ledger.csv`: `6fd17b4cb09d7ec525592334076ff087901279371919aec2985138e758169594`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/final-eleven-event-and-unit-review.json`: `0b1b7c954cb2e58ffbd6c4b8fbe647a33515290728a4024213674c7a1c2a62e8`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/final-eleven-event-and-unit-review.md`: `23666c09dbe374c8c938d5b4a058686b3e54c6360f2c6014ac122521e12d9f90`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/final-ledger-factor-crosscheck.csv`: `d6c0b6d6749fc10f9ed98e608f2b4b89f0bbf5734c8765ceb5f040c81f6982ef`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/final-ledger-source-excerpts.json`: `723125e56a1baa667026869e2ba694443363cc80ee27b76d9580be043e449327`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/finalize_evidence.py`: `5fe073c728da4a414d176fac0f5d5121e05ed66a21ce65123f1b52393436fa7d`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/old-prefix-three-event-review.json`: `090f5d0d8749025bcbeae54cf170eec212730dda8d7301f5447f9d6d84f46533`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/old-prefix-three-event-review.md`: `86792cb7eed9f850006736b18cf11e043e32ad8a6ccd6d4b8018b809780adacb`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/XEC-2018-10K.txt`: `21b59dc9d61806be8394604fbe0d03930543f2a6a2beb23ca537299edcff1b98`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/XEC-2019-Q2-capital-stock-R13.txt`: `3ba9c60d2e00cb852263c8ad477f5ba94df81eb792d651aa2b46ecd4497e72e8`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/XEC-secondary-A2-history.txt`: `8a4473fdb9d702928bbce8172ab9461d2c9da6ba662b60ea1a8d050924a486cc`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/XEC-secondary-Marketlog-history.txt`: `648f3667529d7be5b5863fca4ad7b0291cb650675ed56259d493dbd65b94b735`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/request-01-2019-annual-search.json`: `5150482c553c7a39034aeb0666f2720c271c31b789d561f2cdee14f35774491f`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/request-02-specific-CIK-annual-search.json`: `18dfe6173a410632d7730431dfad87d4f178231f3e766d9f77739ac65c7cb7e8`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/request-03-XEC-2018-10K.json`: `58edee811067236b0fb816460b8571614dc3f89b0e1a85ffcd39d60798c35325`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-evidence/request-04-issuer-dividend-releases.json`: `77b6ac78d353d19586eeefa679e23e242516429b37e79701ddfae980817d3438`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/primary-excerpts.json`: `aed3d74a0f7bb8737190b1c8fe726dec3d344e6e41e08674e8b1191483d9d848`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-primary-actions/report.md`: `d97c7d8e2918bed43d73ef3d30ef4163ccc99098270cd8ee93cf3ef31d42fc31`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/01-2017-mirror.json`: `c0f1316a0c8ce31343e9978d0b9caace2a3168549c9bee676a57fc15d548e9d1`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/02-mirror-discovery.json`: `38ace8b3a796df8648846d899c75bd02b2af2069eac033362aae205ca968d1a7`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/03-2018-mirror-response.json`: `05c1afeb6cca88ae8583bcb1a94a7409400a2fc092a8891d0d3291b936e8256e`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/04-annual-pdf-discovery.json`: `b92491a2b61f49dd46d6e62f48d16318416e88abca0e81ef4aa2862504823638`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/05-2019-R10-unavailable.json`: `ef31c321010d6e56fff66a078bb9e49fc54c8d5b934a040dd8c7793bd2521992`.
- `data/reference/v04-remediation/price-evidence/XEC-2020-extension/v04-xec-source-tables/2017-capital-stock-excerpt.txt`: `95fab3f84676ba635b5fd1968a04aba2d172d8dd9623b48eec595cc2809d553f`.

Promoted price: `data/research/v04/prices/XEC-repaired-through-2020-03-10.parquet`; SHA-256 `a0593a53521087bc2c255a1706ace68aceef0c1e1fd39391fc347dd7e22e0fc5`.
