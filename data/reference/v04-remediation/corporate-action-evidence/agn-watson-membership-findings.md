# Old AGN versus Watson / Actavis membership correction

Reviewed 2026-09-07 Asia/Taipei. Evidence and proposal only; source CSV, loader, prices and manifests remain unchanged.

## Conclusion

**Old Allergan and Watson/Actavis were two independently eligible S&P 500 issuers throughout the 2005 development period up to the old Allergan index removal. Preserve old AGN as AGN_OLD and restore the missing Watson/Actavis lineage; deleting old AGN would be incorrect.**

The base has **no WPI or ACT tokens anywhere**, including no ticker containing either root as a delisting suffix. The only WAT-like token is **WAT**, which is Waters Corporation, a different company (SEC issuer release, CIK 1000697). No alternate Watson token was found.

## Primary membership proof before and within the research period

The SEC-hosted **SPDR Trust, Series 1 annual reports** explicitly describe full replication: “all 500 securities of the S&P 500 Index are owned by the Trust.” Their schedules independently contain all three companies:

| As of | Old Allergan, Inc. | Watson Pharmaceuticals | Waters Corp. |
|---|---|---|---|
| 2004-09-30 | 572,296 shares; $41,520,075 | 474,209 shares; $13,970,197 | 535,133 shares; $23,599,365 |
| 2005-09-30 | 556,406 shares; $50,977,918 | 433,967 shares; $15,887,532 | 487,162 shares; $20,265,939 |

Primary URLs:
- [SPDR 2004 annual report](https://www.sec.gov/Archives/edgar/data/884394/000095013505000099/b52997nanv30dza.txt), saved as `spy-2004-membership.primary.txt` and exact excerpt/hash file `spy-2004-membership.evidence.json`.
- [SPDR 2005 annual report](https://www.sec.gov/Archives/edgar/data/884394/000095013505006765/b57342mfnv30d.txt), corresponding `spy-2005-membership.*`.

These are fund issuer primary holdings records, not a downloaded daily file from the index administrator. They directly confirm that the two healthcare issuers were separate constituents at those dates.

## Entry and removal chronology

[TheStreet, April 6, 1999](https://www.thestreet.com/markets/watson-pharmaceuticals-to-replace-aeroquip-vickers-in-sp-500-733366) contemporaneously reports that Watson Pharmaceuticals **WPI**, then in the S&P MidCap 400, would replace Aeroquip-Vickers **ANV** in the S&P 500 after Friday's closing bell. That Friday was **April 9**, so the first member session is **1999-04-12**. This corroborates the start date but is secondary reporting; an original 1999 S&P press release was not located in this bounded search. The SEC 1999 S-3 and 10-K directly confirm Watson's NYSE ticker **WPI** and CIK **884629**.

The [official S&P announcement of March 16, 2015](https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20150316-155946/155946_americanair1agn5.pdf) states:
- AAL replaces **Allergan Inc. AGN** after the close on **Friday, March 20**.
- **“S&P 500 constituent Actavis plc (NYSE: ACT)”** is acquiring Allergan.

Thus **AGN_OLD membership ends before 2015-03-23**, while ACT was already a separate S&P 500 constituent and remains represented. Old AGN's **trading suspension was earlier**, before the March 17 open, as its completed-merger SEC 8-K confirms. Preserve the index date; do not manufacture trading quotes for the intervening suspended sessions.

## Identity chain

- Watson Pharmaceuticals, Inc., **WPI**, CIK **884629**.
- **2013-01-24**: company adopts Actavis, Inc. and ticker **ACT** ([issuer announcement](https://www.prnewswire.com/news-releases/watson-pharmaceuticals-inc-is-now-actavis-inc-188196701.html)).
- **2013-10-01**: U.S. Actavis becomes a subsidiary of Irish Actavis plc, CIK **1578845**; **each old Actavis common share converts into one new ordinary share**. SEC [Note 5, Subsequent Events](https://www.sec.gov/Archives/edgar/data/1578845/000119312513419816/R10.htm) identifies the new entity as successor issuer and confirms NYSE ticker ACT. Warner Chilcott's separate 0.160 exchange ratio must not be applied to old ACT.
- **2015-06-15**: Actavis plc adopts name Allergan plc and ticker **AGN**; see the already saved issuer and OCC #36885 evidence.
- Original Allergan, Inc. AGN, CIK **850693**, is the separately acquired old issuer, with its March 17, 2015 cash/stock merger. It is not a simple earlier name of the Watson lineage.

## Smallest explicit patch using existing canonical AGN prices

Use `AGN` as the **canonical identity key** for Watson/Actavis/Allergan plc, and `AGN_OLD` for original Allergan:

1. On source rows before **2015-03-23**, replace existing AGN with **AGN_OLD**.
2. On rows **1999-04-12 <= date < 2015-03-23**, independently add canonical **AGN** for Watson/Actavis.
3. From **2015-03-23 onward**, retain the existing canonical AGN; no AGN_OLD.

This retains old Allergan before 1999 and gives both issuers during the overlap. It does not claim Watson traded as AGN in 2005: the actual-symbol timeline above remains distinct metadata.

Base SHA256: `39a9202c9ef69a74c0ff07e2113ad41fb6da7c8c5b6cd9541f0185fb4391e717`.
- Old issuer preserved: **2,134 source rows**, 1996-01-02–2015-03-19.
- Dual-issuer interval: **1,744 source rows**, 1999-04-12–2015-03-19.
- Of those, **1,119 source rows** are dated in 2005 onward.
- These are sparse snapshots, not exchange-session counts; 2015-03-19 carries forward through March 20.
- Exact inventory/boundaries: `agn-watson-base-audit.json`.
- Machine-readable proposal: `agn-watson-membership-proposal.json`.

The base drops from 491 to 490 members on 1999-04-12 while removing ANV and not adding WPI; this is consistent with an omitted new member. It is a diagnostic observation, not a reason to force every historical row to 500.

## DTC cash / stock credit date follow-up

The additional bounded searches of DTCC, SEC and issuer materials did **not** find an event-specific FRX or DTV DTC distribution-allocation notice proving a universal cash or successor-stock availability date. Search results are logged in `dtc-credit-date-search-audit.json`.

Keep **FRX and DTV cash_available_date and successor_stock_available_date unknown**. The existing issuer letters and agreements establish exchange mechanics and legal entitlements. Mailing deadlines, completed-merger announcements, OCC/NSCC option settlement notices, general DTC rules, and Furiex CVR payments do not supply an ordinary FRX/DTV shareholder's available-cash date.
