# V7 public-data research handoff — 14 October 2026

## What is delivered

- [50-row evidence ledger](../data/research/evidence-ledger-2026-10-14.csv): preserves every original selected identity. The original T212 cash row explicitly maps to the previously approved standalone UK bank savings override; it does not claim the bank account is inside Trading 212.
- [Source acquisition manifest](../data/research/source-acquisition-manifest-2026-10-14.json): exact attempted endpoints, HTTP results, timestamps, hashes and source-family acquisition instructions.
- [Issuer history audit](../data/research/issuer-history-audit-2026-10-13.csv): 52 extracted NAV/fund-growth arrays across 26 iShares instruments. These are actual issuer arrays, not executed/reconciled production total-return panels.
- [Issuer factual snapshot](../data/research/issuer-facts-snapshot-2026-10-13.json): per-field dates, fees, currencies, bond-risk fields and holdings acquisition context where supplied. Null or absent fields remain unresolved.
- [SONIA daily observations](../data/research/sonia-daily-boe-2026-10-13.csv) and [acquisition audit](../data/research/sonia-acquisition-audit.json): 7,523 observations, 1997-01-02 through 2026-10-09. 970 overlapping parsed FRED observations agree exactly. This is a partial cross-check, not all-history verification.
- [Calibration decisions](v7-calibration-decisions.md) and [remaining blockers](v7-research-blockers.md).

## Acquisition results and priorities

### 1. Replace the historical short-rate approximation

The BoE HTML table was downloaded successfully even though CSV access had failed. Use the exact IUDSOIA URL in the manifest, extract date/value table cells, and parse rates as percent per annum. Avoid the FRED graph CSV route: it returned 404. The FRED public data page worked but is a secondary cross-check, not an alternative label for US RF.

Published delayed BoE database SONIA is reusable under the UK Open Government Licence according to the Bank's SONIA policy Access section. Attribution: **Source: Bank of England. Contains public sector information licensed under the Open Government Licence v3.0.** This permission is for database data; it does not imply unrestricted redistribution of real-time licensed feeds. The supplied CSV contains observations, not calculated monthly returns. Implement and validate monthly compounding separately. Note the 23 April 2018 methodology reform. Keep historical SONIA, forward short-rate scenarios and the savings AER distinct.

### 2. Complete the exact fixed references

VWRP (IE00BK5BQT80) and VAGS (IE00BG47K971) official pages show downloadable historical prices. The full downloads were **not acquired** in this pass. The HTML `serverApp-state` is configuration, not a complete historical series. Download maximum-range prices from the historical-prices panel; both selected classes accumulate, so own-class NAV is the natural starting point. VWRP USD NAV must be translated to GBP; VAGS GBP-hedged NAV must not receive a second unhedged FX conversion. Current page OCFs are 0.14% and 0.08%. Do not keep an older VWRP fee without its date.

VAGS page gives August 2026 YTM 4.5% and duration 6.0 years. Confirm whether the YTM is underlying pre-hedge yield before using it as GBP carry. Build the 60/40 reference from the same two validated net GBP series with **monthly rebalancing** as the explicit default; also report buy-and-hold sensitivity when comparing long horizons. No silent substitution with other tickers.

XS2D selected class is USD, accumulating, Luxembourg UCITS swap; September 2026 factsheet gives 0.60% fee and the S&P 500 2x Leveraged Daily Net Total Return USD index (SPXT2LUN). Actual product history and current binding financing/reset terms are still required. A validated historical benchmark may be shown independently of forecast-optimisation eligibility; unavailable forecast statistics must remain unavailable. Do not replace it with an unleveraged fund or simulated index labelled XS2D.

Acceptance: exact ISIN and currency, >=36 common actual complete monthly returns for risk, fee-once reconciliation, annual issuer-return comparison, dated latest month, no stale quote data, reproducible hashes and explicit reference weights/rebalancing. Equity FF5 fitting additionally needs >=72 actual months and chronological validation.

### 3. Expand cross-asset coverage from accessible data

The iShares acquisition route covers SGLN, SSLN, IGLS, IGLT, INXG, IS15, SLXX, IBTS, IBTM, IBTL, ITPG, GHYS, SWDA, EMIM, IIND, IASH, IWDP, IWFV, IWFM, IWFQ, MVOL, IWFS, WLDS, IUVF, IEFV and EMVL.

Parse public HTML attributes named `componentprops` with an HTML parser (which decodes entities), then JSON. Under `performance.containersByNameMap.chart.dataPointsByNameMap`, pair `asOfDate` with `value` in `navData` and `performanceData`. Values can be numbers **or numeric strings**. Use neither `benchmarkData` nor stale market `priceData`. SWDA's market-price series ended in 2018 despite its actual fund history continuing into 2026.

For distribution shares, raw NAV is not total return. Reconcile issuer fund growth to published reinvested fund returns; alternatively acquire all distributions/splits. Calendar-month coverage in the audit means at least one observation existed, not that the month is complete. Validate actual exchange/valuation calendars, inception boundary and any missing endpoint. EMVL fund-growth data omit July–November 2018; do not forward-fill. IWFS current equal-weight mid-cap exposure needs an index-change review before treating older strategy returns as homogeneous.

Start with savings / SGLN or SSLN / IGLT plus short gilts / SWDA / IWFV. These supply five categories. The sixth category, leverage, needs actual contract/path validation; do not manufacture six-category completeness. Add XS2D first if its mechanics and overlap pass. Daily leverage can remain disabled while the other categories become usable, with the exact unresolved reference visibly marked.

### 4. Other issuer adapters and manual acquisitions

| Family | Evidence and next action | Admission constraint |
|---|---|---|
| Vanguard nine selected classes | Public product pages retrieved; full historical-prices export plus full distributions for VUSA/VUKE/VMID/VERX/VJPN/VAPX/VEMT | No fabricated full coverage/count from the page's download count; GBP listing does not determine NAV currency |
| SPDR USSC/ZPRX/GLTL | Public pages with dated facts; holdings XLSX links exist. USSC: `https://www.ssga.com/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-zprv-gy.xlsx`; select analogous links from each exact page | Full NAV/distribution files not retrieved; holdings not company-mapped. USSC London USD and ZPRX Xetra EUR require correct quote handling |
| Invesco CMOP/EQQQ | Public pages retrieved; obtain exact-class full NAV and distribution files and current factsheet/contract | CMOP 0.19% ongoing plus 0.15% swap component must be reconciled, not reduced to physical-gold model; EQQQ is distributing |
| WisdomTree COPA/AIGA/CRUD/GGRG/3LUS | Current product pages offer Historical Data date-range XLSX export; old AIGA FR route returned 401 but current GB product page succeeded | Complete files not acquired; futures roll/collateral/index versions and leverage restrikes still need contract checks |
| JPM JPGL | Official product list identifies USD JPGL versus GBX JPLG, same ISIN, 0.20% TER | Full exact-class NAV and dated full holdings outstanding; do not use another JPM fund |
| DWS XS2D | Factsheet retrieved, product page is client shell | Current binding prospectus/index method and full actual daily history outstanding |
| Amundi LQQ | KID identifies FR0010342592 and 0.60% ongoing charge; attempted prospectus download failed PDF extraction | Retrieve valid current prospectus, verify predecessor/merger continuity, funding and native/FX conventions |
| Leverage Shares 3QQQ | Current page and August 2026 final terms obtained; daily 3x QQQ exposure and 16.67% intraday threshold identified | Read incorporated Conditions version 7 and referenced prospectus/supplements; funding spread and intraday path not validated |

Public access does not automatically establish redistribution rights. Issuer raw histories and whole legal documents are not republished here; exact endpoints and extraction instructions are provided. Retain permitted manual source files in the application's private local cache and record original hashes. No paid data or subscription has been assumed.

### 5. Holdings and company diversity

The iShares snapshot records public holdings endpoint context and date lists. This is acquisition metadata, not a downloaded, validated full holdings book. SPDR has a direct daily XLSX route. Vanguard's visible top ten and reported position count cannot establish 95% company coverage. Obtain full files, retain ISIN/SEDOL/issuer identifiers, consolidate multiple share classes, map nested funds and economic derivative exposure, and show unknown exposure explicitly. No effective-company number was calculated in this pass.

### 6. Savings comparison

Charter Easy Access Issue 79 was checked at 4.25% AER, minimum £1 and maximum £1m, variable interest, unrestricted withdrawals and no introductory bonus; a nominated withdrawal account is operational plumbing, not a requirement to purchase a linked current-account package. Terms are dated evidence, not a permanent best-rate claim.

Additional official pages retrieved on 14 October show HTB easy-access tracker 4.18%, Ford Flexible Saver 3.99%, and RCI Freedom 3.95%. RCI specifies £100 initial funding and no bonus/notice penalties; HTB specifies £1 and unlimited withdrawals. The alternative products' complete eligibility and no-linked-account conditions were not fully audited, so these are comparison leads, **not fully qualified replacements**. Keep Charter unless a refreshed complete terms check supports a change. URLs and retrieval hashes are in the manifest.

## Implementation acceptance and separation of failures

Do not change production admission flags merely because this ledger says history acquired. Integrate source adapters, validate net GBP returns, execute real calibrations and record results before admission. Use unit tests for parsers, distribution/split handling, SONIA boundaries and currency identities, then integration tests on actual cached data. Keep synthetic fixtures out of production. Run the repository's required pytest gate for financial-code changes and bump model version/cache identity when behaviour changes.

A hosted dashboard calculation error must be diagnosed by the coding agent from its traceback and actual runtime inputs. It is not evidence that public investment data are unavailable. This research commit changes no application logic or admission flags and does not claim the application is complete.
