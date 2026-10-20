"""Portfolio Construction Lab V8.0 — four-page, immutable release app shell.

Dashboard and ui.v8_shared from Stage 08 Phase 1 are retained. The three
Phase 2 pages run lazily on navigation, never as startup precomputation.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import numpy as np
import streamlit as st
from ui.v8_shared import (TOTAL, checked_weights, copy, release_manifest,
                          require_release_path, _meta_get)
from ui import dashboard, holdings, analysis, methods

st.set_page_config(page_title="Portfolio Construction Lab", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")
from ui.theme import inject_custom_css
inject_custom_css()
PAGES = ("dashboard", "underlying", "analysis", "methods")
READABLE_PARQUETS = frozenset({"fund_catalogue.parquet", "company_holdings.parquet",
    "benchmark_vall.parquet", "fund_links.parquet", "stress_vectors.parquet",
    "stress_results.parquet", "historical_results.parquet"})


def _check_digest(path: Path, expected: str | None) -> None:
    # A SHA-256 is required when declared; reject stale or mixed releases.
    if expected:
        current = sha256(path.read_bytes()).hexdigest()
        if current.lower() != str(expected).lower():
            raise ValueError(f"Release integrity verification failed for {path.name}")


def _sha(manifest: dict, path: str) -> str | None:
    hashes = manifest.get("sha256", {})
    return hashes.get(path) if isinstance(hashes, dict) else None


@st.cache_resource(show_spinner=False, max_entries=4)
def load_model(release_id: str, method: str):
    """Deserialize only trusted locally-built release artefacts (never user ZIPs)."""
    if method not in ("holdings", "etf"):
        raise ValueError("Unrecognised model family")
    import joblib
    from portfolio.model import PreparedModel
    manifest = release_manifest()
    if release_id != manifest["release_id"]:
        raise ValueError("Model release changed")
    relative = f"prepared_{method}.joblib"
    path = require_release_path(relative)
    _check_digest(path, _sha(manifest, relative))
    model = joblib.load(path)
    if not isinstance(model, PreparedModel):
        raise TypeError("Model artefact is not a PreparedModel")
    if _meta_get(getattr(model, "metadata", None), "method", None) != method:
        raise ValueError("Prepared model family mismatch")
    return model



@st.cache_data(show_spinner=False, max_entries=16)
def load_frame(release_id: str, filename: str):
    if filename not in READABLE_PARQUETS:
        raise ValueError("Unexpected release dataset")
    import pandas as pd
    manifest = release_manifest()
    if manifest["release_id"] != release_id:
        raise ValueError("Data release changed")
    path = require_release_path(filename)
    _check_digest(path, _sha(manifest, filename))
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False, max_entries=128)
def load_frontier(release_id: str, method: str, engine_mask: int):
    if method not in ("holdings", "etf") or not 0 <= engine_mask <= 63:
        raise ValueError("Invalid requested frontier")
    manifest = release_manifest()
    if manifest["release_id"] != release_id:
        raise ValueError("Frontier release changed")
    relative = f"frontiers/{method}/{engine_mask:02d}.npz"
    path = require_release_path(relative)
    _check_digest(path, _sha(manifest, relative))
    with np.load(path, allow_pickle=False) as npz:
        data = {key: npz[key].copy() for key in npz.files}
    required = {"q_bps", "certified", "gap"}
    if not required.issubset(data):
        raise ValueError("Frontier quality fields absent")
    q = data["q_bps"]
    if q.ndim != 2 or q.shape[0] != 1001 or not np.issubdtype(q.dtype, np.integer):
        raise ValueError("Frontier must have 1,001 integer-weight points")
    if (q.sum(axis=1, dtype=np.int64) != TOTAL).any() or (
        ((q > 0) & (q < 10)).any()):
        raise ValueError("Frontier fails integer-basis-point validation")
    if len(data["certified"]) != 1001 or len(data["gap"]) != 1001:
        raise ValueError("Frontier lacks pointwise certification")
    return data


@st.cache_data(show_spinner=False, max_entries=128)
def load_wealth(release_id: str, method: str, engine_mask: int):
    if method not in ("holdings", "etf") or not 0 <= engine_mask <= 63:
        raise ValueError("Invalid requested wealth data")
    manifest = release_manifest()
    if manifest["release_id"] != release_id:
        raise ValueError("Wealth release changed")
    relative = f"wealth/{method}/{engine_mask:02d}.npz"
    path = require_release_path(relative)
    _check_digest(path, _sha(manifest, relative))
    with np.load(path, allow_pickle=False) as npz:
        data = {key: npz[key].copy() for key in npz.files}
    return data


def _init_state(release: dict, model) -> list[str]:
    tickers = release.get("tickers")
    if not isinstance(tickers, list) or not tickers or len(set(tickers)) != len(tickers):
        raise ValueError("Release instrument identities are missing/duplicated")
    if len(tickers) != len(model.asset_ids):
        raise ValueError("Model and release dimensions disagree")
    state = st.session_state
    state.setdefault("v8_page", "dashboard")
    state.setdefault("v8_method", "holdings")
    state.setdefault("v8_method_pending", state["v8_method"])
    state.setdefault("v8_theme", "dark")
    # Dashboard owns its category multiselect at key v8_filters; retain across routes.
    if "v8_q_bps" not in state:
        cash_index = _meta_get(getattr(model, "metadata", None), "cash_index", None)
        if cash_index is None or not (0 <= int(cash_index) < len(tickers)):
            raise ValueError("No verified default cash instrument for initial allocation")
        q = np.zeros(len(tickers), dtype=np.uint16)
        q[int(cash_index)] = TOTAL
        state["v8_q_bps"] = list(map(int, q))
    # Never silently reset or re-normalise a user's existing allocation.
    if len(state["v8_q_bps"]) != len(tickers):
        raise ValueError("Saved portfolio length differs from active universe")
    checked_weights(state["v8_q_bps"])
    if state["v8_page"] not in PAGES:
        state["v8_page"] = "dashboard"
    if state["v8_method"] not in ("holdings", "etf"):
        raise ValueError("Invalid active model setting")
    return tickers


def main() -> None:
    state = st.session_state
    state.setdefault("v8_method", "holdings")
    try:
        release = release_manifest()
        if not release.get("release_id") or not release.get("as_of"):
            raise ValueError("No dated immutable release manifest")
        with st.spinner(copy("app.status.loading")):
            model = load_model(release["release_id"], state["v8_method"])
        tickers = _init_state(release, model)
    except (FileNotFoundError, OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        st.error(copy("app.error.missing_release")); st.code(str(exc)); st.stop()
    heading, menu, date = st.columns([3, 7, 2], vertical_alignment="center")
    heading.markdown(f"### {copy('app.title')}")
    menu.segmented_control(copy("app.title"), options=PAGES,
        format_func=lambda p: copy("app.nav." + p),
        key="v8_page", label_visibility="collapsed")
    date.caption(copy("app.release.date", date=release["as_of"]))
    # Streamlit's global theme cannot reliably be changed by this control;
    # refrain from advertising a nonfunctional switch.
    date.button(copy("app.theme.to_light"), disabled=True,
                help=copy("app.theme.unavailable"))
    context = {"release": release, "model": model, "tickers": tickers,
               "load_model": load_model, "load_frame": load_frame,
               "load_frontier": load_frontier, "load_wealth": load_wealth}
    render = {"dashboard": dashboard.render, "underlying": holdings.render,
              "analysis": analysis.render, "methods": methods.render}
    try:
        render[state["v8_page"]](context)
    except Exception as exc:
        # Fail closed, preserve all session allocations and the last good model.
        st.error(copy("app.error.unexpected")); st.exception(exc)


if __name__ == "__main__":
    main()

