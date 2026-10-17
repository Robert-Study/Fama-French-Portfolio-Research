# Fama–French Portfolio Research — V7

A Streamlit research app with **Dashboard, Holdings, Compare and Methods** pages. Model version **0.4.0**, Python **3.14.8**. It solves long-only, fully invested portfolios with explicit asset-category and gross-exposure constraints. The visible 0–100 controls select solved frontier positions; expected return is annualised arithmetic return, not CAGR.

The revised [implementation specification](docs/v7-build-plan.md), [supplied scientific report](docs/v7-methods-report.md), and [implementation/evidence status](docs/v7-implementation-status.md) explain the model and its boundaries.

## Current evidence and assumptions

The selected schedule remains 49 securities plus a cash sleeve. The user's later instruction replaces Trading 212 cash with a **separate UK bank savings account outside Trading 212**. The original 50-item CSV is preserved; `cash-policy.json` records that override. The current publicly verified bank quote is in `bank-quote.json`; rates are variable and expire for admission after 30 days. No individual account eligibility or deposit-protection headroom is checked.

The researched issuer adapters acquire actual histories for **46 securities**, with **41 passing their documented reconciliation checks**. The current frontier admits **32 models**: savings, two physical metals, six government-bond funds, 13 equity ETFs and 10 factor ETFs. Published regional French factors and actual SONIA/ECB GBP data underpin calibration through **August 2026**. Latest observed SONIA is held flat as an explicit forward assumption, separate from bank AER. BoE live access currently returns 403, so the dated actual SONIA observations supplied by the research commit are retained with provenance. Some non-iShares fees use the dated research ledger rather than a live fee quote; that basis is recorded.

Remaining securities retain precise capability blockers. Actual VWRP, VAGS, XS2D and monthly-rebalanced 60/40 historical reference statistics remain available independently of forward-model admission. XS2D history passes an issuer NAV/chart consistency screen, with a disclosed incomplete independent corporate-action audit; its daily forward mechanics remain blocked. Company concentration remains unavailable until acquired holdings are mapped to reviewed companies. Six-category forward coverage is incomplete because no leveraged forecast has passed its mechanics gates.

## Development and data refresh

```bash
uv python install 3.14.8 --no-bin
uv venv --python 3.14.8 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
source .venv/bin/activate
python -m pytest -q
python -m portfolio.providers.universe --root data/research
python -m streamlit run app.py --server.address 127.0.0.1
```

Set `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` to writable directories if needed. Refresh runs **outside** interactive use, with public GET/POST requests, bounded retries and a verified content-addressed cache. A failed candidate retains the last-good snapshot. Fresh clones open calibrated matrices, coefficient diagnostics and derived historical reference statistics; horizon scenarios use labelled IID Gaussian joint risk. Refresh restores synchronised-block paths and full portfolio replay. Raw third-party histories/workbooks remain in ignored `.cache`, outside Git and ZIP exports. Bank rates expire after 30 days; return vintages after 90.

For the strict SONIA/asset-aware contract, use `python -m portfolio.providers.refresh --root data/research --config <source-pack-config.json>`. See [V7 input contract](docs/v7-data-contract.md). `python -m portfolio.providers.pilots` audits the six specified pilot sources. No paid provider, API key or scheduled job is assumed.

## Validation and export

The suite covers parsing/units, chronological selection, cost treatment, covariance, constraints, daily leverage, arithmetic versus compounded horizons, company aggregation, widget synchronisation, complete holdings, same-run comparisons and exact ZIP solve reproduction. **Export ZIP** generates calculations on demand, including the displayed portfolios, all 50 IDs, every solved point, assumptions, source inventory, matrix inputs, scenario results and a reusable calculation script. It reuses the verified default useful-universe screen; custom constraints may require recomputation. The screen is a research diagnostic, not a reason to tune assumptions until every instrument appears.

## Privacy and legacy preservation

Repository visibility was verified as **public** on 15 October 2026 and left unchanged at the user’s request. App visibility was not independently verified. Do not change either automatically. Maintain changes on `main` as requested; deployment/account controls remain with the user. The Streamlit Community Cloud target remains Python 3.14 and `app.py`; no deployment is performed by setup or refresh. Original `data/legacy` files are immutable and excluded from the normal V7 workflow. The old demonstration app remains a separate developer reference at `ui/legacy_app.py`; its numerical tests are retained.
