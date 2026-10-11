# V6 methodology

## What this release does

The app solves a long-only, fully invested minimum-variance frontier and displays the weights at each solved point. There are two input paths:

- **Legacy demonstration** uses the original V5 monthly returns. Their providers, splices, fee treatment and claimed GBP conversion have not been independently reconciled. Sample means and covariance demonstrate the software; they are not authenticated investment forecasts.
- **Return-based FF5** estimates exposures from documented fund/index returns and matching factor, cash and FX inputs. File validation checks the contract, not the truth of source declarations. The app calls these supplied-data research results.

Neither path estimates factor exposures from company characteristics. V5's `fundamentals.csv` contains no observations. The interview figures (beta 1.10, expected return 8%, volatility 18.4%) are not verified outputs of this release.

The hosted Streamlit app supersedes the offline HTML/Excel interface in the earlier implementation plan. Excel is an optional results download. There is no database, external AI call or live data download during a calculation.

## Units and evidence

Estimation and optimisation use monthly simple returns in decimal units. Fund returns include reinvested distributions. The research contract specifies GBP net total returns and records actual-fund versus published-index-proxy histories. It rejects undocumented splices. A proxy is not actual pre-inception fund performance.

Displayed return is `12 × monthly arithmetic mean`. Displayed volatility is `sqrt(12) × monthly standard deviation`, conditional on negligible serial dependence. Neither is a historical CAGR, an exact compounded one-year return, or a promised result.

Original V5 bytes and the source manifest are retained in `data/legacy`. A matching hash establishes identity, not accuracy. Signed cash and derivative balances are preserved. Legacy priors and the empty fundamentals file are retained for audit and are not used as fitted FF5 exposures.

The initial selection is the first 20 equity funds in the saved V5 fund order, chosen for interface testing, not after inspecting investment performance. Users can select any of the 28 legacy equity funds. GHYS is excluded because it is a credit fund. No fund cap below 100% is imposed without a user choice.

## GBP factor conversion

French's developed-market FF5 factors and risk-free series are in USD. Let `x` be the monthly return of USD measured in GBP, `RF_USD` the French cash return and `RF_GBP` the matching GBP cash return:

```
Mkt_GBP = (1 + Mkt_RF_USD + RF_USD) * (1 + x) - 1 - RF_GBP
Style_GBP = Style_USD * (1 + x)
```

The style factors are zero-investment long–short spreads. Adding a standalone FX return to them would be wrong. Currency conversion must precede estimation and calculation of premium assumptions. A hedged share class needs its own hedge model and is excluded here. The current research path covers unleveraged developed-equity funds only; emerging-market funds need an appropriate regional basis and validation.

## Calibration and validation

For each fund, fit `net_return - GBP_cash = intercept + beta × GBP_factors + residual`.

The selected estimation window must contain at least 72 complete months: at least 60 initial training months and a final 12-month holdout. These are practical minimums, not proof of statistical reliability. Inside the training period, expanding chronological folds use 12-month validation blocks and at least 36 initial training months. There are at most five folds. No rows are shuffled.

Choose each fund's ridge penalty from `0, 0.1, 1, 10, 100`, using validation mean-squared error. Standardisation is fitted separately inside each training fold; the intercept is unpenalised. Betas are converted back to original factor units.

The final 12 months assess the chosen specification once. The app reports RMSE against market-only OLS and unregularised FF5, and an out-of-sample R² relative to the original training mean. It then refits the selected penalty on all displayed months for current exposure estimates. A worse market-only comparison is flagged. There is no automatic claim of an acceptable model based solely on a score or row count. Twelve holdout months provide weak evidence about stability, and repeated human tuning against that holdout would contaminate it.

## Forward return and fees

```
monthly_net_mean = assumed_monthly_cash + beta @ assumed_monthly_premiums - annual_TER / 12
```

Expected gross alpha is zero. Historical fitted net alpha remains a diagnostic and is not carried into the forecast. Deducting TER here is appropriate because the starting forecast is gross factor compensation; deducting it again from a historical net mean would double count it.

The research UI defaults premiums to arithmetic means over the entire compatible supplied factor sample. Future premiums are assumptions, not estimated certainties. The cash default annualises the last observed monthly cash return; it is an editable forward assumption, not a quoted bank AER. Users can change each premium and cash assumption. The 50% and zero-style-premium settings are sensitivity cases, not probabilities. The market premium is changed separately.

TER/12 is an additive small-cost approximation. It does not cover all tracking difference, withholding taxes, spreads, brokerage or personal taxes. Do not add an all-in tracking difference and also deduct its constituent fee. Legacy mode treats the saved histories as already net, uses their sample means and makes no additional fee deduction. Its fee field is descriptive and inherited.

## Covariance and shared holdings

In legacy mode, use Ledoit–Wolf covariance of the selected window of simple returns across the fixed eligible equity universe, then take the selected submatrix. Research mode estimates the joint covariance `K` of factors and fund residuals and maps it into fund space:

```
T = [B  I]
Sigma = T @ K @ T.T
```

This includes `B Ω B' + B C + C' B' + Ψ`, where `C = Cov(factors, residuals)`. Ridge residuals need not be orthogonal to factors; dropping those cross terms would be inconsistent. Ledoit–Wolf uses centred observations and its fitted shrinkage intensity. The app also compares with directly shrunk excess-return covariance over the same months. Research risk is conditional on deterministic assumed cash; stochastic cash-rate risk is not modelled.

Exact duplicate observation columns are collapsed before identity-target shrinkage and expanded afterwards. Otherwise shrinkage can give two copies of one return series artificial diversification. This does not establish that near-identical funds will remain identical in the future.

The full empirical residual covariance can already capture co-movement from shared holdings and omitted common drivers. **No separate overlap surcharge is added.** Legacy holding-key overlap is a diagnostic: sum the smaller positive equity weight at matching keys, excluding cash and unitemised residuals. It is neither an issuer count nor complete economic overlap. Names, share classes and ambiguous identifiers need review before making stronger claims.

ETF volatility contributions are `w_i (Sigma w)_i / portfolio_volatility`. They sum to total volatility and can be negative. The current app does not display a factor/residual attribution that discards or arbitrarily allocates cross terms.

## Efficient frontier

At each target, solve:

```
minimise    w' Sigma w
subject to  sum(w) = 1
            0 <= w_i <= fund_cap
            mean' w >= target
```

First solve the constrained global minimum-variance portfolio and a linear programme for the maximum feasible return. Solve 101 evenly spaced return targets between those endpoints. The last QP finds the minimum-variance portfolio among maximum-return portfolios. Equal-return or single-fund inputs can collapse the frontier to one point.

CVXPY uses OSQP with a CLARABEL fallback. Constraints and returns are recomputed from the returned weights. Tiny numerical negative weights are removed and the sum restored; feasibility is checked again. The acceptance tolerance is 1e-6 in weight/exposure and annualised return units. Materially asymmetric or indefinite covariance is rejected. Solver feasibility is a numerical check, not an investment validation.

The slider selects actual solved weights. Lines between points are visual guides, not additional optimised portfolios. No random portfolio trials, spline approximation or mixed-integer minimum-position rules are used. Individual ETF and reference markers are standalone holdings and can breach the portfolio's fund cap.

Country/industry constraints are not available in the interface yet. The optimiser accepts general linear exposure limits, but applying them requires reviewed classifications, issuer mapping and conservative treatment of unknown positions. Negative internal balances must not silently offset concentration. Leveraged/inverse funds require daily reset, financing and path-dependence modelling; credit and stable-income assets require appropriate rate/default drivers.

## Twenty-year illustration

The efficient frontier concerns the initial one-period portfolio. The optional wealth illustration holds ETF units fixed, so weights drift; it does not claim to find the optimal 20-year portfolio. There are no contributions, withdrawals, personal taxes or inflation adjustments.

Assume independent, identically distributed monthly return vectors with constant means and covariance. With `g_i = 1 + monthly_mean_i`, initial wealth `W` and `n` months:

```
E[wealth] = W * sum_i w_i * g_i**n
Var[wealth] = W**2 * sum_ij w_i*w_j * ((g_i*g_j + Sigma_ij)**n - g_i**n*g_j**n)
```

These are exact first two moments under those assumptions. The app moment-matches total wealth to a lognormal distribution for approximate P20, median and P80. A sum of ETF values is generally not lognormal. Fat tails, changing exposures, serial dependence and uncertainty in parameters are omitted. P20–P80 is a conditional 60% outcome band, not model confidence or a worst-case interval. Expected wealth and median wealth are different quantities.

## What is still required

1. Recover documented fund/index return exports, share-class identities, fee dates and currency conventions; prepare the small matching French, GBP cash and FX files.
2. Review calibration stability and out-of-sample evidence before relying on research results. The synthetic tests prove code behaviour, not that real returns are predictable.
3. For the intended holdings-characteristic model, obtain point-in-time size, book-to-market, operating-profitability and asset-growth observations with publication lags, matched returns, identifiers and delisting treatment. Current holdings alone cannot reconstruct historical exposures without look-ahead bias.
4. Fit and validate the pooled characteristics-to-exposures model. Partition common factor, sector/country and company-specific risk before using a structural holdings covariance term. Do not layer it on top of an empirical residual covariance that already contains that risk.

## References

- [French developed-market five factors](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html)
- [scikit-learn Ledoit–Wolf estimator](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html)
- [scikit-learn chronological splits](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [CVXPY quadratic programmes](https://www.cvxpy.org/examples/basic/quadratic_program.html)
