# Fama–French Portfolio Research — V7

A private Streamlit research app with **Dashboard, Holdings, Compare and Methods** pages. Model version **0.2.0**, Python **3.14.8**. It solves long-only, fully invested portfolios with explicit asset-category and gross-exposure constraints. The visible 0–100 controls select solved frontier positions; expected return is annualised arithmetic return, not CAGR.

The revised [implementation specification](docs/v7-build-plan.md), [supplied scientific report](docs/v7-methods-report.md), and [implementation/evidence status](docs/v7-implementation-status.md) explain the model and its boundaries.

## Current evidence and assumptions

The selected schedule remains 49 securities plus a cash sleeve. The user's later instruction replaces Trading 212 cash with a **separate UK bank savings account outside Trading 212**. The original 50-item CSV is preserved; `cash-policy.json` records that override. The current publicly verified bank quote is in `bank-quote.json`; rates are variable and expire for admission after 30 days. No individual account eligibility or deposit-protection headroom is checked.

An explicit refresh job calibrates a **provisional pilot** using published French regional FF5 files and actual issuer histories for IWFV, SGLN and IGLT. Actual ECB reference FX is used where validated. Missing SONIA is transparently proxied by the published US RF series; forward cash uses the dated bank quote. IGLT uses the issuer’s dated weighted-average YTM and effective duration with an explicit flat-yield/no-roll-down carry approximation. Market and equity-estimation uncertainty are modelled; future cash rates and structural uncertainty remain unquantified.

Other securities, including the four leveraged candidates, retain explicit admission blockers. The daily leverage engine is implemented and tested; their issuer mechanics and synchronised actual overlap have **not** been admitted. Effective-company concentration remains unavailable until reviewed look-through holdings meet coverage/freshness gates. This is a provisional implementation, not completion of every production-data acceptance gate.

## Development and data refresh

```bash
uv python install 3.14.8 --no-bin
uv venv --python 3.14.8 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
source .venv/bin/activate
python -m pytest -q
python -m portfolio.providers.provisional --root data/research
python -m streamlit run app.py --server.address 127.0.0.1
```

Set `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` to writable directories if needed. Refresh runs **outside** interactive use. Source ZIPs/pages, hashes and snapshot vintages are retained under ignored `data/research/.cache`; a failure retains the last good snapshot. Fresh clones open the dated derived calibrated model inputs, with an explicitly labelled IID Gaussian scenario approximation and no actual historical replay. Refresh restores the real source cache and synchronised-block paths. Full source histories are retained locally, not committed or exported without established redistribution rights.

For the strict SONIA/asset-aware contract, use `python -m portfolio.providers.refresh --root data/research --config <source-pack-config.json>`. See [V7 input contract](docs/v7-data-contract.md). `python -m portfolio.providers.pilots` audits the six specified pilot sources. No paid provider, API key or scheduled job is assumed.

## Validation and export

The suite covers parsing/units, chronological selection, cost treatment, covariance, constraints, daily leverage, arithmetic versus compounded horizons, company aggregation, widget synchronisation, complete holdings, same-run comparisons and exact ZIP solve reproduction. **Export ZIP** generates calculations on demand, including the displayed portfolios, all 50 IDs, every solved point, assumptions, source inventory, matrix inputs, scenario results and a reusable calculation script. It also runs the predefined useful-universe screen. The screen is a research diagnostic, not a reason to tune assumptions until every instrument appears.

## Privacy and legacy preservation

Keep both repository and app private. Review and merge/deploy require separate authorisation. The Streamlit Community Cloud target remains Python 3.14 and `app.py`; no deployment is performed by setup or refresh. Original `data/legacy` files are immutable and excluded from the normal V7 workflow. The old demonstration app remains a separate developer reference at `ui/legacy_app.py`; its numerical tests are retained.
