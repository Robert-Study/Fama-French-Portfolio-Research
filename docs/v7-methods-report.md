# Efficient-frontier research using regional Fama–French estimation

*Draft for the separate Streamlit Methods page · 12 October 2026 · Proposed V7 method; no V7 empirical results are claimed.*

## Introduction

This model compares conditional portfolio allocations available through a UK Trading 212 Invest account. Its proposed universe contains 49 exchange-traded products and interest-bearing GBP cash, grouped into six categories: savings/cash, commodities, bonds, equity ETFs, factor-tilted ETFs and leveraged products. The objective is to identify portfolios with the lowest modelled variance for a given expected return, while making the assumptions and uncertainty visible.

The Fama–French five-factor model (FF5) provides an empirical description of equity exposures. It does not determine future returns without assumptions about factor premiums. Separate models are required for non-equity assets and daily-reset leverage. All portfolio calculations use nominal GBP total returns before personal tax.

## Body: data and methods

### Data and equity estimation

Fund histories use actual share-class total returns, including reinvested distributions. Prices quoted in pence are normalised and foreign-currency returns are converted consistently to GBP. Pre-inception index proxies are identified separately from actual observations.

The Kenneth French Data Library supplies public US, developed, regional and emerging-market factors. Developed/regional histories extend from July 1990, and emerging-market monthly histories from July 1989; early emerging-factor construction changes require attention to the common complete-factor period. The source returns are expressed in USD. [1, 2]

For fund \(i\), monthly excess returns are estimated as

\[
r_{i,t}^{net}-r_{f,t}=\alpha_i+\boldsymbol{\beta}_i^\top\mathbf f_{g,t}+\varepsilon_{i,t},
\]

where \(\mathbf f_{g,t}\) contains market, size, value, profitability and investment factors for the relevant region. Global all-world exposure can use regularised developed and emerging blocks. Momentum, where used, is a separately identified extension rather than an FF5 factor.

With \(x_t\) denoting the return of GBP per USD, the market factor is converted as

\[
f_{M,t}^{GBP}=(1+f_{M,t}^{USD}+r_{f,t}^{USD})(1+x_t)-1-r_{f,t}^{GBP}.
\]

Long–short style spreads are multiplied by \(1+x_t\); a standalone FX return is not added to them. Compounded SONIA supplies the GBP research cash reference, distinct from the broker's retail cash rate. [3]

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

Bond estimates use current carry, duration, inflation where applicable, credit losses and explicit yield/hedge assumptions. Commodity estimates distinguish physical metals from futures products whose returns include roll and collateral effects. Cash uses the applicable variable rate. Trading 212 cash can include qualifying money-market funds, so it must not be represented as an unconditional insured bank deposit. [4]

Leveraged products are modelled from daily underlying returns, funding, fees and contractual reset rules before monthly aggregation. Multiplying a long-horizon return by the leverage factor is invalid. Native-currency resets precede GBP conversion where required by product mechanics. [5]

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
