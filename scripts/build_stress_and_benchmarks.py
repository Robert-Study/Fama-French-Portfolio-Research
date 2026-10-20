"""Build secondary V8 tables from explicit, provenance-bearing local inputs.

No network access, random histories, fee re-deduction, or missing-data fill.
January 2014 is the historical wealth baseline; returns start February 2014.
Run from any working directory. Exit 2 means one or more tables are blocked.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio.ingestion import build_benchmark, build_holdings, read_constituents, write_holdings

RELEASE_ID = "V8.0-2026-10-18"
METHODS = ("holdings", "etf")
REFERENCES = ("sp500", "all_cap", "global_6040", "bonds", "value", "size")
SLEEVES = {
    1: "Core Developed Equity",
    2: "Factor, Thematic & EM Equity",
    3: "Sovereign & Inflation-Linked Bonds",
    4: "Credit & Emerging Market Debt",
    5: "Real Assets & Commodities",
    6: "GBP Liquidity & Cash Reserve",
}
CORE = set("VWRP SWDA VUSA VUKE VMID VERX VJPN VAPX ACWI VDPG VGER ISFR VALL VHVG".split())
SOVEREIGN = set("IGLS IGLT GLTL INXG IBTS IBTM IBTL ITPG".split())
CREDIT = set("IS15 SLXX VAGS GHYS VEMT".split())
BENCHMARK_COLUMNS = [
    "company_id", "company", "ticker", "country", "sector", "cap_bucket", "benchmark_weight",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def scalar(text, key):
    """Read one uniquely named quoted scalar in the pinned assumptions YAML.

    This intentionally does not claim to parse general YAML. All other
    assumptions remain outside this builder's scope.
    """
    matches = re.findall(r'^\s*' + re.escape(key) + r':\s*"([^"]+)"\s*$', text, re.M)
    require(len(matches) == 1, f"Expected one quoted assumptions scalar: {key}")
    return matches[0]


def columns(frame, names):
    require(set(names).issubset(frame), f"Missing columns: {sorted(set(names) - set(frame))}")
    require(not frame[names].isna().any().any(), "Null required field")


def text_columns(frame, names):
    columns(frame, names)
    for name in names:
        require(frame[name].map(lambda v: isinstance(v, str) and bool(v.strip())).all(),
                f"Empty or non-string {name}")


def build_catalogue(fixtures):
    fixtures = Path(fixtures)
    u = pd.read_csv(fixtures / "01_verified_universe.csv", keep_default_na=False)
    listings = pd.read_csv(fixtures / "01_listings.csv", keep_default_na=False)
    contracts = read_json(fixtures / "02_product_contracts.json")["contracts"]
    assumptions = (fixtures / "02_assumptions.yaml").read_text(encoding="utf-8-sig")
    cash_id = scalar(assumptions, "canonical_id")
    require(scalar(assumptions, "reporting_currency") == "GBP", "Expected GBP assumptions")
    require(scalar(assumptions, "as_of_date") == RELEASE_ID.removeprefix("V8.0-"),
            "Assumptions release date mismatch")
    require(len(u) == 68 and u.canonical_id.nunique() == 68, "Expected 68 unique funds")
    require(u.display_ticker.nunique() == 68, "Duplicate universe tickers")
    require(u.verification_status.eq("verified_current").all(), "Unverified universe identity")
    records = []
    for row in u.to_dict("records"):
        cid, ticker = row["canonical_id"], row["display_ticker"]
        contract = contracts.get(cid, {})
        if cid == cash_id:
            unit, sleeve, dist = "GBP", 6, "Accumulating"
        else:
            preferred = row["preferred_listing_ticker"] or ticker
            match = listings[(listings.canonical_id == cid) & (listings.ticker == preferred)]
            require(len(match) == 1, f"Missing/ambiguous preferred listing for {ticker}: {preferred}")
            unit = match.iloc[0].quote_unit
            require(match.iloc[0].listing_status in ("verified_listing", "issuer_confirmed_alias", "no_LSE_GBP_listing_confirmed", "stale_listing"), f"Unverified listing: {ticker}")
            if unit != row["quote_unit"]:
                require(match.iloc[0].listing_status != "verified_listing",
                        f"Conflicting verified quote units: {ticker}")
                # Dated verified universe takes precedence over an unverified
                # alias. Preserve any conflict in the build report below.
                unit = row["quote_unit"]
            if row["asset_class"] == "Commodities":
                sleeve = 5
            elif ticker in SOVEREIGN:
                sleeve = 3
            elif ticker in CREDIT:
                # VAGS is mixed government/credit: conservatively assigned to credit.
                sleeve = 4
            elif ticker in CORE:
                sleeve = 1
            else:
                require(row["asset_class"] in ("ETFs", "Factor-tilted ETFs", "Leveraged ETFs / ETPs"),
                        f"Unmapped asset class: {ticker}")
                # Scheme C matches existing UI. Leveraged equity and property are
                # thematic sleeve 2; broad all-world/all-cap funds remain core.
                sleeve = 2
            income = row["income_treatment"] or contract.get("income_treatment", "")
            if not income:
                income = row["legal_name"]
            if "distribut" in income.lower() or re.search(r"\bdist\b", income, re.I):
                dist = "Distributing"
            elif "accumul" in income.lower() or re.search(r"\bacc\b", income, re.I):
                dist = "Accumulating"
            else:
                raise ValueError(f"Unresolved income treatment: {ticker}")
        require(unit in ("GBP", "GBx", "USD", "EUR"), f"Unsupported quote unit: {unit}")
        ter = float(row["ocf_ter_pct"]) / 100
        leverage = float(contract.get("leverage_factor", 1.0))
        require(np.isfinite(ter) and 0 <= ter <= 0.02, f"Invalid TER: {ticker}")
        require(np.isfinite(leverage) and 1 <= leverage <= 3, f"Invalid leverage: {ticker}")
        require(bool(row["legal_name"]), f"Missing legal name: {ticker}")
        records.append(dict(
            ticker=ticker, fund_id=cid, name=row["legal_name"], sleeve=sleeve,
            sleeve_name=SLEEVES[sleeve], ter=ter, leverage=leverage, quote_unit=unit,
            quote_unit_conversion=0.01 if unit == "GBx" else 1.0, dist_type=dist,
        ))
    # Row order and display ticker are immutable. Quote fields describe the
    # preferred listing (e.g. COPA display identity -> COPB GBx execution line).
    return pd.DataFrame(records)


def build_stress(path, catalogue):
    spec = read_json(path)
    require(spec["release_id"] == RELEASE_ID, "Stress release mismatch")
    funds = spec["funds"]
    require([r["fund_id"] for r in funds] == catalogue.fund_id.tolist(),
            "Stress canonical fund order differs from catalogue")
    require([r["fund_index"] for r in funds] == list(range(68)), "Stress fund index mismatch")
    require(set(spec["scenarios"]) == {"2008", "2020", "2022"}, "Stress scenarios incomplete")
    records = []
    for method in METHODS:
        for scenario, window in spec["scenarios"].items():
            start, end = (pd.Period(window[k], freq="M") for k in ("start", "end"))
            require(start <= end, "Reversed stress window")
            for row in funds:
                shock = float(row["shocks"][scenario])
                require(np.isfinite(shock) and shock >= -1, "Invalid stress return")
                require(bool(row["lineage"].strip()), "Missing stress lineage")
                records.append(dict(
                    release_id=RELEASE_ID, method=method, scenario=scenario,
                    fund_index=row["fund_index"], shock_return=shock,
                    source_class="Stage06 research calibration; " + row["lineage"],
                    start=str(start), end=str(end),
                ))
    # These supplied GBP product returns already include costs, FX and leverage.
    # Both routes use the same external scenario, not separate empirical fits.
    result = pd.DataFrame(records)
    require(len(result) == 408, "Expected 408 stress rows")
    return result


def build_history(frame):
    text_columns(frame, ["portfolio_id", "date", "method"])
    columns(frame, ["monthly_return"])
    require(set(frame.method) == set(METHODS), "History needs both methods")
    require(set(frame.portfolio_id) == set(REFERENCES), "History needs six references")
    require(not frame.duplicated(["method", "portfolio_id", "date"]).any(), "Duplicate history observation")
    months = pd.period_range("2014-02", "2026-09", freq="M").astype(str).tolist()
    output = []
    for method in METHODS:
        for portfolio in REFERENCES:
            f = frame[(frame.method == method) & (frame.portfolio_id == portfolio)].sort_values("date")
            require(f.date.tolist() == months, f"Missing/extra months for {method}/{portfolio}; need 2014-02 through 2026-09")
            returns = pd.to_numeric(f.monthly_return, errors="raise").to_numpy(dtype=float)
            require(np.isfinite(returns).all() and (returns > -1).all(), "Invalid monthly wealth return")
            wealth = np.r_[1.0, np.cumprod(1 + returns)]
            require(np.isfinite(wealth).all() and (wealth > 0).all(), "Invalid cumulative wealth")
            output.extend(dict(
                portfolio_id=portfolio, date=date, wealth_index=float(value),
                release_id=RELEASE_ID, method=method,
            ) for date, value in zip(["2014-01"] + months, wealth, strict=True))
    return pd.DataFrame(output)


def provenance(inputs, kind):
    meta = read_json(inputs / "secondary_sources.json")[kind]
    require(isinstance(meta.get("source"), str) and bool(meta["source"].strip()), f"Missing {kind} source")
    if kind == "benchmark":
        require(meta.get("benchmark") == "FTSE Global All Cap", "VALL identity is FTSE Global All Cap")
        require(meta.get("weight_basis") == "company_cap_weight", "Benchmark requires company cap weights")
        require(pd.Timestamp(meta["as_of"]) <= pd.Timestamp("2026-10-18"), "Benchmark snapshot is after release")
    else:
        require(meta.get("currency") == "GBP", "Historical returns must be GBP")
        require(meta.get("return_basis") == "net_investor_wealth", "Historical returns must already be net of costs")
        require(meta.get("accounting") == "fixed_units_with_distribution_cash",
                "History must retain fixed fund units and distribution cash")
    return meta


def atomic_write(path, writer):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".secondary-", suffix=".tmp", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        writer(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def build_release(fixtures, inputs, output):
    fixtures, inputs, output = map(Path, (fixtures, inputs, output))
    report = dict(release_id=RELEASE_ID, status="partial", written={}, blocked={}, provenance={})
    catalogue = build_catalogue(fixtures)
    calibration_path = fixtures / "06_stress_calibration.json"
    if calibration_path.is_file():
        calibration = read_json(calibration_path)
        report["provenance"]["stress"] = {k: calibration[k] for k in ("source_url", "source_section", "evidence_status")}
    sources = [fixtures / name for name in (
        "01_verified_universe.csv", "01_listings.csv", "02_assumptions.yaml",
        "02_product_contracts.json", "06_stress_calibration.json")]
    listings = pd.read_csv(fixtures / "01_listings.csv", keep_default_na=False)
    report["listing_warnings"] = listings.loc[listings.listing_status.ne("verified_listing"), ["canonical_id", "ticker", "listing_status", "notes"]].to_dict("records")
    report["input_sha256"] = {str(p): sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()}
    universe = pd.read_csv(fixtures / "01_verified_universe.csv", keep_default_na=False)
    joined = universe.merge(listings, left_on=["canonical_id", "preferred_listing_ticker"],
                            right_on=["canonical_id", "ticker"], suffixes=("_universe", "_listing"))
    report["quote_conflicts"] = joined.loc[
        joined.quote_unit_universe.ne(joined.quote_unit_listing),
        ["canonical_id", "display_ticker", "quote_unit_universe", "quote_unit_listing", "listing_status_listing"],
    ].to_dict("records")
    report["notes"] = [
        "Verified universe quote units override weaker aliases; any discrepancies are listed in quote_conflicts.",
        "Catalogue uses fixture row order and display tickers; quote units refer to preferred listings.",
        "Sleeves follow current UI / model-specification scheme C; VAGS in credit, leveraged equity and property in thematic.",
        "Cash interest is retained (Accumulating). USD/EUR quote currencies are preserved.",
        "Stress comes from Stage06 audit section 3.3, not product_mechanics.md (which has no stress table).",
        "Stress is research calibration, not independently verified historical observations; 2022 runs through December.",
        "VALL is FTSE Global All Cap. Top 100 company weights are renormalised; no legacy assumed-proxy fallback.",
        "History baseline is January 2014; 152 subsequent monthly net investor-wealth returns are required per reference/method.",
        "This secondary report does not certify or update the main release manifest or its hashes.",
    ]

    def benchmark():
        report["provenance"]["benchmark"] = provenance(inputs, "benchmark")
        return build_benchmark(pd.read_csv(inputs / "benchmark_vall.csv", keep_default_na=False,
                                           float_precision="round_trip"))

    def history():
        report["provenance"]["history"] = provenance(inputs, "history")
        return build_history(pd.read_csv(inputs / "reference_monthly_returns.csv", keep_default_na=False))

    builders = {
        "fund_catalogue.parquet": lambda: catalogue,
        "stress_vectors.parquet": lambda: build_stress(fixtures / "06_stress_calibration.json", catalogue),
        "benchmark_vall.parquet": benchmark,
        "historical_results.parquet": history,
    }
    requirements = {
        "benchmark_vall.parquet": "Need company-aggregated VALL constituents in benchmark_vall.csv and benchmark provenance in secondary_sources.json.",
        "historical_results.parquet": "Need reference_monthly_returns.csv (six references, both methods, Feb 2014-Sep 2026) and history provenance in secondary_sources.json.",
    }
    for name, builder in builders.items():
        try:
            frame = builder()
            def write_and_check(path):
                frame.to_parquet(path, index=False, engine="pyarrow")
                pd.testing.assert_frame_equal(pd.read_parquet(path), frame)
            atomic_write(output / name, write_and_check)
            report["written"][name] = dict(rows=len(frame), sha256=sha256((output / name).read_bytes()).hexdigest())
            if name == "benchmark_vall.parquet":
                def write_csv(path):
                    frame.to_csv(path, index=False, float_format="%.17g")
                    restored = pd.read_csv(path, keep_default_na=False, float_precision="round_trip")
                    pd.testing.assert_frame_equal(frame, restored, check_exact=True)
                    require(restored.benchmark_weight.sum() == 1.0, "CSV benchmark sum mismatch")
                atomic_write(output / "benchmark_vall.csv", write_csv)
                report["written"]["benchmark_vall.csv"] = dict(
                    rows=len(frame), sha256=sha256((output / "benchmark_vall.csv").read_bytes()).hexdigest())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["blocked"][name] = dict(
                reason=str(exc), required=requirements.get(name, "Repair source contract."),
                existing_file_retained=(output / name).exists(),
            )
    holdings_names = ("company_holdings.parquet", "fund_links.parquet", "holdings_csr.npz")
    try:
        constituents = read_constituents(inputs)
        dataset = build_holdings(universe, constituents)
        write_holdings(dataset, output)
        report["provenance"]["holdings"] = dict(
            weight_basis="underlying_constituent_weight", as_of="2026-10-18",
            source_dates=sorted(constituents.source_as_of.unique().tolist()),
            sources=sorted(constituents.data_source.unique().tolist()),
            fund_ids=list(dataset.fund_ids), tickers=list(dataset.tickers),
        )
        for name, rows in zip(holdings_names, [len(dataset.company_holdings), len(dataset.fund_links), 68]):
            report["written"][name] = dict(rows=rows, sha256=sha256((output / name).read_bytes()).hexdigest())
        manifest = read_json(inputs / "constituent_sources.json")
        for source in manifest["sources"]:
            path = inputs / source["path"]
            report["input_sha256"][str(path)] = sha256(path.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        for name in holdings_names:
            report["blocked"][name] = dict(
                reason=str(exc), required="Need constituent_sources.json and identity-mapped equity snapshots for all 48 equity funds.",
                existing_file_retained=(output / name).exists(),
            )
    report["notes"].append(
        "Holdings H uses unlevered constituent weights <= 1 per fund, including leveraged products. "
        "Use portfolio.ingestion.attach_holdings with canonical_tickers to attach H to a PreparedModel. "
        "This builder does not overwrite model binaries or certify the main release manifest.")
    for name in ("benchmark_vall.csv", "reference_monthly_returns.csv", "secondary_sources.json", "constituent_sources.json"):
        p = inputs / name
        if p.is_file():
            report["input_sha256"][str(p)] = sha256(p.read_bytes()).hexdigest()
    report["status"] = "complete" if not report["blocked"] else "partial"
    atomic_write(output / "secondary_build_report.json",
                 lambda p: p.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests" / "fixtures")
    parser.add_argument("--inputs", type=Path, default=ROOT / "data" / "release_inputs")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "release")
    args = parser.parse_args()
    try:
        report = build_release(args.fixtures, args.inputs, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    for name, result in report["written"].items():
        print(f"BUILT {name}: {result['rows']} rows")
    for name, result in report["blocked"].items():
        print(f"BLOCKED {name}: {result['required']}")
    print(f"Status: {report['status']}; report: {args.output / 'secondary_build_report.json'}")
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
