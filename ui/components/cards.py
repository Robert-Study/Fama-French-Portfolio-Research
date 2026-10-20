"""Institutional Glassmorphic KPI & Telemetry Cards — Obsidian Terminal 2027."""
from __future__ import annotations

import streamlit as st
from ui.theme import THEME


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string (#RRGGBB) to (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    if len(hex_color) == 3:
        return int(hex_color[0] * 2, 16), int(hex_color[1] * 2, 16), int(hex_color[2] * 2, 16)
    return 0, 242, 254


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str | None = None,
    badge: str | tuple[str, str] | None = None,
    color: str = "#00F2FE",
) -> str:
    """Render a sleek HTML/CSS glassmorphic KPI card with tabular-num typography.
    
    Parameters
    ----------
    title : str
        Metric label displayed in uppercase tracking (e.g. 'EXPECTED RETURN (μ)').
    value : str
        High-impact formatted value string (e.g. '8.42%').
    subtitle : str | None
        Descriptive contextual text below the value.
    badge : str | tuple[str, str] | None
        Optional pill badge (text string or (text, badge_color) tuple).
    color : str
        Accent highlight color for top border glow and metric value.
    """
    badge_html = ""
    if badge is not None:
        if isinstance(badge, tuple) and len(badge) == 2:
            b_text, b_color = badge
        else:
            b_text, b_color = str(badge), color
        
        try:
            r, g, b = _hex_to_rgb(b_color)
            b_bg = f"rgba({r}, {g}, {b}, 0.15)"
            b_border = f"rgba({r}, {g}, {b}, 0.35)"
        except Exception:
            b_bg = "rgba(0, 242, 254, 0.15)"
            b_border = "rgba(0, 242, 254, 0.35)"
            b_color = "#00F2FE"

        badge_html = (
            f'<span class="status-pill" style="background: {b_bg}; '
            f'color: {b_color}; border: 1px solid {b_border};">{b_text}</span>'
        )

    subtitle_html = f'<div class="stat-subtitle">{subtitle}</div>' if subtitle else ""
    
    try:
        r, g, b = _hex_to_rgb(color)
        top_glow = f"0 1px 12px rgba({r}, {g}, {b}, 0.35)"
    except Exception:
        top_glow = "0 1px 12px rgba(0, 242, 254, 0.35)"

    card_html = f"""
    <div class="quant-card" style="border-top: 3px solid {color}; box-shadow: {top_glow}, 0 4px 20px rgba(0, 0, 0, 0.25);">
      <div class="stat-label">
        <span>{title}</span>
        {badge_html}
      </div>
      <div class="stat-value" style="color: {color};">
        {value}
      </div>
      {subtitle_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
    return card_html


def render_kpi_strip(
    mu: float,
    sigma: float,
    sharpe: float,
    gross: float,
) -> None:
    """Render the 4 primary portfolio KPIs with glowing borders and formatted metrics.
    
    Parameters
    ----------
    mu : float
        Annual arithmetic net expected return.
    sigma : float
        Annualized return standard deviation (volatility).
    sharpe : float
        Net Sharpe ratio relative to cash hurdle (3.80% AER).
    gross : float
        Gross portfolio exposure leverage factor (1.00x - 3.00x).
    """
    col1, col2, col3, col4 = st.columns(4)

    # 1. Expected Return (μ)
    with col1:
        render_kpi_card(
            title="EXPECTED RETURN (μ)",
            value=f"{mu:.2%}",
            subtitle="Annual arithmetic net carry",
            badge=("NET", THEME["accent_emerald"]),
            color=THEME["accent_emerald"],
        )

    # 2. Annual Volatility (σ)
    with col2:
        if sigma < 0.08:
            risk_tier, tier_col = "LOW", THEME["accent_emerald"]
        elif sigma < 0.16:
            risk_tier, tier_col = "BALANCED", THEME["accent_cyan"]
        else:
            risk_tier, tier_col = "DYNAMIC", THEME["accent_amber"]
        
        render_kpi_card(
            title="ANNUAL VOLATILITY (σ)",
            value=f"{sigma:.2%}",
            subtitle="Annualized standard deviation",
            badge=(risk_tier, tier_col),
            color=THEME["accent_cyan"],
        )

    # 3. Net Sharpe Ratio
    with col3:
        if sharpe >= 0.80:
            sh_badge, sh_col = "OPTIMAL", THEME["accent_emerald"]
        elif sharpe >= 0.0:
            sh_badge, sh_col = "POSITIVE", THEME["accent_purple"]
        else:
            sh_badge, sh_col = "SUB-HURDLE", THEME["accent_coral"]

        render_kpi_card(
            title="NET SHARPE RATIO",
            value=f"{sharpe:.2f}",
            subtitle="Excess carry over 3.80% cash",
            badge=(sh_badge, sh_col),
            color=THEME["accent_purple"],
        )

    # 4. Gross Exposure (L)
    with col4:
        if gross > 1.01:
            g_badge, g_col = "GEARED", THEME["accent_amber"]
            g_card_col = THEME["accent_amber"]
        else:
            g_badge, g_col = "1.00× CASH", THEME["text_muted"]
            g_card_col = THEME["text_secondary"]

        render_kpi_card(
            title="GROSS EXPOSURE (L)",
            value=f"{gross:.2f}×",
            subtitle="Active leverage factor",
            badge=(g_badge, g_col),
            color=g_card_col,
        )
