# FRX / DTV completed-merger evidence

Reviewed 2026-09-07 Asia/Taipei. Evidence-only research; no application code or main manifest changed.
Machine-readable findings: `frx-dtv-evidence-fields.json`. Sources are saved beside this note.

## Implementable core

| Field | FRX → ACT | DTV → T |
|---|---|---|
| Last traded session | 2014-06-30 | 2015-07-24 |
| Legal merger completion | 2014-07-01 | 2015-07-24 |
| First session old security cannot trade | 2014-07-01, suspension before open | 2015-07-27; merger completed on Friday 07-24 |
| Cash entitlement per old share | **$26.04** under default/no election | **$28.50** |
| Successor stock per old share | **0.3306 ACT** | **1.892 T** |
| Old final raw close | **$99.00**, local archive only | **$93.55**, archive + contemporary reporting + market table |
| Fractional share treatment | Aggregate holder's entitlement; cash residual at **$219/ACT share**, confirmed final | No fractional T issued; cash based on agreement's Average Parent Stock Price; applicable equity rate not uniquely established here |
| Exact spendable cash/account credit date | **Not established** | **Not established** |

These are per-share completed terms, not acquisition enterprise values. A mandatory exchange extinguishes the old shares and creates successor-stock and cash entitlements. It is not an ordinary sell at the old last close.

## FRX: completed terms, election and payment

The [Forest final 8-K](https://www.sec.gov/Archives/edgar/data/38074/000119312514259565/d749194d8k.htm), Item 2.01, states the July 1, 2014 completed merger, the per-share choices, actual proration results, and the no-election default. Item 3.01 states that NYSE suspended FRX **before the open on July 1**; Item 3.03 states the shares were cancelled and converted into merger consideration that day.

Use the **standard/default** $26.04 + 0.3306 ACT unless the model explicitly documented an election before June 27 at 5 p.m. New York time. The alternatives are not interchangeable:

- Cash election: $86.81, actually paid only to holders who elected it.
- Stock election: after actual proration, $25.67 + 0.3326 ACT.
- Standard and no valid election: $26.04 + 0.3306 ACT.

Both the final 8-K and the [July 2 issuer final-results release](https://www.sec.gov/Archives/edgar/data/1578845/000119312514259548/d750228dex993.htm) confirm fractional ACT shares cashed out at **$219.00 per ACT share**. The release contains an apparent drafting error in its no-election bullet (“for each Actavis ordinary share”); the final 8-K and merger agreement unambiguously specify **per Forest share**, which is the operative interpretation.

The primary [Form S-4](https://www.sec.gov/Archives/edgar/data/1578845/000119312514178606/d686059ds4a.htm), pages 113–114 (Transmittal Materials and Procedures) and 117 (No Fractional Shares), says:

- Transmittal materials are sent promptly after the effective time.
- The holder receives stock/cash after delivering a properly executed transmittal and reasonably required documents; **no interest** is payable.
- Entitlements take account of **all shares held by the holder**, so round aggregate successor shares, not each old share separately.
- Fractional cash uses ACT's ten-trading-day VWAP from the eleventh trading day before closing through the second-to-last trading day before closing. The final $219 rate resolves this formula for the actual event.

This establishes when the right exists and the exchange procedure. It does **not** establish a universal July 1 spendable-cash/account-credit time or a universal T+N payment date. Full SEC HTML/text and exact excerpts are retained.

### FRX final quote and successor identity

The local archived raw FRX row is 2014-06-30 O100.16 H100.46 L99.00 C**99.00** V11,460,490; `adj_close` is also 99.00. Its file hash and row are recorded in `local-raw-price-checks.json`. The date is consistent with the SEC trading-suspension notice. **I did not locate an independent contemporary/exchange quote confirming the $99.00 number**. Search pages now using FRX often refer to unrelated Forest Road/Beachbody or Canadian Fennec and must not be treated as corroboration.

The ACT consideration shares belong to **Actavis plc, CIK 1578845**. The [June 15, 2015 issuer release](https://www.sec.gov/Archives/edgar/data/1578845/000119312515223399/d942720dex991.htm) and OCC #36885 confirm a subsequent **1:1 name/symbol change ACT → AGN** at the June 15 open, new CUSIP **G0177J108**. This is not the old Allergan, Inc. AGN (CIK 850693): that older issuer was separately acquired on March 17, 2015, its old shares receiving $129.22 + 0.3683 ACT and ceasing trade before that day's open ([old Allergan 8-K](https://www.sec.gov/Archives/edgar/data/850693/000119312515096184/d894643d8k.htm), Items 2.01/3.01). Its header has an apparent 2014 typo; the transaction paragraphs and filing path are 2015.

The archived `AGN.parquet` raw observations in 2014 look like the ACT lineage (e.g. 2014-07-01 close 224), not old Allergan's pre-acquisition lineage. That is a useful consistency observation, **not independent proof that every historical row is correctly identified**. Keep the two economic identities separate when resolving cache labels.

## DTV: completion, fractional shares and payment

[AT&T's completed-merger 8-K](https://www.sec.gov/Archives/edgar/data/732717/000073271715000069/form8k.htm), Item 2.01, states that on July 24, 2015 each DTV share became the right to **1.892 T + $28.50 + cash in lieu of fractional shares**. It explicitly says DTV ceased trading upon completion and supplies T's unadjusted NYSE closing price that day: **$34.29**. The merger's calculated mark using that T close is $93.37668 per old DTV share before holder-level fractional rounding; that is **not** DTV's actual last trade, which was $93.55.

DTV's final-day close is independently reported in the contemporary [Los Angeles Business Journal story, July 24, 2015](https://labusinessjournal.com/media/t-directv-mega-merger-gets-green-light/): “DireTV shares closed Friday at $93.55.” The story rounds the share ratio to 1.9; use SEC's exact **1.892**. Investing's daily table and the local raw archive agree on O93.91 H94.63 L93.36 C93.55, volume ~17.64M. No new DTV common-stock quote should be created for July 27.

The [executed merger agreement](https://www.sec.gov/Archives/edgar/data/732717/000119312514203711/d729946dex101.htm), sections 4.1 and 4.2, establishes:

- Final exchange ratio is governed by a collar; use the completed 8-K's 1.892 rather than a preliminary ratio or a $95 fixed-value assumption.
- No fractional T shares are issued. Section 4.2(e) bases cash in lieu on the **Average Parent Stock Price** defined in the agreement.
- Transmittal is mailed promptly and within **four business days**. This is a mailing deadline, **not a four-day cash-payment guarantee**.
- Payment follows surrender/processing and carries no interest.
- The [issuer's book-entry letter](https://investors.att.com/~/media/Files/A/ATT-IR/documents/book-only-shares.pdf) confirms automatic exchange of uncertificated shares, crediting of uncertificated T shares, transaction advice, and a check containing the merger cash plus fractional cash. The certificated-holder version requires surrender before cash/dividends are released.

Two later numerical fractional-cash observations need separate labels:

1. AT&T's [tax-basis illustration](https://investors.att.com/~/media/Files/A/ATT-IR-V2/documents/dtv-cost-basis.pdf) uses **$35.14/T share** and **$7.03 for 0.2 T**. The document explicitly describes illustrative tax calculations and is not an individual account settlement record.
2. OCC [#37310, August 19, 2015](https://infomemo.theocc.com/infomemos?number=37310) says adjusted **T1 options** had deliverable 189 T + $2,850 + cash in lieu of 0.2 T. OCC uses **$34.916215/T share**, rounded to **$6.98 per option contract**, and confirms the cash component was delayed while stock exercise/assignment deliveries had settled through NSCC.

Do not copy the option deliverable, its rounding, or its August 19 cash-clearance statement into the ordinary-stock account as though they establish universal equity settlement. Record the channel-specific rates and leave an exact account credit date unknown.

## Implementation implications and remaining uncertainty

- Store legal effective date, last trading session, first untradable session, entitlement creation date, and cash/share availability separately.
- Convert the **economic share quantity**, not arbitrary units of a total-return-adjusted price series. If stored prices equal raw price × factor, nominal old shares = model units × old factor; successor model units = nominal old shares × exchange ratio ÷ successor factor. Without that basis conversion, using today's dividend-adjusted T price (~12 for July 2015) with the nominal 1.892 ratio would create a fictitious loss versus raw T at $34.29.
- A realistic integer-share account should aggregate the holder's successor entitlement, issue whole shares, and create the fractional cash receivable. A fractional-share research approximation may retain the full ratio, but must label the approximation.
- Creation of a cash receivable preserves net asset value; it does not prove the money was immediately reusable for purchases. If a simplified cash-availability convention is chosen, label it as a model assumption and test whether it changes the decision.
- Two unresolved evidence items remain material to a literal historical-account replay: exact cash/share credit timing for each account and FRX's independent final raw quote. DTV's precise applicable equity fractional-cash rate also remains distinct from the identified illustrative/option rates. These do not invalidate the fixed per-share core terms or justify carrying extinguished FRX/DTV positions forever.

