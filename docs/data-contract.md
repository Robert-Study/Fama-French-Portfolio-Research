# Research input contract

The app accepts a ZIP containing exactly these five UTF-8 files at its root. The compressed and uncompressed bundle must each be at most 10 MB. Files are read in memory; nothing is extracted or executed.

Preparing this bundle is part of the project work, not a software-maintenance task for the person testing the app. Recover existing provider exports first. Only the missing factor, currency, cash and source evidence should be acquired.

| File | Required columns |
| --- | --- |
| `funds.csv` | `ETF_ID,Name,ISIN,AssetClass,Region,Hedged,Leverage,TER,ReturnKind,Source` |
| `returns.csv` | `Month` followed by exactly the ETF IDs in `funds.csv` |
| `factors.csv` | `Month,Mkt-RF,SMB,HML,RMW,CMA,RF` in this order |
| `cash_fx.csv` | `Month,GBP_RF,USD_GBP` |
| `manifest.json` | The declarations and sources below |

## Fund metadata

- One row per share class; IDs must be unique and match the return columns.
- `AssetClass` must be `Equity`, `Region` must be `Developed`, `Hedged` must be `False` and `Leverage` must be `1`. These declarations are scope checks, not independent verification of the fund.
- `TER` is an annual decimal: `0.002` means 0.2%. Values outside 0–0.05 require review rather than automatic acceptance.
- `ReturnKind` is `actual_fund` or `documented_index_proxy`. A documented proxy is a clearly identified published index series, not an invented pre-inception fund history. Mixed/spliced histories require a future contract extension with segment-level provenance.
- `Source` identifies the dated share-class/fee evidence and any proxy identity. Record distributing/accumulating treatment, hedging, withholding-tax convention and distributions reinvested in the accompanying source descriptions.
- Ticker, trading currency and fund base currency are not interchangeable. Returns in this contract are GBP regardless of listing currency.

## Time series

Use monthly simple returns as decimals, never prices, log returns or percentages. `0.01` means a 1% return. Use one month per row in increasing order, with no duplicates, gaps, missing observations or infinities. `Month` can be `YYYY-MM` or a date in the relevant calendar month; the parser aligns by calendar month and does not interpret a first-of-month label as a one-day observation.

Fund data must contain at least 72 common, complete months and cover precisely the same fund IDs as the metadata. Complete history is required because pairwise deletion can produce inconsistent covariance. Exclude unsupported funds rather than fill missing returns with zero.

Factor data are French **developed-market FF5 in USD**, with French `RF`. Convert the provider's percentage values to decimals during bundle preparation. The market column is excess return; the four style columns are long–short spreads. Exclude any annual-return section in the provider file.

`GBP_RF` is the documented monthly simple GBP cash return. `USD_GBP` is the simple monthly return of USD measured in GBP: `(GBP per USD at end / GBP per USD at start) - 1`. If the source quotes USD per GBP, invert the exchange rate first. Use consistent month-end cutoffs. Do not substitute zero for missing FX or cash.

Factor and cash/FX files must have exactly matching months. They may start before the fund-return file, but must cover every fund month and end at the same information date. The longer compatible factor sample supplies the default premium assumptions; the selected fund window supplies regression and covariance observations. Upload complete months only.

## Manifest

The fixed declarations below must match exactly. Replace each source description with the actual provider, series identifier, dated download, covered period and transformations. Placeholder descriptions in this example are not evidence.

```json
{
  "schema_version": 1,
  "return_currency": "GBP",
  "return_type": "monthly_simple_net_total",
  "factor_currency": "USD",
  "factor_region": "Developed",
  "units": "decimal",
  "fx_definition": "GBP per USD simple return",
  "sources": {
    "funds": "Dated share-class, fee and scope evidence",
    "returns": "Provider, series, reinvestment/tax convention and currency conversion",
    "factors": "French developed-market FF5 file, download date, percent-to-decimal conversion",
    "cash": "GBP cash series, provider and monthly return construction",
    "fx": "FX series, quote direction, month-end convention and provider"
  }
}
```

The ZIP's SHA-256 is recorded in every run. Uploading a conforming manifest does not authenticate its claims or prove the model is suitable. Research outputs retain that limitation.

## What can be reused now

All six original V5 CSVs and the manifest are committed without changing their bytes. Fund identities, saved holdings and classifications provide starting points for review. The historical return CSV can exercise the legacy workflow. Its inherited splices and GBP claims cannot pass the evidence review merely by being copied into a new ZIP.

The minimum remaining work is to recover the original fund/index exports and prepare matching French, FX and cash data. The company-characteristic stage additionally needs a dated, matched company panel; adding current fundamentals alone would not implement that calibration.
