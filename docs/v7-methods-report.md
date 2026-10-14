# Efficient-frontier research using regional Fama–French estimation

*Methods page · 14 October 2026 · Model 0.3.0. Executed calibration diagnostics and current capability exclusions appear below this report.*

## Introduction

This model compares conditional GBP portfolio allocations from a selected universe of 49 exchange-traded products plus a separate UK bank savings account. Public Trading 212 listings do not establish individual-account eligibility. The original six categories remain visible: savings/cash, commodities, bonds, equity ETFs, factor-tilted ETFs and leveraged products. Thirty forward models currently pass their capability gates; the remainder retain specific exclusions. The objective is to identify portfolios with the lowest modelled variance for a given expected return, while making assumptions and uncertainty visible.

The Fama–French five-factor model (FF5) provides an empirical description of equity exposures. It does not determine future returns without assumptions about factor premiums. Separate models are required for non-equity assets and daily-reset leverage. All portfolio calculations use nominal GBP total returns before personal tax.

## Body: data and methods

### Data and equity estimation

Fund histories use actual share-class total returns, including reinvested distributions. Prices quoted in pence are normalised and foreign-currency returns are converted consistently to GBP. Pre-inception index proxies are identified separately from actual observations.

The Kenneth French Data Library supplies public US, developed, regional and emerging-market factors. Developed/regional histories extend from July 1990; the acquired Emerging five-factor panel has complete observations from July 1992 after missing-value sentinels are excluded. GBP premium estimation uses the common actual FX/factor period and ends in August 2026. The source returns are expressed in USD. [1, 2]

For fund \(i\), monthly excess returns are estimated as

\[
r_{i,t}^{net}-r_{f,t}=\alpha_i+\boldsymbol{\beta}_i^\top\mathbf f_{g,t}+\varepsilon_{i,t},
\]

where \(\mathbf f_{g,t}\) contains market, size, value, profitability and investment factors for the relevant region. Global all-world exposure can use regularised developed and emerging blocks. Momentum, where used, is a separately identified extension rather than an FF5 factor.

With \(x_t\) denoting the return of GBP per USD, the market factor is converted as

\[
f_{M,t}^{GBP}=(1+f_{M,t}^{USD}+r_{f,t}^{USD})(1+x_t)-1-r_{f,t}^{GBP}.
\]

Long–short style spreads are multiplied by \(1+x_t\); a standalone FX return is not added to them. Actual delayed SONIA supplies the GBP research cash reference, distinct from savings AER. Each business-day observation accrues simply over its ACT/365 calendar interval; month-boundary allocations use ratios of accrued levels so subperiod factors telescope. Current live BoE access fails, so dated actual observations supplied by the research task are used. Latest observed SONIA held flat is an explicit forward scenario, not a market OIS forecast. [3]

Ridge regression uses up to 120 recent months, with 72 required for an ordinary equity fit. Scaling, penalty selection and model-extension selection occur inside chronological training folds. The final 12 months are reserved for assessment. Market-only and unregularised FF5 models provide comparisons; the selected specification is then refitted for current exposures.

### Expected returns and other assets

Long-history factor means are shrunk towards explicit zero-centred priors using their estimated sampling uncertainty. If \(m\) is the annualised historical mean vector, \(V\) its sampling covariance and \(P_0\) the prior covariance,

\[
\widehat\lambda=(V^{-1}+P_0^{-1})^{-1}V^{-1}m.
\]

Prior scales are research choices tested in sensitivity analysis. Negative premiums are retained. Forward monthly equity returns are

\[
\mu_i=r_f^{forward}+\boldsymbol\beta_i^\top\widehat\lambda/12-c_i.
\]

Expected gross alpha is zero. Historical net returns already contain fund expenses; forecasting costs are deducted once, with financing and underlying-fund charges reconciled separately.

Admitted government-bond estimates use dated issuer YTM and duration with constant yields and zero assumed roll-down. Unresolved credit, inflation and hedge inputs block the other forward models. Physical metals use a neutral zero excess-return prior over forward SONIA, less ongoing charges; this is an assumption, not a metal coupon. Futures products remain blocked pending roll/collateral/swap reconciliation. Savings uses the dated bank's variable AER, with conditional deposit-protection and eligibility limits; it is outside Trading 212. Actual net histories are not charged expenses again.

The leverage engine models daily underlying returns, funding, fees and contractual resets before monthly aggregation. No selected leveraged forward model has yet passed all those evidence gates. XS2D remains available as an actual historical reference after issuer workbook/chart reconciliation within a declared 1bp trigger, with an incomplete independent corporate-action audit disclosed. Multiplying monthly returns by leverage is invalid; native resets precede GBP conversion. [5]

### Risk, optimisation and concentration

Synchronised returns provide a common cross-asset covariance matrix, with shrinkage and duplicate-series checks. Leveraged inclusion requires joint daily scenarios whose monthly means and covariance reconcile with the other asset models. Cross-asset correlations are retained.

For weights \(w\), the programme solves

\[
\min_w w^\top\Sigma w\quad
\text{subject to }\mathbf1^\top w=1,\;w\ge0,\;\mu^\top w\ge q,
\]

plus stated category and economic-exposure limits. The 0–100 control indexes 101 targets between minimum variance and maximum feasible expected return. It is not a personal risk score.

Company exposures are consolidated across funds. For normalised mapped equity-company weights \(p_j\), the effective-company count is \(1/\sum_j p_j^2\). It measures equity concentration, not total portfolio safety. Cash and bonds do not inflate the count; insufficient holdings coverage produces an unavailable result.

### Horizon uncertainty and validation

The frontier uses annualised arithmetic mean \(\mu_a=12\mu_m\) and volatility \(\sigma_a=\sqrt{12}\sigma_m\). For the annualised average of \(12T\) monthly portfolio returns, IID sampling gives a standard deviation \(\sigma_a/\sqrt T\). This is not CAGR, and does not imply that cumulative wealth uncertainty decreases with time.

The shaded region represents the simulated 15.87th–84.13th percentiles of that same horizon-average statistic. Synchronised blocks preserve dependence; jointly re-estimated inputs represent estimation uncertainty. The approximation \(\sqrt{\sigma_{LR}^2/T+\tau_\mu^2}\) illustrates why an uncertain expected return leaves a persistent uncertainty floor. Compounded outcomes and drawdowns are reported separately. No interval guarantees coverage under a different future regime.

| Validation area | Evidence required before reporting results |
|---|---|
| Data | Identity, distributions, currency, source dates and proxy reconciliation |
| Estimation | Chronological validation, holdout error, coefficient stability and premium sensitivity |
| Risk and products | PSD covariance, cross-asset dependence, daily leverage and fee checks |
| Optimisation | Feasible weights, target/cap reconciliation and allocation stability |
| Reproducibility | Displayed result matches exported inputs, assumptions, versions and seeds |

## Conclusion

V7 is designed as a transparent conditional research model, combining published equity-factor evidence with asset-specific forecasts and constrained optimisation. Its main limitations are uncertain premiums, unstable relationships, imperfect histories and incomplete tail-event information. A portfolio's appearance on the frontier is therefore a consequence of stated inputs, not proof of superior future performance. Validation results and excluded instruments must be reported before investment-performance claims are made.

## References

1. [Kenneth French: Data Library and regional factor downloads](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
2. [French: developed FF5 definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html); [emerging FF5 definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5emerging.html).
3. [Bank of England: SONIA features and compounding](https://www.bankofengland.co.uk/markets/sonia-benchmark/sonia-key-features-and-policies).
4. [Trading 212: interest on cash and its terms](https://helpcentre.trading212.com/hc/en-us/articles/15475153380637-What-is-interest-on-cash).
5. [DWS: S&P 500 2× daily product](https://etf.dws.com/en-fi/LU0411078552-s-p-500-2x-leveraged-daily-swap-ucits-etf-1c/); [Leverage Shares: 3× Nasdaq-100 product](https://leverageshares.com/en/etps/leverage-shares-3x-long-nasdaq-100-etp/).
