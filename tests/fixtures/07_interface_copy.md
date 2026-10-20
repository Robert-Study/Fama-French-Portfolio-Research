# Portfolio Construction Lab
## Interface Microcopy — Version V8.0

**Stage:** 07 — Methods Documentation & Interface Microcopy  
**Pages:** Dashboard, Underlying Holdings, Analysis, Methods  
**Language:** British English  
**Financial reporting currency:** GBP  
**Default appearance:** Dark  
**Implementation format:** Namespaced UI copy keys

---

# 1. Interface Copy Contract

## 1.1 Purpose

This document provides implementation-ready text for the four-page Portfolio Construction Lab interface.

It includes:

- Page titles and navigation;
- Field and table labels;
- Control labels and accessible descriptions;
- Contextual question-mark tooltips;
- Input validation messages;
- Operational warnings;
- Missing-data and empty states;
- Calculation and provenance descriptions;
- Import/export messages;
- Model limitations and release information.

## 1.2 Text conventions

1. Use British English throughout.
2. Display money in GBP unless a source quotation explicitly uses another currency.
3. Display portfolio allocations to two decimal percentage places.
4. Express allocation editing in basis points internally.
5. Distinguish annual arithmetic expected returns from compounded CAGR.
6. Distinguish historical observations from scenario calculations.
7. Display unavailable data as `N/A`, `Not available`, or an explanatory contextual state; never substitute zero.
8. Do not use unexplained acronyms in primary chart titles.
9. Use consistent names for financial metrics across pages.
10. Use the same control wording for the same portfolio action on different pages.
11. Do not expose internal model or data schema identifiers in routine user-facing labels where plain English suffices.
12. Where relevant, preserve dates and source conventions in tooltips and Methods.
13. Dynamic numerical values must be supplied by the current release or live user action, not hard-coded into interface text.

## 1.3 Interpolation

Strings may contain named placeholders:

- `{portfolio}`
- `{instrument}`
- `{value}`
- `{total}`
- `{count}`
- `{date}`
- `{period}`
- `{source}`
- `{method}`
- `{completed}`
- `{available}`
- `{release}`
- `{difference}`
- `{category}`
- `{reason}`

Substitution must use validated, appropriately escaped values.

The interface must never render an unresolved placeholder as user-facing text.

## 1.4 Zero chart-side decorative badges

**Non-negotiable V8.0 interface rule:**

Do not display methodological badges, decorative status pills, explanatory caveat captions or warning ribbons immediately beside, above or below financial charts.

Permitted chart-adjacent elements are:

- Chart title;
- Proper axis labels and units;
- Functional legend;
- Chart controls;
- Contextual question-mark help;
- Interactive hover information;
- Genuine loading, empty or error states.

Methodology and conditional assumptions belong in question-mark help and the Methods page.

Operational warnings belong in a relevant control, form or status area, not as decorative chart annotations.

A genuine data integrity error may replace or disable a chart. The zero-badge rule does not suppress meaningful failures.

---

# 2. Shared Navigation and Application Shell

```yaml
app.title: "Portfolio Construction Lab"
app.version: "Version V8.0"
app.currency: "GBP"
app.nav.dashboard: "Dashboard"
app.nav.underlying: "Underlying Holdings"
app.nav.analysis: "Analysis"
app.nav.methods: "Methods"

app.theme.to_light: "Switch to light mode"
app.theme.to_dark: "Switch to dark mode"
app.theme.help: "Change the interface appearance. Your portfolio allocations and calculations will not change."
app.theme.unavailable: "The appearance control is temporarily unavailable. Your portfolio data is unaffected."

app.release.label: "Data and model release"
app.release.help: "All calculations use a consistent, dated model release. Source dates, assumptions and model diagnostics are available in Methods."
app.release.value: "Release {release}"
app.release.date: "Data snapshot: {date}"
app.release.changed: "A newer model release is available. Recalculate your portfolio to use its updated data and assumptions."

app.method.label: "Equity model"
app.method.holdings: "Underlying companies"
app.method.etf: "ETF returns"
app.method.help: "Choose how equity factor exposures are estimated. Underlying companies uses calibrated company characteristics and fund holdings. ETF returns uses historical fund-return calibration. Bonds, commodities, cash and leverage use shared product mechanics."
app.method.switch: "Use selected model"
app.method.switch_warning: "Changing models may change expected returns, risk estimates and the efficient frontier. Your unsaved portfolio allocations will be preserved."
app.method.switch_success: "The selected model is ready. Portfolio calculations now use its matching release data."
app.method.unavailable: "This model cannot be loaded because required data are unavailable. See Methods for the missing inputs."
app.method.unsaved: "Your allocation edits are preserved. Review the recalculated results before replacing your saved portfolio."

app.help.aria: "More information"
app.help.close: "Close explanation"
app.help.methods_link: "Read the full methodology"

app.status.ready: "Ready"
app.status.loading: "Preparing portfolio data"
app.status.indeterminate: "Checking the required data and calculation stages"
app.status.progress: "{completed} of {total} stages complete"
app.status.holdings: "Holdings: {completed} of {total} securities processed"
app.status.mapping: "Mapping company identities and economic exposures"
app.status.calculating: "Calculating the holdings comparison"
app.status.frontier: "Loading precomputed efficient-frontier results"
app.status.analysis: "Preparing portfolio projections"
app.status.complete: "All requested calculations are ready"
app.status.partial: "The main portfolio is ready. Detailed holdings calculations are still loading."
app.status.failed: "Some data could not be prepared. The last valid results remain available."
app.status.retry: "Retry loading"
app.status.retry_success: "The requested data are ready."
app.status.retry_failure: "Loading could not be completed. Review the error details or try again."

app.action.save_copy: "Save copy"
app.action.copy: "Copy"
app.action.paste: "Paste"
app.action.import_zip: "Import ZIP"
app.action.export_zip: "Export ZIP"
app.action.cancel: "Cancel"
app.action.apply: "Apply"
app.action.close: "Close"
app.action.remove: "Remove"
app.action.duplicate: "Duplicate"
app.action.rename: "Rename"
app.action.reset: "Reset"
app.action.search: "Search"
app.action.clear: "Clear"
app.action.retry: "Retry"

app.save.name_label: "Portfolio name"
app.save.name_placeholder: "Enter a portfolio name"
app.save.success: "A copy of {portfolio} has been saved in this browser."
app.save.local_help: "Saved portfolios use browser-local storage where available. Download a ZIP or JSON copy for durable backup."
app.save.session_only: "Browser storage is unavailable. This portfolio is retained for the current session only. Export it to keep a copy."
app.save.conflict: "A portfolio with this name already exists. Choose another name or replace the existing saved copy."

app.copy.success: "Portfolio JSON copied."
app.copy.fallback: "Clipboard access is unavailable. Select and copy the portfolio JSON shown below."
app.copy.failure: "The portfolio could not be copied. Try Export ZIP instead."

app.import.prompt: "Select a Portfolio Construction Lab ZIP file."
app.import.validating: "Checking portfolio schema, identities, weights and release compatibility"
app.import.success: "Portfolio imported: {portfolio}"
app.import.invalid: "This ZIP is not a valid Portfolio Construction Lab portfolio."
app.import.unknown_fund: "One or more instruments could not be matched to verified identities. Review the mapping before proceeding."
app.import.invalid_weights: "Imported weights must total 100.00%, with valid instrument allocations."
app.import.unsafe: "The archive contains unsupported or unsafe files and cannot be imported."
app.import.release_mismatch: "This portfolio was created using a different data release."
app.import.keep_snapshot: "View historical snapshot"
app.import.recalculate: "Recalculate with current release"
app.import.no_silent_normalise: "Unmatched instruments will not be dropped or automatically reallocated."
app.import.cancelled: "Import cancelled. Your existing portfolio is unchanged."

app.export.preparing: "Preparing export"
app.export.ready: "Export ready"
app.export.success: "Portfolio export created."
app.export.failure: "The export could not be prepared. Your portfolio remains unchanged."
app.export.help: "The ZIP includes the portfolio definition, current model identity, relevant calculations and permitted derived data. Raw third-party histories may be excluded."
app.export.full_precision: "CSV calculations retain their stored calculation precision; displayed values may be rounded."

app.error.missing_release: "The required model release is missing or incomplete. The application cannot safely substitute fabricated data."
app.error.incompatible_release: "These calculations belong to a different model release. Refresh or select a compatible snapshot."
app.error.invalid_data: "An instrument or source file failed validation. Affected calculations are unavailable until the issue is resolved."
app.error.unexpected: "An unexpected error occurred. Your last valid portfolio has been retained."
```

---

# 3. Dashboard

## 3.1 Page hierarchy

Primary order:

1. Compact headline metrics;
2. Expected return and volatility chart;
3. Compact allocation summary;
4. Frontier selector and actions;
5. Editable allocation table.

There is no separate fund-level Holdings page.

## 3.2 Titles and headline metrics

```yaml
dashboard.title: "Dashboard"
dashboard.subtitle: "Explore efficient portfolios and refine your fund allocation."

dashboard.metric.expected_return: "Net expected annual return"
dashboard.metric.volatility: "Annual volatility"
dashboard.metric.effective_companies: "Effective companies"
dashboard.metric.max_drawdown: "Historical maximum drawdown"
dashboard.metric.p20: "5-year P20 return"

dashboard.metric.expected_return_help: "The model's annualised arithmetic expected return after applicable ongoing costs. It is not a guaranteed return or the same as compound annual growth."
dashboard.metric.volatility_help: "Annualised standard deviation calculated from the full covariance matrix, including correlations between holdings."
dashboard.metric.effective_companies_help: "A concentration-adjusted count calculated from mapped underlying equity-company exposures. It is not the number of funds or securities. Incomplete look-through coverage may make this unavailable or partial."
dashboard.metric.max_drawdown_help: "The largest peak-to-trough decline in the stated historical replay. The observation period and daily or monthly frequency determine the result. This is not a forecast maximum loss."
dashboard.metric.p20_help: "The twentieth percentile of modelled cumulative five-year return. Under the selected assumptions, approximately 20% of the modelled distribution lies below this value."
dashboard.metric.p20_cagr: "Equivalent annualised P20 CAGR: {value}"
dashboard.metric.p20_horizon: "P20 horizon"
dashboard.metric.p20_horizon_help: "Change the horizon used for this downside-return metric without changing the growth-chart horizon unless explicitly linked."

dashboard.metric.ter: "Weighted TER"
dashboard.metric.financing: "Modelled financing"
dashboard.metric.gross_exposure: "Initial gross exposure"
dashboard.metric.mapped_coverage: "Mapped equity exposure"

dashboard.metric.ter_help: "Initial-weighted fund expense rates. Embedded underlying fees, financing and swap costs are shown separately where relevant, without charging the same cost twice."
dashboard.metric.financing_help: "Modelled annual financing drag on the applicable borrowed exposure. Actual future financing rates may change."
dashboard.metric.gross_exposure_help: "The initial sum of fund weights multiplied by their economic exposure multiples. Exposure can drift after purchase, including within leveraged products."
dashboard.metric.mapped_coverage_help: "Share of economic equity exposure matched to verified underlying securities or companies. This is different from coverage of directly sourced financial characteristics."

dashboard.metric.not_available: "N/A"
dashboard.metric.partial: "Partial — {value} mapped coverage"
dashboard.metric.history_missing: "No comparable observed history"
```

## 3.3 Efficient frontier

```yaml
dashboard.frontier.title: "Expected return and volatility"
dashboard.frontier.x_axis: "Annual volatility (%)"
dashboard.frontier.y_axis: "Net expected annual return (%)"

dashboard.frontier.position: "Frontier position"
dashboard.frontier.position_input: "Position (0.0–100.0)"
dashboard.frontier.position_min: "Minimum variance"
dashboard.frontier.position_max: "Maximum expected return"
dashboard.frontier.position_help: "Select one of 1,001 target-return positions from minimum variance to maximum expected return. This is not a volatility percentage or equity allocation."
dashboard.frontier.position_step_help: "Positions change in 0.1 increments. Multiple positions may share the same exact integer allocation."

dashboard.frontier.selected: "Selected allocation"
dashboard.frontier.edited: "Edited portfolio"
dashboard.frontier.use: "Use frontier allocation"
dashboard.frontier.use_help: "Replace the current draft allocation with the selected frontier weights. This action does not rebalance your portfolio in future periods."
dashboard.frontier.replace_confirm: "Replace your current allocation with the selected frontier allocation?"
dashboard.frontier.no_distinct_range: "Only one distinct feasible portfolio is available for these categories."
dashboard.frontier.unavailable: "No certified frontier is available for this selection."
dashboard.frontier.loading: "Loading the precomputed frontier for the selected categories"

dashboard.frontier.hover.position: "Position: {value}"
dashboard.frontier.hover.return: "Net expected return: {value}"
dashboard.frontier.hover.volatility: "Annual volatility: {value}"
dashboard.frontier.hover.ter: "Weighted TER: {value}"
dashboard.frontier.hover.top_funds: "Largest allocations"
dashboard.frontier.hover.reference: "Reference: {value}"

dashboard.frontier.help: "The frontier minimises expected variance for specified return targets using long-only integer allocations. Every positive holding is at least 0.10%. Points are calculated using the selected model release and category constraints. Refer to Methods for solver certification and assumption limitations."
dashboard.frontier.uncertified_help: "A computed candidate did not meet the required optimisation bound. It is not represented as a certified efficient-frontier solution."
```

The chart does not display a methodological badge, solver-status caption, alpha label, model-version pill or extra qualification ribbon.

## 3.4 Exactly six reference strategies

```yaml
dashboard.reference.sp500: "S&P 500"
dashboard.reference.all_cap: "All-world all-cap"
dashboard.reference.global_6040: "Global 60/40"
dashboard.reference.bonds: "Bonds"
dashboard.reference.value: "Value sleeve"
dashboard.reference.size: "Size sleeve"

dashboard.reference.help: "Reference strategies use dated, documented fund recipes with applicable costs. Their positions are fixed for the current release and are not re-optimised when you change category switches."

dashboard.reference.all_cap_help: "Uses VALL as the developed- and emerging-market all-cap reference, including small-cap exposure."
dashboard.reference.global_6040_help: "Starts with 60% global all-cap equity and 40% GBP-hedged global aggregate bonds. The default investor policy is buy-and-hold rather than ongoing 60/40 rebalancing."
dashboard.reference.value_help: "Targets value exposure while matching the broad benchmark's geographical and capitalisation composition as closely as the available instruments allow. Achieved deviations are documented in Methods."
dashboard.reference.size_help: "Uses explicitly small-cap instruments with regional targets based on the all-cap reference. The achieved regional allocation may differ from those targets."
```

## 3.5 Category filters and fund picker

```yaml
dashboard.categories.title: "Investable categories"
dashboard.categories.savings: "Savings"
dashboard.categories.commodities: "Commodities"
dashboard.categories.bonds: "Bonds"
dashboard.categories.broad_equity: "Broad equity"
dashboard.categories.factor_equity: "Factor equity"
dashboard.categories.leveraged: "Leveraged"

dashboard.categories.help: "Choose which asset classes the optimiser may use. Disabled categories are excluded from new frontier allocations. Imported portfolios containing excluded funds remain viewable."
dashboard.categories.none: "No categories selected. Enable at least one category to construct a portfolio."
dashboard.categories.loading: "Loading the allocation options for this category selection"
dashboard.categories.imported_excluded: "This portfolio contains instruments outside the currently enabled categories. Enable those categories to edit or rebuild the allocation under the same constraints."
dashboard.categories.leveraged_help: "Includes daily-reset leveraged products with path-dependent returns, financing costs and potentially severe losses. Their long-term returns are not fixed multiples of the underlying market."

dashboard.fund.add: "Add fund"
dashboard.fund.search: "Search by ticker, name or ISIN"
dashboard.fund.category: "Category"
dashboard.fund.name: "Fund"
dashboard.fund.ticker: "Ticker"
dashboard.fund.currency: "Listing currency"
dashboard.fund.ter: "TER"
dashboard.fund.add_selected: "Add selected fund"
dashboard.fund.already_added: "This fund is already in the portfolio."
dashboard.fund.category_disabled: "Enable {category} to add this fund."
dashboard.fund.no_results: "No verified instruments match your search."
dashboard.fund.identity_help: "Instrument identity is verified by share class and listing. Hover over a ticker for ISIN, exchange, currency, quote unit and hedge status."
dashboard.fund.unavailable: "This instrument is not admitted to the active model release."
```

## 3.6 Allocation editor

```yaml
dashboard.allocation.title: "Portfolio allocation"
dashboard.allocation.subtitle: "Edit your initial fund weights. Future weights drift naturally unless you trade."

dashboard.allocation.column.ticker: "Ticker"
dashboard.allocation.column.name: "Exposure"
dashboard.allocation.column.weight: "Weight (%)"
dashboard.allocation.column.return: "Net return (%)"
dashboard.allocation.column.market: "Market base"
dashboard.allocation.column.size: "Size"
dashboard.allocation.column.value: "Value"
dashboard.allocation.column.profitability: "Profitability"
dashboard.allocation.column.investment: "Investment"
dashboard.allocation.column.momentum: "Momentum"
dashboard.allocation.column.ter: "TER"
dashboard.allocation.column.other_costs: "Other costs"
dashboard.allocation.column.volatility: "Volatility"
dashboard.allocation.column.currency: "Quote"
dashboard.allocation.column.diversification: "Diversification"

dashboard.allocation.column_return_help: "Annualised arithmetic net expected return for this instrument."
dashboard.allocation.factor_help: "Signed annual expected-return contributions from calibrated factor exposures relative to the appropriate market benchmark. N/A means an equity factor contribution is not applicable."
dashboard.allocation.ter_help: "Annual fund wrapper expense, separated from financing and distinct implementation costs."
dashboard.allocation.currency_help: "Exchange quotation currency and unit, not necessarily the currency of the underlying economic risk."
dashboard.allocation.diversification_help: "For stochastic assets, 50 × (1 − correlation with the rest of the portfolio). Higher scores indicate less positive correlation. Cash may use a separately labelled deterministic convention."

dashboard.allocation.total: "Total allocation"
dashboard.allocation.total_valid: "100.00%"
dashboard.allocation.draft: "Draft allocation"
dashboard.allocation.normalise: "Normalise draft weights"
dashboard.allocation.normalise_help: "Scale your draft positive weights to 100.00%, then allocate exact integer basis points while enforcing a 0.10% minimum positive holding."
dashboard.allocation.normalise_preview: "Review weight adjustments"
dashboard.allocation.normalise_removal: "Some small positions must be increased or removed to meet the minimum buy-in. Review the changes before applying."
dashboard.allocation.normalise_confirm: "Apply normalised weights"
dashboard.allocation.normalise_cancel: "Keep draft"

dashboard.allocation.minimum: "Minimum positive allocation: 0.10%"
dashboard.allocation.invalid_total: "Draft weights total {total}. A valid invested portfolio must total 100.00%."
dashboard.allocation.invalid_minimum: "Each nonzero fund allocation must be at least 0.10%."
dashboard.allocation.invalid_negative: "Fund weights cannot be negative."
dashboard.allocation.invalid_number: "Enter a finite numeric weight."
dashboard.allocation.all_zero: "Add or increase at least one holding before normalising."
dashboard.allocation.pending: "Your draft has not replaced the last valid portfolio."
dashboard.allocation.valid: "Allocation validated."
dashboard.allocation.remove_confirm: "Remove {instrument} from this portfolio?"
dashboard.allocation.unsaved: "You have unsaved allocation changes."
dashboard.allocation.last_valid: "The chart continues to show the last valid allocation while you edit."

dashboard.allocation.ticker_hover: "{instrument} | ISIN {value} | {source}"
dashboard.allocation.n_a: "N/A"
dashboard.allocation.cash_diversification: "100 — deterministic cash convention"
```

## 3.7 Dashboard warnings and empty states

```yaml
dashboard.empty.no_portfolio: "Your portfolio is empty. Add a fund or use a frontier allocation to begin."
dashboard.empty.no_categories: "Enable at least one investable category."
dashboard.empty.no_frontier: "No certified allocation is available for this category selection."
dashboard.empty.no_history: "Historical drawdown is unavailable because the required observed return history is incomplete."
dashboard.empty.no_lookthrough: "Company concentration is unavailable until sufficient underlying exposure has been mapped."
dashboard.empty.no_funds: "No eligible instruments are available in the selected categories."

dashboard.warning.draft: "Your edited weights do not yet form a valid invested portfolio."
dashboard.warning.leverage: "This allocation contains leveraged products. Daily reset, financing and extreme-market losses can materially affect long-term results."
dashboard.warning.model_switch: "The model has changed. Review the updated forecasts before applying a different allocation."
dashboard.warning.source_gap: "Some results use documented proxy or assumption inputs. Details are available in the relevant help and Methods."
dashboard.warning.stale_release: "These displayed results do not belong to the selected release. Reload matching calculations before using them."
```

Warnings appear in actionable editor/status locations or within help, not as chart-side decorative banners.

---

# 4. Underlying Holdings

## 4.1 Page titles and exposure views

```yaml
underlying.title: "Underlying Holdings"
underlying.subtitle: "Explore the economic companies and securities behind your portfolio."

underlying.view.label: "Exposure view"
underlying.view.whole: "Whole portfolio economic exposure"
underlying.view.normalised: "Equity-normalised comparison"

underlying.view.whole_help: "Company exposure is measured against initial portfolio NAV. Leveraged products can generate economic equity exposure above 100%. Cash, bonds, commodities and unmapped exposures are reconciled separately."
underlying.view.normalised_help: "Portfolio and benchmark company exposures are each normalised to their mapped equity totals. This supports like-for-like comparisons of companies, countries, sectors and capitalisation."

underlying.granularity.label: "Group by"
underlying.granularity.company: "Company"
underlying.granularity.security: "Security / share class"
underlying.granularity.help: "Company view consolidates verified securities belonging to the same economic company. Security view preserves individual instruments and share classes."

underlying.benchmark.label: "Benchmark"
underlying.benchmark.value: "VALL — Global all-cap"
underlying.benchmark.help: "VALL is the primary all-world all-cap equity comparator. Portfolio and benchmark use consistent company classifications and dated economic exposure."
```

## 4.2 Metrics and exposure reconciliation

```yaml
underlying.metric.securities: "Mapped securities"
underlying.metric.companies: "Mapped companies"
underlying.metric.coverage: "Economic equity coverage"
underlying.metric.characteristics: "Direct characteristic coverage"
underlying.metric.effective: "Effective companies"
underlying.metric.gross_equity: "Gross economic equity exposure"
underlying.metric.unmapped: "Unmapped equity exposure"
underlying.metric.non_equity: "Non-equity portfolio allocation"

underlying.metric.securities_help: "The number of distinct verified security identities, not the total number of fund-holding rows."
underlying.metric.companies_help: "The number of distinct verified economic companies after consolidating relevant security identities."
underlying.metric.coverage_help: "Percentage of total economic equity exposure mapped to verified underlying securities or companies."
underlying.metric.characteristics_help: "Percentage of weighted economic equity exposure supported directly by sourced financial characteristics rather than peer or regional priors."
underlying.metric.effective_help: "Inverse concentration of mapped, equity-normalised companies. The result may be unavailable or qualified when coverage is insufficient."
underlying.metric.gross_equity_help: "Initial economic company exposure, including any leverage embedded in selected products. This can exceed 100% of initial portfolio NAV."
underlying.metric.unmapped_help: "Economic equity exposure that could not be assigned to a verified security/company. It remains part of the reconciliation."
underlying.metric.non_equity_help: "Cash, bond, physical metal, futures and other non-equity allocations are not counted as equity companies."

underlying.reconciliation.title: "Exposure reconciliation"
underlying.reconciliation.mapped: "Mapped equity"
underlying.reconciliation.unmapped: "Unmapped equity"
underlying.reconciliation.cash: "Cash"
underlying.reconciliation.bonds: "Bonds"
underlying.reconciliation.commodities: "Commodities"
underlying.reconciliation.other: "Other / residual"
underlying.reconciliation.help: "This reconciliation distinguishes initial portfolio capital allocation from economic exposure. Leveraged equity notional can exceed its invested capital."
```

## 4.3 Company and security table

```yaml
underlying.table.title: "Company and security exposure"
underlying.table.search: "Search companies, tickers or securities"
underlying.table.sort: "Sort by"
underlying.table.filter_country: "Country"
underlying.table.filter_sector: "Sector"
underlying.table.filter_cap: "Capitalisation"
underlying.table.filter_fund: "Source fund"

underlying.table.column.company: "Company"
underlying.table.column.ticker: "Ticker"
underlying.table.column.country: "Country"
underlying.table.column.sector: "Sector"
underlying.table.column.cap: "Cap bucket"
underlying.table.column.portfolio: "Portfolio (%)"
underlying.table.column.benchmark: "Benchmark (%)"
underlying.table.column.active: "Active (pp)"
underlying.table.column.funds: "Source funds"
underlying.table.column.date: "Data date"
underlying.table.column.provenance: "Data source"
underlying.table.column.characteristics: "Characteristics"
underlying.table.column.premium: "Factor contribution"

underlying.table.active_help: "Portfolio weight minus benchmark weight, expressed in percentage points under the selected exposure denominator."
underlying.table.source_funds_help: "The funds contributing to this company's economic exposure. Repeated holdings in different funds are aggregated."
underlying.table.date_help: "The relevant source holdings date. Different funds may have different verified dates."
underlying.table.cap_help: "A consistent company capitalisation classification. Unverified classification is shown as Unknown."
underlying.table.benchmark_only: "Benchmark holding — no portfolio exposure"
underlying.table.unknown: "Unknown"
underlying.table.unmapped: "Unmapped"
underlying.table.partial: "Partial coverage"
underlying.table.results: "{count} matching rows"
underlying.table.page: "Showing {completed} of {total} rows"
underlying.table.virtualised_help: "The visible table is paged for performance. Exports include the full qualifying dataset, not only the rows currently displayed."

underlying.table.security_identity_help: "Security identity uses verified identifiers. Share classes and ADRs may share a company but remain distinct securities."
underlying.table.synthetic_help: "Synthetic and leveraged products are mapped to economic index exposure where verified. Posted swap collateral is not substituted for the tracked equity companies."
```

## 4.4 Country, sector and capitalisation charts

```yaml
underlying.country.title: "Country exposure"
underlying.country.axis: "Equity exposure (%)"
underlying.country.help: "Compares mapped, equity-normalised company country allocations with the global all-cap benchmark. Fund domicile does not determine company country."

underlying.sector.title: "Sector exposure"
underlying.sector.axis: "Equity exposure (%)"
underlying.sector.help: "Uses a consistent sector classification for portfolio and benchmark. Unknown classifications remain visible."

underlying.cap.title: "Market-capitalisation exposure"
underlying.cap.axis: "Equity exposure (%)"
underlying.cap.large: "Large cap"
underlying.cap.mid: "Mid cap"
underlying.cap.small: "Small cap"
underlying.cap.unknown: "Unknown"
underlying.cap.help: "Compares large-, mid- and small-company exposure under the same classification rules. The categories describe underlying companies, not the size of the holding ETF."

underlying.chart.portfolio: "Portfolio"
underlying.chart.benchmark: "VALL benchmark"
underlying.chart.active: "Difference"
```

Chart help contains the relevant definitions. No secondary methodology label or caveat is printed beside these charts.

## 4.5 Data management and exports

```yaml
underlying.action.save_copy: "Save copy"
underlying.action.copy: "Copy"
underlying.action.import_zip: "Import ZIP"
underlying.action.export_zip: "Export ZIP"

underlying.export.help: "Export the complete aggregate company/security comparison, benchmark-only rows, active differences, classification summaries, source dates and applicable coverage details."
underlying.export.complete: "Full underlying exposure"
underlying.export.filtered: "Include a separate filtered-view CSV"
underlying.export.success: "Underlying holdings export created."
underlying.export.missing: "The available holdings are incomplete. The export will preserve unmapped and unknown exposure rather than inventing underlying positions."

underlying.import.help: "Importing a portfolio changes the selected portfolio definition. It does not replace the curated underlying company or security dataset."
underlying.read_only: "Underlying company rows are calculated from fund allocations and verified exposure data. Edit fund weights on Dashboard."
```

## 4.6 Loading and empty states

```yaml
underlying.loading.title: "Preparing underlying holdings"
underlying.loading.download: "Reading verified holdings snapshots"
underlying.loading.identity: "Resolving duplicate securities and companies"
underlying.loading.expand: "Expanding economic fund exposures"
underlying.loading.compare: "Building the benchmark comparison"
underlying.loading.progress: "{completed} of {total} securities processed"

underlying.empty.no_portfolio: "Select or create a portfolio to view its underlying economic exposure."
underlying.empty.no_equity: "This portfolio has no mapped equity exposure. Cash, bonds and commodities remain in the portfolio reconciliation."
underlying.empty.no_match: "No companies match these filters. Clear a filter to see more results."
underlying.empty.missing_source: "Underlying holdings are not available for one or more selected instruments."
underlying.empty.no_benchmark: "The all-cap benchmark's required holdings are unavailable for this model release."
underlying.empty.incomplete: "A complete company comparison cannot be calculated until the missing exposure data are resolved."

underlying.warning.partial: "{value} of economic equity exposure is mapped. Unmapped holdings are retained in the reconciliation."
underlying.warning.date_mismatch: "The portfolio and benchmark use different available source dates. Review their dates before interpreting small active differences."
underlying.warning.low_coverage: "Company concentration is qualified because underlying mapping coverage is below the release threshold."
underlying.warning.leveraged: "Economic company exposure may exceed invested capital because this portfolio contains leveraged products."
underlying.warning.source_failure: "A required holdings file failed integrity validation. Affected company rows are unavailable."
```

---

# 5. Analysis

## 5.1 Page and portfolio management

```yaml
analysis.title: "Analysis"
analysis.subtitle: "Compare portfolio risk, long-term wealth and underlying exposures."

analysis.portfolios.title: "Portfolios"
analysis.portfolios.add: "Add portfolio"
analysis.portfolios.add_paste: "Paste"
analysis.portfolios.add_import: "Import ZIP"
analysis.portfolios.add_typical: "Typical"
analysis.portfolios.add_custom: "Custom"

analysis.portfolios.rename: "Rename portfolio"
analysis.portfolios.duplicate: "Duplicate portfolio"
analysis.portfolios.remove: "Remove portfolio"
analysis.portfolios.remove_confirm: "Remove {portfolio} from this comparison?"
analysis.portfolios.save: "Save copy"
analysis.portfolios.count: "{count} of 5 portfolios"
analysis.portfolios.limit: "You can compare up to five portfolios at once. Remove one before adding another."
analysis.portfolios.duplicate_success: "Portfolio duplicated."
analysis.portfolios.rename_success: "Portfolio renamed."
analysis.portfolios.remove_success: "Portfolio removed from this comparison."

analysis.portfolios.typical_help: "Choose one of the six documented reference strategies. Each uses the current release's benchmark recipe and costs."
analysis.portfolios.custom_help: "Create a portfolio using the same exact-weight editor and validation rules as Dashboard."
analysis.portfolios.paste_help: "Paste a valid Portfolio Construction Lab portfolio JSON definition."
analysis.portfolios.no_data: "This portfolio cannot be compared until its required model inputs are available."
analysis.portfolios.release_mismatch: "This portfolio belongs to a different release. Choose snapshot view or recalculate with the current model."
```

## 5.2 Metrics

```yaml
analysis.metrics.title: "Portfolio metrics"
analysis.metrics.expected_return: "Net expected annual return"
analysis.metrics.volatility: "Annual volatility"
analysis.metrics.effective: "Effective companies"
analysis.metrics.drawdown: "Historical maximum drawdown"
analysis.metrics.p20: "P20 cumulative return"
analysis.metrics.p20_cagr: "P20 annualised CAGR"
analysis.metrics.ter: "Weighted TER"
analysis.metrics.financing: "Modelled financing"
analysis.metrics.exposure: "Initial gross exposure"

analysis.metrics.p20_horizon: "Downside-return horizon"
analysis.metrics.p20_help: "P20 is the lower twentieth percentile of the modelled cumulative return distribution at the selected horizon."
analysis.metrics.cagr_help: "Compound annual growth corresponding to the selected cumulative return percentile, not the arithmetic expected annual return."
analysis.metrics.drawdown_help: "Calculated from a historical portfolio wealth series over the stated observation period and frequency. Period differences can make statistics non-comparable."
analysis.metrics.effective_help: "A concentration-adjusted measure of mapped underlying equity companies. It does not count bonds, physical metals or cash as companies."
analysis.metrics.link_horizons: "Link P20 and chart horizons"
analysis.metrics.link_horizons_help: "When enabled, changes to either horizon control update the other. Otherwise the controls work independently."
analysis.metrics.no_drawdown: "No adequate common observed history"
analysis.metrics.proxy_drawdown: "Proxy-extended drawdown"
```

## 5.3 Wealth-growth chart

```yaml
analysis.growth.title: "Projected portfolio wealth"
analysis.growth.subtitle_control: "Initial investment: £10,000"
analysis.growth.x_axis: "Years"
analysis.growth.y_axis: "Portfolio wealth (£)"
analysis.growth.start: "£10,000"

analysis.growth.horizon: "Projection horizon"
analysis.growth.horizon_help: "Choose the period over which analytical wealth outcomes are projected. This does not change the Dashboard frontier."
analysis.growth.band: "Uncertainty interval"
analysis.growth.band_default: "68.27% central interval"
analysis.growth.band_half_sigma: "0.5 standard deviation"
analysis.growth.band_one_sigma: "1 standard deviation"
analysis.growth.band_two_sigma: "2 standard deviations"
analysis.growth.band_p20_p80: "P20–P80"
analysis.growth.band_custom: "Custom percentiles"
analysis.growth.lower: "Lower percentile"
analysis.growth.upper: "Upper percentile"
analysis.growth.display: "Band display"
analysis.growth.display_shaded: "Shaded interval"
analysis.growth.display_boundary: "Boundaries only"
analysis.growth.scale: "Vertical scale"
analysis.growth.linear: "Linear"
analysis.growth.log: "Logarithmic"

analysis.growth.median: "Median wealth"
analysis.growth.lower_hover: "Lower bound"
analysis.growth.upper_hover: "Upper bound"
analysis.growth.year_hover: "Year {value}"
analysis.growth.wealth_hover: "Projected wealth: {value}"

analysis.growth.help: "Analytical buy-and-hold projections start from £10,000. Investor fund units remain fixed and fund weights drift over time. Distributing fund payments accumulate in GBP cash where supported by the release's exact cash-flow model. Bands are conditional, moment-matched approximations, not guarantees or complete market-event forecasts."
analysis.growth.method_help: "The projection uses calibrated asset log-return moments and joint covariance. It does not run a new Monte Carlo simulation every time you change the view."
analysis.growth.leverage_help: "For leveraged products, daily reset, changing finance costs, intraday barriers and issuer events can create outcomes not fully represented by long-horizon analytical bands."
analysis.growth.distribution_help: "Distributions are retained in the GBP cash account without repurchasing fund units. If exact distribution-event data are unavailable, any reinvested total-return approximation is explicitly identified in Methods and export metadata."
analysis.growth.parameter_help: "The band includes the uncertainty represented by the current model. Parameter-estimation uncertainty is included only where a separately validated covariance estimate is supplied."
analysis.growth.cash_help: "Cash projections hold the selected AER scenario constant for illustration. Actual account rates can change."
analysis.growth.log_scale_help: "A logarithmic scale shows equal proportional changes at equal vertical distances. It does not alter the underlying wealth calculation."

analysis.growth.invalid_percentiles: "Choose a lower percentile below the upper percentile."
analysis.growth.invalid_horizon: "Choose a supported positive projection horizon."
analysis.growth.log_invalid: "Logarithmic wealth display requires strictly positive plotted values."
analysis.growth.unavailable: "A coherent set of projection inputs is unavailable for this portfolio."
```

## 5.4 Band intersections

```yaml
analysis.intersection.title: "Band intersections"
analysis.intersection.portfolio_a: "First portfolio"
analysis.intersection.portfolio_b: "Second portfolio"
analysis.intersection.show: "Show intersection markers"
analysis.intersection.hide: "Hide intersection markers"

analysis.intersection.help: "A marker identifies a positive-time crossing between the lower band of one portfolio and the upper band of another. The shared initial £10,000 starting point is excluded. An intersection does not establish the probability that one portfolio will outperform the other."
analysis.intersection.crossing: "Interval boundary crossing at year {value}"
analysis.intersection.multiple: "{count} boundary crossings"
analysis.intersection.always_overlap: "These portfolio intervals overlap throughout the selected horizon."
analysis.intersection.never_overlap: "The intervals do not overlap after the initial common starting point."
analysis.intersection.identical: "These portfolios have identical bands. No separate crossing markers are needed."
analysis.intersection.none: "No positive-time boundary crossing was found."
analysis.intersection.need_two: "Add a second portfolio to compare uncertainty-band intersections."
analysis.intersection.same_selection: "Choose two different portfolios."
analysis.intersection.partial: "A boundary comparison is unavailable because one of the required projection bands is missing."
```

## 5.5 Country, sector and capitalisation comparisons

```yaml
analysis.comparison.title: "Underlying exposure comparison"
analysis.comparison.benchmark: "VALL — Global all-cap"
analysis.comparison.portfolio: "{portfolio}"
analysis.comparison.portfolio_share: "Portfolio equity exposure (%)"
analysis.comparison.benchmark_share: "Benchmark equity exposure (%)"
analysis.comparison.active: "Active difference (pp)"

analysis.comparison.country: "Country allocation"
analysis.comparison.sector: "Sector allocation"
analysis.comparison.cap: "Market-capitalisation allocation"

analysis.comparison.help: "Each portfolio is compared with the same all-cap benchmark using equity-normalised mapped economic exposures. Charts retain the same category order and scale for like-for-like comparison."
analysis.comparison.unknown_help: "Unknown holdings or classifications remain visible in the reconciliation rather than being assigned invented company attributes."
analysis.comparison.no_equity: "This portfolio has no mapped equity exposure to compare."
analysis.comparison.low_coverage: "The comparison is partial because underlying holdings coverage is incomplete."
```

## 5.6 Covariance and correlation

```yaml
analysis.covariance.title: "Constituent covariance"
analysis.covariance.mode_covariance: "Covariance"
analysis.covariance.mode_correlation: "Correlation"
analysis.covariance.frequency: "Annualised"
analysis.covariance.units: "Decimal return squared"
analysis.covariance.help: "Covariance is calculated from the selected release's fund-return risk model. Annualised covariance is monthly covariance multiplied by 12. Correlation rescales covariance by asset volatilities and is undefined for zero-variance assets."

analysis.covariance.row: "Instrument"
analysis.covariance.column: "Instrument"
analysis.covariance.cash: "N/A — deterministic cash correlation"
analysis.covariance.full_precision: "CSV exports retain the calculation precision and instrument identities."
analysis.covariance.no_holdings: "Add a portfolio with at least one nonzero holding to display constituent risk."
analysis.covariance.invalid: "A valid covariance matrix is unavailable for this portfolio."

analysis.cross_covariance.title: "Cross-portfolio covariance"
analysis.cross_correlation.title: "Cross-portfolio correlation"
analysis.cross_help: "Compares portfolio returns calculated from the same model covariance matrix. These are return-risk relationships, not correlations between long-horizon wealth paths."
analysis.cross_need_two: "Add a second portfolio to compare portfolio-level covariance or correlation."
```

## 5.7 Analysis warnings and empty states

```yaml
analysis.empty.initial: "Add a portfolio using Paste, Import ZIP, Typical or Custom."
analysis.empty.no_valid: "No valid portfolios are available for analysis."
analysis.empty.no_history: "The selected portfolios do not share an adequate observed period for comparable historical drawdowns."
analysis.empty.no_projection: "Projection inputs are unavailable for one or more selected portfolios."
analysis.empty.no_comparison: "At least one portfolio with mapped equity holdings is needed for underlying exposure comparisons."
analysis.empty.no_covariance: "Risk matrices require validated fund-return moments from the active model release."

analysis.warning.leverage: "This comparison includes leveraged products. Analytical projection bands do not capture every possible intraday reset, issuer or termination event."
analysis.warning.cash_scenario: "The projected cash return uses an assumed constant AER. The actual variable account rate may change."
analysis.warning.proxy: "One or more results use documented benchmark or factor proxies. Historical observations and modelled extensions are distinguished in Methods."
analysis.warning.distribution_proxy: "Exact distribution-event data are unavailable for one or more funds. A reinvested-return approximation is separately labelled and is not exact cash-retention accounting."
analysis.warning.period: "Historical comparisons use different available periods. Do not interpret the resulting drawdown figures as directly ranked performance."
analysis.warning.model_mismatch: "The selected portfolios use incompatible model releases. Recalculate on one release before comparing current risk and expected returns."
analysis.warning.bad_inputs: "A portfolio contains invalid allocations or unmatched instruments. Resolve these before calculating its current analysis."
```

Warnings appear in relevant portfolio management/status locations or help, never as decorative chart-side badges.

---

# 6. Methods Page

## 6.1 Navigation and headings

```yaml
methods.title: "Methods"
methods.subtitle: "The data, mathematics and assumptions behind Portfolio Construction Lab."

methods.section.abstract: "Abstract"
methods.section.scope: "Scope and investable universe"
methods.section.data: "Data and provenance"
methods.section.identity: "Fund and company identity"
methods.section.models: "Dual-model architecture"
methods.section.holdings: "Holdings-informed factor calibration"
methods.section.etf: "ETF-return calibration"
methods.section.returns: "Expected returns and costs"
methods.section.leverage: "Leveraged-product mechanics"
methods.section.bonds: "Fixed-income modelling"
methods.section.commodities: "Commodity and collateral modelling"
methods.section.cash: "GBP cash modelling"
methods.section.covariance: "Covariance and risk estimation"
methods.section.optimisation: "Efficient frontier optimisation"
methods.section.projections: "Buy-and-hold projections"
methods.section.benchmarks: "Reference strategies"
methods.section.lookthrough: "Underlying holdings"
methods.section.validation: "Validation and reproducibility"
methods.section.limitations: "Limitations"
methods.section.references: "References"
methods.section.contact: "Contact and corrections"

methods.document.title: "Scientific methodology"
methods.document.version: "Version V8.0"
methods.document.asof: "Research evidence cut-off: 18 October 2026"
methods.document.help: "This document explains the specified calculations and documented evidence. The active release diagnostics identify which calculations and source checks have been implemented and validated."
methods.document.print: "Print methods"
methods.document.copy: "Copy methods reference"
```

## 6.2 Model settings

```yaml
methods.model.title: "Model settings"
methods.model.label: "Equity exposure estimation"
methods.model.holdings: "Underlying companies"
methods.model.etf: "ETF returns"
methods.model.default: "Default: Underlying companies"

methods.model.holdings_help: "Uses dated fund holdings, underlying company financial characteristics and empirically calibrated regional factor exposures. Missing characteristics use explicit peers or regional priors with disclosed coverage."
methods.model.etf_help: "Uses fund-return histories and regional factor regressions to estimate exposures. Historical fitted alpha is not automatically carried into forward expected returns."
methods.model.shared_help: "Both models use the same core universe, non-equity mechanics, currency rules, cost accounting and optimisation constraints."
methods.model.validation_help: "Model comparisons first hold histories, fees and covariance assumptions consistent, then examine native risk-model differences separately."
methods.model.change: "Apply model"
methods.model.change_warning: "Changing the model updates expected-return estimates and may select different frontier allocations. Existing portfolio weights are preserved until you explicitly apply another allocation."

methods.model.status_ready: "Model available"
methods.model.status_partial: "Model available with documented proxy coverage"
methods.model.status_unavailable: "Model unavailable — required inputs missing"
methods.model.status_loading: "Loading model diagnostics"
```

## 6.3 Assumption and source information

```yaml
methods.assumptions.title: "Assumption register"
methods.assumptions.help: "Assumed quantities are not historical observations or issuer guarantees. Every material prior has a source, effective date, selected value and sensitivity where appropriate."

methods.assumptions.column.parameter: "Parameter"
methods.assumptions.column.value: "Current value"
methods.assumptions.column.unit: "Unit"
methods.assumptions.column.origin: "Evidence category"
methods.assumptions.column.date: "As-of date"
methods.assumptions.column.sensitivity: "Sensitivity"

methods.assumptions.type.observed: "Observed"
methods.assumptions.type.calculated: "Calculated"
methods.assumptions.type.proxy: "Proxy"
methods.assumptions.type.assumed: "Assumed"
methods.assumptions.type.unverified: "Unverified"

methods.assumptions.cash_observed: "Observed Trading 212 Invest GBP AER: 3.80% on 18 October 2026."
methods.assumptions.cash_scenario: "Alternative planning cash AER: 4.25%. This is not the observed provider quote."
methods.assumptions.inflation: "Default developed-market inflation planning assumption: 2.00%, with 1.00%, 3.00% and 4.00% sensitivity cases."
methods.assumptions.leverage_spread: "Where an issuer funding spread remains unverified, the provisional assumption is 2.00% annually on applicable borrowed notional, tested at 1.00% and 3.00%."
methods.assumptions.credit: "Default expected-credit-loss haircuts are planning assumptions rather than issuer-published default forecasts."
methods.assumptions.futures: "Expected futures excess return is provisionally set to zero when no defensible forecast has been established."

methods.sources.title: "Data sources and coverage"
methods.sources.instrument: "Instrument evidence"
methods.sources.history: "Historical return coverage"
methods.sources.holdings: "Holdings coverage"
methods.sources.characteristics: "Company characteristics"
methods.sources.benchmarks: "Benchmark data"
methods.sources.release: "Release provenance"
methods.sources.unresolved: "Unresolved external source limitations"
methods.sources.none: "No verified source available for this field."
methods.sources.help: "Published factsheets, downloadable issuer files, benchmark methodology and model assumptions have different evidence classifications. Missing source bytes are not replaced by fictional histories."
```

## 6.4 Source limitation text

```yaml
methods.limitations.title: "Important limitations"
methods.limitations.intro: "The model combines observed instrument data with calibrated estimates and explicit forward assumptions. Not all third-party histories, holdings and product-contract details are publicly retrievable."

methods.limitations.vanguard: "VAGS and VEMT issuer holdings and price download controls were identified, but reusable direct export links and complete downloaded files were not verified in Stream C."
methods.limitations.invesco: "CMOP product and index methodology information was identified, but a complete direct historical CSV was not verified."
methods.limitations.wisdomtree: "WisdomTree commodity historical export controls were observed, but complete direct source files were not verified. The exact daily accrual convention for the displayed annual swap rate remains unresolved."
methods.limitations.metals: "SGLN and SSLN bullion reports were identified. Direct bullion backing CSV files were not verified."
methods.limitations.cash: "The cash AER is variable. No authenticated customer-specific bank/QMMF allocation or historical Trading 212 Invest rate path was obtained."
methods.limitations.vags_yield: "VAGS 4.83% is a published underlying local-currency YTW, not a verified net-GBP hedged expected return."
methods.limitations.ghys_yield: "GHYS 7.46% published YTM has no explicitly verified FX-forward-carry inclusion convention."
methods.limitations.itpg_yield: "ITPG real yield is linked to US CPI-U; the published real yield is not a verified net-GBP nominal forecast."
methods.limitations.duration: "Vanguard Average Duration has not been formally confirmed as equivalent to effective or option-adjusted duration."
methods.limitations.credit: "Published ratings do not provide a complete set of future default probabilities or recovery assumptions."
methods.limitations.futures: "Future roll yields and futures curve paths are not known from current spot prices."
methods.limitations.leverage: "Daily closing prices cannot reproduce every future intraday restrike, price gap or issuer termination event."
methods.limitations.holdings: "The design supports approximately 15,000 securities, but actual mapped counts and characteristic coverage are determined by available source data."
methods.limitations.projections: "Moment-matched uncertainty bands are conditional approximations. They do not guarantee investment outcomes or necessarily include all model-parameter and event risk."
methods.limitations.history: "Proxy-extended histories are counterfactual reconstructions and must remain distinct from actual fund observations."
```

## 6.5 Release diagnostics

```yaml
methods.diagnostics.title: "Release diagnostics"
methods.diagnostics.release: "Release ID"
methods.diagnostics.code_hash: "Model code hash"
methods.diagnostics.data_hash: "Data hash"
methods.diagnostics.snapshot: "Data snapshot"
methods.diagnostics.family: "Model family"
methods.diagnostics.instrument_count: "Admitted instruments"
methods.diagnostics.mapped_count: "Mapped securities"
methods.diagnostics.company_count: "Mapped companies"
methods.diagnostics.coverage: "Economic exposure coverage"
methods.diagnostics.direct_characteristics: "Direct characteristic coverage"
methods.diagnostics.covariance: "Covariance validation"
methods.diagnostics.frontier: "Frontier certification"
methods.diagnostics.projections: "Projection validation"
methods.diagnostics.sources: "Source verification"
methods.diagnostics.dependencies: "Calculation dependencies"

methods.diagnostics.help: "Diagnostics identify the exact datasets, calculations and quality checks used by the active immutable release. Planned acceptance criteria are not displayed as achieved results until independently validated."
methods.diagnostics.missing: "This diagnostic has not been supplied by the active release."
methods.diagnostics.not_certified: "This calculation has not satisfied the specified release-quality gate."
methods.diagnostics.failed: "The release validation failed. Affected calculations must not be presented as certified."
methods.diagnostics.pending: "Validation evidence is pending."
methods.diagnostics.complete: "Validation completed."
```

## 6.6 Contact

```yaml
methods.contact.title: "Contact and corrections"
methods.contact.intro: "Have a data correction, instrument suggestion or methodology question?"
methods.contact.email: "mail@robertgardner.co.uk"
methods.contact.help: "For a specific data issue, include the fund name, ISIN, source URL, publication date and field requiring review."
methods.contact.copy: "Copy email address"
methods.contact.copied: "Email address copied."
methods.contact.disclaimer: "This application is an investment research tool, not personal financial advice."
```

---

# 7. Cross-Page Warnings and Failure Handling

## 7.1 Warnings that require direct user action

These messages may appear in contextual status areas or forms:

```yaml
warning.invalid_allocation: "Your weights do not total 100.00%. Fix the draft or choose Normalise draft weights."
warning.unknown_instrument: "An instrument cannot be matched to a verified share class. Review its ISIN and listing."
warning.missing_release: "Required model data are missing. Current calculations cannot be completed safely."
warning.corrupt_source: "A source file failed validation. Affected calculations are unavailable."
warning.incompatible_snapshot: "This result belongs to a different release. Recalculate before comparing it with current results."
warning.bad_export: "This export cannot be completed because the portfolio or release data failed validation."
warning.import_security: "The selected archive contains unsupported content and was rejected."
warning.outdated_inputs: "One or more inputs are older than the active release policy permits. Review their source dates."
warning.solver_uncertified: "The requested frontier point lacks the required optimisation certificate."
```

## 7.2 Caveats that belong in tooltips or Methods

These should not become persistent chart-side banners:

```yaml
caveat.expected_returns: "Expected returns are estimates, not guaranteed future performance."
caveat.leverage: "Daily leveraged returns are path-dependent and sensitive to financing costs, volatility and intraday events."
caveat.cash: "The selected cash AER is a variable-rate scenario held constant for modelling."
caveat.distributions: "Distributing fund income enters GBP cash without repurchasing fund units under the default investor policy."
caveat.proxy_history: "Modelled return proxies are distinct from observed fund history."
caveat.credit: "Credit-loss haircuts are assumptions unless supported by separately verified default and recovery evidence."
caveat.fx: "GBP trading currency does not establish GBP-hedged economic exposure."
caveat.covariance: "Covariance is estimated from aligned return evidence and may include shrinkage or documented proxies."
caveat.company_coverage: "Company exposure and fundamentals coverage can differ; unmapped economic exposure remains visible."
caveat.bands: "Forecast intervals are conditional model approximations, not exhaustive probability bounds."
caveat.frontier: "Certified optimisation refers to the mathematical problem under the specified inputs, not certainty about those inputs."
```

## 7.3 Empty versus zero versus unknown

| State | Display | Interpretation |
|---|---|---|
| Valid calculated zero | `0.00%` or `£0` | Genuine numerical result |
| Not applicable | `N/A` | Metric does not apply |
| Source unavailable | `Not available` | No verified source value |
| Calculation not ready | `Calculating…` | Valid task still in progress |
| Model assumption | Labelled scenario value | Explicit prior, not observation |
| Partially observed | Qualified value with coverage | Available subset only |
| Integrity failure | Specific error and retry | Cannot safely produce result |

An explicitly published zero may be retained as zero.

A blank provider field is not evidence of zero.

A missing historical return is not replaced with a fabricated observation.

---

# 8. Financial Formatting and Accessibility

## 8.1 Formatting rules

```yaml
format.currency.gbp: "GBP"
format.currency.symbol: "£"
format.percentage: "{value}%"
format.percentage_points: "{value} pp"
format.multiple: "{value}×"
format.years: "{value} years"
format.basis_points: "{value} bps"
format.date: "{date}"
format.unknown: "N/A"
format.missing: "Not available"
format.not_calculated: "Not calculated"
```

Displayed allocation percentages use two decimal places.

Underlying company exposures may require greater precision where positions are materially smaller than 0.01%; preserve full precision in exports.

Expected-return and volatility values use clearly labelled annual conventions.

Covariance and correlation values retain enough display precision to distinguish meaningful small estimates, with full stored precision in CSV exports.

## 8.2 Accessibility

```yaml
accessibility.loading: "Portfolio data loading: {completed} of {total}"
accessibility.loading_unknown: "Portfolio data loading; total work not yet known"
accessibility.ready: "Portfolio calculations ready"
accessibility.failed: "Portfolio loading failed. Retry is available."

accessibility.theme: "Toggle light or dark appearance"
accessibility.help: "Open information about this calculation"
accessibility.frontier: "Select efficient-frontier position from zero to one hundred"
accessibility.frontier_value: "Frontier position {value}"
accessibility.category: "Toggle investable category {category}"
accessibility.chart: "Interactive financial chart"
accessibility.portfolio: "Portfolio {portfolio}"
accessibility.table: "Sortable financial data table"
accessibility.modal_close: "Close dialog"
accessibility.copy: "Copy portfolio definition"
accessibility.export: "Download portfolio export"
```

Controls must support keyboard operation, focus visibility and screen-reader descriptions.

Help content must be accessible through hover, focus, tap and keyboard selection.

The loading ring must provide an accessible status independent of its animation.

Users requesting reduced motion must not depend on animation to understand loading progress.

Light and dark palettes must preserve adequate contrast for financial values, errors, focus indicators, charts and table contents.

---

# 9. Implementation Acceptance Checklist

The interface passes Stage 07 copy integration when all of the following are true:

- [ ] The application contains exactly four pages: Dashboard, Underlying Holdings, Analysis and Methods.
- [ ] The displayed product version is Version V8.0, without a second model-number badge.
- [ ] The model selector uses understandable model names and loads matching calculations.
- [ ] All financial chart titles and units are consistent with the Methods definitions.
- [ ] No chart has decorative methodology badges, repeated caveat captions or warning ribbons.
- [ ] Every material forecast assumption has contextual help and a corresponding Methods explanation.
- [ ] The six reference strategies use the specified names.
- [ ] The frontier selector is labelled as a position rather than volatility or allocation.
- [ ] Allocation total and minimum buy-in validation uses exact basis points.
- [ ] Invalid drafts never silently replace the last valid portfolio.
- [ ] Fund identity help includes ISIN, exchange, quote currency/unit and hedging status.
- [ ] GBP/GBx distinctions do not imply an economic hedging status.
- [ ] Cash interest distinguishes 3.80% observed AER and 4.25% planning AER.
- [ ] Stream C's missing source fields are not displayed as numerical zeros.
- [ ] Effective companies and correlation-based diversification are distinguished.
- [ ] Historical drawdown identifies its actual period and frequency.
- [ ] Analysis can compare one to five portfolios.
- [ ] Growth chart horizons and P20 metric horizons can operate independently.
- [ ] Distributing fund cash-retention and reinvestment proxies are properly distinguished.
- [ ] Uncertainty bands and intersection markers carry appropriate help.
- [ ] Underlying comparison includes benchmark-only companies.
- [ ] Underlying exports preserve the full dataset, not just the visible viewport.
- [ ] Cash correlation is not misrepresented as a measured statistic.
- [ ] Portfolio import/export messages distinguish validation and release compatibility.
- [ ] The top loading ring reports genuine progress or indeterminate work without inventing counts.
- [ ] Loading failures provide an actionable retry state.
- [ ] Light/dark switching updates the actual application appearance.
- [ ] Screen-reader and keyboard access work across all four pages.
- [ ] The Methods page exposes data limitations, validation, sources and contact information.
- [ ] The finished interface is reviewed at desktop, tablet and mobile widths in both colour themes.

---

# 10. Copy Governance

This file is the canonical Stage 07 source for user-facing interface wording.

The implementation should centralise copy keys rather than duplicating strings across Streamlit page modules.

When future model or data changes affect user interpretation, update the Methods document and its corresponding tooltip or status text together.

Do not change a mathematical definition in UI text without checking the calculation contract.

Do not replace a meaningful missing-data state with a visually attractive default value.

Do not introduce new chart-side methodology badges or secondary narrative captions during UI polish.

The aim is an interface that is concise during normal portfolio research and mathematically transparent whenever users request an explanation.