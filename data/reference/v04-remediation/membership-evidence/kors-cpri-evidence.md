# KORS / CPRI duplicate membership audit

Reviewed: 2026-09-06 16:15 UTC (2026-09-07 Asia/Taipei).
Scope: read-only source verification; no source CSV, loader, or remediation manifest edited.

## Minimal actionable conclusion

**Remove the premature CPRI token only from the 328 source rows that contain both KORS and CPRI, dated 2016-01-04 through 2018-09-18 inclusive; then use the already verified KORS → CPRI canonical issuer mapping.** This removes a duplicate representation of one issuer without removing that issuer's membership or inventing a second security.

The identity evidence is explicit: the issuer's SEC-hosted announcement says it changed its name from Michael Kors Holdings Limited (NYSE: KORS), with CPRI becoming its NYSE ticker on **2019-01-02**. CPRI was not an additional issuer admitted in 2016.

From 2018-09-19 onward the base file already contains CPRI alone, although the real ticker remained KORS through 2018-12-31. Preserve this as a **canonical issuer view**, and explicitly do not claim CPRI was the contemporaneous ticker in 2018. It is unnecessary to add back KORS or drop the issuer in that interval to resolve the duplicate.

## Primary evidence and effective dates

1. S&P Dow Jones Indices, 2013-11-08: [Previously Announced S&P 500 Addition Michael Kors to Join Index on November 12](https://press.spglobal.com/2013-11-08-Previously-Announced-S-P-500-Addition-Michael-Kors-to-Join-Index-on-November-12).
   - Exact relevant statement: “Michael Kors Holdings Limited (NYSE: KORS) will replace NYSE Euronext Inc. (NYSE:NYX) in the S&P 500 after the close of trading on Tuesday, November 12.”
   - Therefore first member trading session is **2013-11-13**, matching the base.
   - This dated final notice supersedes an earlier October 28 announcement proposing November 1; use the November 8 notice.
   - Saved source: `kors-20131108-sp500-addition.source.json`.

2. Issuer release filed with SEC, CIK **1530721**, 2018-12-31: [Exhibit 99.1, Completes Acquisition of Versace](https://www.sec.gov/Archives/edgar/data/1530721/000119312518362322/d653406dex991.htm).
   - Exact relevant statement: “Capri Holdings Limited ... announced today that it has changed its name from Michael Kors Holdings Limited (NYSE: KORS), and beginning on January 2, 2019, its New York Stock Exchange ticker symbol will be CPRI.”
   - This is a same-company name/ticker change alongside its acquisition of Versace, not a separate listing of a second S&P 500 issuer.
   - Name changed by **2018-12-31**; ticker change effective **2019-01-02**.
   - Saved source: `kors-cpri-20181231-sec-rename.source.json`.
   - Independently retrieved again; matches existing repository alias evidence in `data/reference/v04-remediation/price-evidence/investigation-report.md` and `alias-price-validation.json`.

3. S&P Dow Jones Indices, 2020-05-06: [DexCom & Domino's Pizza Set to Join S&P 500; ... Capri Holdings to Join S&P SmallCap 600](https://press.spglobal.com/2020-05-06-DexCom-Dominos-Pizza-Set-to-Join-S-P-500-Salesforce-com-to-Join-S-P-100-STORE-Capital-to-Join-S-P-MidCap-400-Capri-Holdings-to-Join-S-P-SmallCap-600).
   - Effective “prior to the opening on Tuesday, May 12”; “Domino's Pizza Inc. (NYSE:DPZ) will replace Capri Holdings Ltd. (NYSE:CPRI) in the S&P 500.”
   - CPRI leaves S&P 500 / joins S&P SmallCap 600 on **2020-05-12**, so final S&P 500 member trading session is **2020-05-11**.
   - Saved source: `cpri-20200506-sp500-deletion.source.json`.

## Exact local inspection

Base file: `/Users/fighting/code/short-hold-momentum/data/reference/sp500_history.csv`.
SHA256: `39a9202c9ef69a74c0ff07e2113ad41fb6da7c8c5b6cd9541f0185fb4391e717`.
Source rows: 2,718.

| Source state transition | KORS present | CPRI present | Interpretation |
|---|---:|---:|---|
| 2013-11-13 | yes | no | Correct first membership session |
| 2016-01-04 | yes | yes | Duplicate representation starts |
| 2018-09-19 | no | yes | Duplicate ends; CPRI label is premature |
| 2020-05-12 | no | no | Correct removal effective session |

The 328 duplicate source dates are listed in `kors-cpri-base-audit.json`. These are **source snapshot rows**, not 328 exchange sessions. The source is sparse/event-based. Its last positive CPRI row is 2020-04-06, followed by the negative 2020-05-12 row; carry-forward membership therefore lasts through 2020-05-11. **Do not misinterpret 2020-04-06 as the deletion date.**

No 2013 admission or 2020 removal date discrepancy was found under the source's carry-forward snapshot semantics. If a consumer instead treats positive rows as isolated daily observations, its derived boundary would be wrong; that is not evidence to alter the source dates.

## Bounds

The issuer identity and duplicate removal are resolved by direct primary evidence. The reason the upstream dataset began duplicate CPRI labels in 2016, and switched the remaining label in September 2018, is not established. The adjustment should be logged as an explicit source normalization, not claimed as an S&P constituent event or as validation of every other historical member.

