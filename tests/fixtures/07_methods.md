# Portfolio Construction Lab
## Methods — Version V8.0

**Document:** Scientific methodology and model disclosure  
**Product:** Portfolio Construction Lab  
**Reporting currency:** GBP  
**Research evidence cut-off:** 18 October 2026  
**Primary model:** Holdings-informed factor calibration  
**Alternative model:** ETF-return-calibrated factor model  
**Investment policy:** Set-and-forget buy-and-hold  

> This document specifies the methodology against which the deployed release must be validated. Numerical outputs, data coverage, optimiser certificates and performance results must be obtained from the active immutable release. A specification is not evidence that a calculation has been implemented or independently certified.

---

# Abstract

Portfolio Construction Lab is a quantitative investment research application designed to compare exchange-traded funds, exchange-traded products, bonds, commodities, leveraged instruments and interest-bearing cash within a single GBP-denominated portfolio framework.

Its central objective is to construct diversified portfolios using transparent expected-return assumptions, empirically calibrated risks and explicit product costs, while preserving the economic mechanics of the instruments actually held.

The application distinguishes two complementary approaches to equity modelling:

1. **Holdings model (`method="holdings"`):** Estimates fund exposures from the underlying companies, their financial characteristics and calibrated relationships with market and style-factor returns.
2. **ETF model (`method="etf"`):** Estimates factor exposures directly from observed fund and benchmark return histories, with appropriate regularisation, proxy treatment and validation.

Both models use the same instrument identities, non-equity mechanics, portfolio constraints, accounting conventions and reporting definitions. They are independent modelling approaches, not different versions of the application.

Portfolio Construction Lab uses a long-only mixed-integer mean–variance optimisation to construct an efficient frontier at 1,001 selector positions, with allocations recorded in integer basis points and a minimum positive allocation of 0.10%.

Long-horizon wealth is projected under a **buy-and-hold policy**, rather than assuming periodic portfolio rebalancing. Investor-owned fund units remain fixed after purchase. Dividends from distributing share classes enter a separate GBP interest-bearing cash account unless a different, explicitly labelled policy is selected.

The application is a research and planning tool. Its expected returns, frontier positions and probability bands are model outputs rather than guaranteed investment outcomes.

---

# 1. Scope and Investable Universe

## 1.1 Instrument coverage

The V8.0 reconciled candidate universe comprises **68 fund/share-class identities**, assembled from the earlier V4 and V7 instrument registries.

The final admitted release universe is established through identity verification, deduplication and data-contract validation. Consequently, 68 is the reconciled design-universe count, not a claim that every instrument has already passed production admission.

Six top-level asset categories govern portfolio selection:

| Category | Economic contents |
|---|---|
| Savings | GBP interest-bearing cash |
| Commodities | Physical precious-metal ETCs and collateralised commodity-futures products |
| Bonds | Sovereign, inflation-linked, investment-grade, high-yield and emerging-market fixed income |
| Broad equity | Diversified geographical and market-capitalisation equity funds |
| Factor equity | Funds with value, size, quality, profitability, investment, momentum or other systematic tilts |
| Leveraged | Daily-reset leveraged equity ETFs and ETPs |

The instrument registry retains actual share-class and product distinctions. Related listings are not counted as independent investments merely because they trade under different tickers.

The registry must support additional verified instruments without requiring mathematical changes to the model.

## 1.2 Instrument identity

A fund's legal share class is primarily identified by its ISIN. An exchange listing additionally requires:

- ISIN or synthetic stable ID;
- exchange and market identifier code (MIC);
- trading ticker;
- quotation currency;
- quotation unit;
- share-class distribution treatment;
- relevant currency-hedging treatment;
- source and effective dates.

A ticker alone is insufficient to identify a financial product.

The internal cash identity is `cash:T212_GBP_CASH`. It has no ISIN and no exchange ticker.

The normal user-facing ticker for the US small-cap value instrument is `USSC`; alternate exchange tickers are preserved for matching and provenance.

Likewise, Stream C establishes important commodity listing aliases:

| Source alias | Preferred sterling listing | Quote unit |
|---|---|---|
| COPA | COPB | GBx |
| AIGA | AGAP | GBx |
| CRUD | CRUP | GBx |
| CMOP | CMOP | GBx |
| SGLN | SGLN | GBx |
| SSLN | SSLN | GBx |

The source alias and preferred listing can be associated through verified product identity. They must not produce two independent portfolio holdings.

## 1.3 GBP and GBx normalisation

All portfolio calculations and presented financial metrics use nominal pounds sterling.

A London listing quoted in **GBx** or **GBp** is priced in pence. It is converted into GBP exactly once:

\[
P_t^{GBP}=0.01P_t^{GBx}.
\]

A listing quoted in GBP requires no pence conversion.

For an instrument priced in another currency \(C\), let \(X_t^{GBP/C}\) represent GBP per unit of \(C\):

\[
P_t^{GBP}=P_t^C X_t^{GBP/C}.
\]

The GBP return is then:

\[
1+R_t^{GBP}
=
(1+R_t^C)(1+R_t^{FX}).
\]

For distributing products, the relevant total-return calculation must additionally account for distributions.

**A GBP exchange quotation does not imply that the economic exposure is GBP-hedged.** In particular, the preferred sterling listings of IBTS, IBTM, IBTL, VEMT and the commodity ETCs can retain foreign-currency exposure.

Currency conversion is applied after identifying the correct contractual return and currency basis. A product must not receive multiple FX conversions merely because its benchmark, NAV and trading line use different currencies.

## 1.4 Historical return classifications

Every historical return observation must be classified as one of:

- **Observed fund return:** Derived from verified actual fund NAV, distributions and, where applicable, GBP conversion.
- **Observed benchmark return:** Derived from an identified benchmark with its documented return convention.
- **Benchmark proxy:** Constructed from a documented benchmark, adjusted for the appropriate product mechanics and costs.
- **Factor proxy:** Reconstructed from realised regional market and factor histories with explicit exposure and residual-risk assumptions.
- **Scenario or prior:** Assumed rather than historically observed.

For distributing funds, ex-distribution NAV price returns must not be silently substituted for total returns.

Historical net fund returns already incorporate actual recurring product expenses and relevant realised implementation effects. These costs are not deducted a second time.

No proxy observation is labelled as observed fund history. Pre-inception extensions retain their proxy classification and the source period to which they belong.

---

# 2. Dual-Model Architecture

## 2.1 Shared model interface

The application retains a small, stable `prepare_model()` entry point.

The intended public contract is:

`prepare_model(method="holdings", release_id=..., settings=...)`

or:

`prepare_model(method="etf", release_id=..., settings=...)`

Both adapters return an identical universe ordering and compatible outputs, including:

- Monthly net expected simple returns;
- Monthly covariance matrix;
- Annual display-return and volatility fields;
- Product cost components;
- Factor or carry attribution;
- Instrument and holdings coverage;
- Source dates and provenance;
- Projection log-return inputs;
- Benchmark recipes;
- Quality diagnostics and model-release identifiers.

Common adapters provide the bond, commodity, cash and leveraged-product mechanics for both equity-model choices.

Only the mechanism for deriving equity exposures differs.

Switching methods must load corresponding model moments, frontier allocations, diagnostics and assumptions from the same coherent release family.

The application never averages the two methods together without a separately specified ensemble model.

## 2.2 Holdings-informed company model

### Economic look-through

Let:

\[
H_{ic}
\]

be fund \(i\)'s economic exposure to company \(c\), expressed relative to the fund's NAV.

For unleveraged physical equity funds, the sum of economic company weights normally approximates the equity allocation after cash and other residual assets.

For leveraged funds, economic exposure can exceed NAV. Synthetic product collateral must not be confused with exposure to the tracked equity index.

The system is designed for approximately **15,000 distinct underlying securities**. This is a capacity objective; the actual observed count depends on source data.

Different security lines can belong to the same economic company. A verified company-identity map consolidates multiple share classes, ADRs and duplicated securities across funds.

Name matching alone is not adequate evidence for consolidation.

Company coverage, mapped economic exposure and directly sourced financial-characteristic coverage are reported separately.

### Fundamental characteristics

The holdings model uses dated company information to estimate systematic exposures.

Relevant characteristics include:

| Characteristic | Illustrative measurement |
|---|---|
| Size | Market capitalisation, commonly log-scaled |
| Value | Book equity divided by market equity |
| Profitability | Operating profitability relative to book equity |
| Investment | Growth in total assets |
| Momentum | Prior cumulative return excluding the most recent month |

Accounting conventions follow the relevant Fama–French factor definitions where applicable.

For example, the momentum signal is based on the historical months 2–12 convention and therefore requires a properly dated price history.

Financial institutions, negative book equity, near-zero denominators, unavailable statements and cross-country accounting differences require explicit treatment.

A missing characteristic is not automatically assigned zero exposure.

### Calibration

Company fundamentals do not determine precise factor betas by themselves.

Let the estimated factor exposure of company \(c\) to factor \(k\) be:

\[
\widehat{\beta}_{ck}
=
f_k(X_c;\widehat{\theta}),
\]

where \(X_c\) is the company's dated characteristic vector and \(\widehat{\theta}\) represents parameters estimated using historical market or factor evidence.

The preferred calibration approach is:

1. Estimate security return exposures to regionally appropriate market/style factors where sufficient valid histories exist.
2. Estimate a regularised mapping between dated characteristics and those exposures.
3. Test the relationship out of sample, accounting for information availability.
4. Apply the mapping to present-day holdings.
5. Shrink uncertain estimates towards justified regional or peer-group priors.

Where security-level histories are insufficient, regional characteristic-sorted portfolio histories may supply calibrated exposure anchors.

This fallback is documented as an approximation rather than presented as exact company-level beta estimation.

Characteristics and betas must be calibrated jointly where possible. Independently attaching five arbitrary factor scores does not establish a coherent five-factor model.

### Fund-level aggregation

The estimated fund exposure to factor \(k\) is:

\[
\widehat{\beta}_{ik}
=
\sum_c H_{ic}\widehat{\beta}_{ck}
+
\beta_{ik}^{unmapped}.
\]

The final term represents the documented treatment of unmapped economic exposure. It is not an unexplained positive factor premium.

Fund characteristics and expected-return attribution are compared against compatible regional broad-market reference exposures.

### Data coverage

The initial release-admission policy targets:

- At least 95% mapped economic equity exposure for concentration reporting;
- At least 80% directly sourced weighted characteristic coverage before presenting a fund's characteristics as predominantly company-modelled.

These are engineering policy thresholds, not statistical constants.

When thresholds are missed, the model retains explicitly labelled proxy or prior treatment and reports the affected economic weight.

The underlying holdings page may display partial available exposure even if a fund is insufficiently covered for a reliable complete company-count statistic.

## 2.3 ETF-return-calibrated model

The alternative model estimates fund exposures directly from observed ETF returns.

For an unlevered equity fund \(i\), a regional factor regression may be represented as:

\[
R_{i,t}^{excess}
=
\alpha_i
+
\beta_{i,M}MKT_t
+
\beta_{i,S}SMB_t
+
\beta_{i,V}HML_t
+
\beta_{i,P}RMW_t
+
\beta_{i,I}CMA_t
+
\beta_{i,U}UMD_t
+
\varepsilon_{i,t}.
\]

The implemented factor set may differ by region and available evidence.

Regression inputs must be aligned to the correct currencies, return frequencies, benchmark definitions and dates.

Regularisation, robust estimation, short-history proxies and residual-risk floors prevent unstable coefficients from being treated as precise forecasts.

**Historical regression alpha is not assumed to be persistent future investment skill.**

The ETF model applies the same forward factor-premium assumptions, cost accounting and non-equity product mechanics as the holdings model.

It is therefore a methodological alternative to holdings-driven exposure estimation rather than a licence to extrapolate historical ETF returns without adjustment.

## 2.4 Matched-model validation

Model comparisons initially use:

- The same instrument universe;
- The same regional benchmark definitions;
- The same factor premium assumptions;
- The same fee and financing rules;
- The same historical source periods where feasible;
- The same common covariance matrix for controlled expected-return comparison.

Native covariance estimates may subsequently be compared separately.

Differences are attributed to exposure estimates, risk models or source coverage rather than conflated into a single unexplained performance difference.

Relevant validation statistics include exposure stability, held-out return prediction errors, uncertainty calibration, risk reconstruction and fund-level tracking residuals.

Where a model's prerequisites are missing, the application reports the missing dependency rather than silently switching methods.

---

# 3. Expected Returns and Factor Attribution

## 3.1 Forecasting convention

The optimiser uses annualised arithmetic expected returns derived consistently from monthly model moments.

For monthly simple-return expectation \(\mu_i\):

\[
\mu_{i,\mathrm{annual,arith}}=12\mu_i.
\]

The corresponding monthly covariance \(\Sigma\) gives annualised portfolio volatility:

\[
\sigma_{p,\mathrm{annual}}
=
\sqrt{12w^\top\Sigma w}.
\]

An annualised arithmetic mean is not the same as a projected compound annual growth rate.

The latter depends on the sequence and distribution of returns.

## 3.2 Equity expected-return decomposition

For unleveraged equity fund \(i\):

\[
\begin{aligned}
E[R_i^{GBP}] \approx {}&
R_{i,\mathrm{market\ base}} \\
&+\sum_k
\left(
\beta_{ik}-\beta_{B(i),k}
\right)\lambda_k\\
&-f_{i,\mathrm{wrapper}}
-c_{i,\mathrm{other}},
\end{aligned}
\]

where:

- \(B(i)\) is the relevant regional broad-market reference;
- \(\lambda_k\) is the forward expected premium for factor \(k\);
- \(\beta_{ik}\) is the estimated fund exposure;
- \(\beta_{B(i),k}\) is the comparable benchmark exposure;
- \(f_{i,\mathrm{wrapper}}\) is the applicable fund expense;
- \(c_{i,\mathrm{other}}\) includes distinct forecast costs not already incorporated elsewhere.

The market base and relative factor effects must be constructed on compatible return conventions.

This avoids counting a factor premium both inside the market baseline and as an additional fund-specific contribution.

Supported style factors include size, value, profitability, investment and momentum. Estimated factor contributions may be positive, zero or negative.

A fund is not assigned a favourable premium simply because its marketing name contains a particular style.

The allocation table reconciles:

**Market base + signed factor contributions − TER − other costs = net expected return.**

For bonds, commodities and cash, inappropriate equity factor columns remain not applicable rather than displaying misleading synthetic zero values.

## 3.3 Cost reconciliation

The cost engine distinguishes:

1. Fund wrapper OCF/TER or management fee;
2. Embedded underlying-fund fees;
3. Financing or borrowing expenses;
4. Swap-related fees and implementation spreads;
5. Currency-hedging implementation costs;
6. Transaction costs and bid–ask spread assumptions, where explicitly modelled.

Historical fund NAV total returns normally reflect the expenses already charged within the vehicle.

A gross index used as a forecast starting point requires appropriate fee deductions.

A net ETF historical return must not receive the same fee deduction again.

PRIIPs aggregate cost disclosures may combine ongoing charges, financing and transactions. They cannot automatically be added to a separately decomposed cost model.

Every cost has a provenance, inclusion flag, unit, effective date and charging basis.

---

# 4. Leveraged ETF and ETP Mechanics

## 4.1 Included products

The four specified daily-reset leveraged instruments are:

| Ticker | Product identity | ISIN | Target daily leverage |
|---|---|---|---|
| XS2D | Xtrackers S&P 500 2x Leveraged Daily Swap UCITS ETF | LU0411078552 | +2x |
| LQQ | Amundi Nasdaq-100 Daily (2x) Leveraged UCITS ETF | FR0010342592 | +2x |
| 3LUS | WisdomTree S&P 500 3x Daily Leveraged | IE00B7Y34M31 | +3x |
| 3QQQ | Leverage Shares 3x Long US Tech 100 ETP | XS2472197065 | +3x |

The 3QQQ product in this model is the Leverage Shares ETP, not a different issuer's similarly named 3x Nasdaq product.

## 4.2 Daily-reset returns

A leveraged fund attempts to deliver a multiple of its reference exposure over its specified daily reset period.

For a simple leveraged-long construction, a first-order native-currency return approximation is:

\[
R_{L,d}^{native}
\approx
L R_{U,d}^{native}
-
(L-1)(r_{ref,d}+s_{i,d})\delta_d
-
f_{i,d}
-
c_{i,d}^{other}.
\]

Here:

- \(L\) is target daily leverage;
- \(R_{U,d}\) is the appropriate underlying daily return;
- \(L-1\) is the simple long-product borrowed-notional multiple;
- \(r_{ref,d}\) is the relevant financing reference rate;
- \(s_{i,d}\) is the applicable spread;
- \(\delta_d\) is the contract-specific accrual fraction;
- fees and other implementation effects are deducted once.

The actual implementation must respect the issuer's financing basis, intraday reset provisions, underlying exposure and benchmark conventions.

This equation is not a universal formula for every leveraged product.

A product tracking an already financed, leveraged index cannot have its financing or leverage applied a second time.

For an underlying ETF such as QQQ, observed net QQQ returns already incorporate QQQ's ongoing expense.

## 4.3 Daily compounding and volatility decay

With no additional costs and a constant daily leverage target:

\[
\frac{V_T}{V_0}
=
\prod_{d=1}^{T}
\left(1+L R_{U,d}\right).
\]

This is generally different from:

\[
1+L\left(\frac{U_T}{U_0}-1\right).
\]

For example, a +10% followed by −10% underlying return produces:

- Unlevered: \(1.10\times0.90=0.99\), or −1%;
- Ideal daily 2x: \(1.20\times0.80=0.96\), or −4%;
- Ideal daily 3x: \(1.30\times0.70=0.91\), or −9%.

All figures exclude expenses.

For an illustrative continuous-time underlying with annual arithmetic drift \(\mu\), volatility \(\sigma\) and constant cost rate \(c\), the leveraged product's expected logarithmic growth is approximately:

\[
g_L
=
L\mu-\frac{1}{2}L^2\sigma^2-c.
\]

Equivalently, relative to the underlying logarithmic growth \(g_U=\mu-\sigma^2/2\):

\[
g_L
=
Lg_U
-\frac12L(L-1)\sigma^2-c.
\]

The term:

\[
\frac12L(L-1)\sigma^2
\]

describes the additional volatility drag relative to leveraged underlying log growth.

This is a continuous-time diagnostic under simplifying assumptions. Actual daily product results are path-dependent and affected by resets, financing, fees, tracking behaviour and gap events.

Volatility drag must not be deducted again as a separate fee if it is already represented by daily compounding.

## 4.4 Contract-specific handling

### XS2D

XS2D uses a synthetic daily 2x S&P 500 exposure.

The Stage 02 mechanics report records a 0.60% annual wrapper fee and a daily funding model based on USD overnight financing.

An unverified additional OTC implementation spread is represented by an explicitly provisional 2.00% annual assumption on the applicable borrowed notional, tested at 1.00% and 3.00%.

These spread assumptions are not issuer-verified terms.

### LQQ

LQQ uses synthetic daily 2x Nasdaq-100 exposure.

The Stage 02 report records 0.60% ongoing charges, with the issuer portal verified but a linked PDF unavailable during the audit.

The USD underlying and EUR listing/NAV context require consistent contractual currency accounting.

The additional OTC spread remains provisional under the 1.00%/2.00%/3.00% sensitivity framework.

### 3LUS

3LUS is a WisdomTree collateralised-swap daily 3x S&P 500 product.

Stage 02 records:

- 0.75% management fee;
- A 1.0020% funding spread effective 1 October 2026, reduced from 1.2450%;
- A 20% underlying intraday-drop restrike trigger;
- A separately identified 25% overnight threshold indicator.

These terms are dated and subject to the binding product conditions.

The relevant intraday and overnight mechanisms cannot be reconstructed precisely from daily closing prices alone.

### 3QQQ

3QQQ is the Leverage Shares physical-margin product referencing Invesco QQQ.

Stage 02 records:

- 3x QQQ exposure;
- Borrowed notional of approximately 2x product NAV;
- USD reference funding plus a stated 2.00% margin spread;
- 0.75% wrapper management fee;
- QQQ's 0.20% embedded expense, accounted for consistently with the gross/net return starting point;
- An intraday airbag threshold corresponding to approximately a 16.67% underlying fall.

The source-reported KID aggregate daily cost is not added on top of the independently decomposed wrapper, underlying and financing costs.

## 4.5 FX and loss barriers

Daily leverage operates on the contractual underlying/product exposure.

After the native product return has been calculated, the product's return is translated into GBP once using the appropriate currency conversion.

Foreign-exchange movements are not multiplied by 2x or 3x merely because the equity exposure is leveraged.

Products with limited-liability NAV cannot have a negative investor NAV.

Where a product suffers a full wipeout:

\[
V_{d}=0
\quad\Rightarrow\quad
V_{d+k}=0,\quad k>0.
\]

A later positive underlying-market return does not revive a zero-value position.

If the issuer makes a mandatory redemption with a positive cash settlement, the actual proceeds enter the investor's GBP cash account.

No automatic reinvestment into surviving funds occurs.

## 4.6 Leveraged risk disclosure

Long-horizon results for leveraged products are conditional model approximations.

Observed product histories may incorporate actual past daily resets. Forward daily-close reconstructions may not reproduce intraday restrikes, extreme gaps, suspended trading, counterparty events or issuer termination mechanisms.

The application therefore separates:

- Observed product returns;
- Contract-based daily return proxies;
- Assumed forward financing conditions;
- Explicit crash, funding and reset stress tests.

The uncertainty bands do not represent issuer-guaranteed outcomes or a complete probability model of product termination.

No universal long-term 2x or 3x return multiplier is used.

---

# 5. Bonds: Carry, Duration, Credit and Currency

## 5.1 Bond return decomposition

Bond expected returns are based on an explicit approximation to prospective carry, financing/hedging effects and expected credit loss.

For a conventional nominal bond fund:

\[
E[R_j^{GBP}]
\approx
y_j^{base}
+h_j^{GBP}
+E[\Delta FX_j]
-\ell_j^{credit}
-f_j^{fund}
-c_j^{other}.
\]

The currency terms apply only as appropriate: GBP-domestic bonds have no foreign-currency conversion, unhedged overseas bonds remain FX-sensitive, and currency-hedged funds require a consistent treatment of forward carry.

The starting yield can be yield-to-maturity (YTM) or yield-to-worst (YTW) according to the instrument and its underlying holdings.

**Published portfolio yields are not realised future total returns.**

Returns can deviate because of yield-curve changes, spread changes, issuer defaults, prepayments, convexity, index turnover, inflation and currency changes.

## 5.2 Verified issuer measurements

Stream C recovered the following dated issuer observations.

| Fund | Published yield (%) | Duration (years) | Measurement date |
|---|---:|---:|---|
| IGLS | 4.62 YTM | 2.14 effective | 15 Oct 2026 |
| IGLT | 5.13 YTM | 7.01 effective | 15 Oct 2026 |
| GLTL | 5.77 YTM | 15.01 effective | 15 Oct 2026 |
| INXG | 1.87 real yield | 12.65 effective | 15 Oct 2026 |
| IS15 | 5.58 YTM | 2.39 effective | 15 Oct 2026 |
| SLXX | 6.11 YTM | 5.42 effective | 15 Oct 2026 |
| VAGS | 4.83 underlying YTW | 6.00 average | 30 Sep 2026 |
| IBTS | 4.75 YTM | 1.81 effective | 15 Oct 2026 |
| IBTM | 5.07 YTM | 6.85 effective | 15 Oct 2026 |
| IBTL | 5.48 YTM | 14.83 effective | 15 Oct 2026 |
| ITPG | 2.81 real yield | 6.40 effective | 15 Oct 2026 |
| GHYS | 7.46 YTM | 3.12 effective | 15 Oct 2026 |
| VEMT | 6.80 effective YTM | 5.90 average | 30 Sep 2026 |

Yields are percentage figures as published, not decimal return inputs or forecasts.

VAGS and VEMT publish an **Average Duration** measure. Its exact equivalence to effective or option-adjusted duration was not established during the audit. The original label is preserved.

VAGS 4.83% is an underlying local-currency YTW, not a verified net-GBP hedged return.

GHYS 7.46% is an underlying published YTM. Its precise treatment of FX-forward carry has not been explicitly documented by the issuer.

The ITPG real yield is likewise not a verified net-GBP nominal return.

These limitations must be respected before constructing a forward GBP estimate.

## 5.3 Duration and convexity

Effective duration is a sensitivity measure, not additional annual income.

For a small parallel yield change:

\[
\frac{\Delta P}{P}
\approx
-D_{\mathrm{eff}}\Delta y
+\frac12 C(\Delta y)^2,
\]

where \(C\) denotes the relevant convexity measure.

Duration estimates are applied under their published or independently validated convention.

For example, a duration of 7 years implies an approximate 7% price decline for a +100-basis-point parallel yield shock before convexity and other effects.

This is a local sensitivity approximation, not an exact prediction.

## 5.4 Inflation-linked bonds

INXG holds UK RPI-linked gilts. ITPG holds US TIPS linked to US CPI-U.

Their real-yield and inflation assumptions must remain distinct.

For an inflation-linked instrument:

\[
1+y_{\mathrm{nominal}}
\approx
(1+y_{\mathrm{real}})(1+\pi_{\mathrm{assumed}}).
\]

Consequently:

\[
y_{\mathrm{nominal}}
\approx
y_{\mathrm{real}}
+\pi_{\mathrm{assumed}}
+y_{\mathrm{real}}\pi_{\mathrm{assumed}}.
\]

The V8.0 planning inflation assumption is 2.00%, with 1.00%, 3.00% and 4.00% sensitivity cases.

It is a modelling assumption rather than an observed market-implied inflation rate.

INXG's separately published nominal YTM of 5.42% and ITPG's separately published nominal YTM of 4.97% must not receive a second assumed inflation uplift.

For ITPG, GBP currency hedging does not replace the US inflation index with UK inflation.

Inflation indexation lags, real-rate changes and fund expenses require their own treatment.

## 5.5 Expected credit loss

Expected credit loss is a modelling input, distinct from a published yield or rating.

A general representation is:

\[
\ell_j
=
\sum_b
\omega_{jb}
\,PD_b\,LGD_b,
\]

where:

- \(\omega_{jb}\) is the exposure to credit bucket \(b\);
- \(PD_b\) is the assumed annual default probability;
- \(LGD_b\) is the assumed loss given default.

Where properly sourced probabilities and recovery assumptions are unavailable, V8.0 uses explicitly disclosed scenario haircuts rather than invented issuer-level default probabilities.

Initial assumptions are:

| Exposure category | Annual expected-loss assumption | Sensitivity |
|---|---:|---|
| Developed sovereign | 0.00% central planning haircut | Separate sovereign stress |
| Investment-grade corporate | 0.20% | 0.10%–0.40% |
| Global high-yield corporate | 2.00% | 1.00%–4.00% |
| Emerging-market sovereign | 0.75% | 0.375%–1.50% |
| Global aggregate IG | 0.05% simplified planning haircut | 0.025%–0.10% |

These are scenario heuristics, not empirical default forecasts.

Rating classifications and issuer categories must not be collapsed into a single mutually exclusive set.

For example, VEMT's below-investment-grade rating share is part of its emerging-market sovereign exposure, not an additional independent asset class.

Likewise, rated high-yield, unrated, cash, derivatives and already defaulted exposures remain separate where published.

No universal investment-grade loss haircut is applied again to a sovereign holding already classified under a sovereign-specific treatment.

## 5.6 Currency-hedging limitations

VAGS, GHYS and ITPG have GBP-hedged share-class exposure.

Hedging reduces targeted foreign-currency exposure but does not eliminate all tracking error, credit risk, interest-rate risk or implementation differences.

Published underlying yields may exclude realised or future forward-currency carry.

Currency-hedged forecast construction must establish:

1. The local-currency yield basis;
2. The underlying currency exposure weights;
3. The hedging instrument and currency-forward convention;
4. The date and annualisation of hedging assumptions;
5. Which implementation costs or hedge effects are already included.

When these cannot be verified, the model displays an assumption-qualified estimate or N/A rather than a falsely precise issuer-verified GBP carry figure.

---

# 6. Commodities and Collateral Mechanics

## 6.1 Physical precious metals

The physical precious-metal products are:

| Instrument | Exposure | Published annual TER |
|---|---|---:|
| SGLN | Physical gold | 0.12% |
| SSLN | Physical silver | 0.20% |

These are physically backed ETCs, not equity UCITS ETFs and not collateralised commodity-futures indices.

They have no ordinary bond YTM, contractual coupon or US Treasury-bill collateral return.

For planning purposes:

\[
E[R_{\mathrm{metal}}^{GBP}]
\approx
\pi_{\mathrm{assumed}}
+
g_{\mathrm{real,assumed}}
-
TER
+
E[\Delta FX]
\]

under a consistently specified sterling exposure convention.

The baseline real metal growth assumption is 0.00%, with 2.00% nominal inflation in the reference scenario and a separately disclosed fee.

Test nominal zero growth and ±5-percentage-point nominal-growth variations.

These assumptions are not forecasts published by iShares.

Physical backing reduces certain futures-roll exposures, but does not remove metal-price, FX, issuer, custody or trading risks.

## 6.2 Commodity futures products

The futures-based products require their benchmark's precise total-return and collateral convention.

| Product | Index reference | Collateral reference | Annual charges |
|---|---|---|---|
| CMOP | Bloomberg Commodity Index Total Return (BCOMTR) | 13-week US Treasury bills | 0.19% ongoing + 0.15% swap |
| COPA/COPB | Bloomberg Commodity Copper Subindex 4W Total Return (BCOMHG4T) | 4-week US Treasury bills | 0.49% MER + 0.45% swap |
| AIGA/AGAP | Bloomberg Commodity Agriculture Subindex 4W Total Return (BCOMAG4T) | 4-week US Treasury bills | 0.49% MER + 0.45% swap |
| CRUD/CRUP | Bloomberg WTI Crude Oil Multi-Tenor 4W Total Return (BCLMT4T) | 4-week US Treasury bills | 0.49% MER + 0.45% swap |

For a gross total-return index:

\[
R_{\mathrm{futures,TR}}
=
R_{\mathrm{futures,ER}}
+
R_{\mathrm{collateral}}
+
\text{compounding interactions}.
\]

This identity is applied at the appropriate index-return frequency, not as a guarantee that simple annual percentages add exactly.

The futures excess-return component incorporates the relevant contract-price and roll effects.

A total-return benchmark already includes its specified collateral return.

The underlying swap collateral securities are not necessarily the source of the index's T-bill accrual.

Do not add cash collateral income again to an existing total-return benchmark.

## 6.3 Roll and curve assumptions

Contango, backwardation and maturity selection affect futures-index performance.

CRUD's specified multi-tenor methodology differs from a continuous front-month oil price.

A spot commodity price cannot be substituted for the total return on a rolling futures strategy.

The planning expected futures excess-return premium is:

\[
E[R_{\mathrm{futures,ER}}]=0
\]

until a defensible source-based estimate has been established.

Therefore the provisional expected-return model is:

\[
E[R_{\mathrm{commodity}}]
\approx
E[R_{\mathrm{collateral}}]
-
f_{\mathrm{wrapper}}
-
f_{\mathrm{swap}}
+
E[\Delta FX],
\]

subject to the appropriate benchmark and FX conventions.

This is a conservative scenario, not a claim that actual futures roll yield is always zero.

For CMOP, the sum of published annual charges is 0.34%. For the three WisdomTree ETCs, it is 0.94%.

These sums are calculations, not necessarily the issuers' own single quoted TER measures.

## 6.4 Treasury-bill calculation

The collateral index methodology determines which observed bill statistic applies:

- The specified 13-week auction-rate convention for BCOMTR;
- The specified 4-week weekly bill discount-rate convention for the 4W indices.

A bill discount quote is not automatically a directly compounding annual investment yield.

Conversion must respect the original price/discount convention, remaining maturity and day-count basis.

Without verified daily source observations and calculation terms, a daily collateral series must not be reconstructed using arbitrary constant yields.

The exact WisdomTree annual swap-rate daily accrual divisor remains unverified in Stream C and is a release input requiring further evidence.

---

# 7. GBP Cash Instrument

## 7.1 Identity and observed interest rate

The cash instrument is:

`cash:T212_GBP_CASH`

It represents Trading 212 GBP interest-bearing uninvested cash in an **Invest** account, not a listed ETF or an assumed bank savings deposit.

Stream C independently verified an advertised:

**3.80% GBP AER — observed 18 October 2026.**

The earlier Stage 02 mechanics resource contains a 3.85% observation. The more recent Stream C audit is the controlling evidence snapshot for this document.

The V8.0 **4.25% AER** is preserved as a separate planning scenario.

It is not represented as Trading 212's current verified rate.

## 7.2 Compound-rate calculation

For a constant annual equivalent rate \(r_{AER}\), a monthly illustrative rate is:

\[
r_m=(1+r_{AER})^{1/12}-1.
\]

Under a constant cash-rate scenario:

\[
W_t
=
W_0(1+r_{AER})^{t/12}.
\]

This is deterministic conditional on the assumed unchanged rate.

The 3.80% and 4.25% values must never be combined or silently substituted.

V8.0 tests ±1- and ±2-percentage-point cash-rate sensitivities.

A variable published account rate is not a guaranteed 20-year forward rate.

## 7.3 Operational and counterparty qualifications

Trading 212's published mechanics include daily interest calculation and payment. The audit records:

- Interest calculation based on qualifying free cash at 22:00 GMT;
- Typical interest distribution between 01:00 and 02:00 GMT;
- A published daily AER-derived calculation convention;
- Rounding and residual carry-forward at the provider level.

These operational mechanics are distinct from the monthly analytical investment projection.

The cash facility may involve qualifying money-market funds, time deposits and bank accounts, subject to account configuration and applicable permissions.

A qualifying money-market fund is not identical to a protected bank deposit.

The public audit did not establish an individual customer's account allocation, protection eligibility or historical interest-rate series.

The account's authenticated displayed information is authoritative for the individual implementation.

Do not use the Invest rate as a substitute for a separately advertised Cash ISA or SIPP rate.

## 7.4 Deterministic covariance treatment

Under the constant-rate analytical scenario:

\[
\sigma_{\mathrm{cash}}^2=0,
\]

and:

\[
\operatorname{Cov}
(R_{\mathrm{cash}},R_i)=0.
\]

This is a model convention, not an empirical finding that the interest rate can never change.

Pearson correlation is mathematically undefined for a zero-variance cash series.

For the interface, the cash diversification score may be displayed as 100 by explicit convention, accompanied by the explanation that it represents a deterministic nominal-rate scenario rather than measured correlation.

---

# 8. Covariance and Risk Estimation

## 8.1 Joint monthly return covariance

All included asset classes contribute to a coherent monthly GBP total-return covariance matrix:

\[
\Sigma
=
\operatorname{Cov}(\mathbf{R}_t).
\]

The matrix must include cross-asset correlations between:

- Broad and factor equity;
- Sovereign and corporate bonds;
- Commodity exposures;
- Leveraged products;
- The remaining stochastic fund universe.

The cash row and column retain structural zeros in the conditional deterministic cash scenario.

## 8.2 Covariance calibration

The default risk estimate combines harmonised observed or documented proxy return histories with shrinkage.

Candidate shrinkage estimators include Ledoit–Wolf and Oracle Approximating Shrinkage, selected subject to appropriate data assumptions and validation.

Where sample coverage is insufficient, the engine may use factor-informed covariance estimates and conservative residual floors.

Shorter observed histories are never quietly represented as longer histories.

The general shrinkage estimator is:

\[
\widehat{\Sigma}
=
(1-\delta)S+\delta F,
\]

where:

- \(S\) is the empirical covariance;
- \(F\) is a structured target;
- \(\delta\) is the calibrated shrinkage intensity.

All matrices must use consistent frequency, currency and return conventions.

## 8.3 Positive-semidefinite validation

The optimiser requires:

\[
\Sigma=\Sigma^\top
\quad\text{and}\quad
\Sigma\succeq0.
\]

A small numerical repair may be applied to the stochastic covariance block using eigenvalue adjustment and diagonal-preserving rescaling.

Repair diagnostics record:

- Minimum eigenvalue before repair;
- Repair magnitude;
- Maximum elementwise adjustment;
- Matrix condition number.

A material PSD repair triggers investigation. It is not silently treated as evidence that the original covariance estimates were reliable.

Deterministic cash variances and covariances remain zero after repair.

## 8.4 Holdings-scale computation

The main look-through system uses a sparse fund-by-security/company exposure matrix.

A factor-plus-residual representation avoids constructing a dense 15,000 × 15,000 company covariance matrix in the interactive viewer.

An optional dense research calculation may be performed offline after memory preflight, with comparison against the default factor representation.

Data precision is selected by validated numerical error rather than by a universal float64 policy:

- Exact integer basis-point allocations;
- Compact validated IDs and category flags;
- Float32 candidate storage for large holdings and factor blocks;
- Float64 for sensitive covariance, optimisation and accumulated long-horizon calculations.

This is a computational design choice, not a relaxation of the financial accounting requirements.

---

# 9. Efficient Frontier Optimisation

## 9.1 Objective and feasible universe

For active fund weights \(w\), monthly expected returns \(\mu\), and monthly covariance \(\Sigma\):

\[
E[R_p]=\mu^\top w
\]

and:

\[
\sigma_p^2=w^\top\Sigma w.
\]

The default objective minimises variance subject to a target expected return and investment constraints.

All fund holdings are long-only, and total initial capital must be fully allocated.

Category selection creates a feasible universe of available products.

The six category switches generate 64 possible masks, one of which is empty.

There are 63 non-empty feasible-category masks before model-specific or data-admission restrictions.

## 9.2 Integer basis-point optimisation

The decision variable is the exact integer allocation:

\[
q_i\in\mathbb Z_{\ge0}
\]

with:

\[
w_i=\frac{q_i}{10,000}.
\]

A fully allocated portfolio satisfies:

\[
\sum_i q_i=10,000.
\]

Let \(z_i\in\{0,1\}\) indicate whether fund \(i\) is held.

The minimum positive investment constraint is:

\[
10z_i\le q_i\le10,000z_i.
\]

Thus each holding has either:

\[
w_i=0
\]

or:

\[
w_i\ge0.001
\]

equivalent to **0.10% of initial capital**.

Disabled-category instruments must have zero allocation.

No general per-fund, equity-sleeve or gross-notional cap is imposed in the default user-facing optimisation.

An enabled single fund may constitute 100% of a portfolio.

## 9.3 MIQP formulation

For target monthly expected return \(\tau_k\):

\[
\begin{aligned}
\min_{q,z}\quad&
\frac{1}{10,000^2}q^\top\Sigma q\\
\text{subject to}\quad&
\mathbf1^\top q=10,000,\\
&\mu^\top q\ge10,000\tau_k,\\
&10z_i\le q_i\le10,000z_i,\\
&q_i=0\quad\text{for disabled funds},\\
&q_i\in\mathbb Z_{\ge0},\quad z_i\in\{0,1\}.
\end{aligned}
\]

The offline solver selected for the production method is **SCIP**, using a compatible mixed-integer quadratic optimisation interface.

Continuous quadratic-programming relaxations provide lower bounds and candidate warm starts.

A heuristic rounded solution is not automatically a certified MIQP solution.

## 9.4 Exactly 1,001 frontier positions

The frontier selector is defined by:

\[
k\in\{0,1,\ldots,1000\}.
\]

The displayed position is:

\[
p_k=\frac{k}{10},
\]

so the positions are:

0.0, 0.1, 0.2, ..., 100.0.

The grid interpolates the **target expected return** between:

- The global minimum-variance portfolio;
- The maximum-expected-return feasible portfolio.

For endpoint expected returns \(\mu_{\min var}\) and \(\mu_{\max}\):

\[
\tau_k
=
\mu_{\min var}
+
\frac{k}{1000}
(\mu_{\max}-\mu_{\min var}).
\]

The selector is not a volatility percentage, equity percentage or allocation percentage.

Distinct target positions may produce the same optimal integer allocation. Such solutions are deduplicated internally but retain an exact mapping to all 1,001 positions.

If the feasible frontier has only one distinct result, the selector is disabled and the single allocation is displayed.

## 9.5 Optimisation certification

For monthly variance incumbent \(U_k\) and valid same-problem lower bound \(LB_k\), the specified release-quality gate is:

\[
\sqrt{12U_k}
-
\sqrt{12\max(LB_k,0)}
\le0.0001.
\]

This is a maximum certified annual-volatility gap of **0.01 percentage points**.

When annualised incumbent variance is below \(10^{-10}\), an additional annualised variance-gap tolerance of \(10^{-12}\) applies.

Every distinct solution retains:

- Integer allocation;
- Feasibility result;
- Monthly objective variance;
- Valid lower bound;
- Annual volatility gap;
- Solver status;
- Solve duration;
- Certification result.

Solutions that merely satisfy integer constraints but have not achieved the bound requirement are labelled uncertified and cannot be presented as fully certified frontier points.

The expensive 1,001-position, all-mask optimisation is performed offline and bundled into the immutable release.

The interactive viewer loads verified results; it does not rerun large MIQP workloads every time the user moves the frontier selector.

## 9.6 Manual allocations

The allocation editor uses exact integer basis points.

A manually edited portfolio is valid only when its nonzero holdings meet the minimum and the total equals 10,000 basis points.

If the draft does not total 100%, the last valid portfolio marker remains active.

**Normalise draft weights** proportionally adjusts positive draft weights and applies deterministic, constraint-aware integer rounding.

Any holdings that would be removed to satisfy the minimum buy-in must be disclosed before applying the change.

The edited portfolio's expected return and volatility are calculated directly from the current model moments.

An edited portfolio does not need to be an efficient frontier optimum.

---

# 10. Reference Strategies and Comparability

Exactly six default reference strategies are displayed on the Dashboard frontier.

| Reference | Construction |
|---|---|
| S&P 500 | Lowest-TER eligible verified unlevered S&P 500 tracker, with recorded share class |
| All-world all-cap | VALL, ISIN IE000VAHT5T0 |
| Global 60/40 | Initially 60% VALL and 40% VAGS |
| Bonds | VAGS GBP-hedged global aggregate bonds |
| Value sleeve | Geography/capitalisation-matched value-tilted basket |
| Size sleeve | Explicit small-cap basket using broad all-cap regional targets |

All references include relevant product expenses.

Reference compositions are frozen for each immutable release.

VALL is the primary global all-cap baseline. It spans developed and emerging markets and includes small-cap exposure.

MSCI World All Cap is an optional developed-market comparator, not an interchangeable name or equivalent substitute for VALL.

The value and size sleeves target geography comparable to VALL rather than assuming equal regional allocations.

For the value sleeve, the initial planned style target is 0.5 cross-sectional standard deviations above the all-cap reference.

Initial sleeve tolerances are 2 percentage points per relevant region/capitalisation bucket and 0.1 standard deviations for style. Where infeasible, a relaxed 5-percentage-point regional/cap tolerance may be used with achieved deviations disclosed.

These are portfolio construction policies rather than benchmark-index facts.

The reference allocations are held according to the same buy-and-hold investor policy unless explicitly labelled otherwise.

---

# 11. Underlying Holdings and Concentration

## 11.1 Two exposure denominators

The Underlying Holdings page distinguishes:

**Whole portfolio economic exposure:** Company exposure relative to the portfolio's initial NAV. Leveraged economic positions may result in aggregate company exposure greater than 100%.

**Equity-normalised comparison:** Portfolio and benchmark equity exposures separately normalised to 100% of their respective mapped equity exposures.

For company \(c\), the whole-portfolio exposure is:

\[
e_c=\sum_iw_iH_{ic}.
\]

For equity-normalised weights:

\[
p_c=
\frac{e_c}{\sum_{d\in\mathrm{equity}}e_d}.
\]

The benchmark undergoes the corresponding normalisation.

The active comparison is:

\[
\Delta_c=p_c-b_c,
\]

reported in percentage points.

Company matching is an outer join. Companies present only in the benchmark remain visible with zero portfolio weight.

## 11.2 Country, sector and capitalisation

Classification uses the economic company rather than the legal domicile of the holding fund.

Country, sector and large/mid/small capitalisation definitions must be consistent between portfolio and benchmark.

Unknown classifications remain visible and enter coverage reconciliation.

Cash, physical bullion and bond issuer lines are not counted as equity companies.

Synthetic and leveraged equity exposures look through to their economic underlying rather than substituting the swap collateral portfolio.

## 11.3 Effective company count

For mapped and equity-normalised company exposure \(p_c\):

\[
N_{\mathrm{effective}}
=
\frac{1}{\sum_cp_c^2}.
\]

This is an inverse-Herfindahl concentration measure.

It is generally smaller than the raw number of companies and does not measure the number of securities, share-class lines or fund positions.

With insufficient mapping coverage, the application displays a qualified partial estimate or N/A, alongside the applicable coverage percentage.

It does not imply that 15,000 underlying securities provide 15,000 independent sources of risk.

---

# 12. Buy-and-Hold Wealth Projections

## 12.1 Investor policy

The default wealth projection assumes:

- An initial £10,000 investment;
- Fixed fund units after the initial purchase;
- No periodic investor rebalancing;
- No subsequent contributions or withdrawals;
- Distributions paid into a separate GBP cash account;
- Product-level resets continuing according to each product's terms;
- Portfolio economic weights drifting naturally.

A daily reset inside a leveraged ETP is not an investor-level portfolio rebalance.

## 12.2 Accumulating fund units

Let \(N_i\) denote the investor's purchased units and \(P_i(t)\) the GBP value per unit.

The investor unit count is:

\[
N_i(t)=N_i(0).
\]

For a fund represented by a suitable accumulating/reinvested total-return growth factor:

\[
G_i(t)=
\prod_{\tau=1}^{t}(1+R_{i,\tau}).
\]

Portfolio wealth is:

\[
W_t
=
W_0\sum_iw_i(0)G_i(t).
\]

The economic weight drift is:

\[
w_i(t)
=
\frac{w_i(0)G_i(t)}
{\sum_jw_j(0)G_j(t)}.
\]

For leveraged economic exposure:

\[
L_{\mathrm{portfolio}}(t)
=
\sum_iw_i(t)L_i(t),
\]

where \(L_i(t)\) respects the relevant product's evolving actual economic exposure.

Thus portfolio leverage, concentrations and asset proportions may move materially away from their initial values.

## 12.3 Distributions retained in GBP cash

For distributing funds, income payments do not buy new units.

Let \(P_i^{ex}(t)\) be the ex-distribution price, and let \(D_{i,t}\) represent the cash distribution due to the investor's fixed units.

The GBP cash account follows:

\[
B_t
=
B_{t-1}(1+r_{\mathrm{cash},t})
+
\sum_iD_{i,t}
+
C_t^{redemption}.
\]

Here \(C_t^{redemption}\) is any compulsory redemption cash paid at time \(t\).

Total portfolio wealth is:

\[
W_t
=
\sum_{i\ne cash}N_i(0)P_i^{ex}(t)
+
B_t.
\]

The distribution cash balance earns the dated or scenario-specific GBP cash rate.

Cash is not automatically redistributed across the remaining funds.

A distributing fund's NAV-only price series is not a total-return series, and a dividend-reinvested total-return series cannot reproduce this default investor cash-retention policy without further adjustments.

Where distribution-event data are unavailable, a same-fund-reinvestment proxy must be separately labelled and may not be described as exact fixed-unit, cash-retained accounting.

## 12.4 Analytical log-return moments

The interactive default does not require startup Monte Carlo simulation.

Let monthly log gross returns satisfy a calibrated multivariate model with mean vector \(m\) and covariance \(C\).

For accumulating assets or a properly labelled total-return proxy:

\[
G_i(n)=
\exp\left(\sum_{t=1}^{n}g_{i,t}\right).
\]

Define:

\[
M_i(n)
=
\exp\left(nm_i+\frac12nC_{ii}\right).
\]

Expected buy-and-hold wealth is:

\[
E[W_n]
=
W_0\sum_iw_i(0)M_i(n).
\]

Its variance is:

\[
\operatorname{Var}(W_n)
=
W_0^2
\sum_i\sum_j
w_i(0)w_j(0)
M_i(n)M_j(n)
\left[\exp(nC_{ij})-1\right].
\]

This follows from the covariance of jointly lognormal asset growth factors.

For portfolios with distributing assets and cash retention, the engine instead propagates the ex-distribution fund-price processes and the cash-flow recurrence jointly.

The cash-retained distribution model must incorporate payout timing and the covariance of dividends with underlying fund values.

## 12.5 Lognormal portfolio approximation

A weighted sum of correlated lognormal variables is not generally exactly lognormal.

The application approximates terminal portfolio wealth by matching the first two moments.

Let:

\[
E_n=E[W_n], \qquad V_n=\operatorname{Var}(W_n).
\]

Define:

\[
s_n^2
=
\ln\left(1+\frac{V_n}{E_n^2}\right)
\]

and:

\[
a_n
=
\ln(E_n)-\frac12s_n^2.
\]

An approximate wealth percentile \(p\) is:

\[
W_n^{(p)}
=
\exp\left(a_n+\Phi^{-1}(p)s_n\right).
\]

This is a moment-matched approximation, not an exact distributional guarantee.

For a deterministic cash-only portfolio, all quantile curves coincide at its scenario-determined wealth.

## 12.6 Uncertainty bands

The default chart shows:

- Median projected wealth;
- A central 68.27% interval, approximately P15.865–P84.135.

Optional presets include:

- 0.5 standard deviation;
- 1 standard deviation;
- 2 standard deviations;
- P20–P80;
- Custom percentile bounds.

The chart supports shaded and boundary-only bands, linear/logarithmic wealth axes and local horizon selection.

The default central interval is a conditional model interval under the selected return and risk assumptions.

Unless separately estimated and incorporated, parameter uncertainty is not included.

If drift-estimation covariance \(U\) is available and consistently defined, the future log-growth covariance can incorporate a term scaling as \(n^2U\), in addition to the ordinary \(nC\) market-risk term.

The application does not invent parameter uncertainty to create wider-looking bands.

## 12.7 Return percentiles and CAGR

Cumulative return at horizon \(H\) for percentile \(p\) is:

\[
R_{H,p}^{cum}
=
\frac{W_{12H}^{(p)}}{W_0}-1.
\]

The corresponding annualised CAGR percentile is:

\[
CAGR_{H,p}
=
\left(
\frac{W_{12H}^{(p)}}{W_0}
\right)^{1/H}-1.
\]

The default downside metric is:

**5-year P20 cumulative return.**

P20 represents the twentieth percentile of the modelled return distribution, not an expected return, worst-case loss or probability of investment failure.

Its annualised CAGR equivalent is shown in help or supporting detail.

## 12.8 Historical maximum drawdown

Historical maximum drawdown is calculated from an observed portfolio wealth replay with a stated sampling frequency and common observation dates.

For wealth observations \(W_t\):

\[
M_t=\max_{s\le t}W_s
\]

and:

\[
DD_t=1-\frac{W_t}{M_t}.
\]

Maximum historical drawdown is:

\[
MDD=\max_tDD_t.
\]

The headline identifies whether the replay is daily or monthly and the actual historical period.

Where an adequate common observed period is unavailable, the interface does not imply that different funds' own-period drawdowns are directly comparable.

Proxy-extended drawdown is a separate secondary statistic.

A historical maximum drawdown is not a mathematically guaranteed bound on future losses.

## 12.9 Band intersections

For two portfolios \(A\) and \(B\), define their lower and upper forecast bands as:

\[
[L_A(t),U_A(t)]
\]

and:

\[
[L_B(t),U_B(t)].
\]

A boundary crossing is detected when either:

\[
L_A(t)=U_B(t)
\]

or:

\[
L_B(t)=U_A(t)
\]

at a positive time.

The trivial common starting point at \(t=0\) is ignored.

Numerical root-finding determines crossings between chart observations.

Multiple crossings are preserved.

If the bands overlap throughout the horizon, the interface says so.

If identical portfolios are compared, duplicate intersection markers are omitted.

Overlap of marginal bands is not evidence that two portfolios are statistically indistinguishable. It is also not a direct probability that one portfolio outperforms another.

---

# 13. Dashboard Metrics

The Dashboard presents:

| Metric | Definition |
|---|---|
| Net expected annual return | Annualised arithmetic expected return from the active model |
| Annual volatility | Square root of annualised portfolio variance |
| Effective companies | Inverse-Herfindahl count of mapped equity company exposure |
| Historical maximum drawdown | Observed historical high-water-mark decline with period/frequency |
| 5-year P20 return | Modelled twentieth-percentile cumulative five-year return |
| Weighted TER | Initial allocation-weighted recurring fund wrapper charges |
| Modelled financing | Initial allocation-weighted separately modelled financing costs |
| Initial gross exposure | Sum of initial position weights multiplied by appropriate economic exposure multiples |

The diversification score for stochastic instruments compares each fund with the rest of the invested portfolio:

\[
D_i
=
50(1-\rho_{i,-i}).
\]

This gives:

- 0 for perfect positive correlation;
- 50 for zero correlation;
- 100 for perfect negative correlation.

The fund itself is excluded from the remainder.

If the rest of the portfolio is empty or deterministic, correlation and the ordinary score are N/A.

The cash-only convention described earlier is not an empirical correlation measurement.

Portfolio volatility must always be calculated from the full covariance matrix, not by averaging constituent volatilities.

---

# 14. Application Structure and Data Presentation

## 14.1 Dashboard

The Dashboard contains the efficient frontier, six reference strategies, category selection, compact portfolio metrics and editable fund allocation table.

Frontier selector positions correspond to expected-return targets, not risk percentages.

Manual edits remain separate from frontier solutions until the user explicitly chooses to apply a frontier allocation.

## 14.2 Underlying Holdings

The Underlying Holdings page displays searchable, sortable company and security economic exposure against the VALL reference.

It retains benchmark-only companies, mapping coverage, leveraged exposure reconciliation, country/sector/cap comparisons and complete data exports.

The underlying dataset may contain approximately 15,000 distinct security rows; virtualised or paginated display does not restrict the completeness of the exported aggregate.

## 14.3 Analysis

Analysis supports between one and five populated portfolios.

It presents expected-return and risk metrics, £10,000 growth projections, portfolio-versus-benchmark geographical and style comparisons, and constituent covariance/correlation matrices.

The growth chart owns its horizon controls and band settings.

The P20 metric has its own horizon control, optionally linked to the chart horizon by an explicit user choice.

## 14.4 Methods

Methods contains this scientific explanation, the data assumptions, source qualifications, benchmark methodology, model comparison and release diagnostics.

Technical details belong in Methods and contextual question-mark help rather than decorating financial charts.

**Charts must not carry decorative methodological badges, qualification captions or secondary warning ribbons.** Proper titles, axes, units, legends, data-selection affordances and real error states remain essential.

---

# 15. Data Provenance and Third-Party Limitations

## 15.1 Audit status

The fixed-income, commodity and cash research evidence comes from Stream C's audit completed 18 October 2026.

The audit covers 20 identities:

- 13 bond funds;
- 6 commodity products;
- 1 GBP cash facility.

Its completion status is **complete with documented source gaps**, not complete end-to-end ingestion of every historical dataset.

An audit may verify a product's identity, fees or issuer factsheet without establishing a usable full historical return series.

## 15.2 Verified downloads

Stream C reports:

- Ten directly fetched iShares bond-holdings CSVs dated 15 October 2026;
- Twelve iShares fund downloads in Excel XML format;
- Historical NAV worksheets inspected for selected iShares products;
- GLTL State Street holdings and NAV workbooks fetched and checked;
- Issuer pages and published characteristics independently cross-checked for selected other instruments.

A direct XLSX/XML workbook is not a CSV merely because its contents can be parsed into tabular data.

The audit encountered an invalid XML character in one generic parsing attempt. Production source parsing must retain raw bytes and apply controlled parsing/validation rather than assuming that an `.xlsx` extension guarantees modern zipped XLSX format.

Some source observations were inherited from earlier dated audit checkpoints. The 18 October research completion date does not mean that every instrument's holdings or numerical statistics were published or independently re-fetched on that day.

## 15.3 Outstanding downloads and historical data

The following remain explicitly incomplete or conditional:

| Source area | Limitation |
|---|---|
| VAGS | Download controls observed, but reusable direct holdings/history export URL and bytes not verified |
| VEMT | Same unresolved direct holdings/history export limitation |
| CMOP | Direct reusable commodity fund historical CSV/source file not verified |
| WisdomTree COPB/AGAP/CRUP | Historical-data export controls observed; direct complete export URLs/bytes unresolved |
| SGLN and SSLN | Bullion backing PDFs identified; bullion CSV exports not verified |
| Trading 212 cash | No public account-specific cash/QMMF allocation file and no verified historical AER time series |
| WisdomTree fees | Exact annual swap-rate daily accrual/day-count not independently settled |
| VAGS/VEMT duration | Formal effective/option-adjusted equivalence of published Average Duration unresolved |
| VAGS | Underlying local-currency yield is not a verified net-GBP forward yield |
| GHYS | FX-forward carry inclusion in published 7.46% YTM not explicitly documented |
| ITPG | Verified published US real yield, but no fully documented net-GBP nominal forward carry figure |
| Commodity futures | No verified constant future roll yield or synthetic complete return history |
| Credit risk | No verified future default probabilities/recoveries for all constituent holdings |
| FX assumptions | No universally verified future GBP exchange-rate path or complete hedge-forward forecast |
| Leveraged products | Future intraday reset paths and unverified contractual spreads cannot be inferred from daily close histories alone |

Unavailable fields must remain null, not silently turn into zero or synthetic observations.

Where a forward model requires a missing value, the assumption must be visible with source, date, bounds and sensitivity.

## 15.4 Source conflicts resolved

The documented source-precedence decisions are:

1. **Cash:** Use Stream C's observed 3.80% GBP AER as of 18 October, rather than Stage 02's earlier 3.85%; keep 4.25% as planning-only.
2. **SSLN expenses:** Prefer current issuer 0.20% TER over an inconsistent 0.21% LSE display.
3. **ITPG income:** Prefer the issuer's distributing share-class identification over a contradictory LSE title.
4. **SGLN structure:** Prefer current physical-backing issuer documentation over stale exchange wording implying a swap product.
5. **Commodity sterling lines:** Use COPB, AGAP and CRUP while retaining COPA, AIGA and CRUD as identity aliases.
6. **GHYS:** Use the audited 7.46% YTM, not the earlier 7.48% figure.
7. **Vanguard dates:** Preserve the 30 September observation date rather than relabelling values as October figures.

Stale exchange holdings snapshots, including an old SSLN snapshot, are not treated as current underlying holdings.

## 15.5 Data-source hierarchy

Preferred evidence order:

1. Current dated official issuer reports, factsheets, holdings and product terms;
2. Official benchmark and index-provider methods;
3. Documented exchange information;
4. Verified third-party data with clear rights and reproducible provenance;
5. Transparently constructed proxies;
6. Explicit modelling assumptions.

This is not a universal rule that any recent issuer webpage supersedes a binding prospectus. Contractual definitions and effective dates are evaluated according to their legal and methodological relevance.

Interactive chart availability does not establish access to a downloadable bulk history.

No authenticated, paid, restricted or guessed API is represented as publicly verified unless actually authorised and tested.

---

# 16. Sensitivity Analysis and Model Risk

The application separates market-risk uncertainty from assumption uncertainty.

Material sensitivity dimensions include:

- Equity factor premia and shrinkage;
- Holdings characteristic coverage;
- Equity covariance estimation windows;
- Interest rates and bond yield-curve shocks;
- Real rates and inflation paths;
- Credit-loss assumptions;
- Currency-forward hedge carry and unhedged FX;
- Commodity futures excess return and collateral rates;
- Leveraged funding reference rates and spreads;
- Leveraged volatility and crash/reset scenarios;
- GBP cash AER changes.

Scenario results are conditional calculations.

Changes to model assumptions, instrument costs, benchmark recipes, data snapshots or code produce a new immutable release identity or invalidate the relevant cached outputs.

Previously cached allocations must never be displayed against newly edited expected returns while retaining the old portfolio metrics.

---

# 17. Validation and Reproducibility

## 17.1 Required financial tests

The release must verify:

1. GBP/GBx conversion and FX direction;
2. ISIN/listing identity and alias deduplication;
3. Distribution-adjusted historical return calculations;
4. No duplicate wrapper, swap, financing or hedge deductions;
5. Holdings and benchmark exposure reconciliation;
6. Leveraged daily compounding and wipeout absorption;
7. Non-negativity and PSD of risk structures where required;
8. Exact integer frontier allocations and category exclusions;
9. Valid optimisation lower-bound certificates;
10. Buy-and-hold wealth and separate distribution cash accounting;
11. Cash compounding and zero-variance scenario handling;
12. P20, CAGR, drawdown and band-intersection conventions;
13. Complete import/export identity and numeric round trips;
14. Correct source and proxy flags after any ingestion refresh.

A documented methodology does not replace these tests.

## 17.2 Release diagnostics

Each immutable release should provide:

- Product Version V8.0;
- Model family;
- Data snapshot date;
- Code and data hashes;
- Model and covariance provenance;
- Instrument admission count;
- Mapped exposure/characteristic coverage;
- Latest relevant cost/rate source dates;
- Reference-strategy recipes;
- Optimiser quality and certification summary;
- Unresolved source limitations;
- Precision and numerical validation status;
- Runtime dependency and calculation-build identifiers.

Model family IDs and internal hashes are reproducibility metadata, not separate public product version numbers.

## 17.3 Data exchange

Portfolio ZIP exports include the current model-release identity, portfolio weights, underlying source assumptions and applicable calculated metrics.

An imported portfolio with a different release identity can be viewed as a historical snapshot or recalculated using current assumptions, but the two results must not be presented as identical.

Portfolio JSON and ZIP files do not replace curated underlying source data.

Unverified or licence-restricted raw data must not be redistributed merely because it was downloadable in a research environment.

---

# 18. Interpretation and Limitations

Portfolio Construction Lab does not establish that the highest modelled expected return will be the highest future realised return.

The efficient frontier depends on estimates of expected returns, covariance, constraints, source coverage and the chosen model family.

Changes in any of these inputs can materially alter optimal allocations.

A portfolio concentrated in a high-expected-return leveraged ETP may be mathematically admissible under the long-only rules while remaining exposed to severe losses, reset risks, financing costs and counterparty or issuer risks.

The application does not guarantee capital preservation, investment liquidity, tax treatment, platform availability or deposit protection.

The base model does not fully price every market regime shift, default event, commodity curve shock or leveraged instrument termination probability.

Historical data can describe realised outcomes but cannot prove future factor premia.

Buy-and-hold portfolio projections are not equivalent to automatically rebalanced strategy returns.

Central probability bands describe selected assumptions, not all possible outcomes.

No output constitutes a personal recommendation to purchase or sell any instrument.

---

# 19. References

## Governing V8.0 design and calculations

- `00 Specifications/V8.0_Execution_Plan.md`
- `00 Specifications/V8.0_Decision_Register.md`
- `01 Resources/02_product_mechanics.md`
- `01 Resources/03_algorithm_design.md`
- `05 Subagents/Outputs/Stream_C_Result.md`
- Canonical V8.0 instrument and model contracts, where available in the immutable release

## External methodology and instrument evidence

- [Kenneth R. French — Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- [Trading 212 — Interest on Cash](https://www.trading212.com/interest-on-cash)
- [Trading 212 — Cash Interest Help](https://helpcentre.trading212.com/hc/en-us/articles/15475153380637-What-is-interest-on-cash)
- [iShares — Physical Gold ETC](https://www.ishares.com/uk/individual/en/products/258441/ishares-physical-gold-etc)
- [iShares — Physical Silver ETC](https://www.ishares.com/uk/individual/en/products/258443/ishares-physical-silver-etc)
- [Invesco — Bloomberg Commodity UCITS ETF](https://www.invesco.com/uk/en/financial-products/etfs/invesco-bloomberg-commodity-ucits-etf.html)
- [WisdomTree — Copper](https://www.wisdomtree.com/gb/products/commodities/wisdomtree-copper)
- [WisdomTree — Agriculture](https://www.wisdomtree.com/gb/products/commodities/wisdomtree-agriculture)
- [WisdomTree — WTI Crude Oil](https://www.wisdomtree.com/gb/products/commodities/wisdomtree-wti-crude-oil)
- [Bloomberg — Commodity 4-Week Total Return Methodology](https://assets.bbhub.io/professional/sites/27/Bloomberg-Commodity-4-Week-Total-Return-Index-Methodology.pdf)
- [Bloomberg — Commodity Index Methodology](https://assets.bbhub.io/professional/sites/27/BCOM-Methodology-JAN-2025.pdf)
- [Vanguard — Global Aggregate Bond GBP Hedged Factsheet](https://fund-docs.vanguard.com/Global_Aggregate_Bond_UCITS_ETF_GBP_Hedged_Accumulating_9685_EU_INT_UK_EN.pdf)
- [UK Debt Management Office — Index-Linked Gilts](https://www.dmo.gov.uk/data/gilt-market/index-linked-gilts/)
- [US Treasury — TIPS](https://www.treasurydirect.gov/marketable-securities/tips/)

References document the sources and modelling conventions used in the research handover. They are not a representation that all underlying public resources were freshly re-downloaded for this Methods document.

---

# 20. Contact and Corrections

For instrument corrections, issuer-document updates, missing-data reports, benchmark methodology queries or suggestions for additional eligible funds:

**mail@robertgardner.co.uk**

Please include the instrument name, ISIN, relevant source URL, publication date and the field requiring review where possible.

Corrections must pass source verification and release validation before entering the production calculation dataset.
