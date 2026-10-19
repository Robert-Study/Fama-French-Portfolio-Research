"""Serialize a complete, provenance-bearing V8 calibration into a MarketSnapshot.

Run .venv/Scripts/python.exe scripts/build_market_snapshot.py from the repo.
Default input: data/release_inputs/market_calibration.json. Exit 2 means blocked.

The JSON contract requires as_of_date, source_as_of, source, method (etf or
holdings), reporting_currency=GBP, return_basis=net_total_return,
moment_basis=monthly_simple_decimal, tickers (68 fixture display tickers in
order), mu_monthly (68), cov_monthly (68x68), and C_mat/U_mat (68x68 annual
log-wealth uncertainty coefficients). These are calibrated outputs, not prices.
The upstream calibration must apply product costs exactly once. This serializer
only annualizes monthly arithmetic moments by 12 and derives log drift.

Universe identities and product assumptions cannot supply missing covariances,
equity premia or parameter uncertainty. No synthetic defaults are supplied.
The snapshot records its calibration route and assumption status; it does not
calibrate a second route or certify the quality of upstream market estimates.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio.contracts import MarketSnapshot
from scripts.build_stress_and_benchmarks import build_catalogue

DEFAULT_FIXTURES = ROOT / "tests/fixtures"
AS_OF_DATE = "2026-10-18"
CASH_ID = "cash:T212_GBP_CASH"


def build_snapshot(fixtures: Path, calibration: Path) -> MarketSnapshot:
    catalogue = build_catalogue(fixtures)
    calibration = Path(calibration)
    if not calibration.is_file():
        raise ValueError(f"Missing calibrated moments: {calibration}. "
                         "Provide all 68 instruments; universe metadata is not market calibration.")
    raw = calibration.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    for key, expected in {
        "as_of_date": AS_OF_DATE, "reporting_currency": "GBP",
        "return_basis": "net_total_return", "moment_basis": "monthly_simple_decimal",
    }.items():
        if data.get(key) != expected:
            raise ValueError(f"{key} must be {expected!r}")
    if data.get("method") not in ("holdings", "etf"):
        raise ValueError("method must identify the calibrated holdings or etf route")
    if not isinstance(data.get("source"), str) or not data["source"].strip():
        raise ValueError("source must document the upstream calibration and evidence")
    if date.fromisoformat(data["source_as_of"]) > date.fromisoformat(AS_OF_DATE):
        raise ValueError("source_as_of exceeds the snapshot cut-off")
    tickers = tuple(catalogue.ticker)
    if tuple(data.get("tickers", ())) != tickers:
        raise ValueError("Calibration must contain all 68 tickers in exact canonical order")
    cash_indices = np.flatnonzero(catalogue.fund_id.eq(CASH_ID))
    if len(cash_indices) != 1:
        raise ValueError("Expected exactly one cash:T212_GBP_CASH")
    means = np.asarray(data["mu_monthly"], dtype=np.float64) * 12.0
    covariance = np.asarray(data["cov_monthly"], dtype=np.float64) * 12.0
    if means.shape != (68,) or covariance.shape != (68, 68):
        raise ValueError("Monthly moments require shapes (68,) and (68, 68)")
    sleeve_bits = 1 << (catalogue.sleeve.to_numpy(dtype=np.int64) - 1)
    masks = (np.arange(64)[:, None] & sleeve_bits[None, :]) != 0
    return MarketSnapshot(
        as_of_date=AS_OF_DATE, tickers=tickers, cash_index=int(cash_indices[0]),
        cov_ann=covariance, mu_arith_ann=means,
        mu_log_ann=means - 0.5 * np.diag(covariance),
        param_uncertainty=(np.asarray(data["C_mat"], dtype=np.float64),
                           np.asarray(data["U_mat"], dtype=np.float64)),
        sleeve_masks=masks,
        metadata={"calibration_method": data["method"], "source": data["source"],
                  "calibration_status": data.get("calibration_status", "unspecified"),
                  "calibration_details": data.get("calibration_details", {}),
                  "source_as_of": data["source_as_of"], "calibration_sha256": sha256(raw).hexdigest(),
                  "fixture_sha256": {
                      name: sha256((Path(fixtures) / name).read_bytes()).hexdigest()
                      for name in ("01_verified_universe.csv", "01_listings.csv",
                                   "02_product_contracts.json", "02_assumptions.yaml")},
                  "reporting_currency": "GBP", "return_basis": "net_total_return",
                  "annualization": "12 * monthly simple decimal moments"},
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--calibration", type=Path,
                        default=ROOT / "data/release_inputs/market_calibration.json")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data/release_inputs/market_snapshot.joblib")
    args = parser.parse_args(argv)
    try:
        snapshot = build_snapshot(args.fixtures, args.calibration)
        if args.out.exists():
            raise ValueError(f"Refusing to overwrite existing snapshot: {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Validate before publication. Windows rename refuses an existing target.
        with tempfile.TemporaryDirectory(prefix=".market-snapshot-", dir=args.out.parent) as staging:
            staged = Path(staging) / "market_snapshot.joblib"
            joblib.dump(snapshot, staged, compress=3)
            loaded = joblib.load(staged)
            loaded.__post_init__()
            staged.rename(args.out)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Market snapshot blocked: {exc}", file=sys.stderr)
        return 2
    print(f"Loaded snapshot: {len(loaded.tickers)} tickers, as_of: {loaded.as_of_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
