# Fama–French Portfolio Research

A Streamlit app for comparing ETF portfolios and inspecting a constrained efficient frontier.

V6 starts with the original V5 files. Those histories have unverified splices and currency treatment, so the bundled data is **demonstration data**. Company fundamentals are empty. Neither fitted holdings exposures nor the figures in the interview draft have been established by these files.

The first release includes:

- A 101-point constrained frontier and a slider showing each solved portfolio.
- Fund selection, fund weight limits, holdings/overlap diagnostics and volatility contributions.
- Return-based FF5 ridge calibration with chronological validation, explicit GBP conversion and a fee-consistent forecast.
- An optional 20-year buy-and-hold illustration with approximate P20/median/P80 bands.
- Excel results and a diagnostic ZIP with assumptions, model/data IDs and the full frontier.

The bundled legacy workflow works immediately. The FF5 path requires the documented input bundle described below. Holdings-characteristic calibration, country/industry limits in the UI, leveraged funds and income assets remain later work.

[Methodology and limitations](docs/methodology.md) · [Research data contract](docs/data-contract.md) · [Deployment and first test](docs/deployment.md)

[V7 build plan](docs/v7-build-plan.md) · [Dashboard concept](docs/v7-dashboard-concept.png)

The V7 plan covers verified fund data, asset-specific models and a redesigned dashboard. It is a planning handover; the deployed application remains V6.

## Hosting

Deploy this private repository through Streamlit Community Cloud:

| Setting | Value |
| --- | --- |
| Repository | `Robert-Study/Fama-French-Portfolio-Research` |
| Branch | `main` |
| Main file | `app.py` |
| Python | `3.14` (tested on `3.14.8`) |
| Secrets | None required |
| App access | Private |

Open [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app → Yup, I have an app**. Use the settings above and keep access private. The app runs on the host; using it does not require Python on a laptop. Development and data refreshes are separate from everyday use.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m streamlit run app.py
```

Keep changes small enough to review. Run the numerical tests after changing estimation, fees, constraints or projections. Source files under `data/legacy` are immutable; their checksums belong to the original V5 manifest.

No API keys, paid data connections or background refresh jobs are required. Do not commit credentials, account statements or licensed datasets without checking the intended use.
