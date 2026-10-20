"""Hyper-Modern UI Theme Engine — Obsidian Terminal 2027 (Cyber-Quant Aesthetic).

Centralises visual tokens, glassmorphic CSS injection, and dark Plotly layout templates
for Portfolio Construction Lab V8.0.
"""
from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

# -------------------------------------------------------------------------
# Design Tokens — Obsidian Terminal 2027
# -------------------------------------------------------------------------
THEME: dict[str, str] = {
    "bg_root": "#0A0E17",                 # Deep obsidian background
    "bg_card": "rgba(22, 31, 48, 0.75)",  # Translucent glass card
    "bg_card_hover": "rgba(30, 41, 59, 0.85)",
    "border_subtle": "rgba(255, 255, 255, 0.08)",
    "border_glow": "rgba(0, 242, 254, 0.40)",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "accent_cyan": "#00F2FE",             # Primary telemetry & frontier
    "accent_emerald": "#10B981",          # Return & Sharpe ratios
    "accent_purple": "#8B5CF6",           # Factor & equity sleeves
    "accent_amber": "#F59E0B",            # Volatility & gearing
    "accent_coral": "#EF4444",            # Stress, drawdowns & caution
}

SLEEVE_COLORS: dict[str, str] = {
    "Core Developed Equity": "#00F2FE",               # Neon cyan
    "Factor, Thematic & EM Equity": "#8B5CF6",        # Cyber purple
    "Sovereign & Inflation-Linked Bonds": "#38BDF8",  # Sky blue
    "Credit & Emerging Market Debt": "#F59E0B",       # Amber
    "Real Assets & Commodities": "#EC4899",           # Pink / Coral
    "GBP Liquidity & Cash Reserve": "#10B981",        # Emerald
}

# -------------------------------------------------------------------------
# Custom CSS Generator & Injection
# -------------------------------------------------------------------------
def get_custom_css() -> str:
    """Generate high-contrast, glassmorphic CSS rules for Streamlit application."""
    return """
    /* Obsidian Terminal 2027 Global Root Styles */
    .stApp {
        background-color: #0A0E17 !important;
        color: #F8FAFC !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    header[data-testid="stHeader"] {
        background-color: rgba(10, 14, 23, 0.85) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    }

    /* Glassmorphic KPI & Quantitative Cards */
    .quant-card {
        background: rgba(22, 31, 48, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 18px;
        transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), 
                    box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1), 
                    border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        margin-bottom: 10px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }

    .quant-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px -10px rgba(0, 242, 254, 0.25);
        border-color: rgba(0, 242, 254, 0.35);
    }

    /* Monospace Tabular Numerical Telemetry */
    .stat-value {
        font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Roboto Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 2.05rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.15;
        margin: 4px 0 6px 0;
    }

    .stat-label {
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        color: #94A3B8;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }

    .stat-subtitle {
        font-size: 0.78rem;
        color: #64748B;
        margin-top: 4px;
        font-variant-numeric: tabular-nums;
    }

    /* Telemetry Status Pills & Badges */
    .status-pill {
        display: inline-flex;
        align-items: center;
        border-radius: 9999px;
        padding: 2px 8px;
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-family: 'JetBrains Mono', monospace;
    }

    .slider-badge {
        background: rgba(0, 242, 254, 0.12);
        color: #00F2FE;
        border: 1px solid rgba(0, 242, 254, 0.3);
        border-radius: 6px;
        padding: 2px 8px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    /* Micro-interactions for Streamlit Buttons */
    div.stButton > button {
        background: rgba(22, 31, 48, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #F8FAFC;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    div.stButton > button:hover {
        border-color: #00F2FE;
        color: #00F2FE;
        box-shadow: 0 0 14px rgba(0, 242, 254, 0.3);
        transform: translateY(-1px);
        background: rgba(30, 41, 59, 0.95);
    }

    div.stButton > button:active {
        transform: translateY(0);
    }

    /* Streamlit Slider Styling */
    div[data-testid="stSlider"] div[data-baseweb="slider"] {
        font-variant-numeric: tabular-nums;
    }

    div[data-testid="stSlider"] [role="slider"] {
        background-color: #00F2FE !important;
        box-shadow: 0 0 12px rgba(0, 242, 254, 0.7) !important;
        border: 2px solid #FFFFFF !important;
    }

    /* Streamlit Tabs */
    div[data-testid="stTabs"] button[role="tab"] {
        color: #94A3B8;
        font-weight: 600;
        font-size: 0.9rem;
        border-radius: 6px;
        padding: 8px 16px;
        transition: all 0.2s ease;
    }

    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #00F2FE !important;
        border-bottom-color: #00F2FE !important;
        text-shadow: 0 0 10px rgba(0, 242, 254, 0.4);
    }

    /* Minimalist Dark Scrollbars */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0A0E17;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 242, 254, 0.4);
    }
    """


def inject_custom_css() -> None:
    """Inject custom glassmorphic styling into the active Streamlit app session."""
    st.markdown(f"<style>{get_custom_css()}</style>", unsafe_allow_html=True)
    get_plotly_template()


# -------------------------------------------------------------------------
# Plotly Dark Layout Template
# -------------------------------------------------------------------------
def get_plotly_template() -> go.layout.Template:
    """Build, register, and return the Obsidian Terminal 2027 Plotly template."""
    template = go.layout.Template()
    template.layout = go.Layout(
        paper_bgcolor="#0A0E17",
        plot_bgcolor="#0A0E17",
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            color="#F8FAFC",
            size=12,
        ),
        colorway=[
            "#00F2FE",  # Neon Cyan
            "#10B981",  # Emerald
            "#8B5CF6",  # Cyber Purple
            "#F59E0B",  # Amber
            "#EF4444",  # Coral / Red
            "#38BDF8",  # Sky Blue
            "#EC4899",  # Pink
        ],
        hoverlabel=dict(
            bgcolor="#161F30",
            bordercolor="rgba(0, 242, 254, 0.4)",
            font=dict(
                family="'JetBrains Mono', 'SF Mono', monospace",
                size=12,
                color="#F8FAFC",
            ),
        ),
        xaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
            zerolinecolor="rgba(255, 255, 255, 0.08)",
            tickfont=dict(
                family="'JetBrains Mono', monospace",
                size=11,
                color="#94A3B8",
            ),
            title=dict(font=dict(color="#94A3B8", size=12)),
        ),
        yaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.05)",
            linecolor="rgba(255, 255, 255, 0.12)",
            zerolinecolor="rgba(255, 255, 255, 0.08)",
            tickfont=dict(
                family="'JetBrains Mono', monospace",
                size=11,
                color="#94A3B8",
            ),
            title=dict(font=dict(color="#94A3B8", size=12)),
        ),
    )
    # Register with plotly.io
    pio.templates["obsidian_terminal"] = template
    pio.templates.default = "obsidian_terminal"
    return template
