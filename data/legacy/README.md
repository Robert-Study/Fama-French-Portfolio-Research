# Rob Portfolio V5

Open **Rob_Portfolio_V5.xlsx**. Edit the blue proposed weights on Dashboard, keeping their total at 100%. Change the lump sum as needed. Current weights are editable on Portfolio. All portfolio calculations work from the populated tables without Power Query setup.

The model assumes a nominal GBP lump sum held for 20 years, with no ETF-level rebalancing, contributions, inflation adjustment, shorting or optimisation. Fund-internal rebalancing is part of the inherited fund/index return assumptions.

## What is complete

- Seven visible sheets, with compact inputs and live current/proposed comparisons.
- External holdings and security data: no large holdings formula grid inside Excel.
- Buy-and-hold history and terminal-wealth calculations that let ETF weights drift.
- Covariance rebuilt from monthly log returns, with data-dependent correlation shrinkage.
- P20/P50/P80, expected terminal wealth, initial volatility and separate return-assumption sensitivities.
- Twelve Power Query definitions, strict joins and a fixed output layout.

## Important evidence limits

This is a **provisional research implementation**, not the fully calibrated model originally envisaged. The saved V5 supplied return histories and assumptions but not the underlying provider downloads or the code that created its splices. Their claimed GBP conversion and net-total-return treatment could not be independently verified. They are retained transparently rather than represented as newly sourced observations.

Dated company fundamentals were not supplied. The `fundamentals.csv` file therefore contains headers only. Value, profitability and momentum return contributions remain labelled judgemental priors. Their retention weights are not data coverage. Raw fundamental coverage is zero. Adding data will populate the raw-metric summaries; it will **not automatically create a statistically calibrated percentage-point return bridge**. That mapping still needs dated characteristic spreads, compatible published factor returns and out-of-sample checks. The size signal also retains the earlier workbook's classifications and scale assumptions.

Currency allocations, fund costs and listing identities are inherited. Trading 212 availability and ISA eligibility have not been freshly verified. The historical return CSV is treated as already net of fees; deducting TER again would risk double charging. Regional and factor-premium assumptions still need an overlap/double-counting review.

## Power Query setup — Windows desktop Excel

1. Extract the entire ZIP into a local folder, retaining `Data` and `Queries` beside the workbook.
2. Close the workbook in Excel.
3. Open PowerShell in the extracted folder and run:

   ```powershell
   .\Install-PowerQuery.ps1
   ```

4. Open the workbook. Subsequent source changes use **Data → Refresh All**. Editing trial weights needs no refresh.

The setup script uses Excel's native Queries API. It installs the queries into a working copy, refreshes the four small output ranges synchronously, checks for formula errors, then saves a backup and replaces the selected workbook. It does not change Excel's macro trust settings or the machine's script-execution policy. If your policy blocks the script, use the manual route below or ask your administrator.

**The script and M queries have not been executed in desktop Excel in this environment.** Native installation, privacy prompts and Refresh All behaviour remain to be verified on your machine. The delivered workbook contains populated outputs, but no embedded native query connections yet. Keep the source folder beside the workbook. If you move it after installation, rerun setup to update the path.

### Manual setup

In Excel, create a blank query for each `.m` file in `Queries/query_order.json`, using its filename without `.m` as the query name. Paste its contents into Advanced Editor. Set `pDataFolder` to a quoted absolute path to the extracted `Data` folder. Staging queries and functions are connection-only. Load only the four outputs in `Queries/load_map.json` at their specified cells, replacing their existing populated snapshot ranges after saving a backup. Do not append a second copy. Mac Excel support and the manual load process have not been tested here.

## Data layout

| File | Purpose |
|---|---|
| `holdings.csv` | One fund-membership table with signed source weights and legacy row references. |
| `securities.csv` | Unique local keys and inherited names, classifications and ISINs. |
| `fundamentals.csv` | Dated raw company metrics; currently empty. One observation per holding key. |
| `fund_master.csv` | Fixed 29-fund universe, ISINs, costs and source limitations. |
| `monthly_returns.csv` | One inherited 360-month return table, August 1996–July 2026. |
| `legacy_factor_priors.csv` | Audit copy of inherited judgemental priors. Live editable assumptions remain in Factor Calibration. |
| `source_manifest.json` | Provenance notes and file checksums. |

Power Query joins holdings to security attributes and aggregates once per refresh. It loads a 29-row size table, a 29-row raw-fundamental table, cumulative ETF return multiples and a 29×29 log-covariance matrix. The detailed holdings remain external. Headers, dates and fund order are fixed for this research snapshot; changing the universe or extending the history requires an explicit model revision.

The source contains negative internal cash/derivative balances and some anomalous security records. These are preserved for audit, not clipped or silently normalised. Long-only validation applies to the ETF portfolio weights. Conflicting attributes under a legacy security key are kept as separate variants. Counts of these records must not be interpreted as distinct companies or effective diversification. Country, market and sector classifications are inherited and may conflict with a chosen index taxonomy.

## Forecast calculation and checks

For each ETF, the annual log drift is `ln(1 + compound-return assumption)`. The model calculates its expected terminal multiple and pairwise terminal covariance. It sums those moments using the starting holdings and matches the resulting portfolio mean and variance to a lognormal distribution. This is a fast approximation to a sum of correlated ETF values; it does not rebalance them.

P20/P50/P80 reflect market risk conditional on the assumptions. The separate lower/upper return scenarios shift log drifts by the assumed sensitivity. They are not empirically calibrated confidence intervals. Constant parameters and Gaussian log increments do not capture all long-horizon risks.

Checks performed on the exported workbook include current/proposed equality, a 100% VALL trial, negative and zero-total weight rejection, zero lump sum, formula-error scan, independent moment reconstruction, covariance symmetry and positive eigenvalues. With the supplied current weights, a separate 200,000-path simulation differed from the analytic approximation by about −2.9% at P20, −0.2% at the median and +1.7% at P80. These errors can change for other trial portfolios. This checks the approximation, not the predictive accuracy of the return assumptions.

Sources for implementation: [Microsoft Queries API](https://learn.microsoft.com/en-us/office/vba/api/excel.queries.add), [Table.Group](https://learn.microsoft.com/en-us/powerquery-m/table-group), [Table.NestedJoin](https://learn.microsoft.com/en-us/powerquery-m/table-nestedjoin), and [Chen et al., covariance shrinkage](https://arxiv.org/abs/0907.4698). The covariance estimator is an OAS-style adaptation applied to standardised log returns; its Gaussian optimality results should not be assumed to hold for these reconstructed investment histories.
