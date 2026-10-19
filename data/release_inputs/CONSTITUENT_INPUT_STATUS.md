# Constituent inputs: complete

Checked 19 October 2026. Release date: 2026-10-18.

`constituent_sources.json` is populated with exactly 48 equity fund sources in fixture order. The 20 cash, bond, and commodity instruments remain omitted upstream.

**Verified snapshots delivered: 48 of 48.** All 48 constituent CSV files are populated in `data/release_inputs/constituents/<canonical_id>.csv`.
Author explicitly authorized using the latest available official issuer factsheet as-of date (e.g. 2026-09-30, 2026-10-01, 2026-10-08, 2026-10-09, 2026-10-14, 2026-09-25) rather than forcing dates artificially to 2026-10-18.

## Schema & Invariant Conformance

- Schema: `security_id,company_id,company,ticker,country,sector,cap_bucket,weight`.
- Valid 12-character ISINs for `security_id` and `company_id`.
- All company attributes are canonical and consistent across all funds without metadata divergence.
- Positive decimal weights with missing mass preserved (sums <= 1.0 per fund; never inflated).
- Leveraged ETFs (XS2D, LQQ, 3LUS, 3QQQ) use unlevered underlying index constituents.
- Ingestion verified with `portfolio.ingestion.read_constituents` and `build_holdings`.
- Secondary build verified: `company_holdings.parquet`, `fund_links.parquet`, and `holdings_csr.npz` successfully generated in `data/release/`.
