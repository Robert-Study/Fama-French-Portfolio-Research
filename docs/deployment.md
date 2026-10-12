# Hosted setup and testing

## Deploy

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with the GitHub account that can access this repository.
2. Grant Streamlit access to the private repository if it cannot see it. Sign-in and source-control access are separate permissions.
3. Select **Create app → Yup, I have an app**. Enter these values:

| Field | Value |
| --- | --- |
| Repository | `Robert-Study/Fama-French-Portfolio-Research` |
| Branch | `main` |
| Main file | `app.py` |
| Advanced settings → Python | `3.12` |
| Secrets | Leave blank |
| App URL | Accept the generated URL, or choose an available name |

4. Deploy and keep app access private. Check the sharing setting is **Only specific people can view this app**. Do not make the repository public to solve an access problem.

The repository already contains the code, V5 inputs and Python requirements. You do not need to install Python, Git, an editor or Excel on your computer to use the hosted app. The app has no API keys or paid data connection.

## First test

1. Confirm the legacy-data warning appears. This is intentional: the bundled data is not a verified FF5 forecast.
2. Move the frontier slider from the first to the last point. Weights, return and volatility should change together; weights should sum to 100%.
3. Set a 20% fund limit and select at least five funds, then recalculate. No fund should exceed the selected limit beyond numerical tolerance.
4. Select two funds with a 20% cap. The app should explain that this is infeasible and retain the last successful run, with its original run ID and settings.
5. Download the workbook and check that its selected weights match the screen. If the wealth illustration is enabled, its table and initial investment should also be included.
6. Switch to Return-based FF5 without a bundle. The app should explain the missing input evidence and show no pretend calibrated results.

Report a problem with the page URL, what you changed, a screenshot and the diagnostic ZIP if one is available. For a startup failure, the Streamlit build log is more useful than a diagnostic ZIP. Do not send passwords or account tokens.

## If startup fails

An error at `from sklearn.linear_model import Ridge` happens before portfolio calculation. The package is named `scikit-learn` in `requirements.txt`; `sklearn` is its Python import name. It is already a required dependency, so adding a package called `sklearn` is not the fix.

All runtime pins are kept in the root `requirements.txt`. The deployment installs wheels rather than compiling packages. An unavailable wheel will produce an installation error instead of a long source build. `requirements-dev.txt` adds test tools only.

After a requirements update, allow Streamlit to finish rebuilding. If the dependency error remains, use **Manage app → ⋮ → Reboot app** once. If it fails again, share the Cloud log's Python version, dependency-file selection, installation errors and final `ModuleNotFoundError` line. Those distinguish a failed installation from a deployment using the wrong branch or environment. Repeated reboots without reading the log will not diagnose the cause.

Check that the deployment uses `main`, `app.py` and Python **3.12**. Changing the Python version of an existing Community Cloud app requires redeployment; a reboot alone does not change it. Keep app access private. Account controls and private Cloud logs cannot be accessed through the GitHub connector, so the user needs to perform this hosting step or share the relevant log excerpt.

## Updates and responsibilities

Code changes and data preparation can be handled through subsequent authorised project sessions. GitHub commits are the source of the deployed app. The user tests the result and completes account sign-ins, access grants or provider exports that require their own credentials.

There is no unattended monitoring, scheduled data refresh, promise of permanent uptime or automatic repair. Streamlit sessions can reset, and uploaded bundles and current settings are not a persistent database. Export a result if you need to keep it. A future project change can make a reviewed dataset the default without requiring repeated uploads.

The app caches parsed data, calibration and frontiers, with bounded cache sizes. Slider movement selects saved points and does not refit the model. Calculations run on the host, but the browser and cloud service still have finite resources. The initial 20-fund frontier has been tested locally; hosted startup and performance must be checked on the deployed app.

Official guide: [Deploy a Streamlit app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
