"""Dashboard — interactive MIQP efficient frontier, 6-bit sleeve filter, allocation editor and wealth projection cone."""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import streamlit as st

from ui.v8_shared import (
    TOTAL,
    REFERENCE_KEYS,
    checked_weights,
    as_weights,
    copy,
    diagnostics,
)
from portfolio.wealth import buy_and_hold_moments, wealth_quantiles

SLEEVES = (
    (1, "Core Developed Equity"),
    (2, "Factor, Thematic & EM Equity"),
    (4, "Sovereign & Inflation-Linked Bonds"),
    (8, "Credit & Emerging Market Debt"),
    (16, "Real Assets & Commodities"),
    (32, "GBP Liquidity & Cash Reserve"),
)


def _compute_wealth_cone(model: Any, q_bps: np.ndarray, max_years: int = 30) -> pd.DataFrame:
    """Evaluate discrete Buy-and-Hold wealth quantiles P20, P50, P84 across 1..max_years."""
    w = as_weights(q_bps)
    mu_arith = getattr(model, "mu_arith_ann", np.zeros_like(w))
    cov_ann = getattr(model, "cov_ann", np.eye(len(w)) * 0.04)
    param_uncertainty = getattr(model, "param_uncertainty", None)

    records = []
    for y in range(1, max_years + 1):
        try:
            m_n, v_n = buy_and_hold_moments(w, mu_arith, cov_ann, float(y))
            q_dict = wealth_quantiles(m_n, v_n, horizon_years=float(y), quantiles=(0.20, 0.50, 0.84135))
            q20 = q_dict[0.20]
            q50 = q_dict[0.50]
            q84 = q_dict[0.84135]
        except Exception:
            # Fallback simple lognormal if full state-space moments fail
            annual_mu = float(w @ getattr(model, "mu_arith_ann", np.zeros_like(w)))
            annual_var = float(w @ getattr(model, "cov_ann", np.zeros((len(w), len(w)))) @ w)
            annual_sd = np.sqrt(max(annual_var, 0.0))
            drift = (annual_mu - 0.5 * annual_var) * y
            vol = annual_sd * np.sqrt(y)
            q20 = float(np.exp(drift - 0.8416 * vol))
            q50 = float(np.exp(drift))
            q84 = float(np.exp(drift + 1.0 * vol))

        records.append({
            "Year": y,
            "P20 (Downside)": q20,
            "P50 (Median)": q50,
            "P84 (Upside)": q84,
        })

    return pd.DataFrame(records)


def render(context: dict) -> None:
    """Render the primary interactive portfolio construction dashboard."""
    release = context["release"]
    model = context["model"]
    tickers = context["tickers"]
    load_frontier = context.get("load_frontier")

    st.subheader(copy("dashboard.title"))
    st.caption(copy("dashboard.subtitle"))

    state = st.session_state
    state.setdefault("v8_filters", [name for _, name in SLEEVES])

    # Category Mask Multiselect
    col_filters, col_presets = st.columns([7, 5])
    with col_filters:
        selected_sleeves = st.multiselect(
            "Active Asset Category Sleeves",
            options=[name for _, name in SLEEVES],
            default=state["v8_filters"],
            help="Select which asset sleeves participate in portfolio construction.",
            key="v8_sleeve_multiselect",
        )
        state["v8_filters"] = selected_sleeves

    # Compute 6-bit engine mask
    engine_mask = 0
    for bit, name in SLEEVES:
        if name in selected_sleeves:
            engine_mask |= bit

    with col_presets:
        st.markdown("**Quick Preset Allocations**")
        pcols = st.columns(4)
        refs = release.get("references", {})
        if pcols[0].button("100% Cash"):
            cash_idx = getattr(getattr(model, "metadata", None), "cash_index", len(tickers) - 1)
            q = [0] * len(tickers)
            q[int(cash_idx)] = TOTAL
            state["v8_q_bps"] = q
            st.rerun()
        if pcols[1].button("Global 60/40") and "global_6040" in refs:
            ref_q = refs["global_6040"].get("q_bps")
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                st.rerun()
        if pcols[2].button("All-Cap Eq.") and "all_cap" in refs:
            ref_q = refs["all_cap"].get("q_bps")
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                st.rerun()
        if pcols[3].button("S&P 500") and "sp500" in refs:
            ref_q = refs["sp500"].get("q_bps")
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                st.rerun()

    # Current Portfolio Metrics
    curr_q = np.array(state["v8_q_bps"], dtype=np.int64)
    # Check weights validation
    try:
        curr_q = checked_weights(curr_q)
    except Exception as exc:
        st.warning(f"Allocation adjustment needed: {exc}")

    # Leverage calculation
    leverage = np.ones(len(tickers), dtype=np.float64)
    if "3QQQ" in tickers:
        leverage[tickers.index("3QQQ")] = 3.0
    for t in ("QQQ3", "LQQ3"):
        if t in tickers:
            leverage[tickers.index(t)] = 3.0

    diag = diagnostics(model, curr_q, leverage)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(copy("dashboard.metric.expected_return"), f"{diag['mu']:.2%}", help=copy("dashboard.metric.expected_return_help"))
    m2.metric(copy("dashboard.metric.volatility"), f"{diag['sigma']:.2%}", help=copy("dashboard.metric.volatility_help"))
    cash_rate = 0.038  # 3.80% AER cash anchor
    sharpe = (diag["mu"] - cash_rate) / diag["sigma"] if diag["sigma"] > 1e-6 else 0.0
    m3.metric("Net Sharpe Ratio", f"{sharpe:.2f}", help="Excess return over 3.80% cash divided by annual volatility.")
    m4.metric(copy("dashboard.metric.gross_exposure"), f"{diag['gross']:.2f}×", help=copy("dashboard.metric.gross_exposure_help"))

    st.divider()

    # Efficient Frontier Chart & Wealth Cone in tabs
    tab_frontier, tab_cone, tab_alloc = st.tabs([
        "📈 " + copy("dashboard.frontier.title"),
        "⏳ Wealth Projection Cone",
        "📝 Allocation Editor"
    ])

    with tab_frontier:
        frontier_data = None
        if load_frontier and engine_mask > 0:
            try:
                frontier_data = load_frontier(release["release_id"], state.get("v8_method", "holdings"), engine_mask)
            except Exception:
                frontier_data = None

        if frontier_data is not None and "q_bps" in frontier_data:
            f_q = frontier_data["q_bps"]
            w_mat = f_q.astype(np.float64) / float(TOTAL)
            f_mu = w_mat @ getattr(model, "mu_arith_ann", np.zeros(len(tickers)))
            cov_ann = getattr(model, "cov_ann", np.eye(len(tickers)))
            f_var = np.einsum("ij,jk,ik->i", w_mat, cov_ann, w_mat)
            f_sigma = np.sqrt(np.maximum(f_var, 0.0))

            chart_df = pd.DataFrame({
                "Annual Volatility": f_sigma,
                "Expected Return": f_mu,
            }).sort_values("Annual Volatility")

            st.line_chart(
                chart_df.set_index("Annual Volatility"),
                use_container_width=True,
            )
            st.caption(f"MIQP Frontier ({len(f_q)} points). Category Mask: {engine_mask:02d}. Current portfolio: Volatility {diag['sigma']:.2%}, Return {diag['mu']:.2%}.")
        else:
            st.info("Precomputed 1,001-point frontier will display once release artifacts are generated for this category mask.")
            # Render simple scatter representation of current allocation vs single-asset universe
            single_mu = getattr(model, "mu_arith_ann", np.zeros(len(tickers)))
            single_cov = getattr(model, "cov_ann", np.eye(len(tickers)))
            single_sigma = np.sqrt(np.maximum(np.diag(single_cov), 0.0))
            asset_df = pd.DataFrame({
                "Ticker": tickers,
                "Annual Volatility": single_sigma,
                "Expected Return": single_mu,
            })
            st.scatter_chart(
                asset_df,
                x="Annual Volatility",
                y="Expected Return",
                color="Ticker",
                use_container_width=True,
            )

    with tab_cone:
        st.markdown("#### Cumulative Wealth Growth Distribution (Initial £10,000)")
        cone_df = _compute_wealth_cone(model, curr_q, max_years=30)
        # Scale to £10,000 initial investment
        scaled_cone = cone_df.copy()
        scaled_cone["P20 (£)"] = scaled_cone["P20 (Downside)"] * 10000.0
        scaled_cone["P50 (£)"] = scaled_cone["P50 (Median)"] * 10000.0
        scaled_cone["P84 (£)"] = scaled_cone["P84 (Upside)"] * 10000.0

        st.line_chart(
            scaled_cone.set_index("Year")[["P20 (£)", "P50 (£)", "P84 (£)"]],
            use_container_width=True,
        )
        st.dataframe(
            scaled_cone.style.format({
                "P20 (Downside)": "{:.2f}x",
                "P50 (Median)": "{:.2f}x",
                "P84 (Upside)": "{:.2f}x",
                "P20 (£)": "£{:,.0f}",
                "P50 (£)": "£{:,.0f}",
                "P84 (£)": "£{:,.0f}",
            }),
            hide_index=True,
            use_container_width=True,
        )

    with tab_alloc:
        st.markdown("#### Portfolio Position Ledger (Integer Basis Points)")
        rows = []
        for i, t in enumerate(tickers):
            rows.append({
                "Index": i,
                "Ticker": t,
                "Weight (bps)": int(curr_q[i]),
                "Weight (%)": f"{curr_q[i] / 100.0:.2f}%",
            })
        alloc_df = pd.DataFrame(rows)
        # Show only active positions or all
        show_all = st.checkbox("Show all 68 universe instruments", value=False)
        if not show_all:
            alloc_df = alloc_df[alloc_df["Weight (bps)"] > 0]

        st.dataframe(alloc_df, hide_index=True, use_container_width=True)
        st.caption(f"Total Allocation: {int(curr_q.sum())} / {TOTAL} basis points.")
