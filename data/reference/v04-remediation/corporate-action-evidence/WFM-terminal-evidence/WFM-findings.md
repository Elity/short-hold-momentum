# WFM terminal-event evidence — work only

Status: **UNVERIFIED_TERMINAL_SESSION**. No price data, source code, or runtime manifest was modified. This packet is not eligible to freeze a winner.

## Confirmed legal terms

The issuer's SEC 8-K, dated August 28, 2017, states that Amazon completed the acquisition on **2017-08-28**, and each eligible outstanding ordinary share “was converted into the right to receive **$42.00 in cash, without interest**.” Whole Foods survived as Amazon's wholly owned subsidiary; WFM ordinary equity ceased under the merger. The default ordinary-share terms exclude specified company/acquirer-owned shares and dissenting shareholders. Employee stock awards in the same 8-K are not exchange-traded option settlement evidence.

SEC source: https://www.sec.gov/Archives/edgar/data/865436/000114420417045261/v474128_8k.htm

## The last executable session is unresolved

The 8-K says the company “is requesting” Nasdaq to “suspend trading ... **prior to market open on August 28, 2017**.” That is a request, not a completed exchange halt timestamp.

Nasdaq's own updated Equity Corporate Actions Alert ECA2017-10 says **“The merger became effective today, August 28, 2017.”** Its table states **“Marketplace Effective Date for Suspension:  August 29, 2017”**. The exchange's marketplace suspension field is **more direct operational evidence than the issuer's request**; these statements should not be treated as two equally authoritative final halt records. Prefer the exchange date when forming the work-only proposal.

The Nasdaq title explicitly contains **(UPDATED)**. Its visible header is **Thursday, August 24, 2017** and Search_MCP `lastUpdatedAt` is `2017-08-24T00:00:00.0000000`; the body itself refers to August 28 as today. The exact revision timestamp is therefore **not supplied**. The search crawler timestamp (`2025-02-15T11:12:00.0000000Z`) is not an event or update date. The SEC document is dated August 28; no separate last-updated timestamp is provided. `WFM-exact-source-quotes.json` preserves both verbatim excerpts, URLs, and date metadata.

Nasdaq source: https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2017-10

The local archive's last two observations are:

| Date | Open | High | Low | Close | Volume |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2017-08-25 | 41.99 | 42.00 | 41.99 | 41.99 | 4,268,652 |
| 2017-08-28 | 41.99 | 41.99 | 41.99 | 41.99 | 760,065 |

The final row's nonzero volume corroborates August 28 market activity, consistent with Nasdaq's August 29 suspension date. **Recommendation: preserve August 28 and prefer August 29 as the effective session in the review proposal. Do not crop the archive at August 25 merely from the issuer request.** The constant OHLC still does not establish a normal executable daily session or the precise intraday halt. The packet keeps automatic application disabled until that narrower issue is resolved; it does not claim the archive is contaminated. The exact verified last trading session and halt timestamp remain null, alongside populated recommended dates for review.

## Final ordinary dividend is already in adjusted prices

The SEC 2017 annual report lists the final ordinary dividend as declared **2017-06-07**, amount **$0.18**, record date **2017-06-30**, payment date **2017-07-11**. Its fiscal-2017 table lists three dividends, $0.14 + $0.14 + $0.18 = $0.46, with no later ordinary dividend in that table. The archive's June 28 ex-date is crosschecked by DividendHistory and DividendMax; the captured SEC table does not itself quote the ex-date.

SEC source: https://www.sec.gov/Archives/edgar/data/865436/000086543617000238/wfm10k2017.htm

On June 27 the archive raw close is 42.56 and adjusted close is 42.379448503417. On June 28 raw and adjusted close are both 42.25, with ex-dividend 0.18. The prior-day factor is **0.9957577185953242**, matching **42.25 / (42.25 + 0.18)** to less than 1e-12. The adjusted ex-day return therefore equals **(42.25 + 0.18) / 42.56 - 1**. This is the archive's observed total-return convention; it is not the different approximation `1 - dividend / prior_close`.

The research close matches the archive adjusted close, while `as_traded_close` matches raw close. From June 28 through the archive tail the price factor is 1. Consequently the $0.18 ordinary dividend is already in adjusted-price performance. **The terminal cash event is $42.00, not $42.18**; do not separately pay the ordinary dividend again or both liquidate and redeem the same shares. Raw OHLC alone do not separately credit dividend cash; a raw-price accounting model would need its own dividend ledger. This audit does not certify all historical WFM adjustments.

## ADR-014 cash release is a model date

ADR-014 selects release on the **fifth XNYS session strictly after the effective session**. Cash is receivable and part of NAV at the event, but is unavailable for new purchases until release. This is not a claim about any investor's actual broker posting date.

The cutoff evidence produces a preferred mapping and an alternative requiring stronger confirmation; these are date interpretations, not strategy candidates:

| Condition requiring confirmation | Last tradable session | Effective session | Model cash release |
| --- | --- | --- | --- |
| Issuer-requested pre-open suspension actually prevented the August 28 strategy session | 2017-08-25 | 2017-08-28 | 2017-09-05 |
| August 28 was an executable session and August 29 is the first unavailable session | 2017-08-28 | 2017-08-29 | 2017-09-06 |

Both retain **2017-08-28 as the confirmed legal merger date**. September 4 was a market holiday. **The recommended review mapping is last session August 28, effective session August 29, model release September 6**, because Nasdaq is the direct marketplace source. Neither mapping is applied. The verified/automatic action fields remain null, while `recommended_alternative_for_review` contains the preferred dates and limitations. No broker posting date is claimed and no cash may silently release merely from this work-only proposal.

## Reproducibility and focused checks

`audit_wfm_terminal.py` reads only the two existing WFM parquet files and ADR-014. It records their hashes, the evidence hashes, the final dividend arithmetic, the archive/research field mapping, the terminal observations, and both calendar mappings. It makes no external requests and asserts the inputs remain unchanged. The task used exactly three external searches and performed no broad historical-price search.
