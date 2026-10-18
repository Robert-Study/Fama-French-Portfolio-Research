"""Analysis — release-calibrated historical shocks, leverage and band crossings.

Only immutable current-release stress vectors/wealth moments are admissible.
No fixed percentage 'historical' return is hard-coded in the presentation.
"""
from __future__ import annotations

from inspect import signature, Parameter
from itertools import combinations
import math
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from portfolio.wealth import find_band_intersection_time
from ui.v8_shared import (Portfolio, REFERENCE_KEYS, as_weights, checked_weights,
                           copy, diagnostics)

MAX_PORTFOLIOS = 5
SCENARIOS = (("2008", "2008 GFC"), ("2020", "2020 COVID"),
             ("2022", "2022 Inflation Shock"))


def _items(context: dict) -> list[Portfolio]:
    items = st.session_state.get("v8_analysis_portfolios")
    rid = context["release"]["release_id"]
    method = st.session_state["v8_method"]
    if items is None:
        items = [Portfolio(copy("app.nav.dashboard"),
                           tuple(int(x) for x in checked_weights(
                               st.session_state["v8_q_bps"])), method, rid)]
        st.session_state["v8_analysis_portfolios"] = items
    return items


def _selection(context: dict) -> list[Portfolio]:
    rid = context["release"]["release_id"]
    method = st.session_state["v8_method"]
    return [p for p in _items(context) if p.release_id == rid and p.method == method]


def _manage(context: dict) -> list[Portfolio]:
    st.subheader(copy("analysis.portfolios.title"))
    items = _items(context)
    st.caption(copy("analysis.portfolios.count", count=len(items)))
    if len(items) > MAX_PORTFOLIOS:
        st.error(copy("analysis.portfolios.limit")); return []
    refs = context["release"].get("references", {})
    choices = [k for k in REFERENCE_KEYS if isinstance(refs.get(k), dict)
               and refs[k].get("available") and refs[k].get("q_bps") is not None]
    cols = st.columns(3)
    if choices:
        with cols[0]:
            ref = st.selectbox(copy("analysis.portfolios.add_typical"), choices,
                               format_func=lambda k: copy("dashboard.reference." + k),
                               help=copy("analysis.portfolios.typical_help"))
            if st.button(copy("analysis.portfolios.add"), key="v8_reference_add"):
                if len(items) >= MAX_PORTFOLIOS:
                    st.warning(copy("analysis.portfolios.limit"))
                else:
                    q = checked_weights(refs[ref]["q_bps"])
                    items.append(Portfolio(copy("dashboard.reference." + ref),
                        tuple(int(x) for x in q), st.session_state["v8_method"],
                        context["release"]["release_id"]))
                    st.rerun()
    with cols[1]:
        if st.button(copy("analysis.portfolios.add_custom"),
                     help=copy("analysis.portfolios.custom_help")):
            if len(items) >= MAX_PORTFOLIOS:
                st.warning(copy("analysis.portfolios.limit"))
            else:
                items.append(Portfolio(f"Custom {len(items) + 1}",
                    tuple(int(x) for x in checked_weights(st.session_state["v8_q_bps"])),
                    st.session_state["v8_method"], context["release"]["release_id"]))
                st.rerun()
    with cols[2]:
        if items:
            index = st.selectbox(copy("analysis.intersection.portfolio_a"),
                                list(range(len(items))),
                                format_func=lambda k: items[k].name,
                                key="v8_analysis_current")
            if st.button(copy("analysis.portfolios.duplicate"), key="v8_duplicate"):
                if len(items) >= MAX_PORTFOLIOS:
                    st.warning(copy("analysis.portfolios.limit"))
                else:
                    p = items[index]
                    items.append(Portfolio(p.name + " (copy)", p.q_bps,
                                           p.method, p.release_id))
                    st.success(copy("analysis.portfolios.duplicate_success")); st.rerun()
            if st.button(copy("analysis.portfolios.remove"), key="v8_remove"):
                items.pop(index)
                st.success(copy("analysis.portfolios.remove_success")); st.rerun()
    return _selection(context)


def _metrics(context: dict, portfolios: list[Portfolio], catalog: pd.DataFrame) -> None:
    _require_catalogue(catalog, len(context["tickers"]))
    leverage = catalog["leverage"].to_numpy(float)
    rows = []
    for p in portfolios:
        d = diagnostics(context["model"], p.vector(), leverage)
        rows.append({"Portfolio": p.name,
                     copy("analysis.metrics.expected_return"): f"{d['mu']:.2%}",
                     copy("analysis.metrics.volatility"): f"{d['sigma']:.2%}",
                     copy("analysis.metrics.exposure"): f"{d['gross']:.2f}×"})
    st.subheader(copy("analysis.metrics.title"))
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _require_catalogue(catalog: pd.DataFrame, count: int) -> None:
    if len(catalog) != count or "leverage" not in catalog:
        raise ValueError("Fund catalogue missing aligned leverage column")
    lev = pd.to_numeric(catalog["leverage"], errors="raise").to_numpy(float)
    if not np.all(np.isfinite(lev)) or np.any((lev < 1) | (lev > 3)):
        raise ValueError("Gross leverage parameters outside validated 1×–3× domain")


def _exposure(portfolios: list[Portfolio], catalog: pd.DataFrame) -> None:
    lev = catalog["leverage"].to_numpy(float)
    st.subheader(copy("analysis.metrics.exposure"))
    for p in portfolios:
        w = as_weights(p.vector())
        gross = float(w @ lev)
        borrowed = float(w @ np.maximum(lev - 1, 0))
        # Visual gauge is explicitly initial economic exposure, not margin debt.
        st.metric(p.name, f"{gross:.2f}×")
        st.progress(min(1.0, max(0.0, (gross - 1) / 2)),
                    text=f"Gross {gross:.2f}× · Borrowed notional {borrowed:.2%} of NAV")
        if borrowed > 0:
            st.warning(copy("analysis.warning.leverage"))


def _stress_frame(context: dict) -> pd.DataFrame:
    release = context["release"]["release_id"]
    # Preferred release contract: one asset-specific shock per scenario and fund;
    # product-level shocked return already includes daily-reset/FX/fee mechanics.
    f = context["load_frame"](release, "stress_vectors.parquet")
    required = {"release_id", "method", "scenario", "fund_index", "shock_return",
                "source_class", "start", "end"}
    if not required.issubset(f.columns):
        raise ValueError("Calibrated Stage 06 shock-vector schema is incomplete")
    f = f[(f["release_id"].astype(str) == str(release)) &
          (f["method"] == st.session_state["v8_method"])].copy()
    if f.empty:
        raise ValueError("No calibrated stress vectors for current model release")
    f["fund_index"] = pd.to_numeric(f["fund_index"], errors="raise").astype(int)
    f["shock_return"] = pd.to_numeric(f["shock_return"], errors="raise")
    if f["shock_return"].isna().any() or not np.isfinite(f["shock_return"]).all():
        raise ValueError("Stress vectors contain invalid returns")
    if not f["fund_index"].between(0, len(context["tickers"]) - 1).all():
        raise ValueError("Stress instrument index outside current release")
    if f.duplicated(["scenario", "fund_index"]).any():
        raise ValueError("Duplicate scenario/fund shocks")
    return f


def _stress(context: dict, portfolios: list[Portfolio]) -> None:
    st.subheader(copy("analysis.metrics.drawdown"),
                 help=copy("analysis.metrics.drawdown_help"))
    try:
        frames = _stress_frame(context)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.info(copy("analysis.empty.no_history")); st.code(str(exc)); return
    scenario_cards = st.columns(3)
    for column, (code, title) in zip(scenario_cards, SCENARIOS):
        with column:
            st.markdown(f"#### {title}")
            # Only exact named scenario IDs are accepted; no partial substring guesses.
            f = frames[frames["scenario"].astype(str).isin((code, title))]
            if f.empty or len(f) != len(context["tickers"]):
                st.info(copy("analysis.empty.no_history")); continue
            if f["fund_index"].nunique() != len(context["tickers"]):
                st.info(copy("analysis.empty.no_history")); continue
            ordered = f.sort_values("fund_index")
            shock = ordered["shock_return"].to_numpy(float)
            # A one-period full-portfolio weighted return is a calibrated
            # scenario impact, NOT a simulated historical NAV path/drawdown.
            for p in portfolios:
                impact = float(as_weights(p.vector()) @ shock)
                st.metric(p.name, f"{impact:+.2%}")
            source = ", ".join(sorted(f["source_class"].astype(str).unique()))
            dates = f["start"].astype(str).unique()
            ends = f["end"].astype(str).unique()
            st.caption(f"{source} · {', '.join(dates)}–{', '.join(ends)}")


def _crossing(context: dict, p: Portfolio, q: Portfolio) -> float | None:
    """Call wealth backend's exact resolver; reject signature drift explicitly.

    t*=0 is excluded by the backend contract. Do not interpolate plotted lines
    independently or invent crossings when calibration inputs are absent.
    """
    model = context["model"]
    vals = {
        "w_a": as_weights(p.vector()), "w_b": as_weights(q.vector()),
        "weights_a": as_weights(p.vector()), "weights_b": as_weights(q.vector()),
        "model": model, "prepared_model": model,
        "mu_log": getattr(model, "mu_log_ann", None),
        "mu_log_ann": getattr(model, "mu_log_ann", None),
        "cov_log": getattr(model, "cov_ann", None),
        "cov_ann": getattr(model, "cov_ann", None),
        "max_years": 100.0, "horizon_max": 100.0,
    }
    uncertainty = getattr(model, "param_uncertainty", None)
    if isinstance(uncertainty, (list, tuple)) and len(uncertainty) == 2:
        vals["c_mat"], vals["u_mat"] = uncertainty
    params = signature(find_band_intersection_time).parameters
    unknown = [name for name, item in params.items()
               if item.default is Parameter.empty and
               item.kind not in (Parameter.VAR_KEYWORD, Parameter.VAR_POSITIONAL)
               and (name not in vals or vals[name] is None)]
    if unknown:
        raise TypeError(f"Unmatched wealth calculation contract: {unknown}")
    result = find_band_intersection_time(**{key: value for key, value in vals.items()
             if key in params and value is not None})
    if result is None:
        return None
    # Some backend versions return an object with the intersection scalar.
    t = getattr(result, "t_star", result)
    if isinstance(t, dict):
        t = t.get("t_star", t.get("year"))
    if t is None:
        return None
    if not isinstance(t, (int, float, np.number)) or not math.isfinite(float(t)):
        raise ValueError("Unrecognised crossing result")
    if float(t) <= 0 or float(t) > 100:
        return None
    return float(t)


def _intersections(context: dict, ps: list[Portfolio]) -> None:
    st.subheader(copy("analysis.intersection.title"),
                 help=copy("analysis.intersection.help"))
    if len(ps) < 2:
        st.info(copy("analysis.intersection.need_two")); return
    labels = [p.name + f" [{i+1}]" for i, p in enumerate(ps)]
    cells: list[list[str]] = [["—" for _ in ps] for _ in ps]
    for i, j in combinations(range(len(ps)), 2):
        try:
            forward = _crossing(context, ps[i], ps[j])
            backward = _crossing(context, ps[j], ps[i])
        except (TypeError, ValueError, ArithmeticError, KeyError) as exc:
            cells[i][j] = cells[j][i] = "N/A"
            st.info(copy("analysis.intersection.partial")); st.code(str(exc))
            continue
        cells[i][j] = (f"{forward:.2f}" if forward is not None else "—")
        cells[j][i] = (f"{backward:.2f}" if backward is not None else "—")
    st.dataframe(pd.DataFrame(cells, index=labels, columns=labels),
                 use_container_width=True)
    if all(cells[i][j] == "—" for i in range(len(ps))
           for j in range(len(ps)) if i != j):
        st.caption(copy("analysis.intersection.none"))


def _history(context: dict, ps: list[Portfolio]) -> None:
    # Historical observation paths are optional and NEVER proxied by stress cards.
    try:
        f = context["load_frame"](context["release"]["release_id"],
                                 "historical_results.parquet")
    except (OSError, ValueError):
        return
    if not {"portfolio_id", "date", "wealth_index", "release_id", "method"}.issubset(f):
        return
    r = context["release"]["release_id"]
    f = f[(f["release_id"] == r) & (f["method"] == st.session_state["v8_method"])]
    for p in ps:
        series = f[f["portfolio_id"] == p.name].sort_values("date")
        if series.empty or (series["wealth_index"] <= 0).any():
            continue
        nav = series["wealth_index"].to_numpy(float)
        mdd = float(np.min(nav / np.maximum.accumulate(nav) - 1))
        st.metric(f"{p.name} · {copy('analysis.metrics.drawdown')}", f"{mdd:.2%}")


def render(context: dict) -> None:
    st.title(copy("analysis.title")); st.write(copy("analysis.subtitle"))
    ps = _manage(context)
    if not ps:
        st.info(copy("analysis.empty.no_valid")); return
    try:
        cat = context["load_frame"](context["release"]["release_id"],
                                    "fund_catalogue.parquet")
        _metrics(context, ps, cat)
        _exposure(ps, cat)
        _stress(context, ps)
        _history(context, ps)
        _intersections(context, ps)
    except (KeyError, ValueError, TypeError, OSError) as exc:
        st.error(copy("app.error.invalid_data")); st.code(str(exc))
