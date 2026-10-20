"""Underlying Holdings — verified, release-locked CSR economic look-through.

Contracts: model.holdings_csr is fund x company economic exposure per GBP NAV;
company_holdings.parquet identifies each CSR column by unique company_index;
benchmark_vall.parquet contains the same company IDs and fractional weights.
No fallback to collateral, ticker joins or invented unmapped exposures.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import io
import math
import re
import zipfile
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from scipy import sparse
from ui.v8_shared import as_weights, checked_weights, copy, require_release_path, _meta_get

COLS = ("company_id", "company", "ticker", "country", "sector", "cap_bucket")


def _require(df: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = sorted(set(columns).difference(df.columns))
    if missing:
        raise ValueError(f"{label}: required release columns missing: {missing}")


def _validated_csr(model: Any, m: int) -> sparse.csr_matrix:
    raw = getattr(model, "holdings_csr", None)
    if raw is None:
        csr_path = require_release_path("holdings_csr.npz")
        if csr_path.is_file():
            try:
                raw = sparse.load_npz(csr_path)
                try:
                    object.__setattr__(model, "holdings_csr", raw)
                except Exception:
                    try:
                        setattr(model, "holdings_csr", raw)
                    except Exception:
                        pass
            except Exception:
                raw = None
    if raw is None or not sparse.issparse(raw):
        raise ValueError("PreparedModel.holdings_csr is unavailable")
    matrix = raw.tocsr(copy=False)
    if matrix.ndim != 2 or matrix.shape[0] != m:
        raise ValueError("Holdings matrix fund dimension differs from release universe")
    if not np.all(np.isfinite(matrix.data)) or (matrix.data < 0).any():
        raise ValueError("Holdings matrix contains invalid economic exposure")
    return matrix


def _company_metadata(context: dict, k: int) -> pd.DataFrame:
    data = context["load_frame"](context["release"]["release_id"],
                                 "company_holdings.parquet").copy()
    _require(data, ("company_index",) + COLS, "Company metadata")
    # Exactly one company row per CSR column; repeated fund holdings are NOT
    # summed again, as the CSR matrix already encodes economic exposures.
    meta = data[list(("company_index",) + COLS + tuple(c for c in
              ("as_of", "source_as_of", "data_source", "characteristic_origin", "security_count")
              if c in data))].drop_duplicates("company_index")
    idx = pd.to_numeric(meta["company_index"], errors="raise").to_numpy()
    if not np.array_equal(np.sort(idx), np.arange(k)) or len(meta) != k:
        raise ValueError("CSR company_index metadata is missing, duplicated or misaligned")
    meta = meta.sort_values("company_index").reset_index(drop=True)
    if meta["company_id"].isna().any() or meta["company_id"].duplicated().any():
        raise ValueError("Company identities not unique")
    return meta


def _benchmark(context: dict) -> pd.DataFrame:
    b = context["load_frame"](context["release"]["release_id"],
                              "benchmark_vall.parquet").copy()
    _require(b, ("company_id", "benchmark_weight"), "VALL benchmark")
    b["benchmark_weight"] = pd.to_numeric(b["benchmark_weight"], errors="raise")
    if not np.isfinite(b["benchmark_weight"]).all() or (b["benchmark_weight"] < 0).any():
        raise ValueError("Invalid benchmark weights")
    if b["company_id"].isna().any():
        raise ValueError("Benchmark company identity missing")
    # Duplicate securities for same economic company are expected and aggregated.
    amounts = b.groupby("company_id", as_index=False)["benchmark_weight"].sum()
    total = amounts["benchmark_weight"].sum()
    if not (0.99 <= total <= 1.01):
        raise ValueError("VALL constituent weights do not reconcile to 100%")
    amounts["benchmark_weight"] /= total
    attrs = [c for c in COLS if c in b.columns and c != "company_id"]
    if attrs:
        amounts = amounts.merge(b.drop_duplicates("company_id")[["company_id"] + attrs],
                                how="left", on="company_id", validate="one_to_one")
    return amounts


def _source_funds(matrix: sparse.csr_matrix, w: np.ndarray,
                  tickers: list[str]) -> dict[int, str]:
    names: dict[int, list[str]] = defaultdict(list)
    for fund_index in np.flatnonzero(w):
        row = matrix.getrow(int(fund_index))
        for column, exposure in zip(row.indices, row.data):
            if exposure > 0:
                names[int(column)].append(tickers[int(fund_index)])
    return {k: ", ".join(v) for k, v in names.items()}


@dataclass(frozen=True)
class Lookthrough:
    rows: pd.DataFrame
    mapped_exposure: float
    mapped_count: int
    hhi: float | None
    effective: float | None
    top10: float | None
    source_dates: tuple[str, ...]


def calculate(context: dict, q_bps: np.ndarray | list[int] | None = None) -> Lookthrough:
    model, tickers = context["model"], list(context["tickers"])
    q = checked_weights(st.session_state["v8_q_bps"] if q_bps is None else q_bps)
    if len(q) != len(tickers):
        raise ValueError("Allocation and fund universe dimensions differ")
    matrix = _validated_csr(model, len(tickers))
    meta = _company_metadata(context, matrix.shape[1]); benchmark = _benchmark(context)
    w = as_weights(q)
    exposure = np.asarray(w @ matrix).reshape(-1)
    if (exposure < -1e-10).any() or not np.isfinite(exposure).all():
        raise ValueError("Calculated company exposure is invalid")
    mapped = float(exposure.sum())
    meta["portfolio_exposure"] = np.maximum(exposure, 0)
    meta["source_fund"] = meta["company_index"].map(
        _source_funds(matrix, w, tickers)).fillna("")
    # Outer join retains companies in benchmark but not portfolio.
    result = meta.merge(benchmark, on="company_id", how="outer", suffixes=("", "_b"),
                        validate="one_to_one")
    for field in COLS[1:]:
        bfield = field + "_b"
        if bfield in result:
            result[field] = result[field].fillna(result.pop(bfield))
        result[field] = result[field].fillna(copy("underlying.table.unknown"))
    result["portfolio_exposure"] = result["portfolio_exposure"].fillna(0.0)
    result["benchmark_weight"] = result["benchmark_weight"].fillna(0.0)
    result["source_fund"] = result["source_fund"].fillna("")
    result["portfolio_equity_pct"] = (result["portfolio_exposure"] / mapped
                                      if mapped > 0 else np.nan)
    result["benchmark_equity_pct"] = result["benchmark_weight"]
    result["active_pp"] = 100 * (result["portfolio_equity_pct"]
                                 - result["benchmark_equity_pct"])
    mapped_positive = exposure[exposure > 0]
    if mapped > 0:
        p = mapped_positive / mapped
        hhi = float(p @ p); effective = (1 / hhi) if hhi > 0 else None
        top10 = float(np.sort(p)[-10:].sum())
    else:
        hhi = effective = top10 = None
    date_column = "source_as_of" if "source_as_of" in result else "as_of"
    dates = tuple(sorted({part.strip() for value in result.get(date_column, pd.Series(dtype=str))
                          .dropna().unique() for part in str(value).split("|")}))
    return Lookthrough(result, mapped, int(np.count_nonzero(exposure)), hhi,
                       effective, top10, dates)


def _reconcile(context: dict, result: Lookthrough) -> None:
    constituent_basis = _meta_get(getattr(context["model"], "metadata", None), "holdings_weight_basis", None) == "underlying_constituent_weight"
    st.subheader(copy("underlying.reconciliation.title"),
                 help=copy("underlying.reconciliation.help"))
    c = st.columns(4)
    c[0].metric(copy("underlying.metric.companies"), f"{result.mapped_count:,}",
                help=copy("underlying.metric.companies_help"))
    c[1].metric("Mapped constituent weight" if constituent_basis else copy("underlying.metric.gross_equity"),
                f"{result.mapped_exposure:.2%}",
                help=copy("underlying.metric.gross_equity_help"))
    c[2].metric(copy("underlying.metric.effective"),
                f"{result.effective:,.1f}" if result.effective is not None else "N/A",
                help=copy("underlying.metric.effective_help"))
    c[3].metric(copy("underlying.metric.securities"),
                "N/A", help=copy("underlying.metric.securities_help"))
    # Never infer unmapped exposures as 1 - mapped: leveraged exposure can > 1.
    info = context["release"].get("exposure_reconciliation", {})
    if not isinstance(info, dict):
        info = {}
    fields = ("mapped", "unmapped", "cash", "bonds", "commodities", "other")
    entries = []
    for key in fields:
        raw = result.mapped_exposure if key == "mapped" else info.get(key)
        entries.append({"Type": copy("underlying.reconciliation." + key),
                        ("Weight before leverage" if constituent_basis else "Exposure / NAV"): (f"{100*raw:.2f}%" if isinstance(raw, (int, float))
                                           and math.isfinite(raw) else "N/A")})
    st.dataframe(pd.DataFrame(entries), hide_index=True, use_container_width=True)
    if result.mapped_exposure > 1 + 1e-8:
        st.warning(copy("underlying.warning.leveraged"))
    if result.hhi is not None:
        # HHI and top-10 are calculated directly from mapped, normalised equity.
        st.write(f"HHI: {result.hhi:.6f} · Top 10: {result.top10:.2%}")


def _constituent_rows(matrix: sparse.csr_matrix, meta: pd.DataFrame,
                      fund_index: int) -> pd.DataFrame:
    row = matrix.getrow(fund_index)
    if row.nnz == 0:
        return pd.DataFrame()
    sub = meta.iloc[row.indices][["company", "ticker", "country", "sector"]].copy()
    sub["Exposure / fund NAV (%)"] = (100 * row.data).round(5)
    return sub.sort_values("Exposure / fund NAV (%)", ascending=False)


def _fund_links(context: dict) -> dict[int, list[tuple[int, float]]]:
    """Optional dated nested-fund graph; not multiplied into already expanded CSR."""
    try:
        df = context["load_frame"](context["release"]["release_id"],
                                   "fund_links.parquet")
    except (FileNotFoundError, OSError):
        return {}
    if {"fund_id", "ticker", "company_id", "weight"}.issubset(df.columns):
        # V8 ingestion company links duplicate CSR edges for audit/export.
        # They contain no nested-fund graph and must not be applied twice.
        return {}
    _require(df, ("parent_fund_index", "child_fund_index", "fraction"),
             "Nested-fund relationship graph")
    graph: dict[int, list[tuple[int, float]]] = defaultdict(list)
    m = len(context["tickers"])
    for row in df.itertuples(index=False):
        parent, child = int(row.parent_fund_index), int(row.child_fund_index)
        amount = float(row.fraction)
        if not (0 <= parent < m and 0 <= child < m and
                math.isfinite(amount) and 0 < amount <= 1):
            raise ValueError("Invalid nested-fund link")
        graph[parent].append((child, amount))
    for edges in graph.values():
        if sum(frac for _, frac in edges) > 1 + 1e-8:
            raise ValueError("Nested-fund fractions exceed NAV")
    return graph


def _walk_graph(index: int, weight: float, graph: dict,
                tickers: list[str], visited: frozenset[int]) -> None:
    """Recursive fund-of-fund identity view; CSR remains the sole exposure total."""
    if index in visited:
        raise ValueError("Cyclic fund-of-funds graph")
    if len(visited) >= 16:
        raise ValueError("Nested-fund graph exceeds validated recursion limit")
    for child, frac in graph.get(index, []):
        with st.expander(f"{tickers[child]} · {100*frac:.3f}% of parent NAV"):
            st.write(f"Path share: {100*weight*frac:.5f}% of selected fund NAV")
            _walk_graph(child, weight*frac, graph, tickers, visited | {index})


def _expand(context: dict) -> None:
    """Portfolio -> ETF -> nested fund (if dated links exist) -> company.

    The pre-expanded CSR is always used for terminal economic company exposures;
    graph traversal is for verified provenance, not a second leverage multiplier.
    """
    with st.expander(copy("underlying.loading.expand"), expanded=False):
        tickers = list(context["tickers"])
        matrix = _validated_csr(context["model"], len(tickers))
        meta = _company_metadata(context, matrix.shape[1])
        selected = st.selectbox(copy("underlying.table.filter_fund"), tickers,
                                key="v8_expander_fund")
        index = tickers.index(selected)
        company_rows = _constituent_rows(matrix, meta, index)
        if _meta_get(getattr(context["model"], "metadata", None), "holdings_weight_basis", None) == "underlying_constituent_weight":
            company_rows = company_rows.rename(columns={"Exposure / fund NAV (%)": "Constituent weight (%)"})
        if company_rows.empty:
            st.info(copy("underlying.empty.missing_source"))
        else:
            st.dataframe(company_rows, hide_index=True, use_container_width=True)
        # Additional fund-of-fund ancestry only when certified release graph exists.
        try:
            links = _fund_links(context)
            _walk_graph(index, 1.0, links, tickers, frozenset())
        except (ValueError, TypeError, KeyError) as exc:
            st.error(copy("underlying.warning.source_failure")); st.code(str(exc))


def _comparison(data: pd.DataFrame, group: str) -> None:
    import plotly.express as px
    if data["portfolio_equity_pct"].isna().all():
        st.info(copy("underlying.empty.no_equity")); return
    label = {"country": "underlying.country", "sector": "underlying.sector",
             "cap_bucket": "underlying.cap"}[group]
    with st.container():
        st.subheader(copy(label + ".title"), help=copy(label + ".help"))
        grouped = data.groupby(group, dropna=False)[
            ["portfolio_equity_pct", "benchmark_equity_pct"]].sum().reset_index()
        df = grouped.melt(id_vars=group, var_name="Series", value_name="Weight")
        df["Series"] = df["Series"].map({
            "portfolio_equity_pct": copy("underlying.chart.portfolio"),
            "benchmark_equity_pct": copy("underlying.chart.benchmark")})
        fig = px.bar(df, x=group, y="Weight", color="Series", barmode="group")
        fig.update_layout(yaxis_tickformat=".0%", margin=dict(t=12, b=12))
        st.plotly_chart(fig, use_container_width=True)


def render(context: dict) -> None:
    st.title(copy("underlying.title")); st.write(copy("underlying.subtitle"))
    model = context["model"]
    basis = _meta_get(getattr(model, "metadata", None), "holdings_weight_basis", None)
    if basis == "underlying_constituent_weight":
        st.info("This dataset shows constituent weights before leverage. For leveraged funds, "
                "these weights do not measure economic exposure per pound invested.")

    # Check CSR availability before running calculations
    if getattr(model, "holdings_csr", None) is None:
        csr_path = require_release_path("holdings_csr.npz")
        if csr_path.is_file():
            try:
                csr = sparse.load_npz(csr_path)
                try:
                    object.__setattr__(model, "holdings_csr", csr)
                except Exception:
                    try:
                        setattr(model, "holdings_csr", csr)
                    except Exception:
                        pass
            except Exception:
                pass

    if getattr(model, "holdings_csr", None) is None:
        st.warning("Underlying holdings lookthrough CSR data is unavailable for this release. "
                   "Provenance: data/release/holdings_csr.npz could not be loaded.")
        return

    try:
        with st.spinner(copy("underlying.loading.title")):
            state = calculate(context)
    except (FileNotFoundError, OSError, ValueError, KeyError, TypeError) as exc:
        st.error(copy("underlying.empty.missing_source")); st.code(str(exc)); return
    _reconcile(context, state)
    if state.mapped_exposure <= 0:
        st.info(copy("underlying.empty.no_equity")); return
    _expand(context)
    mode = st.radio(copy("underlying.view.label"), ("whole", "normalised"),
                    format_func=lambda k: copy("underlying.view." + k),
                    help=copy("underlying.view.normalised_help"), horizontal=True,
                    key="v8_holdings_view")
    source = state.rows.copy()
    source["Portfolio (%)"] = 100 * (source["portfolio_exposure"] if mode == "whole"
                                        else source["portfolio_equity_pct"])
    source["Benchmark (%)"] = 100 * source["benchmark_weight"]
    source["Active (pp)"] = (source["Portfolio (%)"] - source["Benchmark (%)"]
                              if mode == "normalised" else np.nan)
    st.subheader(copy("underlying.table.title"),
                 help=copy("underlying.table.active_help"))
    find = st.text_input(copy("underlying.table.search"), key="v8_company_find")
    countries = sorted(source["country"].astype(str).unique())
    sectors = sorted(source["sector"].astype(str).unique())
    c1, c2 = st.columns(2)
    country = c1.selectbox(copy("underlying.table.filter_country"), [""] + countries,
                           key="v8_company_country")
    sector = c2.selectbox(copy("underlying.table.filter_sector"), [""] + sectors,
                          key="v8_company_sector")
    filt = source
    if find:
        filt = filt.loc[filt["company"].astype(str).str.contains(re.escape(find), case=False)
                        | filt["ticker"].astype(str).str.contains(re.escape(find), case=False)]
    if country:
        filt = filt.loc[filt["country"] == country]
    if sector:
        filt = filt.loc[filt["sector"] == sector]
    filt = filt.sort_values("Portfolio (%)", ascending=False)
    st.caption(copy("underlying.table.results", count=f"{len(filt):,}"))
    st.caption(copy("underlying.table.virtualised_help"))
    page_size = 100
    pages = max(1, int(math.ceil(len(filt) / page_size)))
    page = st.number_input(copy("underlying.table.page", completed=1, total=pages),
                           min_value=1, max_value=pages, step=1, key="v8_holding_page")
    columns = {
        "company": copy("underlying.table.column.company"),
        "ticker": copy("underlying.table.column.ticker"),
        "country": copy("underlying.table.column.country"),
        "sector": copy("underlying.table.column.sector"),
        "cap_bucket": copy("underlying.table.column.cap"),
        "Portfolio (%)": copy("underlying.table.column.portfolio"),
        "Benchmark (%)": copy("underlying.table.column.benchmark"),
        "Active (pp)": copy("underlying.table.column.active"),
        "source_fund": copy("underlying.table.column.funds"),
    }
    view = filt.iloc[(page-1)*page_size:page*page_size]
    st.dataframe(view[list(columns)].rename(columns=columns), height=470,
                 use_container_width=True, hide_index=True)
    st.markdown(f"#### Top 50 — {copy('underlying.table.title')}")
    st.dataframe(source.sort_values("portfolio_exposure", ascending=False).head(50)
                 [list(columns)].rename(columns=columns), hide_index=True,
                 use_container_width=True)
    for key in ("country", "sector", "cap_bucket"):
        _comparison(source, key)
    # Complete export; benchmark-only rows and unknown classifications retained.
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("underlying_complete.csv", state.rows.to_csv(index=False))
        z.writestr("exposure_reconciliation.json",
                   __import__("json").dumps({("mapped_constituent_weight" if _meta_get(getattr(
                       context["model"], "metadata", None), "holdings_weight_basis", None) == "underlying_constituent_weight" else "mapped_equity_nav"): state.mapped_exposure,
                                             "hhi": state.hhi, "top10": state.top10}, indent=2))
    st.download_button(copy("underlying.action.export_zip"),
                       data=archive.getvalue(),
                       file_name="v8_underlying_complete.zip",
                       mime="application/zip", help=copy("underlying.export.help"))
