"""Secondary release data contracts; synthetic inputs stay in pytest temp folders."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.build_stress_and_benchmarks import (
    build_catalogue, build_stress, build_benchmark, build_history, build_release,
    METHODS, REFERENCES,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def test_catalogue_identity_order_units_and_costs():
    f = build_catalogue(FIXTURES)
    u = pd.read_csv(FIXTURES / "01_verified_universe.csv", keep_default_na=False)
    assert len(f) == 68
    assert f.fund_id.tolist() == u.canonical_id.tolist()
    assert f.ticker.tolist() == u.display_ticker.tolist()
    assert np.array_equal(f.ter, u.ocf_ter_pct.astype(float) / 100)
    by = f.set_index("ticker")
    assert by.loc["SWDA", "quote_unit_conversion"] == 0.01
    assert by.loc["WLDS", "quote_unit_conversion"] == 1
    assert by.loc["COPA", "quote_unit"] == "GBx"  # preferred COPB listing
    assert by.loc["LQQ", "quote_unit"] == "EUR"
    assert by.loc["3QQQ", "leverage"] == 3
    assert by.loc["VUSA", "dist_type"] == "Distributing"
    assert by.loc["SWDA", "dist_type"] == "Accumulating"
    assert set(f.sleeve) == set(range(1, 7))


def test_stress_alignment_and_no_second_cost_deduction():
    c = build_catalogue(FIXTURES)
    f = build_stress(FIXTURES / "06_stress_calibration.json", c)
    assert len(f) == 408
    assert f.groupby(["method", "scenario"]).size().eq(68).all()
    v = f[(f.method == "etf") & (f.scenario == "2008")].set_index("fund_index")
    assert v.loc[48, "shock_return"] == pytest.approx(-0.942)
    assert v.loc[0, "shock_return"] == pytest.approx(0.038)
    assert f.loc[f.scenario == "2022", "end"].eq("2022-12").all()
    assert f.source_class.str.startswith("Stage06 research calibration").all()
    with pytest.raises(ValueError, match="order"):
        build_stress(FIXTURES / "06_stress_calibration.json", c.iloc[::-1])


def benchmark_input():
    return pd.DataFrame({
        "company_id": [f"company-{i}" for i in range(105)],
        "company": [f"Synthetic company {i}" for i in range(105)],
        "ticker": [f"T{i}" for i in range(105)],
        "country": "TEST", "sector": "TEST", "cap_bucket": "Large",
        "benchmark_weight": np.arange(1, 106, dtype=float),
    })


def test_benchmark_top100_and_exact_normalisation():
    b = build_benchmark(benchmark_input())
    assert len(b) == 100
    assert b.benchmark_weight.sum() == 1.0
    assert b.company_id.iloc[0] == "company-104"
    assert b.company_id.iloc[-1] == "company-5"
    assert b.benchmark_weight.iloc[0] / b.benchmark_weight.iloc[1] == pytest.approx(105 / 104)


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "negative", "too_short"])
def test_benchmark_rejects_invalid_input(mutation):
    f = benchmark_input()
    if mutation == "duplicate":
        f.loc[1, "company_id"] = f.loc[0, "company_id"]
    elif mutation == "nan":
        f.loc[0, "benchmark_weight"] = np.nan
    elif mutation == "negative":
        f.loc[0, "benchmark_weight"] = -0.1
    else:
        f = f.iloc[:99]
    with pytest.raises(ValueError):
        build_benchmark(f)


def history_input():
    return pd.DataFrame([
        (p, str(d), 0.01 if i == 0 else 0.0, m)
        for m in METHODS for p in REFERENCES
        for i, d in enumerate(pd.period_range("2014-02", "2026-09", freq="M"))
    ], columns=["portfolio_id", "date", "monthly_return", "method"])


def test_history_baseline_calendar_compounding_and_both_methods():
    f = build_history(history_input())
    assert len(f) == 6 * 153 * 2
    for _, path in f.groupby(["method", "portfolio_id"]):
        assert path.date.iloc[0] == "2014-01"
        assert path.date.iloc[-1] == "2026-09"
        assert path.wealth_index.iloc[0] == 1.0
        assert path.wealth_index.iloc[1] == 1.01
        assert path.wealth_index.iloc[-1] == 1.01


@pytest.mark.parametrize("mutation", ["gap", "duplicate", "wipeout", "inf"])
def test_history_rejects_missing_or_invalid_observations(mutation):
    f = history_input()
    if mutation == "gap":
        f = f.iloc[1:]
    elif mutation == "duplicate":
        f = pd.concat([f, f.iloc[:1]])
    elif mutation == "wipeout":
        f.loc[0, "monthly_return"] = -1
    else:
        f.loc[0, "monthly_return"] = np.inf
    with pytest.raises(ValueError):
        build_history(f)


def test_partial_build_reports_missing_sources_without_fake_tables(tmp_path):
    report = build_release(FIXTURES, tmp_path / "inputs", tmp_path / "release")
    assert report["status"] == "partial"
    assert set(report["written"]) == {"fund_catalogue.parquet", "stress_vectors.parquet"}
    assert len(report["blocked"]) == 5
    assert not (tmp_path / "release" / "benchmark_vall.parquet").exists()
    assert not (tmp_path / "release" / "historical_results.parquet").exists()
    assert pd.read_parquet(tmp_path / "release" / "stress_vectors.parquet").shape[0] == 408


def test_complete_build_roundtrip_with_explicit_synthetic_inputs(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    benchmark_input().to_csv(inputs / "benchmark_vall.csv", index=False)
    history_input().to_csv(inputs / "reference_monthly_returns.csv", index=False)
    universe = pd.read_csv(FIXTURES / "01_verified_universe.csv", keep_default_na=False)
    sources = []
    for fund in universe.itertuples(index=False):
        if fund.asset_class in {"Cash", "Bonds", "Commodities"}:
            continue
        name = f"{fund.display_ticker}.csv"
        pd.DataFrame([dict(security_id="US0000000000", company_id="US0000000000",
                           company="Synthetic company", ticker="TEST", country="TEST",
                           sector="TEST", cap_bucket="Large", weight=0.9)]).to_csv(inputs / name, index=False)
        sources.append(dict(path=name, fund_id=fund.canonical_id, weight_unit="decimal",
                            source_as_of="2026-10-16", data_source="SYNTHETIC TEST ONLY"))
    (inputs / "constituent_sources.json").write_text(json.dumps(dict(
        as_of="2026-10-18", weight_basis="underlying_constituent_weight", sources=sources)), encoding="utf-8")
    (inputs / "secondary_sources.json").write_text(json.dumps({
        "benchmark": {"source": "SYNTHETIC TEST ONLY", "as_of": "2026-09-30",
                      "benchmark": "FTSE Global All Cap", "weight_basis": "company_cap_weight"},
        "history": {"source": "SYNTHETIC TEST ONLY", "currency": "GBP",
                    "return_basis": "net_investor_wealth",
                    "accounting": "fixed_units_with_distribution_cash"}
    }), encoding="utf-8")
    report = build_release(FIXTURES, inputs, tmp_path / "release")
    assert report["status"] == "complete"
    assert len(report["written"]) == 8
    assert pd.read_parquet(tmp_path / "release" / "benchmark_vall.parquet").benchmark_weight.sum() == 1.0
    csv = pd.read_csv(tmp_path / "release" / "benchmark_vall.csv", float_precision="round_trip")
    assert csv.benchmark_weight.sum() == 1.0
    pd.testing.assert_frame_equal(csv, pd.read_parquet(tmp_path / "release" / "benchmark_vall.parquet"), check_exact=True)
    assert pd.read_parquet(tmp_path / "release" / "company_holdings.parquet").shape[0] == 1

