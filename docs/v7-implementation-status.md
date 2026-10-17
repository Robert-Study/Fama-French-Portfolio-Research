# V7 implementation checkpoint — 15 October 2026

Model **0.4.0**, schema **2**, Python **3.14.8**, PyArrow **24.0.0**. The supplied seven-file patch was verified against its manifest and applied after remote main was confirmed at `bc8f2ca5aba3e977ac3c42bbc6f1c498832f83bc`. Original legacy Git objects and working bytes match the supplied tree. The repository is **public**, verified through GitHub; visibility was not changed. App visibility was not inspected.

## Executed results

- **46 security histories acquired, 41 passing documented reconciliation screens, 32 admitted forward models:** savings 1, physical metals 2, government bonds 6, equity ETFs 13, factor ETFs 10, leverage 0. All 50 original identities remain represented.
- EQQQ passed 23 own-share-class net reinvested calendar comparisons, maximum error **0.00612613bp**. Its 0.30% fee is issuer-sourced. GLTL's 2019 distribution reconstruction failed by **80.22497bp** and all history before January 2020 is excluded. Retained 2020–2025 comparisons pass within **0.00007856bp**, and latest YTD within **0.00007757bp**. Ex-date NAVs match. GLTL yield **5.85%**, effective duration **14.94**, dated 14 October; expense **0.15%**. No missing payment or convexity was invented. CMOP's issuer fee is 0.19%; futures mechanics still block its forecast.
- Calibration cutoff remains **August 2026**, with **80 common actual GBP months** and 23 executed equity calibrations. Portable inputs retain the available **72-month** joint-risk sensitivity; 120 months are unavailable. Nominal bank cash stays deterministic and is appended after risky covariance shrinkage.
- Charter Easy Access Issue 79 was rechecked on **15 October**, still **4.25% variable AER**. Actual SONIA observations through **9 October** are retained after live BoE HTTP 403; official compounded-index reconciliation remains pending. No new SONIA values were fabricated.
- VWRP, VAGS, XS2D and monthly-rebalanced 60/40 historical statistics survive fresh checkouts. VAGS/XS2D forward gates remain closed. Historical bank savings returns are unavailable. Mapped company coverage remains **0%**, so effective-company diversity is unavailable independently of financial admission.

## Validation

**78 tests pass** on Python 3.14.8/PyArrow 24, including new issuer identity, basis, unit, incomplete-year, distribution, YTD and invalid-value cases, portable precision/layout and 72-month covariance tests. Six synthetic-test warnings remain from attempted solver paths; independent final constraints are enforced.

A separate checkout containing only shipped files (no raw caches) loaded all four pages, exercised numeric/slider endpoints and horizon changes, retained fixed references and exported through the actual UI. The default screen cache was reused; altered constraints rejected it. All 101 exported weights reproduced within **1e-6**. ZIP content inspection found derived calculations and provenance, no raw issuer histories/workbooks. Full refresh and portable scenarios remain distinct: synchronized blocks versus labelled IID Gaussian joint risk.

Local measurements: load/solve **0.18s**, default cache read **0.011s**, direct ZIP **0.19s**, UI export **0.34s**, ZIP **231,858 bytes**, peak process RSS **376 MiB** including four-page UI testing. The screen records **541 solved removal cases, zero failures**. Maximum independent default frontier violation was **1.57e-11**. These are local measurements, not hosted guarantees. Custom constraint screening can still take minutes.

The supplied hosted log confirms successful clone/dependency installation, Python 3.14.8 and Streamlit 1.50.0. Streamlit replaced PyArrow 26 with 24 for known apache/arrow#50471; requirements now match that mitigation. The excerpt contains **no application exception or traceback**. The original hosted failure therefore remains undiagnosed, and no claim of hosted recovery is made. No deployment was initiated.

## Remaining concrete evidence requirements

1. Complete actual histories for JPGL, LQQ and 3QQQ.
2. WisdomTree COPA/AIGA/CRUD/GGRG/3LUS currency, corporate-action and net-return reconciliation; no guessed split correction.
3. INXG/ITPG real-yield and inflation inputs; IS15/SLXX credit losses/spreads; VAGS/GHYS hedge and yield basis; VEMT yield/credit evidence.
4. Futures roll/collateral/swap terms, IWFS strategy continuity, and exact daily leverage financing/reset/termination terms with stressed same-product overlap and required intraday observations.
5. Reviewed company/share-class/ADR/nested-exposure mappings, missing full books, and at least 95% current mapped economic-equity coverage.
6. Remaining ledger-sourced fee checks, official compounded SONIA comparison and a successful dated SONIA refresh. Flat forward SONIA remains an explicit assumption, not an OIS forecast.
7. Hosted application traceback or observed page failure after startup to establish the original failure's cause and subsequent recovery.

The following sections are historical checkpoints, not the current calibration.

---

# V7 implementation checkpoint — 14 October 2026

Model **0.3.0**, schema **2**, Python **3.14.8**. The user requested that this checkpoint be uploaded and further work pause until instructed. The original 50 identities and `data/legacy` remain unchanged; repository/app privacy and the `main` workflow are preserved.

## Current results

- Public cached adapters execute iShares, Vanguard GraphQL, SPDR XLSX, Invesco, WisdomTree POST and DWS requests, retaining original bytes, SHA256, method/body, URL, content type and retrieval UTC. Bounded retries and validated last-good snapshots keep refresh outside interactive controls.
- **46 actual securities histories acquired; 39 pass documented reconciliation screens.** Passing screens do not prove a complete independent corporate-action audit. Unreconciled NAV/growth stays outside the production net-total-return panel. Per-instrument counts, dates, gaps, currencies and errors are in `acquisition-audit.json`.
- iShares NAV/reinvested growth reconciles to published calendar-year fund returns. Vanguard accumulating NAV reconciles to issuer monthly returns; six distributing equity classes also reconcile using actual ex-date distributions, without double-counting tax components. SPDR accumulating histories retain exact ISIN/currency. DWS XS2D reconciles over 4,105 dates against its exact USD fund chart within a declared 1bp consistency trigger; maximum discrepancy is about 0.386bp. Its independent corporate-action audit and forward mechanics remain incomplete.
- Actual delayed **SONIA replaces the US-RF proxy**. ACT/365 business-day accrual intervals split via ratios of accrued levels at month boundaries. The live BoE request returns HTTP 403 here; the supplied 7,523 actual observations through **9 October 2026** are retained with OGL attribution and the failed request recorded. The research audit compared 970 FRED observations; comparison with the official compounded index remains pending.
- Actual ECB GBP/USD and GBP/EUR conversion, published regional French factors, chronological market/OLS/ridge selection, final untouched holdout, premium shrinkage and joint exposure/premium bootstrap are executed for **22 equity models**. Mixed Developed/Emerging candidates are fitted for VWRP. Selected market-only baselines remain distinguished from full FF5. Calibration/risk ends at **August 2026**, the slowest common source.
- **30 admitted models:** 1 savings, 2 physical metals, 5 government-bond funds, 12 equity ETFs, 10 factor ETFs and **0 leveraged forward models**. Joint risk uses **85 common actual GBP months**. Flat latest SONIA, fixed bank AER, constant-yield carry and zero metal excess premiums are conditional assumptions, not market forecasts. Non-iShares fees lacking live adapter fields use the dated supplied research ledger, with their source basis recorded.
- Actual VWRP, VAGS, XS2D and monthly-rebalanced 60/40 reference statistics survive fresh checkouts independently of forward admission. VAGS/XS2D forward models remain blocked. Current bank AER is a conditional forward reference; no historical savings returns are invented.
- Identity/history/reconciliation/forward/risk/holdings/broker checks are separate capabilities. Full holdings acquisitions retain dates/security IDs without invented company mappings. Mapped company coverage is **0%**; diversity is unavailable and does not disable a passing financial frontier.
- Four pages, six visible categories, synchronized slider/numeric controls, complete non-zero holdings, switches/caps and horizon-dependent arithmetic-return bands remain implemented. Annual volatility does not shrink with horizon. Portable scenarios use labelled IID Gaussian joint risk; refreshed instances use synchronized blocks and actual portfolio replay.
- CLARABEL is tried first to avoid repeated failed high-precision OSQP iterations. A nullspace linear solve preserves an exact feasible zero-risk cash endpoint; comparable targets at/below GMV reuse the same verified minimum portfolio. Independent constraints are checked after solver dust cleanup.
- Lazy ZIP exports all 50 identities, coefficients, covariance, premiums, assumptions, source hashes, statuses, historical reference statistics and sensitivity results. Restricted raw issuer workbooks/histories remain outside Git and ZIPs.

## Checkpoint validation and limitations

Baseline **53 tests passed**; expanded financial/parser/constraint/export/Streamlit suite **61 passed**. New checks cover SONIA boundaries, units, missing months, duplicate dates, Excel row/date alignment, ISIN identity, distribution-component double counting, leverage-history/forecast separation and security-key/company-ID separation. The actual shipped inputs render from a checkout without raw cache.

The actual 30-model ZIP completed (about **121 KB**) and its script reproduced every solved weight within **1e-6**. Source-cache validation/export process peak RSS was about **225 MiB** locally. **Export performance remains follow-up work:** the full predefined sensitivity screen took about **155 seconds**. These are local measurements, not hosted-service guarantees. The historical hosted dashboard exception is not claimed resolved because its traceback has not been supplied.

## Remaining work when instructed

1. Obtain any remaining hosted traceback and measure hosted startup/export performance; optimize the slow sensitivity screen.
2. Acquire full histories for JPGL, LQQ and 3QQQ. Keep their known dated research facts separate from missing histories.
3. Reconcile the seven other acquired histories: GLTL/EQQQ income and WisdomTree COPA/AIGA/CRUD/GGRG/3LUS currency/corporate actions. Do not treat distributing NAV as net total return or guess split adjustments.
4. Resolve bond gates: INXG/ITPG real yield/inflation; IS15/SLXX credit-loss/spread assumptions; VAGS/GHYS hedge/yield basis; VEMT yield/credit evidence. Known duration is insufficient to fill missing inputs.
5. Resolve futures roll/collateral/swap costs, IWFS strategy-regime continuity and exact binding leveraged funding/reset/termination terms plus stressed actual overlap. Intraday gates remain material.
6. Build a reviewed company master, consolidate share classes/ADRs/nested exposure, acquire missing Vanguard books and achieve >=95% current mapped economic-equity coverage.
7. Live-check ledger-sourced fees, compare SONIA with the official compounded index, refresh dated SONIA when access works and expand forward-rate/structural sensitivities where data permits.

**Full six-category forward coverage and every original scientific acceptance gate remain incomplete.** No deployment, publication or paid-data purchase was performed. Further investigation is paused at the user's request.

## Historical record: initial 12 October checkpoint

Prepared 12 October 2026 on `feat/v7-research`, based on upstream `1071128bdb6ad8888133f9152bfc3cc45fa90145`. Model **0.2.0**, input schema **2**, Python **3.14.8**. The revised attached specification and Methods report replace the older planning material. Two later user instructions authorise separate UK bank savings and a provisional calibration with explicit assumptions.

## Working now

- Four active pages; compact metrics and six-category allocation; synchronised visible slider/numeric controls for A/B; curve selection; combined Apply; prior-result retention on infeasibility.
- Seven actual published French FF5 ZIPs retained with SHA-256, percentages parsed once, missing codes rejected, RF preserved. Latest month **August 2026**. Emerging complete-factor history begins **July 1992**; GBP premium history is restricted further by actual ECB FX availability.
- Actual issuer IWFV/SGLN/IGLT histories. Accumulating/no-income products use issuer NAV changes, net of expenses. The distributing gilt uses the issuer reinvested net-performance index. ECB **XML** reference FX history validates through October 2026; only completed months through the common August information date enter the model. GBP-native IGLT is not converted twice. The separate CSV response was rejected as invalid/stale.
- IWFV actual return regression against converted Developed factors: training-only standardisation, chronological market/OLS/ridge selection, untouched final 12-month assessment, full-window current refit, fitted-alpha/residual/beta-change diagnostics. Joint moving-block premium shrinkage uses the specified 5pp market / 2pp style priors. No hard-coded fund means or expected fitted alpha are inserted into forecasts.
- A coherent empirical GBP cross-asset covariance; deterministic nominal cash appended after risky shrinkage; exact solved 101-point frontier; class exclusion before solving; independent residual checks; cash endpoint and highest-return nullspace tie-break.
- Separate cash, bond, commodity and native daily leverage engines. Shared daily funding/FX/block scenarios, actual-overlap gates, total-loss absorption and intraday-term rejection are implemented. No leveraged candidate is admitted on a multiplied-beta shortcut.
- Same-run comparison, common-actual-period monthly historical replay when the source cache exists, indexed outcomes/drawdown, matched scenario comparisons and explicitly distinct arithmetic-average versus CAGR bands. Default cache-backed paths use synchronised monthly blocks plus jointly bootstrapped equity means. Other forward-rate/structural uncertainties remain unquantified.
- Effective-company consolidation/recursive expansion/coverage/freshness logic. No company count is fabricated without mapped holdings.
- Lazy ZIP with every instrument, all solved weights/inputs, diagnostics/costs/coverage, quantiles, scenario assumptions and source hashes. An exported script reproduces the solve. A predefined premium/commodity/covariance/class-switch screen checks inclusion and removal at comparable solved targets. Unavailable candidates remain unevaluated.

## Current default evidence boundary

**Four modelled instruments:** Charter Savings Bank Easy Access Issue 79, SGLN, IGLT and IWFV. **46 selected securities remain blocked** by the detailed [admission table](../data/research/admission-status.csv). A public Trading 212 listing remains distinct from account permission, verified total-return data and issuer mechanics.

The bank's official product summary, retrieved 12 October 2026, publishes **4.25% AER**, £1 minimum, £1m maximum, a variable rate, withdrawals without notice and no introductory bonus. UK adult-resident eligibility and a nominated transfer account apply. It is outside Trading 212; FSCS protection is conditional on eligible deposits/per-person banking-licence limits, which the amount-free app cannot check. The comparison is the highest successfully verified qualifying quote in the checked established-bank set, **not a whole-market best-rate claim**. HTB 4.18%, Ford Money 3.99% and RCI 3.95% were lower verified quotes; headline bonus/limited-withdrawal offers were excluded.

**SONIA remains missing:** the official BoE database returned HTTP 403 Access Denied. The provisional model explicitly uses the actual published US RF series as a historical short-rate proxy, assuming a zero UK–US rate differential. Actual ECB FX is used; the rate proxy is not called observed GBP cash. Forward cash uses the current bank quote.

**IGLT carry uses current issuer evidence:** weighted-average YTM **5.20%** and effective duration **6.93642 years**, dated **9 October 2026**, are present in the official fund data. The carry approximation holds yields constant, adds no unsupported roll-down and charges the 0.07% annual product expense once. Rate stresses use the dated duration and shifted carry; convexity is unavailable, so the price approximation is first order. Isolated equity-factor and FX shocks disclose what is held fixed. Corporate/default/real-yield/hedge/futures and daily-product gates remain mandatory for other candidates.

**Reconciliation remains provisional:** issuer performance-index versus NAV discrepancies are recorded. IWFV and SGLN use actual accumulating/no-income NAV, avoiding hypothetical distributions or fixes; a complete corporate-action audit is still required. FX fixing-time alignment, provider conventions and backfilled rather than point-in-time vintages remain limitations.

**Four fixed references remain unavailable:** VWRP, XS2D, VAGS and the 60/40 combination lack admitted inputs. They are never replaced silently by IWFV/IGLT. The bank cash reference remains available outside active class constraints. Leveraged mechanics need exact terms, native underlying/funding/FX, actual daily overlap and any intraday-reset evidence. Company coverage is insufficient for the equity headline, which says so.

## Portable checkout versus refreshed instance

`model-inputs.json` carries derived calibrated means, covariance, fees, betas, diagnostics and bootstrap mean statistics. It opens a dated calibrated frontier in a fresh private checkout without redistributing raw histories. That mode uses an explicitly labelled **IID Gaussian joint-risk** scenario approximation and has no actual historical replay. Refresh restores the real source cache, synchronised blocks and replay. Matrix-only restoration of leveraged products is prohibited. Data/quote freshness gates still apply; changing a bank quote invalidates the old derived calibration.

`portfolio.providers.provisional` executes the actual public refresh and publishes its last-good pointer only after validation/solve success. Strict snapshots use `portfolio.providers.refresh` with reconciled source inputs. Source artefacts and time-series vintages remain under ignored `.cache`; public factual quotes, provenance and derived inputs are reviewable in Git. None of the setup commands deploys, merges or makes the app public.

## Validation

Baseline: **23 tests passed** before implementation. The expanded suite verifies financial mathematics, parsing/currency/inception gates, chronological isolation, covariance/constraints, leverage, horizon uncertainty, company merging/coverage, full UI and exported solve reproduction. The full suite passes **52 tests with uv and 52 with pip**. No zero-test run is counted.

Measured on this machine using the actual four-instrument provisional inputs: fit about **0.40s**, 101-point frontier **0.11s**, 2,000/5,000-path 20-year summaries **0.06s**, warm numeric/slider rerun **0.12s**, peak process RSS about **392 MB**. The largest interval-endpoint difference between sample sizes was about **0.12 percentage points**, below the declared 0.50pp precision gate. A **synthetic engineering-only** 50-asset/101-point constrained solve took **0.79s**, maximum independent violation about **1.4e-10**; it is not production financial evidence. These measurements do not establish hosted-service performance.

Legacy source-manifest hashes are checked byte for byte. Runtime package compatibility passes. Streamlit startup/health and functional AppTest checks pass. Required input-data acceptance gates above remain incomplete; this is a **provisional V7 review**, not a claim that all 50 production models are ready.

## Concrete next inputs

1. Official compounded SONIA history/current forward convention to replace the rate proxy.
2. Reconciled same-share-class net histories, inception/fees/hedge/legal structure for the remaining securities; VWRP/VAGS/XS2D first for the fixed references.
3. Dated yield/duration/credit/inflation/hedge evidence for the remaining bond models and convexity where required; futures roll/collateral evidence for commodity products.
4. Complete daily issuer leverage terms, underlying/funding/FX histories, actual product overlap and intraday data where contractually necessary.
5. Reviewed company/share-class mappings and >=95% current economic-equity holdings coverage.

No paid data entitlement or individual-account approval is presumed. The app can already support provisional comparisons; unsupported histories/mechanics remain explicit blockers.
