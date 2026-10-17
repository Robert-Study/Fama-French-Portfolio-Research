# V7 research and implementation handoff for Codex

Research cut-off: 14 October 2026. Repository: `Robert-Study/Fama-French-Portfolio-Research`.

## Start here: instruction to Codex

Implement this handoff in the existing repository. Read `AGENTS.md` and the current data contract first. The earlier research commit is `7dea542a36b804b239cbb6d443f35b9a249f0712`. This document supersedes its “manual history download required” conclusions for Vanguard, SPDR, Invesco, WisdomTree and XS2D. Preserve the original 50 identities and existing dashboard requirements. Do not spend another pass reselecting the universe or merely describing a plan.

The dashboard still lacks data because source discovery has not been integrated into production adapters and calibrated inputs. This research supplies executable acquisition requests. Download, parse, reconcile, calibrate, persist the resulting production inputs and update admission evidence. Diagnose any runtime error using its traceback independently of source availability. Do not disable otherwise valid portfolios because an optional company-diversity statistic is unavailable: keep the statistic explicitly unavailable and explain coverage. Preserve any governing contract restrictions; make a documented, explicit contract change if the existing contract couples these independent capabilities.

**Acquired actual history sources: 46 of 49 securities, plus separately sourced savings and historical SONIA.** This count includes NAV series that still require distribution/split reconciliation; it is not a count of production-ready models. JPGL, LQQ and 3QQQ full histories remain unresolved. No new FF5 regression, optimiser or effective-company-diversity calculation was executed by this research task. Source acquisition and fitting are different jobs.

Build the usable universe from the verified sources below. Maintain separate statuses for identity, history, return reconciliation, expected-return model, risk model, holdings coverage and broker listing. A historical benchmark can be available while its forward model remains unavailable. Never invent a required field merely to admit a product.

## 1. Exact acquisition requests

All requests below use public issuer endpoints observed in product pages or their public client code. No paid feeds, keys or authenticated accounts were used. Requests were actually executed successfully unless marked otherwise. A future access failure must be reported, not bypassed. Cache originals locally with URL, request body, retrieval UTC timestamp, content type and SHA256. A hash establishes file identity, not financial validity.

### A. iShares: 26 selected products

GET `https://www.ishares.com/uk/individual/en/products/{product_id}/`.

Use an HTML parser to decode `componentprops` attributes and JSON-decode them. Select the fullest component with `componentId == "performance"`, then:

`containersByNameMap.chart.dataPointsByNameMap.navData`

`containersByNameMap.chart.dataPointsByNameMap.performanceData`

Pair each object's `asOfDate` (YYYYMMDD) with `value` (numeric values **or numeric strings**). NAV is native-currency NAV; performanceData is issuer fund growth and must be reconciled to the fund's published reinvested returns. Do not use `benchmarkData`. Do not use `priceData`: SWDA's market-price array was stale through 2018 while its fund data continued into 2026.

Fees/currency/inception/structure: `keyFundFacts.containersByNameMap.default.dataPointsByNameMap`. Bond fields: `fundamentalsAndRisk` with each field's own `asOfDate`; keep yield definitions, not just numbers. Some components are repeated or empty (INXG key facts); choose the complete object or fall back to the visible issuer facts, never silently set zero.

For full holdings, follow the actual page anchor ending `/latest-holdings.csv`; do not construct a guessed slug. Such anchors were located for 23 selected products. A successful retrieval still needs CSV schema/date/weight checks. Exclude metal-backing lists and bond issuers from equity company counts.

The repository's `issuer-history-audit-2026-10-13.csv` already lists the 52 NAV/growth arrays and coverage diagnostics. EMVL growth misses July–November 2018; do not forward-fill. IWFS changed index/strategy: inspect regime continuity rather than treating old size-factor exposure as unchanged.

### B. Vanguard: nine selected classes, now automatic

POST `https://www.vanguard.co.uk/gpx/graphql` with headers `Content-Type: application/json` and `X-Consumer-ID: uk2`. The latter is the public site's client identifier, not an API key. JSON body is `{ "query": QUERY, "variables": { "portIds": [PORT_ID] } }`.

For actual native NAV, this query was executed (the website's larger request also retrieves market listings/prices):

```graphql
query HistoricalPricesQuery($portIds: [String!]!) {
  funds(portIds: $portIds) {
    portId
    profile { fundCurrency fundInceptionDate fundFullName }
    pricingDetails {
      navPrices(limit: -1) { items { price currencyCode asOfDate } }
    }
  }
}
```

The successful full request contained these same fields plus profile/listing metadata and `marketPrices`. If this reduced query ever differs from the issuer schema, use the public website's `HistoricalPricesQuery` rather than guessing new fields.

For monthly issuer total returns, use the fields in the successfully executed `Growth10kQuery`:

```graphql
query Growth10kQuery($portIds: [String!]!) {
  polarisPerformanceHistory(portIds: $portIds) {
    monthlyReturns {
      totalReturns(limit: -1) {
        items { portId effectiveDate CMLT { _1MTH } }
      }
    }
  }
  funds(portIds: $portIds) {
    profile { fundCurrency fundInceptionDate fundFullName
              distributionStrategy currencyHedgingStrategy }
  }
}
```

`CMLT._1MTH` is a percentage return: divide by 100. Retain actual share-class history only. Drop the inception stub month unless a previous complete month-end valuation exists. Exclude the current incomplete month. Monthly series can start earlier than the available daily NAV series: several daily histories begin 18 November 2014 despite older inception. Do not backfill daily data from monthly returns.

For distributions, use the successful request's fields:

```graphql
query DistributionHistoryQuery($portIds: [String!]!, $startDate: String) {
  funds(portIds: $portIds) {
    portId
    distributionDetails {
      periodicDistributions(limit: 0, startDate: $startDate) {
        items {
          asOfDate exDividendDate recordDate payableDate
          reinvestPrice reinvestmentDate
          taxDetails {
            totalDistributionTypeName distributionLevelCode
            totalDistributionAmount distributionAmount
            distributionType { distCode distDesc }
            currencyCode
          }
        }
      }
    }
  }
}
```

Do not sum a total-distribution row and its component tax rows. Reinvest on the documented ex-date convention and reconcile to the issuer monthly series. The actual full query also asked for profile/yield metadata; the projection above removes unnecessary fields.

Executed cross-check: VWRP month-end NAV returns versus issuer monthly returns matched across 86 complete overlapping months to <0.000001 bp; VAGS matched across 87 months with maximum discrepancy 1.786 bp. These are native-currency checks, not GBP factor regressions. Investigate rounding/valuation conventions before setting final acceptance tolerances; 10 bp is a diagnostic trigger, not automatic proof.

Holdings: both `borHoldings.dailyHoldings` and VWRP `delayeredHoldings` returned empty books in the tested requests. This does **not** mean the funds hold nothing. The public client supports pagination with `limit:1500` and `lastItemKey`, but availability for these port IDs is unresolved. Use the issuer's full portfolio export if available; do not use top-ten or position counts as coverage.

### C. SPDR: actual XLSX downloads

For each slug below, GET:

`https://www.ssga.com/library-content/products/fund-data/etfs/emea/navhist-emea-en-{slug}.xlsx`

`https://www.ssga.com/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-{slug}.xlsx`

Mappings: USSC → `zprv-gy`; ZPRX → `zprx-gy`; GLTL → `sybl-gy`. Exact ISIN in the header, not the filename ticker, controls identity. All six files were downloaded and parsed. Header rows identify fund, ISIN, report date and NAV currency; NAV table begins at row 6 with Date/NAV/Shares Outstanding/Total Net Assets. Dates are strings `DD-Mon-YYYY`, descending. Stop before legal text. USSC and ZPRX accumulate; GLTL distributes and needs income reconciliation.

USSC and ZPRX each have 2,978 NAV observations from 2015-02-18 to 2026-10-13. GLTL has 3,675 from 2012-05-17 to 2026-10-13. Holdings dated 13 October 2026 contain ISIN, SEDOL, security name, currency, quantity and percent of fund, supporting subsequent company mapping. Security identifiers are not yet consolidated company identifiers. The files restrict reproduction/disclosure without permission: retrieve for permitted use, and do not automatically include raw issuer workbooks in the downloadable ZIP or repository.

### D. Invesco: actual share-class growth

GET `https://dng-api.invesco.com/cache/v1/accounts/en_GB/shareclasses/{ISIN}/performance/rolling?idType=isin&variationType=ALL&baseline=10000`.

Use `lineChartData` entry with `type == "Shareclass"`, then `data[].date` and `data[].value`. Ignore the separate index line. “Hypothetical investment growth” describes scaling actual fund returns to 10,000; it does not authorise pre-inception index backfill. Verify `isin`, `inceptionDate`, `effectiveDate` and `currency`.

CMOP: 2,409 records, 2017-01-09 to 2026-10-13, USD. EQQQ: 5,985, 2002-12-02 to 2026-10-13, USD. EQQQ distributes: confirm reinvestment basis against issuer annual fund returns before using growth as net total return. The `/distribution?idType=isin` response was only a small current-distribution response, not proven complete historical distributions. `/keyStats?idType=isin&productCode=ETF&bondType=NotCallable` also responded successfully.

### E. WisdomTree: actual XLSX export

POST `https://www.wisdomtree.com/api/fund-history/{entity_id}/historical-data-export` with JSON content type and body:

```json
{"locale":"en-GB","productName":"TICKER","fromDate":"1990-01-01","toDate":"2026-10-14","includeNav":true,"includeAum":false}
```

Mappings: COPA `1000073`; AIGA `1000063`; CRUD `1000076`; GGRG `1000422`; 3LUS `1000395`. All five requests succeeded. Read workbook rows whose first nonblank cell is an ISO date and next cell is NAV; skip disclaimers/header cells. Values are rounded to five decimal places. Verify currency against the product and file, and corporate-action adjustments before return calculation. The old French AIGA page failed, but the current GB page and export worked.

The public client also exposes `/api/fund-history/{entity_id}?dataset=premiumDiscount&format=json`; that is **premium/discount**, not NAV or total return. Do not confuse the datasets.

### F. XS2D: exact fixed leveraged benchmark, now automatic

GET `https://etf.dws.com/api/pdp/en-gb/etf/LU0411078552/historicaldata/download?startDate=2010-03-18&endDate=2026-10-14&includeTax=true`.

The downloaded workbook has a NAV table headed Date, Asset Under Management, NAV, Index Level, tax fields. It contains **4,105 NAV observations**, 2010-03-18 to 2026-10-13. Dates are `DD.MM.YYYY`, descending; parse header names, not assumed worksheet numbers. Native NAV is USD, accumulating share class 1C. Index Level has missing values and is not the fund's NAV.

Also verified: `https://etf.dws.com/api/pdp/en-gb/etf/LU0411078552/performancechart`. Its `seriesConfiguration` identifies NAV versus index; `values` contains Unix-millisecond dates and nested arrays. Prefer the explicit XLSX NAV column unless the chart schema is separately tested. Fund performance is stated net of fees/index replication costs; do not deduct those again from actual history.

## 2. Download audit and universe mapping

Observation counts below are extracted records, not proof of trading-calendar completeness, absence of stale prices, or admissibility. Reconciliation and calibration remain implementation work. The existing detailed ledger contains legal/fee/source fields and unresolved items. The following mapping is sufficient to route every selected identity to the exact source family.

| Identity | ISIN | Acquisition key | Ongoing fee % pa (dated snapshot) |
|---|---|---|---|

| T212_GBP_CASH | null | bank override | 0 |

| SGLN | IE00B4ND3602 | A / 258441 | 0.12 |

| SSLN | IE00B4NCWG09 | A / 258443 | 0.2 |

| CMOP | IE00BD6FTQ80 | D / ISIN | 0.19 |

| COPA | GB00B15KXQ89 | E / 1000073 | 0.49 |

| AIGA | GB00B15KYH63 | E / 1000063 | 0.49 |

| CRUD | GB00B15KXV33 | E / 1000076 | 0.49 |

| IGLS | IE00B4WXJK79 | A / 251804 | 0.07 |

| IGLT | IE00B1FZSB30 | A / 251806 | 0.07 |

| GLTL | IE00B6YX5L24 | C / sybl-gy | 0.15 |

| INXG | IE00B1FZSD53 | A / 251717 | 0.10 (visible issuer facts; refresh date) |

| IS15 | IE00B5L65R35 | A / 251840 | 0.2 |

| SLXX | IE00B00FV011 | A / 251839 | 0.2 |

| VAGS | IE00BG47K971 | B / 9685 | 0.08 |

| IBTS | IE00B14X4S71 | A / 251715 | 0.07 |

| IBTM | IE00B1FZS798 | A / 251716 | 0.07 |

| IBTL | IE00BSKRJZ44 | A / 272124 | 0.07 |

| ITPG | IE00BDZVH859 | A / 295697 | 0.12 |

| GHYS | IE00B8KQFS66 | A / 253488 | 0.55 |

| VEMT | IE00BZ163L38 | B / 9664 | 0.23 |

| VWRP | IE00BK5BQT80 | B / 9679 | 0.14 |

| SWDA | IE00B4L5Y983 | A / 251882 | 0.2 |

| VUSA | IE00B3XXRP09 | B / 9503 | 0.07 |

| EQQQ | IE0032077012 | D / ISIN | 0.3 |

| VUKE | IE00B810Q511 | B / 9509 | 0.09 |

| VMID | IE00BKX55Q28 | B / 9525 | 0.10 |

| VERX | IE00BKX55S42 | B / 9524 | 0.10 |

| VJPN | IE00B95PGT31 | B / 9504 | 0.10 |

| VAPX | IE00B9F5YL18 | B / 9522 | 0.15 |

| EMIM | IE00BKM4GZ66 | A / 264659 | 0.18 |

| IIND | IE00BZCQB185 | A / 297617 | 0.65 |

| IASH | IE00BQT3WG13 | A / 273192 | 0.4 |

| IWDP | IE00B1FZS350 | A / 251801 | 0.59 |

| IWFV | IE00BP3QZB59 | A / 270048 | 0.25 |

| IWFM | IE00BP3QZ825 | A / 270051 | 0.25 |

| IWFQ | IE00BP3QZ601 | A / 270054 | 0.25 |

| MVOL | IE00B8FHGS14 | A / 251382 | 0.3 |

| IWFS | IE00BP3QZD73 | A / 270057 | 0.3 |

| WLDS | IE00BF4RFH31 | A / 296576 | 0.35 |

| USSC | IE00BSPLC413 | C / zprv-gy | 0.30 |

| ZPRX | IE00BSPLC298 | C / zprx-gy | 0.30 |

| IUVF | IE00BD1F4M44 | A / 285207 | 0.2 |

| IEFV | IE00BQN1K901 | A / 272058 | 0.25 |

| EMVL | IE00BG0SKF03 | A / 297452 | 0.4 |

| JPGL | IE00BJRCLL96 | unresolved full history; see §3 | 0.2 |

| GGRG | IE00BZ56SW52 | E / 1000422 | 0.38 |

| XS2D | LU0411078552 | F / ISIN | 0.6 |

| LQQ | FR0010342592 | unresolved full history; see §3 | 0.6 |

| 3LUS | IE00B7Y34M31 | E / 1000395 | 0.75 |

| 3QQQ | XS2472197065 | unresolved full history; see §3 | 0.75 |

Fees above are ongoing charges, not all-in investor costs. CMOP additionally identifies a 0.15% swap fee; COPA/AIGA/CRUD identify an annual swap fee separately from MER; leveraged funding costs are additional unless embedded in the chosen net index/series. Current product disclosures govern. Missing INXG fee is not zero. Verify fee-effective dates before calibration/export. The T212_GBP_CASH identity is retained for original-ledger continuity only; runtime `GBP_BANK_SAVINGS` is the previously approved standalone bank account, outside Trading 212.

Newly acquired series:

| Security | Records | Earliest | Latest | Series / currency |
|---|---:|---|---|---|

| VWRP | 1864 | 2019-07-23 | 2026-10-13 | native NAV + issuer monthly total returns; USD |

| VAGS | 1889 | 2019-06-18 | 2026-10-13 | native NAV + issuer monthly total returns; GBP |

| VUSA | 3069 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; USD |

| VUKE | 3011 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; GBP |

| VMID | 3011 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; GBP |

| VERX | 3069 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; EUR |

| VJPN | 3069 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; USD |

| VAPX | 3069 | 2014-11-18 | 2026-10-13 | native NAV + issuer monthly total returns; USD |

| VEMT | 2540 | 2016-12-06 | 2026-10-13 | native NAV + issuer monthly total returns; USD |

| CMOP | 2409 | 2017-01-09 | 2026-10-13 | issuer share-class growth; USD |

| EQQQ | 5985 | 2002-12-02 | 2026-10-13 | issuer share-class growth; USD |

| 3LUS | 3384 | 2012-12-10 | 2026-10-13 | issuer NAV export; corporate-action adjustment requires verification; USD; verify file/product currency |

| COPA | 5120 | 2006-09-22 | 2026-10-13 | issuer NAV export; corporate-action adjustment requires verification; USD; verify file/product currency |

| CRUD | 5120 | 2006-09-22 | 2026-10-13 | issuer NAV export; corporate-action adjustment requires verification; USD; verify file/product currency |

| AIGA | 5120 | 2006-09-22 | 2026-10-13 | issuer NAV export; corporate-action adjustment requires verification; USD; verify file/product currency |

| GGRG | 2619 | 2016-06-03 | 2026-10-13 | issuer NAV export; corporate-action adjustment requires verification; USD; verify file/product currency |

The nine Vanguard monthly-return record counts respectively are VWRP 87, VAGS 88, VUSA 173, VUKE 173, VMID 145, VERX 145, VJPN 161, VAPX 161, VEMT 118. Initial stub months must be excluded. Distribution records are 0, 0, 58, 58, 48, 48, 54, 54 and 118 respectively. Use actual monthly returns where daily NAV coverage starts later; never invent earlier daily paths.

## 3. Three remaining full-history gaps, and leverage decisions

### JPGL — IE00BJRCLL96

Official UK page: https://am.jpmorgan.com/gb/en/asset-management/adv/products/jpm-global-equity-multi-factor-ucits-etf-usd-acc-ie00bjrcll96

Issuer search evidence identifies inception 9 July 2019. Product-list evidence identifies JPGL London USD and JPLG London GBX as the same ISIN, with 0.20% TER. The acquired FI product page exposes a FundsMarketingHandler application, not a complete actual NAV series. A full-history endpoint has not been verified. Next concrete acquisition: use that exact issuer page's performance/NAV export or an issuer-supplied file, preserve ISIN/date/currency and audit all observations. Do not use another JPM fund or infer returns from current holdings. This item stays excluded from calibration until a real series is acquired; this need not block the other 46 securities.

### LQQ — FR0010342592

KID: https://www.amundietf.co.uk/pdfDocuments/download/ed9ce1d5-7c5c-456d-9e79-edaa22b312f1/KID_3_CL94477_eng_GBR_20260214_20260224.pdf

Parseable prospectus acquired on this continuation:
https://www.amundietf.co.uk/pdfDocuments/download/25be812e-96f8-435a-bf10-88e42443cb9c/PSC_1_UM94411_ENG_GBR_20231011_20231011.PDF

The previous failed-PDF blocker is resolved for this document. Its filename contains an old date; do not infer current legal effectiveness from successful retrieval. Confirm the latest effective version from the issuer document library before binding a current forecast. The document identifies the current sub-fund's 19 April 2018 creation and the USD NASDAQ-100 Leveraged Notional Net Return strategy. Earlier history may belong to a predecessor and needs merger/continuity evidence. The KID identifies 0.60% ongoing charges. Financing is embedded in the leveraged benchmark; no second application of leverage or financing to that benchmark. Exact current funding spread/reference/reset rules and full actual NAV remain unresolved. An EUR share price does not make the underlying exposure EUR-hedged.

### 3QQQ — XS2472197065

Official product: https://leverageshares.com/en/etps/leverage-shares-3x-long-nasdaq-100-etp/

Final terms: https://leverageshares.com/documents/en/finalterms/3x_qqq_ft_cbi.pdf

Referenced Conditions version 7 source: https://leverageshares.com/documents/en/prospectus/Leverage-Shares-Base-Prospectus-%28CBI%29-Final-15-March-2024.pdf

Current base source: https://leverageshares.com/documents/en/prospectus/Base-Prospectus-%28CBI%29-Final.pdf

Both base PDFs were downloaded and parsed. A material difference needs resolution: the 2024 text describes benchmark +1.5%, while the current base describes benchmark +2%; USD benchmark is effective federal funds. Do not pick one by convenience: reconcile the exact series' final terms, incorporated conditions and amendment notices by effective date. Product exposure is daily 3x QQQ ETF, not a direct Nasdaq index. Current page identifies a 16.67% intraday trigger. Exact full actual product history and intraday reset-path data have not been acquired.

The official product-list PDF labels London 3QQQ as **GBX**, while earlier page research treated the £ label as GBP. Resolve quote units explicitly; use native USD NAV where possible. Product list: https://leverageshares.com/documents/pdfs/en/Leverage-Shares-Products.pdf?x93872=

Exclude unverified 3QQQ forward forecasts. The funding discrepancy and intraday path cannot be repaired by multiplying monthly returns by three.

### XS2D and 3LUS: history available, forecast has additional conditions

XS2D July 2026 prospectus, Annex 49:
https://etf.dws.com/en-gb/AssetDownload/Index/97f28cea-2f24-445d-b135-f9c31a5f884d/Prospectus-Xtrackers.pdf

It specifies daily 2x S&P 500 net-total-return exposure with borrowing cost based on **SOFR +0.02963%** on the borrowed component, already included in its leveraged index. The 0.02963% is 2.963 basis points, not 2.963 percentage points. Obtain exact day-count/reset/index methodology and historical funding-regime changes before reconstructing the full native daily path. The actual net fund NAV is already usable for historical benchmark reconciliation without reconstructing that path. Preserve XS2D as the exact fixed reference.

S&P mathematics source: https://www.spglobal.com/spdji/kr/documents/methodologies/methodology-index-math.pdf?force_download=true . Generic index mathematics does not by itself prove every product-specific term or historical rate regime.

3LUS official prospectus:
https://dataspanapi.wisdomtree.com/pdr/documents/PROSPECTUS/WTMA/GB/EN-GB/IE00B7Y34M31

It was downloaded and parsed. Product page distinguishes unleveraged S&P 500 Net Total Return underlying `.SPXNTR` from the product's 3x exposure; it shows MER 0.75%, daily swap rate 0.001360%, intraday restrike threshold 20%, severe overnight-gap threshold 25%. The prospectus describes restrikes measured over an interval, not simply the close. Verify exact final terms, funding/collateral and day-count before applying the daily swap rate. Do not multiply an already leveraged series again. Actual NAV may contain consolidations/splits: reconcile corporate actions before use. Daily close-only forecast simulation cannot claim exact intraday reset mechanics.

A defensible release can provide actual historical benchmarks and a calibrated unleveraged frontier while keeping unvalidated leveraged forward models disabled. Do not call six-category forecast coverage complete until at least one leveraged model passes its contract and actual-overlap tests.

## 4. Bonds, commodities, holdings and savings

### Bond evidence and modelling rules

The following fields were extracted from iShares snapshots. `yieldToWorst` is the JSON field name; retain the issuer's visible label and definition because the backend key alone does not establish whether the displayed measure is YTM/YTW or nominal/real. Figures are percentage points, duration is years; observations are 9 October 2026. These are current characteristics, not historical forecasts.

| Fund | Yield field | Effective duration | Treatment required |
|---|---:|---:|---|
| IGLS | 4.62 | 2.15174 | Short nominal gilts; GBP |
| IGLT | 5.2 | 6.93642 | Nominal gilts; GBP |
| IS15 | 5.61 | 2.39692 | Short sterling corporate; credit loss assumption |
| SLXX | 6.19 | 5.43084 | Sterling corporate; credit/spread risk |
| IBTS | 4.77 | 1.82685 | Short US Treasury; unhedged USD |
| IBTM | 5.2 | 6.84198 | Intermediate US Treasury; unhedged USD |
| IBTL | 5.65 | 14.67157 | Long US Treasury; unhedged USD |
| ITPG | unavailable | 6.35986 | US TIPS GBP-hedged; real-yield/inflation/hedge distinction |
| GHYS | 7.43 | 3.15448 | Global high yield GBP-hedged; loss and hedge assumptions |

INXG is UK index-linked gilts: verify real versus nominal yield and indexation lag; never substitute the nominal-gilt carry assumption. GLTL issuer page reported YTM 5.87% and long-gilt exposure; use its source date, not retrieval date. VAGS has published YTM 4.5% and duration 6.0 years in the August 2026 snapshot; determine whether the yield is pre-hedge. VEMT is USD emerging-government debt, not domestic sterling sovereign risk; issuer page duration 6.1 years does not supply default-loss forecasts.

Default: constant-yield carry, explicitly zero assumed roll-down, costs and expected credit loss deducted once where not embedded. A yield and a single duration are insufficient for estimated curve roll-down. Use actual joint GBP return covariance for risk. Duration shocks are sensitivities, not replacements for historical risk. Add convexity only with verified data. Missing spread duration, default-loss estimates and hedge-cost definitions must remain explicit assumptions or unavailable inputs; do not fabricate them. Use a transparent stress range if no empirical estimate is available.

### Commodity mechanics

SGLN/SSLN are physically backed metal debt securities, not conventional equity UCITS funds and not deposits. CMOP is synthetic broad commodity-futures exposure. COPA/AIGA/CRUD are collateralised commodity securities; each has its own underlying futures index and roll exposure. Their NAV histories include realised product mechanics, but a forward forecast still requires the exact index version and collateral/roll convention.

CMOP headline ongoing charge 0.19% and separate swap component 0.15% must be reconciled against the contract; COPA/CRUD current pages show MER 0.49% and annual swap rate 0.45%. AIGA's own page must control its terms. Do not assume that ongoing fee alone is all-in cost, that all commodities earn a metal premium, or that collateral remuneration should be added again to a total-return index. Until validated, use an expressly assumed zero excess-return prior with ±5 pp excess-return sensitivities, not a falsely calibrated forward commodity premium. This prior is not a cash coupon paid by physical gold.

### Holdings acquisition and diversity

Continuation result: all **23 discovered iShares `/latest-holdings.csv` endpoints downloaded successfully**. The standard schema contains date header, Ticker, Name, Sector, Asset Class, Market Value, Weight (%), Notional Value, Shares, Price, Location, Exchange and Market Currency. Example verified SWDA endpoint:
https://www.ishares.com/uk/individual/en/products/251882/ishares-core-msci-world-ucits-etf/latest-holdings.csv

The tested CSVs **do not contain ISIN or a consolidated company ID**. A ticker+exchange+currency is a security key, not proof that two share classes are different companies. Obtain/review issuer mappings, merge share classes and ADRs appropriately, and track unknowns. Three SPDR holdings workbooks were also downloaded and include ISIN/SEDOL, but still need company consolidation. Vanguard's tested holdings queries returned empty data; do not interpret that as zero exposure.

Compute portfolio economic-equity exposure first, then consolidate company weights across all funds and normalise them within equity. Effective companies = `1 / sum(p_company**2)`. Publish only when >=95% of economic-equity exposure is mapped to verified company identities and holdings are <=90 days old. Nested funds require recursive mapping; collateral held by swaps is not equivalent to economic stock exposure. Show date and mapped/unknown coverage; never treat a fund's position count as effective companies. This research has acquired books, not completed the company master or produced a diversity score.

### Savings

Use the previously verified standalone Charter Savings Bank Easy Access Issue 79 quote, 4.25% AER, minimum £1, maximum £1m, variable and unrestricted access, as dated evidence; refresh before production use. Official terms: https://chartersavingsbank.co.uk/Products/EasyAccess . A nominated payout account is not itself a requirement to buy a linked current-account package. This bank account is outside Trading 212 and is the explicit approved cash override.

Other official pages retrieved 14 October: HTB easy-access tracker 4.18% (https://www.htb.co.uk/personal-savings/variable-rate-accounts/), Ford Flexible Saver 3.99% (https://www.fordmoney.co.uk/all-products/flexible-saver/), RCI Freedom 3.95% (https://www.rcibank.co.uk/savings-accounts/freedom-savings-account). Their full eligibility/no-linked-account conditions were not completely audited; do not present them as qualified replacements or claim a whole-market highest rate. The savings forecast is a variable-rate scenario, not a guaranteed 20-year rate.

## 5. SONIA, factors and FX: exact sources and units

The repository already contains `data/research/sonia-daily-boe-2026-10-13.csv`: 7,523 actual observations, 1997-01-02 through 2026-10-09. The 970 observations successfully compared against FRED matched. Full-source reconciliation and monthly compounding have not been executed. This is historical SONIA, not US RF relabelled.

Verified BoE HTML endpoint:
https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?CSVF=TT&DAT=RNG&FD=1&FM=Jan&FY=1997&SeriesCodes=IUDSOIA&TD=12&TM=Oct&TY=2026&UsingCodes=Y&html.x=66&html.y=26

Parse date/rate table cells; dates are DD Mon YY and rates are annual percent. Change end date explicitly when refreshing. The CSV route can fail while this HTML route works. `https://fred.stlouisfed.org/data/IUDSOIA` worked as a secondary check; the graph CSV route returned 404. BoE methodology: https://www.bankofengland.co.uk/markets/sonia-benchmark/sonia-key-features-and-policies . Delayed database data reuse is under OGL; retain attribution. SONIA changed methodology 23 April 2018.

Monthly historical RF: ACT/365 fixed, compound each business-day rate across its calendar-day accrual interval: `1 + rate_percent/100 * n_days/365`. Split intervals crossing a reporting boundary using accrued-level ratios so monthly factors telescope. Do not introduce look-ahead from next-business-day publication. Validate against the official compounded index where available. Forward wholesale RF and current bank AER are separate inputs. Flat latest SONIA is an assumption, not an observed forward curve; show ±1/±2 pp sensitivity if no dated public curve is acquired.

Previously verified Kenneth French endpoints from the repository source inventory (retain actual data dates/hashes):
- french:US: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip
- french:Developed: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_5_Factors_CSV.zip
- french:North_America: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/North_America_5_Factors_CSV.zip
- french:Europe: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Europe_5_Factors_CSV.zip
- french:Japan: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Japan_5_Factors_CSV.zip
- french:Asia_Pacific_ex_Japan: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Asia_Pacific_ex_Japan_5_Factors_CSV.zip
- french:Emerging: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Emerging_5_Factors_CSV.zip

Parse monthly rows only, separating annual summary sections, dividing percentages by 100 and rejecting missing-value sentinels. Do not treat the annual section as extra monthly observations. The previous implementation inventory reported factor data through August 2026; the common modelling cut-off must respect the slowest source and be recorded, not assumed current.

ECB full FX history: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml . Quotes are currency units per EUR. GBP per USD = GBP-per-EUR / USD-per-EUR. Use the last available reference fixing on or before the valuation date; record timing mismatch and sensitivity to one-business-day alignment. A GBP listing is not a GBP economic hedge.

## 6. Calibration defaults Codex must execute

The following are modelling decisions, not reported fitted results. Export actual coefficients, residuals, fold dates, selected hyperparameters, uncertainty and diagnostics after execution.


| Decision | Recommended default | Alternative / sensitivity | Acceptance test |
|---|---|---|---|
| Historical short rate | Actual delayed Bank of England IUDSOIA observations, percent per annum, ACT/365 fixed; compound each London-business-day rate over its calendar-day accrual span | Existing published US RF with zero UK–US differential remains a labelled legacy approximation only; if a gap cannot be resolved, show differential ±1 and ±2 percentage points rather than calling it SONIA | Unique increasing dates, reconcile overlapping official/FRED observations, verify London holidays and monthly boundary convention against the BoE compounded index |
| SONIA calendar boundaries | Accrual factor for an interval of n days is 1 + rate_percent/100*n/365. To split one accrual interval at a month boundary use ratios of its accrued level, so adjacent months telescope to the unsplit interval | Daily compounding within weekends is a different convention and must not silently replace simple n-day accrual | Product of subperiod factors equals whole interval factor; leap years still denominator 365. No observation before its next-business-day publication in forecasting information sets |
| Forward short rate | Latest available SONIA held flat as an explicitly assumed scenario, separately from historical realised rates | Public dated OIS curve if acquired; otherwise ±1 and ±2 pp paths, plus mean reversion scenario. No claim that flat SONIA is a market forecast | UI/export identifies date, rate and assumption; savings AER is not substituted |
| Savings | Current bank AER for the separate savings component; convert effective annual to monthly with (1+AER)^(1/12)-1 | Variable-rate paths; bank-minus-SONIA spread is an assumption, not a constant historical fact | Eligibility/minimum/withdrawal terms dated; no extrapolation of today's promotional or variable quote as guaranteed |
| Factor geography | US: VUSA/EQQQ/USSC/IUVF. Europe: VUKE/VMID/VERX/IEFV/ZPRX, with UK-specific basis risk disclosed. Japan: VJPN. Asia Pacific ex Japan: VAPX. Emerging: EMIM/IIND/IASH/EMVL; country concentration remains residual risk. Developed: SWDA/IWFV/IWFM/IWFQ/MVOL/IWFS/WLDS/JPGL/GGRG/IWDP, subject to current index geography check | North America vs US sensitivity; EM country funds require extra residual uncertainty. IWDP is listed equity property, not direct property | Exact fund/index geography verified; no assumption that a regional FF5 spans every country/sector style |
| Mixed world | VWRP jointly regressed on Developed and Emerging factor sets with ridge and a single intercept | Developed-only baseline; regional weight-constrained model using dated holdings, if validated. Never splice different factor histories to create fictitious fund history | Chronological validation improves or retains defensible error relative to simple baseline; report conditioning and coefficient stability |
| Currency | For GBP value of one USD, x = FX_t/FX_(t-1)-1. GBP market excess = (1+MKT_USD+RF_USD)*(1+x)-1-RF_GBP. Each USD zero-investment style = style_USD*(1+x) | Hedge-specific series for hedged funds; do not apply unhedged translation to hedged returns | Synthetic accounting identities, correct percent-to-decimal conversion, same economic month and no future FX; ECB EUR cross-rates GBP per USD = GBP-per-EUR / USD-per-EUR |
| Share-class history | Own actual accumulating NAV or verified reinvested net fund-growth series; distributions at ex-date and splits explicitly handled | Cross-share-class proxy only as a separately labelled research sensitivity, with currency/hedge/fee reconciliation. Index backfill is hypothetical | Compare compounded calendar-year returns with issuer published fund returns, investigate >10 bp discrepancy beyond source rounding; no blanket acceptance of NAV on distributing shares |
| Training | At least 72 actual monthly observations per equity (prefer 120); first 36 training, chronological 12-month validation blocks, final 12-month holdout untouched during selection | Longer expanding windows; no random split. Common covariance history minimum 36 months must remain separate from per-fund fitting threshold | Scalers fitted only on training; fold dates, errors and final holdout logged; hyperparameters locked before holdout; final full-history refit clearly distinguished |
| FF5 regression | Monthly simple net GBP excess returns; ridge grid 0, 0.1, 1, 10, 100 after training-only scaling; intercept unpenalised; future alpha zero | OLS baseline; momentum factor as named extension for IWFM, not relabelled FF5; no mock betas | Executed coefficients, residuals, out-of-sample errors, units and sample dates exported; do not replace fitting with historical sample means |
| Factor premia | Estimate from published regional factors on a disclosed common information date. Gaussian shrinkage to zero with annual prior SD 5 pp market and 2 pp styles; covariance of sample mean from joint 12-month block resampling | Block lengths 6/24, prior SD half/double, full available versus recent 10/20-year windows | Negative estimates allowed; joint covariance retained; posterior annual/monthly conventions consistent; stable linear solve; priors labelled assumptions |
| Joint risk | One aligned net GBP cross-asset monthly panel, shrink covariance jointly; append deterministic cash after shrinkage | Historical regimes and block-bootstrap stress; no fabricated correlations for unavailable assets | PSD, preserved cross-asset and factor/residual cross-covariances; do not add holdings-overlap surcharge or independent category blocks |
| Costs | Actual net NAV already contains ongoing fund expenses. Forecast using gross factor/carry input deducts relevant costs once; do not deduct fees again from fitted net predictions | Broker spread/FX scenario separately, using dated actual fee schedule when obtained | Component cost reconciliation; swap/financing/hedge identified as embedded or separately charged; no duplicated funding of net-funded leveraged index |
| Bond means | Dated issuer YTM only with yield definition. Simplest defensible baseline: constant-yield carry less fee/default-loss/hedge adjustments where not already embedded; assume zero roll-down explicitly | Rate shock: -duration*delta_y; convexity term only when available. Credit loss sensitivities 0/0.5/1 pp IG and 0/2/5 pp HY/EM are stress assumptions, not estimates | Nominal gilts vs real index-linked yield distinguished; real yield requires explicit inflation assumption. Distribution yield is not YTM. Duration alone does not supply curve roll-down |
| Bond hedges | Confirm whether yield field is pre-hedge portfolio yield; apply GBP hedge carry only if absent | Zero/±1 pp unresolved hedge-cost sensitivity; do not present unresolved hedged forward return as calibrated | VAGS/ITPG/GHYS exact share class and yield convention documented; no inference from GBP ticker |
| Commodities | Physical metals use actual net metal-backed product history and an explicitly assumed zero expected excess return over forward cash as neutral research prior | Excess-return scenarios ±5 pp. Futures products require own total-return index roll/collateral definitions and swap fees; do not use gold calibration | Legal exposure and native currency checked; neither collateral nor roll yield added twice; neutral prior is not a gold coupon or executed equilibrium calibration |
| Daily leverage | Simulate native daily index/underlying with exact reset, funding, spread and fee terms, then convert FX; validate on actual same-product overlap | Historical benchmark-only display where actual net product history passes but forecast mechanics fail. Otherwise explicit exclusion | >=60 actual overlap days plus stress/reset periods; split-adjustment reconciliation; daily-close approximation fails where material intraday reset cannot be observed. SPXT2LUN is already leveraged and financed |
| Company diversity | Consolidate share classes to verified issuer/company IDs, recurse funds, map economic equity not collateral; normalise known equity company weights p and calculate 1/sum(p²) only with >=95% mapped economic-equity exposure | Show known/unknown coverage separately; derivative notional mapping only from verified underlying exposures | Holdings <=90 days old; dated identifiers, mapping exceptions and nesting exported; never infer company count from number of positions |
| Horizon band | Average annual arithmetic return A_T = (12/M)*sum monthly returns, M=12T. Show 15.87th and 84.13th percentiles from joint simulations | IID diagnostic SD(A_T)=annual_vol/sqrt(T); parameter uncertainty may prevent band shrinking to zero. CAGR requires its own separately labelled simulation | Annual volatility label stays horizon-independent. Joint block paths and posterior parameter uncertainty included once, not double-counted; band is not a guaranteed outcome |


Additional implementation cautions:

- Align sample dates across assets and factors; do not require every fund's inception date to match, and do not extend short histories with hypothetical index history. Separate a fund's estimation window from the joint portfolio risk window.
- Covariance of actual net monthly GBP fund returns already contains observed overlap and currency co-movement. Do not add an overlap penalty as if it were independent risk.
- Forward net equity return convention must be explicit: either gross factor prediction minus costs once, or a net model with a consistent fee adjustment. A fitted net intercept should not silently become a persistent positive alpha.
- For daily leveraged forecasts, >=60 overlap days is only a minimum availability gate; include stressed periods and any actual reset events. Good calm-period fit does not validate intraday mechanics.
- With projected daily paths, calibrate native-market dynamics first; carry forward the same joint cross-asset/FX shocks. No independently simulated leveraged block that loses covariance with unleveraged equities.
- Historical broker bid/ask spreads and investor-specific FX charges are not in issuer NAV. Keep execution-cost scenarios separate from fund ongoing charges.

## 7. Required implementation order and completion evidence

1. Implement the verified iShares, Vanguard, SPDR, Invesco, WisdomTree and DWS acquisition adapters. Record original response hashes, dates, schema/units and exact ISIN. Use robust timeouts/backoff and a last-known-good cache; do not redownload the universe on every slider move. Monthly refresh of factors, daily/weekly price refresh and monthly characteristics/holdings refresh are adequate defaults; recheck terms before admitting leverage.
2. Parse SONIA and ECB FX, build reconciled actual monthly net GBP returns. For each security output first/last complete month, count, gaps, duplicate dates, corporate actions and annual-return reconciliation errors. Drop current partial months and inception stubs. Never forward-fill missing returns as zeros.
3. Build exact VWRP, VAGS, XS2D historical references and VWRP/VAGS 60/40 with explicitly monthly rebalancing. VWRP and VAGS native-NAV cross-checks above already support the adapter design. Keep references fixed rather than user-selectable replacements. Missing forward XS2D modelling should not erase its validated historical reference.
4. Execute regional/mixed FF5 calibration for all eligible selected equity classes and joint GBP covariance for admitted assets. Add bond carry and explicitly assumed commodity/cash means. Do not stop at hard-coded four-instrument inputs when dozens of histories are now retrievable.
5. Reconcile corporate actions for commodities and leverage, read exact current binding leverage terms and validate daily overlap. Admit only those forward models with enough evidence; leave precise product-specific reasons for failures. Keep JPGL/LQQ/3QQQ unresolved histories separate from software adapter failures elsewhere.
6. Load and consolidate holdings. If >=95% company mapping is unavailable, display coverage and “company diversity unavailable”; keep the frontier usable if its financial model passes and the governing contract permits separate capability gates.
7. Refresh portable production model inputs and the admission/status files. Verify clean Streamlit startup on the supported Python 3.14 environment, fixed-reference rendering, slider endpoints, category constraints, horizon band, and ZIP export. Use repository-required financial/parser tests. A successful HTTP response or a passing unit test alone does not prove finance semantics.
8. In the final coding report state: count of actual histories, count of reconciled returns, count of admitted forward models by six categories, fixed-reference availability, company mapping coverage, and exact remaining blockers. Show the app's actual data cut-off. Do not describe incomplete forecasts as complete research.

Original UI requirements remain: top net-return/annual-volatility/fees/diversity metrics; frontier left with central 68% horizon-dependent average-annual-return band; category allocation right; separate all-nonzero-funds page; comparison page with exact fixed references and a second visible numeric 0–100 frontier position; category colours; disable-leverage/savings/commodities controls; no investment amount; clean compact layout. The annual volatility statistic itself is horizon independent.

ZIP should contain portfolio weights and categories, data dates and provenance, cost conventions, assumptions, actual calibration coefficients and uncertainty, covariance, frontier selection, scenario/horizon definitions and exclusions. Include raw third-party files only when redistribution is permitted. Source URLs, hashes and derived results can be exported without claiming broad issuer data redistribution rights. Review terms for any public deployment; the repository is private.

## 8. Scientific report text for the Streamlit methods page

### Introduction

This application compares GBP portfolios using actual fund histories and a Fama–French five-factor model for eligible equity exposures. Bonds, commodities, savings and daily leveraged products require separate economic assumptions. The efficient frontier is conditional on estimated expected returns, joint covariance and user constraints; it is not a guarantee of future outcomes.

### Methods

Issuer NAV, distribution and net performance data are reconciled to the selected share classes and translated to GBP consistently. Historical short rates use compounded SONIA. Published regional factor returns are aligned to the same information date and translated using explicit currency accounting. Chronological validation chooses regularisation; factor-premium shrinkage and joint resampling quantify estimation uncertainty. Forward equity alpha defaults to zero. Bond forecasts use dated yield information with explicit credit, inflation and hedge assumptions; commodity premiums are separately identified assumptions. Daily leveraged forecasts require native daily reset and financing mechanics validated against actual product observations. All fees are charged once.

Portfolio risk is estimated jointly from aligned net GBP returns. The displayed central 68% interval concerns average annual returns over the selected horizon, while annual volatility remains unchanged by horizon. Company diversity is an inverse-Herfindahl measure computed only from sufficiently complete verified economic-equity holdings; unknown exposure remains visible. Calibration results and source provenance are exported for reproducibility.

### Conclusion

The model supports conditional comparison and sensitivity analysis rather than precise prediction. Its usefulness depends on actual source coverage, chronological validation and honest separation of measured data from assumptions. Unresolved product mechanics or incomplete company mapping are reported explicitly, without fabricating returns or diversity statistics.

## 9. What this handoff does not claim

The research has substantially resolved acquisition: 46 selected securities have downloaded history sources, including every fixed reference. It has not verified every requested field for all 50 identities, acquired complete histories for JPGL/LQQ/3QQQ, established a full company master, completed all futures-index/hedge contracts, or executed new FF5 fits. Those limits are explicit above. This is a concrete implementation handoff, not a declaration that the Streamlit product is finished. Codex should now integrate and validate the retrieved sources and report precisely any remaining scientific exclusions.
