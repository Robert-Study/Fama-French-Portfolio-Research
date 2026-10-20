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
    _meta_get,
    _get_reference_weights,
    require_release_path,
)
import plotly.express as px
from ui.components import (
    render_kpi_strip,
    create_frontier_figure,
    create_wealth_cone_figure,
    create_allocation_sunburst,
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

    records = []
    for y in range(1, max_years + 1):
        try:
            m_n, v_n = buy_and_hold_moments(w, mu_arith, cov_ann, float(y))
            q_dict = wealth_quantiles(m_n, v_n, horizon_years=float(y), quantiles=(0.20, 0.50, 0.84135))
            q20 = q_dict[0.20]
            q50 = q_dict[0.50]
            q84 = q_dict[0.84135]
        except Exception:
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
    """Render the primary interactive portfolio construction dashboard (Two-Panel Responsive Layout)."""
    release = context["release"]
    model = context["model"]
    tickers = context["tickers"]
    load_frontier = context.get("load_frontier")

    # Header Row: Title and Quick Presets
    top_col_info, top_col_presets = st.columns([6, 6], vertical_alignment="center")
    with top_col_info:
        st.subheader(copy("dashboard.title"))
        st.caption(copy("dashboard.subtitle"))

    state = st.session_state
    state.setdefault("v8_filters", [name for _, name in SLEEVES])

    with top_col_presets:
        st.markdown("**Quick Preset Portfolios**")
        pcols = st.columns(4)
        refs = release.get("references", {})
        if pcols[0].button("100% Cash"):
            cash_idx = _meta_get(getattr(model, "metadata", None), "cash_index", len(tickers) - 1)
            q = [0] * len(tickers)
            q[int(cash_idx)] = TOTAL
            state["v8_q_bps"] = q
            state["_preset_active"] = True
            st.rerun()
        if pcols[1].button("Global 60/40") and "global_6040" in refs:
            ref_q = _get_reference_weights(refs["global_6040"])
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                state["_preset_active"] = True
                st.rerun()
        if pcols[2].button("All-Cap Eq.") and "all_cap" in refs:
            ref_q = _get_reference_weights(refs["all_cap"])
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                state["_preset_active"] = True
                st.rerun()
        if pcols[3].button("S&P 500") and "sp500" in refs:
            ref_q = _get_reference_weights(refs["sp500"])
            if ref_q and len(ref_q) == len(tickers):
                state["v8_q_bps"] = list(ref_q)
                state["_preset_active"] = True
                st.rerun()

    # Category Mask Evaluation
    selected_sleeves = state["v8_filters"]
    engine_mask = 0
    for bit, name in SLEEVES:
        if name in selected_sleeves:
            engine_mask |= bit

    # Pre-load frontier for mask if available
    frontier_data = None
    if load_frontier and engine_mask > 0:
        try:
            frontier_data = load_frontier(release["release_id"], state.get("v8_method", "holdings"), engine_mask)
        except Exception:
            frontier_data = None

    is_frontier_certified = (
        frontier_data is not None
        and "q_bps" in frontier_data
        and (
            frontier_data.get("status") == "certified"
            or (
                "certified" in frontier_data
                and bool(np.all(frontier_data["certified"]))
            )
        )
    )

    if is_frontier_certified and not state.get("_preset_active", False):
        pt = int(state.get("v8_frontier_point", 500))
        if 0 <= pt < len(frontier_data["q_bps"]):
            state["v8_q_bps"] = [int(x) for x in frontier_data["q_bps"][pt]]

    # Current Portfolio Metrics & Telemetry
    curr_q = np.array(state["v8_q_bps"], dtype=np.int64)
    try:
        curr_q = checked_weights(curr_q)
    except Exception as exc:
        st.warning(f"Allocation adjustment needed: {exc}")

    leverage = np.ones(len(tickers), dtype=np.float64)
    if "3QQQ" in tickers:
        leverage[tickers.index("3QQQ")] = 3.0
    for t in ("QQQ3", "LQQ3"):
        if t in tickers:
            leverage[tickers.index(t)] = 3.0

    diag = diagnostics(model, curr_q, leverage)
    cash_rate = 0.038  # 3.80% AER cash anchor
    sharpe = (diag["mu"] - cash_rate) / diag["sigma"] if diag["sigma"] > 1e-6 else 0.0

    # Hero KPI Telemetry Strip
    render_kpi_strip(mu=diag["mu"], sigma=diag["sigma"], sharpe=sharpe, gross=diag["gross"])

    st.divider()

    # -------------------------------------------------------------------------
    # Two Balanced Portrait Panels (Side-by-Side on Desktop, Stacked on Mobile)
    # -------------------------------------------------------------------------
    col_left, col_right = st.columns([1, 1], gap="large")

    # =========================================================================
    # LEFT PANEL: Efficient Frontier Navigator & Mathematical Engine
    # =========================================================================
    with col_left:
        st.markdown("### 📈 MIQP Efficient Frontier & Engine")
        
        # Asset Sleeve Multi-Select
        selected_sleeves_input = st.multiselect(
            "Active Asset Category Sleeves",
            options=[name for _, name in SLEEVES],
            default=state["v8_filters"],
            help="Select which asset sleeves participate in MIQP portfolio optimization.",
            key="v8_sleeve_multiselect",
        )
        if selected_sleeves_input != state["v8_filters"]:
            state["v8_filters"] = selected_sleeves_input
            st.rerun()

        # Frontier Plot
        if is_frontier_certified:
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

            fig_frontier = create_frontier_figure(
                chart_df,
                active_vol=diag["sigma"],
                active_return=diag["mu"],
                cash_rate=cash_rate,
                title=f"MIQP Efficient Frontier & CAL ({len(f_q):,} Points)",
            )
            st.plotly_chart(fig_frontier, use_container_width=True)

            point_idx = st.slider(
                "Frontier Point (0 = Min Vol / GMV, 1000 = Max Return)",
                min_value=0,
                max_value=1000,
                value=int(state.get("v8_frontier_point", 500)),
                key="v8_frontier_point",
            )
            if state.get("_last_frontier_point") != point_idx:
                state["_last_frontier_point"] = point_idx
                state["_preset_active"] = False
                state["v8_q_bps"] = [int(x) for x in f_q[point_idx]]
                st.rerun()

            st.caption(
                f"Certified MIQP Frontier ({len(f_q)} points). Sleeve Mask: {engine_mask:02d}. "
                f"Selected Point #{point_idx}: Volatility {diag['sigma']:.2%}, Return {diag['mu']:.2%}, Sharpe {sharpe:.2f}."
            )
        else:
            if engine_mask == 0:
                st.info("No active asset sleeves selected (category mask 00 is infeasible). Select at least one sleeve.")
            else:
                st.info(f"Frontier precomputation for sleeve mask {engine_mask:02d} is being indexed.")

            single_mu = getattr(model, "mu_arith_ann", np.zeros(len(tickers)))
            single_cov = getattr(model, "cov_ann", np.eye(len(tickers)))
            single_sigma = np.sqrt(np.maximum(np.diag(single_cov), 0.0))
            asset_df = pd.DataFrame({
                "Ticker": tickers,
                "Annual Volatility": single_sigma,
                "Expected Return": single_mu,
            })
            fig_scatter = px.scatter(
                asset_df,
                x="Annual Volatility",
                y="Expected Return",
                color="Ticker",
                title="Asset Universe Volatility vs Return",
            )
            fig_scatter.update_layout(xaxis_tickformat=".1%", yaxis_tickformat=".1%", height=460, margin=dict(t=30, b=10))
            st.plotly_chart(fig_scatter, use_container_width=True)

        # Wealth Horizon Control
        horizon_years = st.slider(
            "Wealth Projection Horizon (Years)",
            min_value=1,
            max_value=40,
            value=int(state.get("v8_wealth_horizon", 30)),
            key="v8_wealth_horizon",
        )

    # =========================================================================
    # RIGHT PANEL: Wealth Distribution & Allocation Dynamics
    # =========================================================================
    with col_right:
        st.markdown("### ⏳ Wealth Projection & Allocation")

        # Wealth Moments Data Resolution
        load_wealth = context.get("load_wealth")
        method = state.get("v8_method", "holdings")
        wealth_data = None
        if load_wealth and engine_mask > 0:
            try:
                wealth_data = load_wealth(release["release_id"], method, engine_mask)
            except Exception:
                wealth_data = None
        if wealth_data is None and engine_mask > 0:
            w_path = require_release_path(f"wealth/{method}/{engine_mask:02d}.npz")
            if w_path.is_file():
                try:
                    with np.load(w_path, allow_pickle=False) as npz:
                        wealth_data = {k: npz[k].copy() for k in npz.files}
                except Exception:
                    wealth_data = None

        pt = int(state.get("v8_frontier_point", 500))
        if wealth_data is not None and "moments" in wealth_data:
            moments_arr = wealth_data["moments"]
            pt_idx = max(0, min(pt, moments_arr.shape[0] - 1))
            records = []
            for y in range(1, horizon_years + 1):
                y_idx = y - 1
                q20 = float(moments_arr[pt_idx, y_idx, 2])
                q50 = float(moments_arr[pt_idx, y_idx, 3])
                q84 = float(moments_arr[pt_idx, y_idx, 4])
                records.append({
                    "Year": y,
                    "P20 (Downside)": q20,
                    "P50 (Median)": q50,
                    "P84 (Upside)": q84,
                })
            cone_df = pd.DataFrame(records)
        else:
            cone_df = _compute_wealth_cone(model, curr_q, max_years=horizon_years)

        # Plotly Shaded Wealth Fan Chart
        fig_cone = create_wealth_cone_figure(cone_df, horizon_years, initial_wealth=10000.0)
        st.plotly_chart(fig_cone, use_container_width=True)

        # Dynamic Sleeve & Asset Allocation Sunburst Donut
        fig_sunburst = create_allocation_sunburst(tickers, curr_q)
        st.plotly_chart(fig_sunburst, use_container_width=True)

        # Position Ledger (Accordion / Expander)
        with st.expander("📋 Position Ledger (Integer Basis Points)", expanded=False):
            rows = []
            for i, t in enumerate(tickers):
                rows.append({
                    "Index": i,
                    "Ticker": t,
                    "Weight (bps)": int(curr_q[i]),
                    "Weight (%)": f"{curr_q[i] / 100.0:.2f}%",
                })
            alloc_df = pd.DataFrame(rows)
            show_all = st.checkbox("Show all 68 universe instruments", value=False, key="v8_show_all_instruments")
            if not show_all:
                alloc_df = alloc_df[alloc_df["Weight (bps)"] > 0]
            st.dataframe(alloc_df, hide_index=True, use_container_width=True)
            st.caption(f"Total Portfolio Allocation: {int(curr_q.sum())} / {TOTAL} basis points.")
