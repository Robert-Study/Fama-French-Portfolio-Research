"""Synthetic contracts only; no generated observations enter production data."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from portfolio.ingestion import (
    AS_OF, COMPANY_COLUMNS, build_holdings, parse_constituents,
    read_constituents, write_holdings, attach_holdings, build_benchmark,
)
from portfolio.model import PreparedModel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def universe():
    return pd.read_csv(ROOT / "tests/fixtures/01_verified_universe.csv", keep_default_na=False)


def source_rows(universe, count=105):
    """Explicitly synthetic issuer IDs and classifications for scale tests."""
    rows = []
    for fund in universe.itertuples(index=False):
        if fund.asset_class in {"Cash", "Bonds", "Commodities"}:
            continue
        for i in range(count):
            rows.append(dict(
                fund_id=fund.canonical_id, security_id=f"US{i:010d}",
                company_id=f"US{i:010d}", company=f"Test company {i}", ticker=f"T{i}",
                country="TEST", sector="TEST", cap_bucket="Large",
                weight=0.95 / count, source_as_of="2026-10-16",
                data_source="SYNTHETIC TEST ONLY",
            ))
    return pd.DataFrame(rows)


def test_canonical_order_zero_rows_sparse_scale_and_determinism(universe):
    rows = source_rows(universe, 10_000)
    result = build_holdings(universe, rows)
    assert sparse.isspmatrix_csr(result.holdings_csr)
    assert result.holdings_csr.shape == (68, 10_000)
    assert result.holdings_csr.dtype == np.float32
    assert result.company_holdings.columns.tolist() == COMPANY_COLUMNS
    assert result.company_holdings.company_index.tolist() == list(range(10_000))
    assert result.company_holdings.company_id.is_unique
    assert result.company_holdings.as_of.eq(AS_OF).all()
    sums = np.asarray(result.holdings_csr.sum(axis=1)).ravel()
    non_equity = universe.asset_class.isin(["Cash", "Bonds", "Commodities"])
    assert (sums[non_equity] == 0).all()
    assert np.allclose(sums[~non_equity], 0.95)
    assert (sums <= 1).all()
    again = build_holdings(universe, rows.sample(frac=1, random_state=42))
    pd.testing.assert_frame_equal(result.company_holdings, again.company_holdings)
    pd.testing.assert_frame_equal(result.fund_links, again.fund_links)
    assert (result.holdings_csr != again.holdings_csr).nnz == 0


def test_share_classes_aggregate_and_tickers_never_identify_companies(universe):
    rows = source_rows(universe, 3)
    # Two securities map explicitly to one issuer. A third shares its ticker.
    rows.loc[rows.company_id == "US0000000001", ["company_id", "company", "ticker"]] = [
        "US0000000000", "Test company 0", "T0"]
    rows.loc[rows.company_id == "US0000000002", "ticker"] = "T0"
    result = build_holdings(universe, rows)
    assert result.holdings_csr.shape == (68, 2)
    assert result.fund_links.groupby("fund_id").size().eq(2).all()
    idx = universe.index[universe.display_ticker.eq("VWRP")][0]
    assert result.holdings_csr[idx, 0] == pytest.approx(0.95 * 2 / 3)
    assert result.holdings_csr[idx, 1] == pytest.approx(0.95 / 3)


@pytest.mark.parametrize("mutation", [
    "negative", "nan", "inf", "excess", "duplicate", "unknown_fund", "cash",
    "missing_fund", "bad_id", "future", "empty_source", "conflict", "security_conflict",
])
def test_reject_bad_constituents(universe, mutation):
    f = source_rows(universe, 3)
    if mutation in {"negative", "nan", "inf", "excess"}:
        f.loc[0, "weight"] = {"negative": -0.1, "nan": np.nan, "inf": np.inf, "excess": 1.0}[mutation]
    elif mutation == "duplicate":
        f = pd.concat([f, f.iloc[:1]], ignore_index=True)
    elif mutation == "unknown_fund":
        f.loc[0, "fund_id"] = "NOT_A_FUND"
    elif mutation == "cash":
        f.loc[0, "fund_id"] = universe.iloc[0].canonical_id
    elif mutation == "missing_fund":
        f = f[f.fund_id != f.iloc[0].fund_id]
    elif mutation == "bad_id":
        f.loc[0, "company_id"] = "NAME:UNVERIFIED"
    elif mutation == "future":
        f.loc[0, "source_as_of"] = "2026-10-19"
    elif mutation == "empty_source":
        f.loc[0, "data_source"] = " "
    elif mutation == "conflict":
        f.loc[0, "country"] = "CONFLICT"
    else:
        f.loc[0, "security_id"] = f.loc[1, "security_id"]
    with pytest.raises(ValueError):
        build_holdings(universe, f)


def test_float32_full_rows_never_exceed_one_and_links_reconcile(universe):
    f = source_rows(universe, 105)
    f["weight"] = 1 / 105
    result = build_holdings(universe, f)
    assert (np.asarray(result.holdings_csr.sum(axis=1)) <= 1).all()
    assert (np.asarray(result.holdings_csr.astype(np.float64).sum(axis=1)) <= 1).all()
    links = result.fund_links
    companies = result.company_holdings.set_index("company_id").company_index
    funds = dict(zip(universe.canonical_id, range(68)))
    rebuilt = sparse.csr_matrix((links.weight, (
        links.fund_id.map(funds), links.company_id.map(companies))), shape=result.holdings_csr.shape)
    assert (rebuilt != result.holdings_csr).nnz == 0


def test_parser_explicit_units_mapping_and_dates(tmp_path, universe):
    raw = source_rows(universe, 3).iloc[:3].drop(columns=["fund_id", "source_as_of", "data_source"])
    raw = raw.rename(columns={"weight": "Weight (%)"})
    raw["Weight (%)"] = ["20%", "30%", "45%"]
    path = tmp_path / "issuer.csv"
    raw.to_csv(path, index=False)
    options = dict(fund_id=source_rows(universe, 1).iloc[0].fund_id, weight_unit="percent",
                   source_as_of="2026-10-16", data_source="SYNTHETIC TEST ONLY",
                   column_map={"weight": "Weight (%)"})
    parsed = parse_constituents(path, **options)
    assert parsed.weight.tolist() == [0.2, 0.3, 0.45]
    assert parsed.source_as_of.eq("2026-10-16").all()
    with pytest.raises(ValueError):
        parse_constituents(path, **(options | {"weight_unit": "decimal"}))
    with pytest.raises(ValueError):
        parse_constituents(path, **(options | {"weight_unit": "guess"}))


def test_missing_manifest_fails_without_outputs(tmp_path, universe):
    with pytest.raises(FileNotFoundError):
        read_constituents(tmp_path)
    assert not list(tmp_path.iterdir())


def test_manifest_requires_underlying_weights_and_unique_funds(tmp_path, universe):
    f = source_rows(universe, 3)
    entries = []
    for i, (fund_id, part) in enumerate(f.groupby("fund_id")):
        path = f"fund-{i}.csv"
        part.drop(columns=["fund_id", "source_as_of", "data_source"]).to_csv(tmp_path / path, index=False)
        entries.append(dict(path=path, fund_id=fund_id, weight_unit="decimal",
                            source_as_of="2026-10-16", data_source="SYNTHETIC TEST ONLY"))
    manifest = dict(as_of=AS_OF, weight_basis="underlying_constituent_weight", sources=entries)
    target = tmp_path / "constituent_sources.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    result = build_holdings(universe, read_constituents(tmp_path))
    assert result.holdings_csr.shape == (68, 3)
    manifest["weight_basis"] = "collateral"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="weight_basis"):
        read_constituents(tmp_path)
    manifest["weight_basis"] = "underlying_constituent_weight"
    manifest["sources"].append(entries[0])
    target.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        read_constituents(tmp_path)


def test_parquet_npz_roundtrip_model_and_ui(tmp_path, universe):
    from ui.holdings import calculate, _fund_links
    result = build_holdings(universe, source_rows(universe))
    write_holdings(result, tmp_path)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "company_holdings.parquet"), result.company_holdings)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "fund_links.parquet"), result.fund_links)
    assert (sparse.load_npz(tmp_path / "holdings_csr.npz") != result.holdings_csr).nnz == 0
    model = PreparedModel(
        asset_ids=np.arange(68, dtype=np.uint16), quote_currency=["GBP"] * 68,
        mu_arith_ann=np.zeros(68), mu_log_ann=np.zeros(68), cov_ann=np.zeros((68, 68)),
        cov_monthly=np.zeros((68, 68)), param_uncertainty=(np.zeros((68, 68)), np.zeros((68, 68))),
        dist_policy=(np.zeros(68, dtype=bool), np.zeros(68)), sleeve_masks=np.ones((64, 68), dtype=bool),
        metadata={"canonical_tickers": universe.display_ticker.tolist()}, cash_idx=0,
    )
    attached = attach_holdings(model, result)
    assert model.holdings_csr is None
    assert attached.holdings_csr.shape == (68, 105)
    assert not attached.holdings_csr.data.flags.writeable
    frames = {"company_holdings.parquet": result.company_holdings, "fund_links.parquet": result.fund_links,
              "benchmark_vall.parquet": build_benchmark(result.company_holdings.assign(benchmark_weight=1.0))}
    context = dict(model=attached, tickers=universe.display_ticker.tolist(),
                   release={"release_id": "V8.0-2026-10-18"}, load_frame=lambda _, name: frames[name])
    q = np.zeros(68, dtype=int)
    q[universe.index[universe.display_ticker.eq("VWRP")][0]] = 10000
    lookthrough = calculate(context, q)
    assert lookthrough.mapped_count == 105
    assert lookthrough.mapped_exposure == pytest.approx(0.95)
    assert lookthrough.source_dates == ("2026-10-16",)
    assert _fund_links(context) == {}  # Company links are not nested funds.
    with pytest.raises(ValueError, match="order"):
        attach_holdings(PreparedModel(**{**model.__dict__, "metadata": {"canonical_tickers": list(reversed(context["tickers"]))}}), result)


def test_benchmark_selects_caps_ties_and_exact_sum():
    f = pd.DataFrame(dict(company_id=[f"US{i:010d}" for i in range(120)],
                          company=[f"Test {i}" for i in range(120)], ticker="TEST", country="TEST",
                          sector="TEST", cap_bucket="Large", benchmark_weight=np.arange(1, 121)))
    b = build_benchmark(f.sample(frac=1, random_state=10))
    assert len(b) == 100
    assert b.benchmark_weight.sum() == 1.0
    assert b.company_id.iloc[0] == "US0000000119"
    assert b.company_id.iloc[-1] == "US0000000020"
    assert b.benchmark_weight.iloc[0] / b.benchmark_weight.iloc[1] == pytest.approx(120 / 119)


@pytest.mark.parametrize("count", [3, 17, 257])
def test_full_rows_with_unequal_weights(universe, count):
    f = source_rows(universe, count)
    weights = np.random.default_rng(5).uniform(size=count)
    weights /= weights.sum()
    f["weight"] = np.tile(weights, len(f) // count)
    result = build_holdings(universe, f)
    for dtype in [np.float32, np.float64]:
        sums = np.asarray(result.holdings_csr.astype(dtype).sum(axis=1)).ravel()
        assert (sums <= 1).all()
        assert np.allclose(sums[sums > 0], 1)


@pytest.mark.parametrize("mutation", ["duplicate_id", "missing_fund", "unverified", "unknown_asset"])
def test_universe_contract(universe, mutation):
    f = source_rows(universe, 1)
    if mutation == "duplicate_id":
        universe.loc[1, "canonical_id"] = universe.loc[0, "canonical_id"]
    elif mutation == "missing_fund":
        universe = universe.iloc[:-1]
    elif mutation == "unverified":
        universe.loc[1, "verification_status"] = "unverified"
    else:
        universe.loc[1, "asset_class"] = "Unknown"
    with pytest.raises(ValueError):
        build_holdings(universe, f)
