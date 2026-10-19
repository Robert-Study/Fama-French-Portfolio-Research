"""Dated V8 constituent ingestion. No downloads, inferred identities or proxy data.

``constituent_sources.json`` in data/release_inputs declares ``as_of``,
``weight_basis: underlying_constituent_weight`` and one source per equity fund.
Each source declares path, fund_id, weight_unit (decimal/percent), source_as_of,
data_source, and optionally column_map (canonical -> vendor name), skiprows,
encoding. CSV and Parquet are supported. Input rows are equity constituents;
exclude cash/collateral upstream and retain their missing mass, without rescaling.

Required columns: security_id, company_id, company, ticker, country, sector,
cap_bucket, weight. An audited issuer crosswalk must supply company_id (ISIN or
LEI). Different share classes/ADRs must share that ID and canonical metadata.
Names/tickers are never identity keys. Duplicate securities are errors.

The requested H is unlevered constituent weight (row sum <= 1), including for
leveraged products. It is NOT leveraged exposure per GBP NAV. No prices, fees,
FX conversions or leverage multipliers enter this pipeline. K is data driven.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from scipy import sparse

from portfolio.model import PreparedModel

AS_OF = "2026-10-18"
ATTRIBUTES = ["company", "ticker", "country", "sector", "cap_bucket"]
COMPANY_COLUMNS = ["company_index", "company_id", *ATTRIBUTES, "as_of", "data_source", "source_as_of"]
BENCHMARK_COLUMNS = ["company_id", *ATTRIBUTES, "benchmark_weight"]
EQUITY_CLASSES = {"ETFs", "Factor-tilted ETFs", "Leveraged ETFs / ETPs"}
ZERO_CLASSES = {"Cash", "Bonds", "Commodities"}
WEIGHT_BASIS = "underlying_constituent_weight"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(frame, columns):
    _require(frame.columns.is_unique, "Duplicate column names")
    _require(set(columns).issubset(frame), f"Missing columns: {sorted(set(columns) - set(frame))}")
    for column in columns:
        _require(frame[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all(),
                 f"Missing or non-text {column}")
        frame[column] = frame[column].str.strip()


def _date(value):
    _require(isinstance(value, str) and date.fromisoformat(value).isoformat() == value,
             "Expected ISO source date YYYY-MM-DD")
    _require(value <= AS_OF, "Source date is after release")
    return value


def parse_constituents(path, *, fund_id, weight_unit, source_as_of, data_source,
                       column_map=None, skiprows=0, encoding="utf-8-sig"):
    """Parse one already identity-mapped equity snapshot with explicit units."""
    path = Path(path)
    _require(weight_unit in {"decimal", "percent"}, "weight_unit must be decimal or percent")
    _date(source_as_of)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding, skiprows=skiprows)
    elif path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        raise ValueError("Constituent source must be CSV or Parquet")
    mapping = column_map or {}
    _require(len(set(mapping.values())) == len(mapping), "Ambiguous column_map")
    _require(set(mapping.values()).issubset(frame), "column_map references missing vendor fields")
    frame = frame.rename(columns={v: k for k, v in mapping.items()})
    _text(frame, ["security_id", "company_id", *ATTRIBUTES])
    _require("weight" in frame, "Missing weight column")
    raw = frame["weight"].astype(str).str.strip()
    if weight_unit == "percent":
        raw = raw.str.removesuffix("%")
    frame["weight"] = pd.to_numeric(raw, errors="raise") / (100 if weight_unit == "percent" else 1)
    for key, value in {"fund_id": fund_id, "source_as_of": source_as_of, "data_source": data_source}.items():
        if key in frame:
            _require(frame[key].eq(value).all(), f"Source/manifest {key} conflict")
        frame[key] = value
    return frame


def read_constituents(inputs):
    """Load the local manifest; reject collateral and duplicate fund snapshots."""
    inputs = Path(inputs)
    manifest = json.loads((inputs / "constituent_sources.json").read_text(encoding="utf-8-sig"))
    _require(manifest["as_of"] == AS_OF, "Constituent release date mismatch")
    _require(manifest["weight_basis"] == WEIGHT_BASIS, "Unsupported weight_basis; need underlying constituent weights")
    sources = manifest["sources"]
    _require(isinstance(sources, list) and len(sources) > 0, "Missing source snapshots")
    ids = [s["fund_id"] for s in sources]
    _require(len(set(ids)) == len(ids), "Duplicate fund source snapshots")
    frames = []
    for source in sources:
        options = dict(source)
        path = inputs / options.pop("path")
        frames.append(parse_constituents(path, **options))
    return pd.concat(frames, ignore_index=True)


@dataclass(frozen=True)
class HoldingsDataset:
    company_holdings: pd.DataFrame
    fund_links: pd.DataFrame
    holdings_csr: sparse.csr_matrix
    fund_ids: tuple[str, ...]
    tickers: tuple[str, ...]


def build_holdings(universe, constituents):
    """Aggregate securities to companies, preserving the 68-row fixture order."""
    u, f = universe.copy().reset_index(drop=True), constituents.copy()
    _text(u, ["canonical_id", "display_ticker", "asset_class", "verification_status"])
    _require(len(u) == 68 and u.canonical_id.is_unique and u.display_ticker.is_unique,
             "Expected 68 unique universe funds and tickers")
    _require(u.verification_status.eq("verified_current").all(), "Unverified universe")
    _require(u.asset_class.isin(EQUITY_CLASSES | ZERO_CLASSES).all(), "Unknown universe asset class")
    fields = ["fund_id", "security_id", "company_id", *ATTRIBUTES, "source_as_of", "data_source"]
    _text(f, fields)
    _require(len(f) > 0 and "weight" in f, "Missing constituent weights")
    for field in ["company_id", "security_id"]:
        # Syntax only; the upstream issuer crosswalk supplies verified identities.
        _require(f[field].str.fullmatch(r"(?:[A-Z]{2}[A-Z0-9]{9}[0-9]|[A-Z0-9]{18}[0-9]{2})").all(),
                 f"{field} must be an ISIN or LEI")
    for value in f.source_as_of.unique():
        _date(value)
    f["weight"] = pd.to_numeric(f.weight, errors="raise").astype(np.float64)
    _require(np.isfinite(f.weight).all() and f.weight.ge(0).all(), "Weights must be finite and nonnegative")
    _require(not f.duplicated(["fund_id", "security_id"]).any(), "Duplicate fund/security row")
    _require(f.groupby("security_id").company_id.nunique().le(1).all(), "Conflicting security/company mapping")
    _require(f.groupby("fund_id").source_as_of.nunique().eq(1).all(), "Mixed source dates within fund")
    equity_ids = set(u.loc[u.asset_class.isin(EQUITY_CLASSES), "canonical_id"])
    _require(set(f.fund_id) == equity_ids, "Missing equity funds, unknown funds or non-equity constituent rows")
    sums = f.groupby("fund_id").weight.sum()
    _require(sums.le(1.0 + 1e-12).all(), "Constituent weights exceed one; do not normalise excess mass")
    _require(sums.gt(0).all(), "Equity fund has no positive constituents")
    _require(f.groupby("company_id")[ATTRIBUTES].nunique().le(1).all().all(),
             "Conflicting canonical company metadata; repair issuer crosswalk")
    f = f.loc[f.weight.gt(0)].sort_values(["fund_id", "company_id", "security_id"])
    companies = f[["company_id", *ATTRIBUTES]].drop_duplicates("company_id").sort_values("company_id").reset_index(drop=True)
    companies.insert(0, "company_index", np.arange(len(companies), dtype=np.int32))
    companies["as_of"] = AS_OF
    # Release date is not a claim that each issuer published on that date.
    for field in ["data_source", "source_as_of"]:
        lineage = f.groupby("company_id")[field].agg(lambda values: " | ".join(sorted(set(values))))
        companies[field] = companies.company_id.map(lineage)
    companies = companies[COMPANY_COLUMNS]
    links = f.groupby(["fund_id", "company_id"], as_index=False, sort=True).weight.sum()
    fund_index = dict(zip(u.canonical_id, range(68)))
    company_index = dict(zip(companies.company_id, companies.company_index))
    links["fund_index"] = links.fund_id.map(fund_index)
    links["company_index"] = links.company_id.map(company_index)
    links = links.sort_values(["fund_index", "company_index"]).reset_index(drop=True)
    exact = links.weight.to_numpy()
    values = exact.astype(np.float32)
    # Directed rounding never adds constituent mass. SciPy's float32 reduction
    # can still round upward; only that numerical excess is corrected below.
    rounded_up = values.astype(np.float64) > exact
    values[rounded_up] = np.nextafter(values[rounded_up], np.float32(0))
    matrix = sparse.csr_matrix((values, (links.fund_index, links.company_index)), shape=(68, len(companies)))
    for _ in range(8):
        totals = np.maximum(np.asarray(matrix.sum(axis=1)).ravel(),
                            np.asarray(matrix.astype(np.float64).sum(axis=1)).ravel())
        excess = np.flatnonzero(totals > 1)
        if not len(excess):
            break
        for j in excess:
            start, end = matrix.indptr[j:j + 2]
            largest = start + np.argmax(matrix.data[start:end])
            matrix.data[largest] = np.nextafter(
                np.float32(matrix.data[largest] - (totals[j] - 1)), np.float32(0))
    _require((np.asarray(matrix.sum(axis=1)) <= 1).all()
             and (np.asarray(matrix.astype(np.float64).sum(axis=1)) <= 1).all(), "Cannot bound float32 row sum")
    _require((matrix.data >= 0).all(), "Invalid float32 rounding correction")
    links["weight"] = matrix.data.copy()
    links["ticker"] = links.fund_id.map(dict(zip(u.canonical_id, u.display_ticker)))
    links = links[["fund_id", "ticker", "company_id", "weight"]]
    return HoldingsDataset(companies, links, matrix, tuple(u.canonical_id), tuple(u.display_ticker))


def attach_holdings(model: PreparedModel, dataset: HoldingsDataset) -> PreparedModel:
    """Return a detached model, requiring evidence of canonical fund alignment."""
    _require(model.num_assets == 68, "Expected 68 model assets")
    _require(tuple(model.metadata.get("canonical_tickers", ())) == dataset.tickers,
             "Model canonical fund order does not match holdings")
    if "canonical_fund_ids" in model.metadata:
        _require(tuple(model.metadata["canonical_fund_ids"]) == dataset.fund_ids, "Model fund ID order mismatch")
    matrix = dataset.holdings_csr.copy()
    for array in (matrix.data, matrix.indices, matrix.indptr):
        array.flags.writeable = False
    return replace(model, holdings_csr=matrix, metadata={
        **model.metadata, "holdings_weight_basis": WEIGHT_BASIS, "holdings_as_of": AS_OF,
        "canonical_fund_ids": list(dataset.fund_ids),
        "holdings_company_ids": dataset.company_holdings.company_id.tolist(),
    })


def write_holdings(dataset, output):
    """Stage and round-trip check all tables before replacing any outputs."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    names = ["company_holdings.parquet", "fund_links.parquet", "holdings_csr.npz"]
    with tempfile.TemporaryDirectory(dir=output, prefix=".ingestion-") as temp:
        stage = Path(temp)
        for name, frame in zip(names[:2], [dataset.company_holdings, dataset.fund_links]):
            frame.to_parquet(stage / name, index=False, engine="pyarrow")
            pd.testing.assert_frame_equal(frame, pd.read_parquet(stage / name))
        sparse.save_npz(stage / names[2], dataset.holdings_csr)
        restored = sparse.load_npz(stage / names[2])
        _require(restored.dtype == np.float32 and restored.shape == dataset.holdings_csr.shape
                 and (restored != dataset.holdings_csr).nnz == 0, "CSR round-trip mismatch")
        for name in names:
            (stage / name).replace(output / name)


def build_benchmark(frame):
    """Top 100 company cap weights, with an exact float64 sum of one.

    benchmark_weight must be audited company-level global cap weights, not
    pooled fund holdings or equal weights. Source provenance is checked by the
    release builder. Share classes must already be aggregated upstream.
    """
    f = frame.copy()
    _text(f, BENCHMARK_COLUMNS[:-1])
    _require("benchmark_weight" in f, "Missing benchmark_weight")
    _require(f.company_id.is_unique, "Benchmark must already aggregate share classes to unique companies")
    f = f[BENCHMARK_COLUMNS].copy()
    f["benchmark_weight"] = pd.to_numeric(f.benchmark_weight, errors="raise").astype(float)
    _require(np.isfinite(f.benchmark_weight).all() and f.benchmark_weight.gt(0).all(),
             "Benchmark weights must be finite and positive")
    _require(len(f) >= 100, "Need at least 100 source companies")
    f = f.sort_values(["benchmark_weight", "company_id"], ascending=[False, True]).head(100).reset_index(drop=True)
    total = float(f.benchmark_weight.sum())
    _require(np.isfinite(total) and total > 0, "Invalid benchmark total")
    f["benchmark_weight"] /= total
    for _ in range(8):
        delta = 1.0 - float(f.benchmark_weight.sum())
        if delta == 0:
            break
        f.loc[0, "benchmark_weight"] += delta
    _require(float(f.benchmark_weight.sum()) == 1.0, "Benchmark sum is not exactly 1.0")
    return f
