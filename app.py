from pathlib import Path
import logging

import numpy as np
import pandas as pd
import streamlit as st

from portfolio import __version__
from portfolio.bundle import FACTORS, read_bundle
from portfolio.calibration import fit_ff5
from portfolio.charts import frontier_chart, wealth_chart
from portfolio.data import DataError, legacy_fingerprint, load_legacy
from portfolio.export import diagnostic_bytes, workbook_bytes
from portfolio.holdings import lookthrough, matched_overlap
from portfolio.projection import buy_and_hold_projection
from portfolio.results import legacy_run, research_run
from portfolio.risk import portfolio_metrics


ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Fama–French Portfolio Research", page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False, max_entries=2)
def legacy_inputs(fingerprint):
    return load_legacy(ROOT / "data/legacy")


@st.cache_data(show_spinner=False, max_entries=3)
def research_inputs(raw):
    return read_bundle(raw)


@st.cache_data(show_spinner=False, max_entries=6)
def calibration(fingerprint, window, version, _data):
    return fit_ff5(_data.returns.tail(window), _data.factors, _data.cash)


@st.cache_data(show_spinner=False, max_entries=12)
def calculate(mode, fingerprint, ids, window, cap, premiums, cash, multiplier, version, _data):
    if mode == "Legacy demonstration":
        return legacy_run(_data, ids, window, cap)
    fit = calibration(fingerprint, window, version, _data)
    return research_run(_data, fit, ids, cap, premiums, cash, multiplier)


@st.cache_data(show_spinner=False, max_entries=10)
def downloads(run, point, investment):
    return workbook_bytes(run, point, investment), diagnostic_bytes(run, point, investment)


st.title("Fama–French Portfolio Research")
st.caption("V6 · ETF exposures, portfolio risk and the efficient frontier")
mode = st.sidebar.radio("Data and model", ["Legacy demonstration", "Return-based FF5"], key="mode")

try:
    if mode == "Legacy demonstration":
        data = legacy_inputs(legacy_fingerprint(ROOT / "data/legacy"))
        eligible = data.funds.index[data.funds.AssetClass.eq("Equity")].tolist()
        st.warning("Legacy demonstration — the V5 return sources and GBP treatment are unverified. "
                   "These results test the workflow; they are not calibrated Fama–French forecasts.")
    else:
        st.info("This mode estimates FF5 exposures from fund returns. It does not map company characteristics to factors.")
        upload = st.sidebar.file_uploader("Research input bundle (.zip)", type="zip", key="bundle")
        if upload is None:
            st.subheader("The calculation engine is ready; the research data is still needed")
            st.write("The V5 package contains no French factor file or GBP cash/FX series, and its fund histories have unverified splices. "
                     "A documented input bundle is needed before this mode can run.")
            st.write("The next data step is to recover the original fund/index exports and prepare the small matching factor and currency files. "
                     "This preparation can be handled as a project update; you do not need to maintain a data pipeline.")
            st.markdown("[Input contract and remaining data work](https://github.com/Robert-Study/Fama-French-Portfolio-Research/blob/main/docs/data-contract.md)")
            st.stop()
        data = research_inputs(upload.getvalue())
        eligible = data.funds.index.tolist()
        st.warning("Supplied-data research — file structure and model calculations are checked. "
                   "Source accuracy and suitability still require review; forecasts remain conditional assumptions.")
except (DataError, ValueError, OSError) as exc:
    st.error(str(exc))
    st.stop()

defaults = eligible[:20]
options = [n for n in [72, 120, 240, 360] if n <= len(data.returns)]
default_window = options.index(120) if 120 in options else len(options) - 1
with st.sidebar.form("settings_" + data.fingerprint[:12]):
    st.subheader("Portfolio settings")
    ids = st.multiselect("Funds", eligible, default=defaults, key="funds_" + data.fingerprint[:12])
    window = st.selectbox("Estimation window (months)", options, index=default_window)
    cap_percent = st.number_input("Maximum weight per fund (%)", min_value=1.0, max_value=100.0, value=100.0, step=5.0)
    premiums, cash, multiplier = (), 0.0, 1.0
    if mode == "Return-based FF5":
        st.caption("Annualised arithmetic assumptions (%). Defaults use the supplied factor sample and latest cash month.")
        cash = st.number_input("GBP cash assumption (%)", value=float(data.cash.iloc[-1] * 1200), step=0.25) / 100
        premiums = tuple(st.number_input(f"{factor} premium (%)", value=float(data.factors[factor].mean() * 1200), step=0.25) / 100
                         for factor in FACTORS)
        multiplier = st.selectbox("Non-market premium sensitivity", [1.0, 0.5, 0.0],
                                 format_func=lambda x: {1.0: "Base premiums", 0.5: "50% of style premiums", 0.0: "Zero style premiums"}[x])
    else:
        st.caption("Return assumptions use legacy sample arithmetic means. Fees are already assumed to be in those histories.")
    submitted = st.form_submit_button("Recalculate frontier", type="primary", width="stretch")
st.sidebar.caption("Form changes apply when you recalculate. The frontier slider selects an already solved portfolio.")
st.sidebar.caption("Country/industry limits, leveraged ETFs and income assets are not enabled in this release.")

active = st.session_state.get("active_run")
if submitted or active is None or active.fingerprint != data.fingerprint or active.mode != mode:
    try:
        if not ids:
            raise ValueError("Select at least one fund.")
        with st.spinner("Calculating the frontier…"):
            new_run = calculate(mode, data.fingerprint, tuple(ids), window, cap_percent / 100,
                                premiums, cash, multiplier, __version__, data)
        st.session_state.active_run = new_run
        st.session_state.pop("run_error", None)
    except Exception as exc:
        logging.exception("Portfolio calculation failed")
        st.session_state.run_error = str(exc) if isinstance(exc, ValueError) else "The calculation failed. The last successful result has been kept."

run = st.session_state.get("active_run")
if st.session_state.get("run_error"):
    st.error(st.session_state.run_error)
    st.caption("The results below, if present, retain their previous settings and run ID.")
if run is None or run.fingerprint != data.fingerprint or run.mode != mode:
    st.stop()

st.caption(f"Run {run.run_id} · {len(run.funds)} funds · {run.settings['start']} to {run.settings['end']} "
           f"· fund limit {run.settings['cap']:.0%} · long-only, fully invested")
point = 0
if len(run.frontier.weights) > 1:
    point = st.slider("Move along the efficient frontier", min_value=0, max_value=len(run.frontier.weights) - 1,
                      value=0, key="point_" + run.run_id,
                      help="0 is the constrained minimum-variance portfolio. The final point has the highest feasible model return.")
else:
    st.info("These inputs produce one efficient portfolio; there is no distinct return/risk range to move along.")

weights = pd.Series(run.frontier.weights[point], index=run.funds.index)
mu, vol, contributions = portfolio_metrics(weights.to_numpy(), run.mean, run.covariance)
columns = st.columns(4)
columns[0].metric("Annualised arithmetic return", f"{mu * 12:.2%}")
columns[1].metric("Annualised monthly volatility", f"{vol * np.sqrt(12):.2%}")
columns[2].metric("Weighted annual fund fee", f"{weights @ run.funds.TER:.2%}")
columns[3].metric("Funds above 0.01% weight", str(int((weights >= 0.0001).sum())))
st.caption("Return is not CAGR. Volatility uses √12 scaling. Fees are shown for context and are deducted once under the active model's convention.")

portfolio_tab, holdings_tab, model_tab = st.tabs(["Portfolio", "Holdings", "Model and data"])
with portfolio_tab:
    st.plotly_chart(frontier_chart(run, point), use_container_width=True)
    st.caption("The line connects solved portfolios. Individual ETFs and the reference are shown without the portfolio weight limit. "
               "A position on this curve is conditional on these inputs, not a recommendation.")
    table = run.funds[["Name", "TER"]].copy()
    table["Weight"] = weights
    table["Annual volatility contribution"] = contributions * np.sqrt(12)
    st.dataframe(table.sort_values("Weight", ascending=False).style.format(
        {"TER": "{:.2%}", "Weight": "{:.2%}", "Annual volatility contribution": "{:.2%}"}), width="stretch")
    st.caption("Volatility contributions sum to portfolio volatility; negative contributions can be valid. All fund weights are retained in the download.")
    if run.betas is not None:
        exposures = weights @ run.betas
        st.subheader("Portfolio FF5 exposures")
        st.dataframe(exposures.to_frame("Beta").T.style.format("{:.3f}"), width="stretch")
    projection_investment = None
    if st.checkbox("Show the 20-year buy-and-hold illustration"):
        investment = st.number_input("Initial investment (£)", min_value=100.0, max_value=10000000.0, value=10000.0, step=1000.0)
        try:
            projection = buy_and_hold_projection(weights.to_numpy(), run.mean, run.covariance, investment)
            projection_investment = investment
            st.plotly_chart(wealth_chart(projection), use_container_width=True)
            st.caption("Nominal GBP, no contributions, withdrawals, taxes, inflation or ETF-level rebalancing. "
                       "Initial ETF weights drift. Constant parameters and independent monthly return vectors are assumed. "
                       "P20–P80 is an approximate 60% market-outcome band, not a confidence interval for the model. "
                       "The frontier optimises initial one-period risk, not 20-year wealth.")
            st.dataframe(projection.drop(columns="Variance").set_index("Year").style.format("£{:,.0f}"), width="stretch")
        except ValueError as exc:
            st.warning(str(exc))
    excel, diagnostic = downloads(run, point, projection_investment)
    left, right = st.columns(2)
    left.download_button("Download results (.xlsx)", excel, f"portfolio_{run.run_id}_{point}.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    right.download_button("Download diagnostics (.zip)", diagnostic, f"diagnostics_{run.run_id}_{point}.zip",
                          "application/zip", width="stretch")

with holdings_tab:
    if mode == "Legacy demonstration":
        st.caption("Inherited classifications and holding keys; not verified issuer exposures. Signed cash/derivative balances are preserved.")
        positions, countries, sectors = lookthrough(data.holdings, data.securities, weights)
        left, right = st.columns(2)
        left.dataframe(countries.to_frame("Net portfolio weight").style.format("{:.2%}"), width="stretch")
        right.dataframe(sectors.to_frame("Net portfolio weight").style.format("{:.2%}"), width="stretch")
        st.subheader("Largest recorded positions")
        st.dataframe(positions[["Name", "PortfolioWeight", "AssetClass", "Country", "Sector"]].head(25).style.format(
            {"PortfolioWeight": "{:.2%}"}), width="stretch")
        with st.expander("Matched holding-key overlap"):
            overlap = matched_overlap(data.holdings, data.securities, run.funds.index.tolist())
            st.dataframe(overlap.style.format("{:.1%}"), width="stretch")
            st.caption("Sum of the smaller positive equity weight under matching holding keys. Unknown/residual positions and cash are excluded. "
                       "This is partial recorded overlap, not a company count or a covariance adjustment. No overlap risk surcharge is added.")
    else:
        st.info("This bundle contains return-calibration inputs. Reviewed holdings are needed before adding look-through constraints; "
                "the app does not silently attach older V5 positions to a new dataset.")

with model_tab:
    st.subheader("ETF estimates")
    st.dataframe(run.etfs.style.format({"TER": "{:.2%}", "Annualised arithmetic return": "{:.2%}",
                                       "Annualised monthly volatility": "{:.2%}"}), width="stretch")
    st.subheader("Checks and diagnostics")
    st.dataframe(run.diagnostics, width="stretch")
    st.write(f"Frontier points: {len(run.frontier.weights)}. Maximum solver constraint violation: {run.frontier.max_violation:.2g}.")
    if mode == "Legacy demonstration":
        st.dataframe(data.inventory[["file", "bytes", "status", "checksum_matches"]], hide_index=True, width="stretch")
        st.caption("Matching checksums establish file identity, not the accuracy of the source data. GHYS is excluded because this release covers equities.")
    else:
        st.caption("Penalty selection uses chronological folds within the training period. The final 12 months are assessed once, "
                   "then the selected specification is refitted on all displayed months. Holdout scores are diagnostics, not proof of future performance.")
    with st.expander("Active assumptions and reproducibility"):
        st.json({"model_version": __version__, "run_id": run.run_id, "data_sha256": run.fingerprint,
                 "created_utc": run.created, **run.settings})
    st.markdown("[Methodology](https://github.com/Robert-Study/Fama-French-Portfolio-Research/blob/main/docs/methodology.md) · "
                "[Data contract](https://github.com/Robert-Study/Fama-French-Portfolio-Research/blob/main/docs/data-contract.md)")
