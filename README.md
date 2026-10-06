# Fama–French Portfolio Research

A Streamlit app for comparing ETF portfolios and inspecting a constrained efficient frontier.

V6 starts with the original V5 files. Those histories have unverified splices and currency treatment, so the bundled data is **demonstration data**. Company fundamentals are empty. Neither fitted holdings exposures nor the figures in the interview draft have been established by these files.

The first release separates the portfolio maths from the input evidence. It includes a legacy-data explorer and a return-based FF5 calibration path for a documented input bundle. Holdings-based factor calibration remains a later stage.

## Hosting

Deploy this private repository through Streamlit Community Cloud:

| Setting | Value |
| --- | --- |
| Repository | `Robert-Study/Fama-French-Portfolio-Research` |
| Branch | `main` |
| Main file | `app.py` |
| Python | `3.12` |
| Secrets | None required |
| App access | Private |

The app runs on the host; using it does not require Python on a laptop. Development and data refreshes are separate from everyday use.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m streamlit run app.py
```

Keep changes small enough to review. Run the numerical tests after changing estimation, fees, constraints or projections. Source files under `data/legacy` are immutable; their checksums belong to the original V5 manifest.

No API keys, paid data connections or background refresh jobs are required. Do not commit credentials, account statements or licensed datasets without checking the intended use.
