"""High-Impact Quantitative Data Visualizations — Obsidian Terminal 2027."""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from ui.theme import THEME, SLEEVE_COLORS


def _resolve_columns(df: pd.DataFrame) -> tuple[str, str]:
    """Identify volatility and return column names flexibly."""
    vol_col = next((c for c in df.columns if "vol" in c.lower() or "sigma" in c.lower()), df.columns[0])
    ret_col = next((c for c in df.columns if "ret" in c.lower() or "mu" in c.lower()), df.columns[1])
    return vol_col, ret_col


def create_frontier_figure(
    frontier_df: pd.DataFrame,
    active_vol: float,
    active_return: float,
    cash_rate: float = 0.038,
    title: str | None = None,
) -> go.Figure:
    """Build the Cyber-Quant MIQP Efficient Frontier & Capital Allocation Line (CAL).
    
    Parameters
    ----------
    frontier_df : pd.DataFrame
        DataFrame containing solved frontier points (volatility and return columns).
    active_vol : float
        Selected active portfolio annual volatility.
    active_return : float
        Selected active portfolio annual expected net return.
    cash_rate : float
        AER Cash hurdle anchor (default: 0.038 for 3.80%).
    title : str | None
        Optional custom chart title.
    """
    vol_col, ret_col = _resolve_columns(frontier_df)
    sorted_df = frontier_df.sort_values(vol_col).copy()
    
    v = sorted_df[vol_col].to_numpy(dtype=np.float64)
    r = sorted_df[ret_col].to_numpy(dtype=np.float64)
    
    # Calculate pointwise Sharpe ratios relative to cash anchor
    sharpe_series = (r - cash_rate) / np.maximum(v, 1e-6)
    
    # Identify tangency portfolio (maximum Sharpe ratio point)
    max_idx = int(np.argmax(sharpe_series))
    v_star = float(v[max_idx])
    r_star = float(r[max_idx])
    max_sharpe = float(sharpe_series[max_idx])
    
    # Construct Capital Allocation Line (CAL) ray from (0, cash_rate)
    v_max = float(max(v.max() * 1.15, v_star * 1.35))
    r_max = float(cash_rate + max_sharpe * v_max)
    
    cal_v = [0.0, v_star, v_max]
    cal_r = [cash_rate, r_star, r_max]
    
    fig = go.Figure()
    
    # 1. Capital Allocation Line (CAL)
    fig.add_trace(
        go.Scatter(
            x=cal_v,
            y=cal_r,
            mode="lines",
            name=f"CAL Ray (Tangent Sharpe {max_sharpe:.2f})",
            line=dict(color="rgba(16, 185, 129, 0.70)", width=2, dash="dash"),
            hovertemplate=(
                "<b>Capital Allocation Line (CAL)</b><br>"
                "Annual Volatility: %{x:.2%}<br>"
                "Expected Return: %{y:.2%}<br>"
                f"Hurdle Rate: {cash_rate:.2%}<extra></extra>"
            ),
        )
    )
    
    # 2. Tangency Portfolio (Max-Sharpe Point)
    fig.add_trace(
        go.Scatter(
            x=[v_star],
            y=[r_star],
            mode="markers",
            name=f"Max-Sharpe Tangency ({max_sharpe:.2f})",
            marker=dict(
                size=12,
                color=THEME["accent_emerald"],
                symbol="diamond",
                line=dict(color="#FFFFFF", width=1.5),
            ),
            hovertemplate=(
                "<b>Max-Sharpe Tangency Portfolio</b><br>"
                "Annual Volatility: %{x:.2%}<br>"
                "Expected Return: %{y:.2%}<br>"
                f"Net Sharpe Ratio: {max_sharpe:.2f}<extra></extra>"
            ),
        )
    )
    
    # 3. MIQP Efficient Frontier Curve
    fig.add_trace(
        go.Scatter(
            x=v,
            y=r,
            mode="lines",
            name="MIQP Efficient Frontier",
            line=dict(color=THEME["accent_cyan"], width=3),
            customdata=sharpe_series,
            hovertemplate=(
                "<b>MIQP Frontier Point</b><br>"
                "Annual Volatility: %{x:.2%}<br>"
                "Expected Return: %{y:.2%}<br>"
                "Net Sharpe: %{customdata:.2f}<extra></extra>"
            ),
        )
    )
    
    # 4. Active Portfolio Selection Marker
    active_sharpe = (active_return - cash_rate) / max(active_vol, 1e-6)
    fig.add_trace(
        go.Scatter(
            x=[active_vol],
            y=[active_return],
            mode="markers",
            name="Active Portfolio",
            marker=dict(
                size=16,
                color=THEME["accent_cyan"],
                symbol="circle",
                line=dict(color="#FFFFFF", width=2.5),
            ),
            hovertemplate=(
                "<b>Active Portfolio Selection</b><br>"
                "Annual Volatility: %{x:.2%}<br>"
                "Expected Return: %{y:.2%}<br>"
                f"Net Sharpe Ratio: {active_sharpe:.2f}<extra></extra>"
            ),
        )
    )
    
    chart_title = title or f"MIQP Efficient Frontier & Capital Allocation Line ({len(v):,} Points)"
    fig.update_layout(
        title=dict(text=chart_title, font=dict(size=14, color="#F8FAFC")),
        xaxis=dict(
            title="Annual Volatility (σ)",
            tickformat=".1%",
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
        ),
        yaxis=dict(
            title="Expected Net Return (μ)",
            tickformat=".1%",
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(color="#94A3B8", size=11),
        ),
        hovermode="closest",
        height=460,
        margin=dict(l=20, r=20, t=50, b=20),
        template="obsidian_terminal",
    )
    return fig


def create_wealth_cone_figure(
    cone_df: pd.DataFrame,
    horizon_years: int,
    initial_wealth: float = 10000.0,
) -> go.Figure:
    """Build the Layered Wealth Projection Fan Chart with P20/P84 translucent shading.
    
    Parameters
    ----------
    cone_df : pd.DataFrame
        DataFrame with projection years and P20, P50, P84 wealth metrics.
    horizon_years : int
        Simulation horizon in years.
    initial_wealth : float
        Starting capital in GBP (default: £10,000).
    """
    # Detect columns
    year_col = next((c for c in cone_df.columns if "year" in c.lower()), "Year")
    p20_col = next((c for c in cone_df.columns if "20" in c), None)
    p50_col = next((c for c in cone_df.columns if "50" in c), None)
    p84_col = next((c for c in cone_df.columns if "84" in c), None)
    
    if not (p20_col and p50_col and p84_col):
        raise ValueError("Wealth cone dataframe missing P20, P50, or P84 quantile columns")
    
    years = cone_df[year_col].to_numpy(dtype=np.int64)
    raw_p20 = cone_df[p20_col].to_numpy(dtype=np.float64)
    raw_p50 = cone_df[p50_col].to_numpy(dtype=np.float64)
    raw_p84 = cone_df[p84_col].to_numpy(dtype=np.float64)
    
    # Determine if values are multiples (e.g. 1.25) or already in currency units (> 100)
    is_multiple = np.max(raw_p50) < 100.0
    if is_multiple:
        gbp_p20 = raw_p20 * initial_wealth
        gbp_p50 = raw_p50 * initial_wealth
        gbp_p84 = raw_p84 * initial_wealth
        mult_p20 = raw_p20
        mult_p50 = raw_p50
        mult_p84 = raw_p84
    else:
        gbp_p20 = raw_p20
        gbp_p50 = raw_p50
        gbp_p84 = raw_p84
        mult_p20 = gbp_p20 / initial_wealth
        mult_p50 = gbp_p50 / initial_wealth
        mult_p84 = gbp_p84 / initial_wealth
    
    fig = go.Figure()
    
    # 1. Upper Bound: P84 (Upside 84th Percentile)
    fig.add_trace(
        go.Scatter(
            x=years,
            y=gbp_p84,
            mode="lines",
            line=dict(color="rgba(16, 185, 129, 0.45)", width=1.5, dash="dot"),
            name="P84 Upside (84th %ile)",
            customdata=mult_p84,
            hovertemplate=(
                "<b>P84 Upside (84th Percentile)</b><br>"
                "Year %{x}<br>"
                "Wealth: <b>£%{y:,.0f}</b><br>"
                "Multiple: %{customdata:.2f}×<extra></extra>"
            ),
            showlegend=True,
        )
    )
    
    # 2. Lower Bound: P20 (Downside 20th Percentile) with Shaded Area Fill
    fig.add_trace(
        go.Scatter(
            x=years,
            y=gbp_p20,
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(16, 185, 129, 0.12)",
            line=dict(color="rgba(16, 185, 129, 0.45)", width=1.5, dash="dot"),
            name="P20 Downside (20th %ile)",
            customdata=mult_p20,
            hovertemplate=(
                "<b>P20 Downside (20th Percentile)</b><br>"
                "Year %{x}<br>"
                "Wealth: <b>£%{y:,.0f}</b><br>"
                "Multiple: %{customdata:.2f}×<extra></extra>"
            ),
            showlegend=True,
        )
    )
    
    # 3. P50 Median Wealth Outcome (Vivid Emerald Solid Line)
    fig.add_trace(
        go.Scatter(
            x=years,
            y=gbp_p50,
            mode="lines+markers",
            line=dict(color=THEME["accent_emerald"], width=3.5),
            marker=dict(size=5, color=THEME["accent_emerald"]),
            name="P50 Median Wealth",
            customdata=mult_p50,
            hovertemplate=(
                "<b>P50 Median Outcome</b><br>"
                "Year %{x}<br>"
                "Projected Wealth: <b>£%{y:,.0f}</b><br>"
                "Growth Multiple: %{customdata:.2f}×<extra></extra>"
            ),
        )
    )
    
    dtick = 5 if horizon_years >= 15 else 1
    fig.update_layout(
        title=dict(
            text=f"Cumulative Wealth Growth Distribution (1..{horizon_years} Years, Initial £{initial_wealth:,.0f})",
            font=dict(size=14, color="#F8FAFC"),
        ),
        xaxis=dict(
            title="Projection Horizon (Years)",
            dtick=dtick,
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
            tickfont=dict(family="'JetBrains Mono', monospace", color="#94A3B8"),
        ),
        yaxis=dict(
            title="Projected Wealth (£)",
            tickformat="£,.0f",
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
            tickfont=dict(family="'JetBrains Mono', monospace", color="#94A3B8"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(color="#94A3B8", size=11),
        ),
        hovermode="x unified",
        height=460,
        margin=dict(l=20, r=20, t=50, b=20),
        template="obsidian_terminal",
    )
    return fig


def create_allocation_sunburst(
    tickers: list[str],
    q_bps: np.ndarray | list[int],
    sleeves_mapping: dict[str, str] | pd.DataFrame | None = None,
) -> go.Figure:
    """Build a multi-level Sunburst / Donut chart showing Sleeve -> Asset allocations.
    
    Parameters
    ----------
    tickers : list[str]
        List of all universe instrument tickers.
    q_bps : np.ndarray | list[int]
        Portfolio allocations in integer basis points (0..10,000).
    sleeves_mapping : dict[str, str] | pd.DataFrame | None
        Mapping from ticker symbol to sleeve name. If None, resolves from fund catalogue.
    """
    q_arr = np.array(q_bps, dtype=np.int64)
    active_mask = q_arr > 0
    active_indices = np.where(active_mask)[0]
    
    if len(active_indices) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No active asset allocations (0 bps allocated)",
            showarrow=False,
            font=dict(size=14, color="#94A3B8"),
        )
        fig.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=30, b=20),
            template="obsidian_terminal",
        )
        return fig

    # Resolve sleeve mapping dictionary
    resolved_sleeve_map: dict[str, str] = {}
    if isinstance(sleeves_mapping, dict):
        # Check if dict maps ticker -> sleeve or sleeve -> list of tickers
        first_val = next(iter(sleeves_mapping.values()))
        if isinstance(first_val, (list, tuple, set)):
            for sleeve, tick_list in sleeves_mapping.items():
                for t in tick_list:
                    resolved_sleeve_map[t] = str(sleeve)
        else:
            resolved_sleeve_map = {str(k): str(v) for k, v in sleeves_mapping.items()}
    elif isinstance(sleeves_mapping, pd.DataFrame):
        t_col = next((c for c in sleeves_mapping.columns if "tick" in c.lower()), None)
        s_col = next((c for c in sleeves_mapping.columns if "sleeve_name" in c.lower() or "sleeve" in c.lower()), None)
        if t_col and s_col:
            resolved_sleeve_map = dict(zip(sleeves_mapping[t_col], sleeves_mapping[s_col].astype(str)))
    
    if not resolved_sleeve_map:
        try:
            from ui.v8_shared import require_release_path
            cat_path = require_release_path("fund_catalogue.parquet")
            if cat_path.is_file():
                cdf = pd.read_parquet(cat_path)
                resolved_sleeve_map = dict(zip(cdf["ticker"], cdf["sleeve_name"]))
        except Exception:
            resolved_sleeve_map = {}

    # Build active hierarchy
    active_tickers = [tickers[i] for i in active_indices]
    active_weights = [int(q_arr[i]) for i in active_indices]
    
    sleeve_totals: dict[str, int] = {}
    ticker_to_sleeve: dict[str, str] = {}
    
    for t, w in zip(active_tickers, active_weights):
        sleeve = resolved_sleeve_map.get(t)
        if not sleeve:
            if "cash" in t.lower():
                sleeve = "GBP Liquidity & Cash Reserve"
            else:
                sleeve = "Core Developed Equity"
        ticker_to_sleeve[t] = sleeve
        sleeve_totals[sleeve] = sleeve_totals.get(sleeve, 0) + w

    # Prepare Sunburst data structures
    unique_sleeves = list(sleeve_totals.keys())
    
    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[int] = []
    colors: list[str] = []
    
    # 1. Inner Ring: Sleeves
    for sleeve in unique_sleeves:
        s_id = f"sleeve_{sleeve}"
        ids.append(s_id)
        labels.append(sleeve)
        parents.append("")
        values.append(sleeve_totals[sleeve])
        colors.append(SLEEVE_COLORS.get(sleeve, "#38BDF8"))
        
    # 2. Outer Ring: Tickers
    for t, w in zip(active_tickers, active_weights):
        sleeve = ticker_to_sleeve[t]
        t_id = f"ticker_{t}"
        ids.append(t_id)
        labels.append(t)
        parents.append(f"sleeve_{sleeve}")
        values.append(w)
        s_col = SLEEVE_COLORS.get(sleeve, "#38BDF8")
        colors.append(s_col)

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(
                colors=colors,
                line=dict(color="#0A0E17", width=1.5),
            ),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Allocation: %{value:,.0f} bps (%{percentRoot:.1%})<br>"
                "<extra></extra>"
            ),
            insidetextorientation="radial",
        )
    )

    fig.update_layout(
        title=dict(
            text=f"Active Asset Allocation Sunburst ({len(active_tickers)} Active Holdings)",
            font=dict(size=14, color="#F8FAFC"),
        ),
        height=420,
        margin=dict(l=10, r=10, t=40, b=10),
        template="obsidian_terminal",
    )
    return fig
