# V7 research model — revised build specification

**Planning baseline: 12 October 2026.** This specification replaces the earlier V7 brief where the requirements differ. It does not represent an implemented or calibrated V7 release.

Repository: [Robert-Study/Fama-French-Portfolio-Research](https://github.com/Robert-Study/Fama-French-Portfolio-Research). Current `main` inspected at `1071128bdb6ad8888133f9152bfc3cc45fa90145`. The attached dashboard was reviewed. This planning pass makes no repository or deployment changes.

## 1. Decisions

Build a compact four-page Streamlit research application: **Dashboard · Holdings · Compare · Methods**. Retain Python 3.14 and the existing optimisation engine. The normal workflow opens a dated, verified dataset rather than the legacy demonstration or an upload prompt.

The research universe is **50 instruments: 49 exchange-traded products and Trading 212 GBP interest-bearing cash**. Exact listings, ISINs and intended roles are selected in the accompanying instrument schedule and Appendix A. All 49 product pages were found in Trading 212's public **Invest** catalogue on 12 October 2026. A public listing is evidence of catalogue availability, not a check of this particular account's purchase permissions, current dealing status or appropriateness assessment. Recheck these at admission; do not substitute CFD listings or assume ISA eligibility.

The six mutually exclusive display categories are:

| Category | Number | Classification rule |
|---|---:|---|
| Instant-access savings / cash | 1 | Trading 212 GBP cash facility; retain its true product type |
| Commodities | 6 | Physical-metal and commodity-futures exposure |
| Bonds | 13 | Government, inflation-linked and credit bond funds |
| ETFs | 13 | Unleveraged broad, regional, country and property-equity funds |
| Factor-tilted ETFs | 13 | Deliberate value, quality, momentum, size, minimum-volatility or multifactor selection |
| Leveraged ETFs / ETPs | 4 | Products targeting 2× or 3× daily equity returns |

**Two naming corrections are essential.** A bond ETF belongs in Bonds, not also in ETFs. ETCs and leveraged debt securities retain their actual legal structure even when Trading 212 uses a generic ETF label. The final category can be shortened to “Leveraged” on the dashboard.

**The savings limitation:** a regular Trading 212 Invest account offers interest-bearing uninvested cash, not a choice of ordinary bank savings accounts. Its cash may be placed in banks and qualifying money-market funds. The proposed savings category therefore says “Instant-access savings / cash” with “Trading 212 cash” underneath. It must not claim that every pound is an insured deposit. An actual bank savings account would be outside this account scope. Existing clients' applicable rate must come from their Interest tab; the public new-client rate is not automatically theirs. [S3]

No investment amount, personal-tax model, contributions or order placement is required. Show weights, percentages and growth of an index starting at 100. Without an amount, do not claim to check deposit-protection headroom, minimum order sizes or exact cash rounding.

## 2. What the current code already provides

| Inspected module | Retain | Required change |
|---|---|---|
| `portfolio/calibration.py` | Actual regression machinery: chronological ridge selection, training-only scaling, final 12-month assessment, fitted betas | Add published-factor ingestion, regional bases, specification selection and premium estimation |
| `portfolio/bundle.py` | Decimal-return validation and correct USD-to-GBP factor conversion | Replace developed-equity-only, unhedged, unleveraged five-file contract with an asset-aware snapshot |
| `portfolio/optimise.py` | CVXPY QPs, fallback solver, independent constraint checks; already supports up to 50 assets | Wire class/exposure constraints, disabled assets, deterministic-cash endpoint and stable 0–100 mapping |
| `portfolio/risk.py` | Shrinkage, duplicate-series protection, factor/residual cross-covariances | Build one coherent cross-asset matrix; preserve cross terms in factor diagnostics |
| `portfolio/projection.py` | Useful legacy mathematical reference | Replace fixed 20-year buy-and-hold/P20–P80 illustration with explicit rebalancing and horizon bands |
| `portfolio/holdings.py` | Aggregation infrastructure | Map companies across funds and share classes; add economic derivative exposure and effective-company count |
| `portfolio/results.py` | Run identity, data fingerprint, assumptions | Remove hard-coded single reference and equity-only orchestration |
| `app.py`, `portfolio/charts.py` | Streamlit/Plotly stack and calculation caches | Rebuild navigation and layout; remove amount and primary fund selectors; show only the active page |
| `portfolio/export.py` | Auditable tables, CSV escaping and ZIP generation | One complete, on-demand research ZIP; remove amount dependencies |

The existing FF5 code is not an empty placeholder. The missing element is a verified production input pipeline and the additional asset models. The current app defaults to legacy data and its research path requires an uploaded bundle. Do not describe that as an already populated, calibrated investment model.

Preserve `data/legacy` byte for byte and keep it outside the normal V7 workflow. Preserve repository privacy. Follow `AGENTS.md`, including version bumps when model behaviour/contracts change and `python -m pytest` after changes to financial calculations, parsing, constraints or exports.

## 3. Interface specification

### Dashboard

At desktop width, use one compact header, one control row, four headline metrics and a roughly **65:35 chart/allocation split**. Target the essential view fitting a 1366×768 screen. At narrower widths, stack the allocation beneath the chart.

- Header: application name, four page links, **Export ZIP**.
- Controls: horizon **1, 5, 10, 20, 30 years**; a compact Constraints popover; small dated model-status text. Default horizon: 20 years.
- Four metrics: **Expected return, net (% p.a.) · Annual volatility (%) · Ongoing product fees (% p.a.) · Effective companies**.
- Left: efficient frontier, the horizon-dependent shaded band, selected point and five fixed benchmark markers.
- Right: six category rows with horizontal bars and exact portfolio weights. Keep zero categories visible at 0%; there is no top-five truncation. A single stacked allocation bar above the rows provides a quick total view.
- Immediately below the chart: **Frontier position 50 / 100**, slider and synchronised numeric input. A narrow composition strip shows how the six category weights change along the frontier.
- Footer: common return month, holdings date/coverage and cash-rate date. Detailed diagnostics stay on Methods.

Use six consistent category colours: slate for cash, amber for commodities, blue for bonds, teal for ordinary equity ETFs, violet for factor tilts, coral for leverage. Pair them with labels. The composition strip provides the requested colour progression without pretending a blended colour uniquely describes a portfolio. Keep the uncertainty shading neutral and translucent. Benchmark marker shapes distinguish products that share a category.

**Return definition:** headline and frontier use annualised arithmetic expected return, `12 × monthly mean`, after modelled product expenses and financing. Label this in a short tooltip and Methods. It is not CAGR. Ongoing product fees are `Σ w_i c_i`; financing is shown separately in its tooltip and included once in the return model. Unknown spreads or trading costs are disclosed as excluded, not quietly treated as an all-in net result. No second large metric row.

### Slider and constraints

The slider is a **frontier position**, not a risk score, percentile or recommended allocation:

`target(s) = μ_GMV + (s / 100) × (μ_max − μ_GMV), s = 0, …, 100`.

Point 0 is the constrained global minimum-variance portfolio. Point 100 is the maximum feasible expected-return portfolio, using minimum variance as the tie-break. Solve every point; do not interpolate weights to manufacture unsolved portfolios. Clicking a curve point can update the same state. Moving the slider must not refetch data or refit the model. If only one distinct portfolio exists, show that state and disable the slider.

The three main switches are **Allow savings/cash**, **Allow commodities**, **Allow leverage**. Defaults: on, on, off. Disabling a class sets all its weights to zero by removing those assets before the solve; the current optimiser rejects zero upper bounds, so passing zero caps unchanged is not sufficient. Retain all 50 IDs in the exported result with zero weights where excluded.

When leverage is enabled, the initial research preset limits its combined weight to 25% and gross risky notional exposure to 150% of capital. These are explicit design limits, not claims about a suitable personal risk budget. Advanced settings can change them. Other class and individual-fund caps default to 100%; do not force diversification with an arbitrary universal 20% cap. All portfolios are long-only, fully invested, with no account borrowing or short positions. Exposure from embedded product leverage still counts.

Apply constraint changes together. A failed solve retains the prior result visibly labelled with its prior settings. A successful constraint change creates a new run; position 50 in that run is not the same portfolio as position 50 in the old run.

### Fixed benchmarks

| Display label | Definition |
|---|---|
| All-world | 100% Vanguard FTSE All-World Acc, VWRP |
| 2× US equities | 100% Xtrackers S&P 500 2× daily, XS2D |
| Bonds | 100% Vanguard Global Aggregate Bond GBP Hedged Acc, VAGS |
| Savings / cash | 100% Trading 212 GBP interest-bearing cash |
| Global 60/40 | 60% VWRP + 40% VAGS, rebalanced monthly |

These are fixed references in code/configuration, not user-selectable dashboard inputs. Disable Plotly legend click-to-hide for these reference series. Keep benchmarks visible when a class is excluded from the optimisation; identify them as references outside the active constraints. The 100% leveraged reference consequently remains visible despite the portfolio's 25% leverage cap. If a benchmark lacks valid data, mark it unavailable with a reason rather than substitute another instrument silently.

### Holdings

Show **every non-zero instrument** in the selected portfolio, descending by weight: name, ticker/exchange, category, weight, ongoing charge, financing where applicable, contribution to volatility, currency/hedge label and data status. A positive position that rounds below 0.01% displays “<0.01%”, not zero. Remove solver dust only under a declared numerical tolerance and recheck the constraints afterward.

Optional expanders contain underlying-company exposure, country/sector exposure, bond duration and factor diagnostics. They do not replace the complete fund allocation table.

### Compare

Portfolio A is the current selection. Portfolio B has its own visible 0–100 slider and numeric input, using the **same run, constraints and assumptions**. Show A, B and the fixed references in a compact metrics table. Use the same horizon, GBP currency, reinvestment, cost policy and monthly rebalancing.

Show indexed historical total returns and drawdowns over a common actual-data period, plus simulated compounded-outcome ranges and selected rate/equity/FX stresses. Use matching scenario draws to compare probability of loss and differences between A and B. Clearly distinguish a historical replay of today's weights from a rolling out-of-sample strategy; neither label should imply the other.

The compound-outcome chart shows median CAGR and 15.87/84.13 percentiles, terminal growth of 100 and downside measures. A concise drawdown/tail panel is especially important when leverage is on. No investment amount is needed.

### Methods

Render the accompanying **scientific report** directly as a separate Streamlit page, with Introduction, Methods and limitations, and Conclusion. Keep it about 900–1,200 words, with equations, a compact validation table and numbered references. Below it, put the detailed source inventory and diagnostics in expanders. No invented backtest performance or regression statistics may appear before calibration.

## 4. What the shaded band means

Do not shrink annual volatility itself when the horizon increases. The x-axis remains annualised one-period volatility. The quantity that narrows is dispersion of the **annualised average return over the selected horizon**.

With `M = 12T` monthly returns for a monthly-rebalanced portfolio, define:

`A_T = (12/M) Σ r_p,m`.

Under IID monthly returns, `E[A_T] = μ_a` and `SD(A_T) = σ_a / √T`, where `μ_a = 12μ_m` and `σ_a = √12 σ_m`. Thus the transparent analytical check is `μ_a ± σ_a / √T`. This is an arithmetic average, not the return of a compounded investment.

**Calculated illustration, not a portfolio estimate:** at mean 7% and annual volatility 18%, the IID band is −11% to +25% for one year, and approximately +2.98% to +11.02% for 20 years. Cumulative log-return dispersion grows approximately with `√T`; wealth uncertainty does not disappear.

For the actual display, use the 15.87th and 84.13th percentiles of jointly generated `A_T` outcomes: **“68% modelled range of horizon-average annual returns”**. Under a normal distribution this is the familiar ±1σ interval. With leverage or skew, it is a central 68.27% interval and must not be described as exactly mean ± standard deviation. Hover text supplies the endpoint values and definition. The arithmetic expected-return line and this band use the same return statistic.

Account for serial dependence with synchronised blocks, not independent shocks per asset. Separate:

1. Market-path uncertainty conditional on fitted inputs.
2. Estimation uncertainty in exposures and expected premiums.
3. Unquantified structural uncertainty, such as regime changes or imperfect product terms.

The default band includes the first two, with estimation draws shared across the full horizon. A useful check is `SD(A_T) ≈ sqrt(σ_LR²/T + τ_μ²)`; `τ_μ` is the estimated uncertainty of the annual mean, not an arbitrary fixed add-on. This leaves an uncertainty floor. Changing rates and model misspecification can invalidate simple square-root scaling; do not force simulated bands to narrow mechanically.

The frontier still optimises one-period mean and variance. Changing the display horizon does not turn it into a horizon-optimal portfolio. Compounded-return percentiles belong on Compare; do not silently overlay CAGR percentiles around an arithmetic frontier.

## 5. Real FF5 calibration

### Published data and regional mapping

Kenneth French's free library contains much more than US factors. The developed/regional descriptions currently cover July 1990–August 2026; emerging-market monthly factors cover July 1989–August 2026. The series are USD simple returns, including dividends and capital gains. Emerging SMB construction changes early in the sample, so the long-history multiregion analysis must respect the common complete-factor window. [S1, S2]

Use the actual download links in the French catalogue, retain every source ZIP and hash, parse monthly rows only, divide percentages by 100 once and explicitly reject missing-value codes. Preserve the original RF series. Store factor region and vintage alongside every coefficient.

| Equity exposure | Primary candidate basis |
|---|---|
| Developed world | Developed FF5 |
| US equity | US FF5; North America FF5 as a documented sensitivity |
| UK / Europe | Europe FF5; acknowledge the absence of a dedicated UK FF5 series in this selected set |
| Japan | Japan FF5 |
| Developed Asia-Pacific ex Japan | Asia-Pacific ex Japan FF5 |
| Emerging / India / China A | Emerging FF5; single-country residual risk remains material |
| All-world, VWRP | Joint Developed and Emerging FF5 blocks, regularised; compare against Developed-only |
| Momentum / multifactor strategies | FF5 baseline plus separately labelled published MOM extension where justified by chronological validation |

Do not assume that a fund marketed as “quality” has RMW beta 1, or that MSCI size/minimum-volatility indices are French factors. Fit their realised exposures. Momentum is **not** an FF5 factor. Regional coefficients must retain their basis; adding a US HML beta to a European HML beta as if they were one common exposure is invalid.

### Currency and history

Use actual share-class net total returns with distributions reinvested, converted to GBP. With `x_t` the simple return of GBP per USD, retain:

`MKT_GBP = (1 + MKT_USD + RF_USD)(1 + x_t) − 1 − RF_GBP`

`STYLE_GBP = STYLE_USD × (1 + x_t)`.

Style factors are long–short spreads: do not add a separate standalone FX return. Use compounded SONIA as the GBP research cash reference, with its wholesale-cash convention disclosed. SONIA is not the Trading 212 cash rate. Its public history starts in 1997; use the common verified factor/FX/cash period rather than silently filling earlier GBP cash. [S4]

Prefer 120 recent complete months for fund betas; require 72 actual compatible months for an unconstrained equity regression. Do not truncate every established fund to a recently launched product's short life. Each fit has its own documented window. Recent products need a separately validated proxy model and cannot acquire fictitious actual returns before inception. The leveraged products use the separate daily-mechanics route.

### Regression and validation

Fit `r_i,t^net − RF_GBP,t = α_i + β_i′ f_g,t + ε_i,t`.

Retain ridge penalties `0, 0.1, 1, 10, 100`, an unpenalised intercept and fold-specific standardisation. Select penalty **and any model extension** using chronological training folds with at least 36 initial months and 12-month validation blocks. The final 12 months are assessment only. Never choose FF5 versus market-only using that final holdout and then report it as untouched validation. Refit the selected specification on the full eligible window for current estimates.

Compare market-only, unregularised FF5 and ridge FF5. Assess validation RMSE, fitted alpha, holdout performance, residual volatility and beta stability. Report failed or unstable FF5 fits honestly. Company fundamentals are not required for this return-based calibration, and it must not be described as a holdings-characteristic model.

### Estimate premiums, rather than insert ETF historical means

Estimate factor premiums from the longest compatible published history, separate from the shorter beta window. Replace the previous blanket “50% of every style mean” default with explicit statistical shrinkage.

Let `m` be the vector of annualised factor sample means and `V` the estimated covariance of those means, using synchronised 12-month moving blocks (6/24-month sensitivity). Choose a zero-centred normal prior, with annual premium standard deviations of **5 percentage points for market factors and 2 percentage points for styles/MOM**. These scales are transparent research judgements, not fitted truths. Then:

`P = (V⁻¹ + P0⁻¹)⁻¹`

`λ_hat = P V⁻¹ m`.

Use stable linear solves and documented regularisation if the mean-covariance estimate is singular. Retain cross-region covariance, keep negative estimates negative and compare half/double prior scales, unshrunk premiums, and zero style premiums. Include a ±2 percentage-point market-premium sensitivity. Freeze these policy choices before inspecting the selected funds' frontier contribution.

The forward equity estimate is `μ_i,m = RF_GBP,m^forward + β_i′(λ_hat/12) − c_i,m`, with **zero expected gross alpha**. Historical fitted net alpha remains diagnostic. Actual net return histories already include expenses; do not subtract TER again in historical charts or covariance. Deduct incremental costs once when forecasting from gross factor premiums. A measured all-in tracking drag replaces the cost components it already contains.

For estimation bands, jointly block-resample the relevant history and refit exposures/recompute shrunken premiums with the specification and prior policy fixed. Use the resulting mean-return draws; do not add the posterior covariance a second time to the same uncertainty calculation. Label this as bootstrap estimation uncertainty, conditional on the model specification.

## 6. Other assets and the shared risk model

| Model | Forward-return policy | Required evidence |
|---|---|---|
| Trading 212 cash | Actual applicable AER converted to accrual periods; variable future-rate scenarios | Dated quote, account type, rate eligibility, cash terms; no invented deposit guarantee |
| Nominal government bonds | Carry from correctly defined current yield, net costs; explicit yield-change and roll-down assumptions | Dated yield, duration, convexity where available and yield curve |
| Inflation-linked bonds | Real yield plus explicit inflation/indexation assumptions; real-yield duration | Do not misread real yield as nominal total return or treat long-duration linkers as riskless inflation hedges |
| Corporate / high-yield / EM bonds | Carry less expected default losses and costs; spread and government-rate sensitivities | Yield-to-worst where appropriate, credit/spread duration, loss/recovery assumptions |
| Hedged foreign bonds | Actual hedged share-class history and consistent forward hedge-cost treatment | VAGS, ITPG and GHYS hedge definitions; avoid charging the hedge twice |
| Physical gold/silver | Price/FX model; no FF5 or coupon assumption | Actual product NAV and costs; physical-metal legal structure |
| Commodity futures | Actual total-return benchmark/product, with roll/collateral already recognised where embedded | Index variant, roll schedule, collateral treatment and product fees |
| Daily leveraged equities | Daily underlying paths, reset/funding/fees, then compound to months | Issuer terms, actual daily overlap and reset/termination rules |

For commodities, use a declared neutral **zero excess premium over GBP cash before product costs** as the base research prior, with ±5 percentage-point premium scenarios. For physical metals, this is an assumed price appreciation, not an interest payment. This is a policy assumption, not a claim that history proves a positive premium.

Bond forecasts use carry and explicit curve scenarios rather than the mean return of a recent rate cycle. The central approximation holds yields constant and adds no unsupported roll-down. Rate stress uses `−D Δy + 0.5 C (Δy)²` plus carry/costs; inflation, FX and spread moves require separate terms. Current yield/duration values cannot be used retrospectively as if known in past years.

**Leverage is an engine feature, not a multiplied beta shortcut.** A schematic daily formula is `r_L,d ≈ L r_U,d − (L−1) funding_d − product_cost_d − other_documented_drag_d`; use each issuer's exact mechanics, underlying return definition and currency. Financing may already be embedded in an index. A wrapper on QQQ already inherits QQQ expenses. Do not charge either twice. If the native benchmark is USD-based, apply its reset there and then convert the product into GBP; do not multiply a GBP-converted index by L indiscriminately. [S5–S7]

A calculated test: an underlying rising 10% then falling 9.0909% ends flat. Ignoring costs, 2× daily exposure loses 1.8182%, and 3× loses 5.4545%. Daily leverage does not equal L times the holding-period return. Product termination is an absorbing loss state; no negative NAV or automatic resurrection. Missing intraday reset evidence is an explicit model limitation/gate, not licence to invent a barrier rule.

For the unleveraged core, estimate one shrinkage covariance from synchronised actual GBP monthly total returns over an adequate common window. Preserve cross-asset correlations. Do not construct independent equity/bond/commodity blocks with zero cross-covariance or use pairwise missing-data covariance without a coherent PSD estimator. A documented index model may extend a short instrument's risk history, but its reconstructed periods remain labelled and residual/tracking risk is retained.

With leverage admitted, derive **all assets' forward joint monthly moments together** from shared daily scenarios; core asset paths are calibrated to their forward means and the leveraged paths follow actual product mechanics. Use synchronised 20-trading-day blocks initially, with 5/60-day sensitivities, and compare resulting core covariance with the empirical estimate. Validate monthly means and cross-covariances jointly. Never graft a simulated leveraged variance onto unrelated correlations.

Treat cash as conditionally deterministic for the next-period nominal frontier only when its quote is known. Append its zero conditional-risk row after shrinking risky assets, so shrinkage cannot manufacture cash volatility or diversification. Longer-horizon rate uncertainty and cash-facility stress are separate scenario inputs. Zero conditional volatility is not a guarantee of safety.

If factor covariance is used as a diagnostic, preserve `BΣ_fB′ + Σ_ε + B Cov(f,ε) + Cov(ε,f)B′`. Ridge residuals need not be orthogonal to factors. Do not add an arbitrary overlap penalty on top of covariance.

## 7. Optimisation, diversity and universe usefulness

Solve `min w′Σw` subject to `1′w=1`, `w≥0`, `μ′w≥target` and the explicit fund/class/economic-exposure bounds. Independent numerical checks must verify the returned weights, target and all exposure limits. Use a highest-return tie-break among numerically equal minimum-variance solutions, particularly with cash. At zero volatility, Sharpe-like ratios are undefined.

The 50 names were selected for differentiated economic roles, not because this planning pass found them optimal. Test usefulness across a **predeclared** set: central/zero-style/unshrunk premiums; market-premium shifts; rate up/down; commodity sensitivities; covariance-window sensitivity; and leverage/cash/commodity switches. Horizons alone do not create different one-period frontiers under this design.

For each instrument record maximum weight, frequency of meaningful inclusion, weight stability under bootstrap draws, and the effect of removing it at comparable return/risk. Flag an instrument that never reaches 1% and never improves an annual frontier metric by even 5 basis points for review. These thresholds are screening judgements, not investment evidence. Do not tune assumptions or introduce artificial caps to make every candidate appear. About 50 options is the design target; a smaller validated useful set is better than padding or unsupported forecasts.

### Effective companies

For each company `j`, aggregate economic equity exposure across all funds: `e_j = Σ_i w_i L_i h_ij`, using recursive underlying exposure for funds of funds/leveraged products. Merge share classes and duplicate listings into a reviewed company/issuer identifier; collateral is not the underlying equity portfolio.

Within mapped equity exposure, define `p_j = e_j / Σ_k e_k`, then:

`N_effective = 1 / Σ_j p_j²`.

100 equally weighted companies give 100; weights 50/25/25 give 2.67. Holding the same companies through two funds does not double the count. Multiplying every equity position by the same leverage factor does not improve this diversity metric.

Show the metric as **“Effective companies — equity sleeve”**, with the mapped coverage and holdings date. Cash, commodities and government bonds do not invent companies. A pure non-equity portfolio displays N/A. Require at least 95% mapped equity exposure for the headline estimate; otherwise display insufficient coverage. Even above that threshold, label a partial-coverage estimate as such and expose the unmapped portion. This describes company concentration, not total portfolio diversification or crisis resilience. Corporate-bond issuer concentration can be shown separately on Holdings.

## 8. Data contract and refresh

The public-source foundation is French factor files, Bank of England cash/FX/curves, Trading 212 instrument/terms evidence and issuer NAV/distribution/holdings/factsheet data. Use issuer total-return histories where available. Reconstruct distributing-share-class total returns only from consistent NAV and distribution records with the reinvestment convention documented.

Do not use Trading 212's displayed price tables as adjusted total-return evidence. For missing history, first use a documented same-fund/share-class source, then a labelled published index proxy with overlap checks. **Do not promise that 49 complete daily total-return histories are free.** EODHD is the selected bulk-provider candidate if issuer exports leave gaps, subject to verified symbol coverage, adjustment quality and permitted hosted use. Its documented free plan currently gives only one year of history and 20 requests/day, insufficient for the proposed calibration. A paid entitlement remains an optional implementation decision, not something purchased by this plan. [S8]

Store these logical tables as small CSV/JSON metadata and compressed time-series files:

- Instrument master: stable ID, ISIN, listing, legal structure, display category, model type, currencies, price unit, inception, hedge, fee conventions and broker-evidence date.
- Actual returns and separately labelled proxies: daily and monthly, with local/GBP units and distribution/split evidence.
- Factor panels, cash/FX, yield curves, dated bond characteristics, leverage terms and applicable cash quote.
- Company holdings/exposures with issuer mapping, coverage and as-of dates.
- Assumptions, constraints, source manifest, licences, retrieval times, hashes, validation status and model/schema version.

Use the latest **common completed** factor/return month; the latest verified French description in this planning pass ends August 2026. Never label a run October-calibrated merely because a current quote is available. Record missing observations rather than filling gaps with zero returns or fictitious prices. Normalise GBX/pence and do not double-convert GBP listings.

Refresh inputs outside interactive use. Begin with an explicit refresh command/job and retain the last good snapshot on failure. Initial freshness gates: return month and model-critical holdings/bond data no more than 90 days stale; applicable cash quote rechecked after 30 days or on terms/bonus changes. Rates can change sooner; always show the actual quote date. Historical vintages are retained going forward; present-day backfills are not true point-in-time data.

## 9. ZIP export

One on-demand download: `portfolio_<run>_<position>_<horizon>y.zip`. Include:

| Contents | Purpose |
|---|---|
| `README.md`, `methods.md` | Definitions, formulas, interpretation and reproduction instructions |
| `portfolio.csv`, `categories.csv`, `comparison.csv` | Full-precision allocations, category totals, both selected portfolios and fixed benchmarks |
| `frontier.csv`, `frontier_weights.csv` | Every solved point and the exact 0–100 mapping |
| `expected_returns.csv`, `covariance.csv`, `correlations.csv` | Engine inputs and risk/return reconciliation |
| `factor_betas.csv`, `factor_premiums.csv`, `calibration_diagnostics.csv` | Factor basis, periods, shrinkage, validation and fitted-alpha diagnostics |
| `costs.csv`, `exposures.csv`, `diversity.csv` | Fee/financing treatment and holdings-derived calculations/coverage |
| `horizon_quantiles.csv`, `stress.csv` | The plotted ranges and clearly named scenarios |
| `assumptions.json`, `constraints.json`, `manifest.json` | Dates, all settings, model commit/version, source hashes, seeds and solver residuals |
| Reusable calculation script and allowed input data | Reproduce the displayed run; retain source/licence restrictions |

Include raw/processed histories only where redistribution is permitted. Otherwise provide the necessary derived matrices, hashes, identifiers and retrieval instructions, and explicitly distinguish reproducing the solve from independently rerunning source ingestion/calibration. Never export credentials. Generate ZIP bytes only on request; remove the current eager workbook generation from normal slider interaction. Excel can remain an optional secondary export.

## 10. Implementation order and acceptance

| Stage | Concrete changes | Acceptance condition |
|---|---|---|
| 1. Snapshot and identities | Asset-aware schema, all 50 identity records, source coverage matrix; pilot VWRP, IWFV, IGLT, SGLN, cash, XS2D | Actual source reconciliation; each gap has an owner/model status; no legacy substitution |
| 2. Calibration | French ingestion, regional fits, chronological specification selection, shrunk premiums, FX/fee conventions | Published data produces reproducible betas and forecasts; final holdout remains untouched |
| 3. Multi-asset engine | Cash, bonds, commodities, shared covariance, constraints and 101-point mapping | Weights/targets/limits reconcile; cash endpoint and all class switches behave correctly |
| 4. Product mechanics | Daily leverage, aligned funding/FX, joint scenarios and horizon ranges | Same-endpoint path test, overlap reconciliation, convergence and termination handling pass |
| 5. Four-page UI | Compact Dashboard, all Holdings, same-run Compare, Methods report | Slider/typed entry stay in sync; fixed benchmarks persist; all displayed figures use the same run |
| 6. Handover | ZIP, source status, performance checks, documented useful-universe review | Download reproduces display, all gates pass, blocked products are identified explicitly |

Stages are implementation order, not permission to call an equity-only intermediate build complete. The deliverable includes working leveraged-product support and a documented decision for each selected candidate. If evidence is insufficient, retain a transparent blocked/comparison-only status rather than fabricate the missing inputs.

Proposed new modules: `portfolio/providers/`, `portfolio/models/{equity,bonds,cash,commodities,leveraged}.py`, `portfolio/scenarios.py`, `portfolio/validation.py`, and small `ui/` page modules. Extend existing optimisation, results, risk, holdings and exports rather than adding another frontend or a database service. Keep calculations out of UI components.

Cache the data snapshot, calibration, frontier and scenario summaries separately, keyed by model version and the inputs they actually use. Reuse one set of scenario draws across points and references. For monthly-rebalanced arithmetic-average bands, accumulate each simulated asset's horizon-average return and multiply by the frontier weight matrix; do not simulate 101 independent portfolio universes. Compound selected portfolios separately on Compare. Process daily paths in batches, retaining sufficient summaries rather than a paths×days×assets×frontier cube.

Initial engineering targets, to be measured rather than promised: warm slider <250 ms, 50-asset frontier <3 s, cached first view <3 s, worker memory <500 MB. Start with 2,000 horizon paths and convergence checks against 5,000; precompute/cache expensive summaries on Apply, not every slider event. If tails or interval endpoints are materially unstable, increase sampling or label insufficient precision instead of printing false decimals.

### Tests that are necessary

- Known dividend/split reconciliation; GBX/GBP/FX conventions; FF percentage parsing and early EM-factor availability.
- No pre-inception actual data; proxy lineage; actual net returns charged once.
- Training-only scaling and specification selection; final holdout isolation; regional factor identifiers retained.
- Symmetric PSD covariance; duplicate exposures do not manufacture diversification; deterministic cash appended correctly.
- Bond real/nominal yield treatment, hedge costs, duration signs and credit-loss accounting.
- Daily leverage path dependence, costs, native-currency reset, total loss and documented barriers.
- 1-year versus 20-year arithmetic band, serial dependence and estimation floor; CAGR never substituted without relabelling.
- Company aggregation across duplicate funds/share classes; 100-name equal weight and 50/25/25 examples; leverage/cash cannot inflate the count.
- Frontier endpoints, all three switches, gross exposure and infeasibility; typed 0/50/100 matches slider; single-point frontier.
- Complete non-zero fund table, same-run A/B comparison, unselectable fixed references and exact export/display agreement.

## 11. Remaining evidence, not unresolved design

This plan fixes the interface, 50 selected exposures, benchmark set, calibration approach and mathematics. It does **not** claim to have downloaded and reconciled every return history, fitted all betas, established each candidate's frontier contribution, or verified personal account permission. Those are explicit build gates.

The only user-specific input needed for cash is the applicable GBP rate/terms visible in the existing Invest account; until supplied or independently confirmed for that account, label the public-rate result as a provisional comparison. Any paid data purchase requires its own concrete coverage/price decision. Neither gap prevents building the schema, public-source adapters, model code or interface.

## References

Sources checked 12 October 2026. Design presets and numerical illustrations above are this specification's choices/calculations, not statements made by the sources.

- **S1.** [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), and [developed/regional FF5 definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html).
- **S2.** [French emerging-market FF5 definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5emerging.html).
- **S3.** [Trading 212: What is interest on cash?](https://helpcentre.trading212.com/hc/en-us/articles/15475153380637-What-is-interest-on-cash). Each exchange-traded candidate has its individual Invest-catalogue source in Appendix A/the CSV.
- **S4.** [Bank of England: SONIA features, history and compounding](https://www.bankofengland.co.uk/markets/sonia-benchmark/sonia-key-features-and-policies).
- **S5.** [DWS: Xtrackers S&P 500 2× daily](https://etf.dws.com/en-fi/LU0411078552-s-p-500-2x-leveraged-daily-swap-ucits-etf-1c/).
- **S6.** [Amundi: Nasdaq-100 daily 2×](https://www.amundietf.lu/en/individual/products/equity/amundi-nasdaq100-daily-2x-leveraged-ucits-etf-acc/fr0010342592).
- **S7.** [Leverage Shares: 3× Nasdaq-100](https://leverageshares.com/en/etps/leverage-shares-3x-long-nasdaq-100-etp/). Full product terms must be captured during the mechanics gate.
- **S8.** [EODHD: historical-data API, adjustment fields and free-plan limits](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes).
- **S9.** [iShares: ITPG GBP-hedged TIPS](https://www.ishares.com/uk/individual/en/products/295697/ishares-tips-ucits-etf-gbp-hedged-dist-fund), [Vanguard: VAGS GBP-hedged aggregate bonds](https://www.vanguard.co.uk/uk-fund-directory/product/etf/bond/9685/global-aggregate-bond-ucits).
- **S10.** [iShares: current world mid-cap equal-weight strategy, IWFS listing](https://www.ishares.com/uk/individual/en/products/270057/ishares-msci-world-size-factor-ucits-etf). Check benchmark-history continuity during admission rather than relying on its older “size factor” name.

## Appendix A — selected instruments

The schedule below is the planning selection, not a claim of completed calibration. All exchange-traded catalogue identities and ISINs were checked; fees, data history, issuer terms and account-specific tradability remain admission checks. The role column states why an exposure is worth testing, not a promise that it improves the efficient frontier.

| # | Category | Selected instrument / catalogue evidence | ISIN | Role |
|---:|---|---|---|---|
| 1 | Instant-access savings / cash | [T212_GBP_CASH — Trading 212 GBP interest-bearing cash](https://helpcentre.trading212.com/hc/en-us/articles/15475153380637-What-is-interest-on-cash) | Not a listed security | Accessible cash; conditional low-risk endpoint |
| 2 | Commodities | [SGLN — iShares Physical Gold](https://www.trading212.com/trading-instruments/invest/SGLN.GB) | IE00B4ND3602 | Gold; monetary/crisis diversification |
| 3 | Commodities | [SSLN — iShares Physical Silver](https://www.trading212.com/trading-instruments/invest/SSLN.GB) | IE00B4NCWG09 | Silver; precious-metal and industrial exposure |
| 4 | Commodities | [CMOP — Invesco Bloomberg Commodity Acc](https://www.trading212.com/trading-instruments/invest/CMOP.GB) | IE00BD6FTQ80 | Diversified commodity futures basket |
| 5 | Commodities | [COPA — WisdomTree Copper](https://www.trading212.com/trading-instruments/invest/COPA.GB) | GB00B15KXQ89 | Industrial-metal supply/demand exposure |
| 6 | Commodities | [AIGA — WisdomTree Agriculture](https://www.trading212.com/trading-instruments/invest/AIGA.GB) | GB00B15KYH63 | Agricultural futures; different supply shocks |
| 7 | Commodities | [CRUD — WisdomTree WTI Crude Oil](https://www.trading212.com/trading-instruments/invest/CRUD.GB) | GB00B15KXV33 | Energy futures; inflation/supply scenarios |
| 8 | Bonds | [IGLS — iShares UK Gilts 0-5yr Dist](https://www.trading212.com/trading-instruments/invest/IGLS.GB) | IE00B4WXJK79 | Short GBP government duration |
| 9 | Bonds | [IGLT — iShares Core UK Gilts Dist](https://www.trading212.com/trading-instruments/invest/IGLT.GB) | IE00B1FZSB30 | Broad GBP government duration |
| 10 | Bonds | [GLTL — SPDR Bloomberg 15+ Year Gilt Dist](https://www.trading212.com/trading-instruments/invest/GLTL.GB) | IE00B6YX5L24 | Long GBP duration; rate sensitivity |
| 11 | Bonds | [INXG — iShares GBP Index-Linked Gilts Dist](https://www.trading212.com/trading-instruments/invest/INXG.GB) | IE00B1FZSD53 | UK inflation linkage and real-rate risk |
| 12 | Bonds | [IS15 — iShares GBP Corp Bond 0-5yr Dist](https://www.trading212.com/trading-instruments/invest/IS15.GB) | IE00B5L65R35 | Short sterling investment-grade credit |
| 13 | Bonds | [SLXX — iShares Core GBP Corp Bond Dist](https://www.trading212.com/trading-instruments/invest/SLXX.GB) | IE00B00FV011 | Broad sterling investment-grade credit |
| 14 | Bonds | [VAGS — Vanguard Global Aggregate Bond GBP Hedged Acc](https://www.trading212.com/trading-instruments/invest/VAGS.GB) | IE00BG47K971 | Diversified GBP-hedged bonds; fixed reference |
| 15 | Bonds | [IBTS — iShares USD Treasury Bond 1-3yr Dist](https://www.trading212.com/trading-instruments/invest/IBTS.GB) | IE00B14X4S71 | Short US government duration plus USD exposure |
| 16 | Bonds | [IBTM — iShares USD Treasury Bond 7-10yr Dist](https://www.trading212.com/trading-instruments/invest/IBTM.GB) | IE00B1FZS798 | Intermediate US duration plus USD exposure |
| 17 | Bonds | [IBTL — iShares USD Treasury Bond 20+yr Dist](https://www.trading212.com/trading-instruments/invest/IBTL.GB) | IE00BSKRJZ44 | Long US duration plus USD exposure |
| 18 | Bonds | [ITPG — iShares USD TIPS GBP Hedged Dist](https://www.trading212.com/trading-instruments/invest/ITPG.GB) | IE00BDZVH859 | US inflation linkage with GBP hedge |
| 19 | Bonds | [GHYS — iShares Global High Yield Corp Bond GBP Hedged Dist](https://www.trading212.com/trading-instruments/invest/GHYS.GB) | IE00B8KQFS66 | Higher credit spread; defaults modelled explicitly |
| 20 | Bonds | [VEMT — Vanguard USD Emerging Markets Government Bond Dist](https://www.trading212.com/trading-instruments/invest/VEMT.GB) | IE00BZ163L38 | Emerging sovereign credit plus USD exposure |
| 21 | ETFs | [VWRP — Vanguard FTSE All-World Acc](https://www.trading212.com/trading-instruments/invest/VWRP.GB) | IE00BK5BQT80 | Developed and emerging core; fixed all-world reference |
| 22 | ETFs | [SWDA — iShares Core MSCI World Acc](https://www.trading212.com/trading-instruments/invest/SWDA.GB) | IE00B4L5Y983 | Developed-only core; independent EM allocation |
| 23 | ETFs | [VUSA — Vanguard S&P 500 Dist](https://www.trading212.com/trading-instruments/invest/VUSA.GB) | IE00B3XXRP09 | US large-cap core |
| 24 | ETFs | [EQQQ — Invesco EQQQ Nasdaq-100 Dist](https://www.trading212.com/trading-instruments/invest/EQQQ.GB) | IE0032077012 | US growth concentration; unleveraged comparator |
| 25 | ETFs | [VUKE — Vanguard FTSE 100 Dist](https://www.trading212.com/trading-instruments/invest/VUKE.GB) | IE00B810Q511 | UK large-cap equity |
| 26 | ETFs | [VMID — Vanguard FTSE 250 Dist](https://www.trading212.com/trading-instruments/invest/VMID.GB) | IE00BKX55Q28 | UK mid-cap/domestic equity mix |
| 27 | ETFs | [VERX — Vanguard FTSE Developed Europe ex UK Dist](https://www.trading212.com/trading-instruments/invest/VERX.GB) | IE00BKX55S42 | Continental developed European equity |
| 28 | ETFs | [VJPN — Vanguard FTSE Japan Dist](https://www.trading212.com/trading-instruments/invest/VJPN.GB) | IE00B95PGT31 | Japanese equity |
| 29 | ETFs | [VAPX — Vanguard FTSE Developed Asia Pacific ex Japan Dist](https://www.trading212.com/trading-instruments/invest/VAPX.GB) | IE00B9F5YL18 | Developed Pacific ex-Japan equity |
| 30 | ETFs | [EMIM — iShares Core MSCI EM IMI Acc](https://www.trading212.com/trading-instruments/invest/EMIM.GB) | IE00BKM4GZ66 | Broad emerging equity including smaller companies |
| 31 | ETFs | [IIND — iShares MSCI India Acc](https://www.trading212.com/trading-instruments/invest/IIND.GB) | IE00BZCQB185 | India sleeve; retain country-specific residual risk |
| 32 | ETFs | [IASH — iShares MSCI China A Acc](https://www.trading212.com/trading-instruments/invest/IASH.GB) | IE00BQT3WG13 | Mainland China sleeve; different local market exposure |
| 33 | ETFs | [IWDP — iShares Developed Markets Property Yield Dist](https://www.trading212.com/trading-instruments/invest/IWDP.GB) | IE00B1FZS350 | Listed property equity; not direct property or bonds |
| 34 | Factor-tilted ETFs | [IWFV — iShares Edge MSCI World Value Factor Acc](https://www.trading212.com/trading-instruments/invest/IWFV.GB) | IE00BP3QZB59 | Developed-world value tilt |
| 35 | Factor-tilted ETFs | [IWFM — iShares Edge MSCI World Momentum Factor Acc](https://www.trading212.com/trading-instruments/invest/IWFM.GB) | IE00BP3QZ825 | Momentum; explicit FF5+MOM extension |
| 36 | Factor-tilted ETFs | [IWFQ — iShares Edge MSCI World Quality Factor Acc](https://www.trading212.com/trading-instruments/invest/IWFQ.GB) | IE00BP3QZ601 | Quality selection; measure actual RMW/CMA exposure |
| 37 | Factor-tilted ETFs | [MVOL — iShares Edge MSCI World Minimum Volatility Acc](https://www.trading212.com/trading-instruments/invest/MVOL.GB) | IE00B8FHGS14 | Defensive equity construction |
| 38 | Factor-tilted ETFs | [IWFS — iShares MSCI World Mid-Cap Equal Weight Acc](https://www.trading212.com/trading-instruments/invest/IWFS.GB) | IE00BP3QZD73 | Size/equal-weight tilt; check strategy-history continuity |
| 39 | Factor-tilted ETFs | [WLDS — iShares MSCI World Small Cap Acc](https://www.trading212.com/trading-instruments/invest/WLDS.GB) | IE00BF4RFH31 | Developed small-cap sleeve |
| 40 | Factor-tilted ETFs | [USSC — SPDR MSCI USA Small Cap Value Weighted Acc](https://www.trading212.com/trading-instruments/invest/USSC.GB) | IE00BSPLC413 | US small/value combination |
| 41 | Factor-tilted ETFs | [ZPRX — SPDR MSCI Europe Small Cap Value Weighted Acc](https://www.trading212.com/trading-instruments/invest/ZPRX.DE) | IE00BSPLC298 | European small/value; Xetra listing |
| 42 | Factor-tilted ETFs | [IUVF — iShares Edge MSCI USA Value Factor Acc](https://www.trading212.com/trading-instruments/invest/IUVF.GB) | IE00BD1F4M44 | US value sleeve |
| 43 | Factor-tilted ETFs | [IEFV — iShares Edge MSCI Europe Value Factor Acc](https://www.trading212.com/trading-instruments/invest/IEFV.GB) | IE00BQN1K901 | European value sleeve |
| 44 | Factor-tilted ETFs | [EMVL — iShares Edge MSCI EM Value Factor Acc](https://www.trading212.com/trading-instruments/invest/EMVL.GB) | IE00BG0SKF03 | Emerging-market value sleeve |
| 45 | Factor-tilted ETFs | [JPGL — JPMorgan Global Equity Multi-Factor Acc](https://www.trading212.com/trading-instruments/invest/JPGL.GB) | IE00BJRCLL96 | Combined factors; test MOM extension explicitly |
| 46 | Factor-tilted ETFs | [GGRG — WisdomTree Global Quality Dividend Growth Acc](https://www.trading212.com/trading-instruments/invest/GGRG.GB) | IE00BZ56SW52 | Quality/dividend-growth construction |
| 47 | Leveraged ETFs / ETPs | [XS2D — Xtrackers S&P 500 2x Leveraged Daily Swap Acc](https://www.trading212.com/trading-instruments/invest/XS2D.GB) | LU0411078552 | 2x broad US daily exposure; fixed leveraged reference |
| 48 | Leveraged ETFs / ETPs | [LQQ — Amundi Nasdaq-100 Daily (2x) Leveraged Acc](https://www.trading212.com/trading-instruments/invest/LQQ.FR) | FR0010342592 | 2x Nasdaq-100 daily; Paris listing |
| 49 | Leveraged ETFs / ETPs | [3LUS — WisdomTree S&P 500 3x Daily Leveraged](https://www.trading212.com/trading-instruments/invest/3LUS.GB) | IE00B7Y34M31 | 3x broad US daily exposure; collateralised ETP |
| 50 | Leveraged ETFs / ETPs | [3QQQ — Leverage Shares 3x Long Nasdaq 100](https://www.trading212.com/trading-instruments/invest/3QQQ.GB) | XS2472197065 | 3x QQQ daily exposure; underlying fund expenses apply |
