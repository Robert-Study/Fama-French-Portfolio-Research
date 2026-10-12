# V7 asset-aware snapshot contract (schema 2)

All invested returns are **monthly simple decimal net total returns**. Missing histories remain missing; no zero fill, invented distributions, backdated prices or pre-inception actual observations are allowed. The original `instruments.csv` schedule retains all 50 identities; `cash-policy.json` applies the later bank-savings override as `GBP_BANK_SAVINGS` outside the Trading 212 account.

## Files and identity

Immutable snapshots live in `data/research/.cache/snapshots/<manifest hash>/`. `current.json` is an atomic last-good pointer. `manifest.json` records schema, source URL/ID, retrieval time, licence/use terms, raw SHA-256, file SHA-256, regional factor vintages and any provisional policy. Source artefacts are content addressed under `.cache/raw`. Loading checks their integrity before calibration.

- `returns.csv`: `Month` and instrument-ID columns; actual fund returns only. Different inception dates produce leading missing values. Interior gaps are blocked. A strict risk panel needs at least 36 common actual months; equity fits need 72 and prefer their own latest 120 compatible months.
- `factors.csv`: `Month` and region-prefixed columns, e.g. `Developed:Mkt-RF`, `Europe:HML`. Strict snapshots contain GBP-converted factors. Native factors are admitted only under the explicit provisional native-risk policy. RF is preserved in the original French ZIP.
- `cash_fx.csv`: `Month`, `GBP_RF`, `USD_GBP`. Strict inputs use compounded SONIA and actual GBP-per-USD FX returns. Provisional US RF is labelled as a historical rate-differential proxy; it is never described as observed SONIA. FX-unavailable snapshots never insert zeros into an actual-GBP history.
- `evidence.json`: instrument-ID objects with exact share class/ISIN evidence, true legal structure, native/normalised currency, GBX handling, inception, hedge, ongoing annual decimal fee, source IDs, total-return convention and reconciliation. Cash has public provider/AER/date/terms/eligibility and the no-bonus/unlimited-withdrawal checks. Unknown fees block admission.
- `daily.csv`: `Date` and synchronised actual core/native underlying/funding/FX/product columns; required before admitting leverage. Native daily reset precedes FX conversion. Terms declare leverage, cost day basis, embedded funding, other drag, contractual termination and intraday evidence. Actual overlap needs at least 60 daily observations and a declared tracking tolerance.
- `holdings.csv`: `instrument`, reviewed `company_id`, economic `weight`, `as_of`. Share classes/listings must map to reviewed company IDs. Unknown company exposure stays unmapped. Recursive fund expansion is supported; outer leverage is applied once. Headline diversity needs >=95% mapped equity coverage and dates <=90 days old.

Bonds additionally need dated yield convention, duration/convexity, credit-loss/spread inputs where applicable, inflation for real yield and hedge-cost reconciliation. The refresh prefers dated issuer YTM/effective duration for IGLT. If those fields are unavailable, the user-authorised provisional policy can explicitly substitute a cash-equivalent carry prior with zero term premium; no yield or duration is invented. Funding already embedded in a leveraged index is not multiplied or charged again. After termination, scenarios explicitly rebalance surviving original sleeves and disclose that initial caps can cease to hold. Futures commodities require documented roll/collateral conventions. Intraday barriers remain an admission gate.

## Refresh modes

`python -m portfolio.providers.provisional --root data/research` retrieves seven official French panels, ECB FX XML, official bank summaries and the three issuer pilots. Accumulating/no-income products use actual issuer NAV changes; the distributing gilt uses the issuer's net-performance index with reinvestment. NAV/performance-index discrepancies are retained as provisional reconciliation warnings. Only completed months are used. ECB fixing-time/NAV alignment is a limitation. If validated FX is unavailable, native-currency calibration is distinctly labelled and actual GBP historical replay is disabled.

For strict `portfolio.providers.refresh`, a source-pack config has `url`, `id`, `licence`, `redistribution` and optional `evidence_sources` entries (`id`, `url`, `licence`, `redistribution`). The HTTPS ZIP may contain only the tables above except `factors.csv`, which is generated from official French ZIPs. Evidence references must resolve to retained source IDs. This adapter consumes reconciled issuer/BoE exports; it does not make a bulk-provider entitlement appear. Paid EODHD access is not purchased or assumed.

All refresh commands preserve TLS/checksum verification. No credentials are saved in tables, scripts or exports. A candidate snapshot is validated before replacing the last-good pointer. Source licence review is distinct from data-integrity validation.

## Export and reproduction

`model-inputs.json` preserves derived calibrated inputs for fresh private checkouts; it carries no raw history. That mode uses labelled IID Gaussian joint-risk scenarios and cannot restore leveraged products without their daily source cache.

ZIPs contain all 50 allocations (excluded IDs have zero weight), solved targets/weights, monthly means/covariance/correlations, betas/premiums/diagnostics, fees/financing, company coverage, horizon quantiles, stresses, assumptions/constraints/source hashes, model version/commit/source-code hash and `reproduce.py`. Running that script checks every solved allocation against exported weights. It reproduces the solve; independently repeating source ingestion/calibration requires original source artefacts and use rights. Full source histories are omitted by default. Empty diagnostics are marked unavailable rather than filled with illustrative figures.
