# Constituent inputs: incomplete

Checked 19 October 2026. Release date: 2026-10-18.

`constituent_sources.json` is a **pending input manifest**, not evidence that
holdings have been acquired. It lists exactly the 48 equity funds in fixture
order. The 20 cash, bond and commodity instruments are excluded.

**Verified snapshots delivered: 0 of 48.** None of the referenced constituent
CSV files exists. The manifest dates and source labels are the requested input
contract, not verified observations. Do not certify production readiness from
the manifest or passing unit tests. The release builder must remain partial.

The local acquisition ledger has no populated holdings download URLs. Existing
legacy holdings include assumed weights and missing security ISINs. They cannot
be relabelled as verified 18 October 2026 factsheet observations. The separate
VALL benchmark input is not a fund constituent snapshot and cannot supply other
funds' weights.

Primary-source spot checks:

- [Vanguard VWRP](https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits)
  shows holdings dated 30 September 2026.
- [BlackRock SWDA](https://www.blackrock.com/uk/intermediaries/products/251882/ishares-core-msci-world-ucits-etf-acc)
  shows portfolio characteristics dated 14 October 2026. The retrieved holdings
  table does not establish an 18 October snapshot.

These checks do not prove that other dated exports are unavailable. They do not
establish the source date required by this manifest.

## Completion requirements

Acquire dated issuer holdings and an audited security-to-company crosswalk.
Keep the original source URLs, dates and file hashes in an accompanying audit
record; the generic source label alone is insufficient lineage. Do not replace
an actual source date with a retrieval date or the release date. If earlier
snapshots are used, explicitly revise the requested fixed source-date contract.

Each CSV must contain exactly:
`security_id,company_id,company,ticker,country,sector,cap_bucket,weight`.
Verify 12-character ISINs, including checksums and issuer identity. Aggregate
share classes through a consistent company ID and canonical company metadata.
Retain positive decimal weights and missing mass; never inflate weights.
Leveraged funds require unlevered underlying index constituents, not collateral.

After all 48 sources are populated, run the secondary builder and the two
requested test modules. Check all 48 equity rows have positive mass and all 20
non-equity rows remain zero. Test fixtures use synthetic inputs and do not
certify the provenance of production data.
