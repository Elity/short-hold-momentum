# ATVI application review: extension and explicit old-row repair

Accept the 349-session extension described in `report.md`, including the
unchanged WIKI total-return convention, bounded share-unit evidence and
same-Yahoo-upstream limitation. The separately retained uncorrected candidate
preserves all 4,154 old rows; the effective file then applies exactly one
explicit old-row correction on 2016-11-25 from the adjacent IEX whole-row audit.
Every other row remains identical. IEX OHLCV is selected as a whole and scaled
by the old canonical factor 0.9940071913703556. The close, volume, nominal close
and dollar volume remain numerically unchanged; the erroneous open is repaired.
Yahoo captures corroborate the nominal prices but report volume 19 shares lower.

All 4,503 effective rows now pass physical OHLCV checks; this does not certify
all historical quotes against an independent vendor. The complete original
files and proposal remain retained; any old claim of `invalid_rows: 0` in the
uncorrected inherited prefix is superseded by this whole-file audit. No price
after 2021-08-19 or terminal merger event is inferred. Existing unresolved data
gates, candidates, costs and cutoff remain unchanged.

Repository-relative inputs and exact hashes:

- `data/research/v04/prices/ATVI-through-2021-08-19.parquet`: `3ae0974fa6785531839c5743c16243894e5d60ff6cd322577a864e727ea82a74`.
- `data/research/v04/prices/ATVI-through-2021-08-19-repaired.parquet`: `60325363742c97f38dcc96f88d7b11b69651bd53b5609f4cec50682b8d0fac41`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/04-sheepb-metadata.body`: `d763dcf15eebed98f3a80bfc65d2269c47905825b77e3417fca6498141bbbc3e`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/ATVI-2020-10K.html`: `079fa346fae873ef3d050841c7254cfe7fd91f6073d2dc909d7c22019f4571fd`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/ATVI-2020-10K.txt`: `1b7d6b2ecd7ef0a1f7c662c94874d0a2865b93bbdace1d0a578c8dd697d13614`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/ATVI-2021-Q3.html`: `e99b107be442d5dc77d9e371bad448984562fbece84817e3192e194d83395195`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/ATVI-2021-Q3.txt`: `87ca3bd1df8d44aea58ab6d8fae026dac5d44b70a93a9322c53c83180e81d138`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/application-audit.json`: `c618c109ae6ed86515093db6bcb7147c1ab0f4209dcc8162a25938b822b75753`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/audit.json`: `b28825f624ffba23d00553e48856450ffa5a8950dda956b8f29e94a0a3c1dfff`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/build_extension.py`: `ff22670aa3db1466cc00a0c0fff8644b902f497d8c7c2445d4bfdd99c01c4e7d`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/manifest-proposal.json`: `55580355f75510b753d839709f17eb8b359fd1829a2fc543a49b9364a7070f73`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/primary-excerpts.json`: `6b781a2aa15a66d697003aab5937a07abd0150dd44dec82b0ef97f4f75692212`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/primary-source-provenance.json`: `d65ff3954179f78ea1b7c9e3b4ef24c363316a921d25e20175abe8d0a7ddc2b9`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/report.md`: `a20596337ab2df11478832e0a5a9d99a37bfa3193bf37846a18ceb60eeb760b2`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/sheepb-2021-download.json`: `ca52947426ff0ddd9e673a10e63ccca8cd5aa338dfe616b1262b994347ce8c95`.
- `data/reference/v04-remediation/price-evidence/ATVI-2021-extension/sheepb-extraction.json`: `44c194569727c7d875e0bf34859b503410958283e34a16a6f1fdafca4dcc5316`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/ATVI-2016-11-25.patch.csv`: `e9ef769f27509d46178fd0eb77334fafd02f856c3a20a921cbed591fc65c4754`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/audit.json`: `bc14d05cf8e42a820aa946ca9a6dc35a5ab777fe990a05d0d66df8f32c38eb22`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/build_proposal.py`: `eb889abe999e561522b1757b1a4ccfc78f549bbbcd812d9a57fdc8d540cfffd0`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/current-canonical-factor-window.csv`: `4eb7ef47719c8e254587c779fd1268fc22e1ab52a71f83b42f98e3dd6db43bd7`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/original-row.json`: `24d253f5ddbabf8c78542b7f1c85b16bd08b30648ad9a3a6acd2f59b2725f549`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/provider-target-and-20-neighbors.csv`: `da0126e6ae92b1bbf005b9919e1c9c8db9760fdc6ace63ce016769387b8a2734`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/repair-proposal.json`: `58c5f535060eafe08840d3a63bb4bd2021e4f5a60cd3f1c0a99d74140e9c9f50`.
- `data/reference/v04-remediation/price-evidence/ATVI-2016-11-25-repair/report.md`: `3c80fe5a38ffcaff773cad2e8704e69f0aed23ae732e3204122df91421e12272`.
