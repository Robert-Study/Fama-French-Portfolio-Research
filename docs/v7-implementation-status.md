# V7 implementation and evidence status

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
