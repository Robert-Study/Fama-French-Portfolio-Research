"""Build the immutable Portfolio Construction Lab V8 offline release.

Run from the repository root::

    python scripts/build_v8_release.py

Required, trusted local inputs (never synthesised by this builder):
    data/release_inputs/market_snapshot.joblib       # portfolio.contracts.MarketSnapshot
    data/release_inputs/reference_portfolios.json    # six strategy ticker -> integer bps maps

Optional --snapshot/--references paths override these.  The production default
runs both routes, all 64 masks, 1,001 frontier points, and 40 annual horizons.

Every nonempty solution is required to carry a genuine optimiser-issued
1-bp annual volatility certificate. Invalid sleeve masks are persisted as
all-zero allocations, certified=False, gap=NaN, status='infeasible'.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from collections.abc import Mapping
from typing import Any

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

METHODS = ("holdings", "etf")
REFERENCES = ("sp500", "all_cap", "global_6040", "bonds", "value", "size")
SLEEVE_COUNT = 6
DEFAULT_N_POINTS = 1001
DEFAULT_HORIZONS = tuple(range(1, 41))
MAX_GAP = 1.0e-4  # one annual-volatility basis point, NOT relative MIP gap


class ReleaseContractError(RuntimeError):
    """Raised if a numerical or data contract cannot be certified."""


def _get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    raise ReleaseContractError(f"Missing required field {names!r} on {type(obj).__name__}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_npz(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The output is staged off-tree; on successful verification it is published.
    np.savez_compressed(path, **arrays)


def _make_call(fn: Any, bindings: dict[str, Any], *, what: str) -> Any:
    """Bind known public API parameter *names*, never silently omit mask data."""
    signature = inspect.signature(fn)
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    missing: list[str] = []
    for name, param in signature.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if name not in bindings:
            if param.default is inspect.Parameter.empty:
                missing.append(name)
            continue
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            args.append(bindings[name])
        else:
            kwargs[name] = bindings[name]
    if missing:
        raise ReleaseContractError(f"{what} signature has unresolved required arguments: {missing}")
    return fn(*args, **kwargs)


def _model_validation(model: Any, expected_method: str, universe_tickers: tuple[str, ...]) -> int:
    tickers = tuple(_get(_get(model, "metadata"), "canonical_tickers"))
    if tickers != universe_tickers:
        raise ReleaseContractError(f"{expected_method}: ticker order mismatches the snapshot")
    if _get(_get(model, "metadata"), "method") != expected_method:
        raise ReleaseContractError(f"{expected_method}: model route identity mismatch")
    m = len(tickers)
    if m != 68:
        raise ReleaseContractError(f"Expected all 68 canonical instruments, found {m}")
    sigma = np.asarray(_get(model, "cov_ann"), dtype=np.float64)
    means = np.asarray(_get(model, "mu_arith_ann"), dtype=np.float64)
    masks = np.asarray(_get(model, "sleeve_masks"))
    if means.shape != (m,) or sigma.shape != (m, m) or masks.shape != (64, m):
        raise ReleaseContractError(f"{expected_method}: invalid PreparedModel dimensions")
    if not np.isfinite(sigma).all() or not np.isfinite(means).all():
        raise ReleaseContractError(f"{expected_method}: nonfinite moments")
    if not np.allclose(sigma, sigma.T, rtol=0, atol=1e-13):
        raise ReleaseContractError(f"{expected_method}: covariance not symmetric")
    if np.linalg.eigvalsh(sigma).min() < -1e-10:
        raise ReleaseContractError(f"{expected_method}: covariance is not PSD")
    cash_idx = int(_get(_get(model, "metadata"), "cash_index"))
    if not (0 <= cash_idx < m) or not np.allclose(sigma[cash_idx, :], 0, rtol=0, atol=1e-12):
        raise ReleaseContractError(f"{expected_method}: cash anchor has nonzero price variance")
    return m


def _extract_frontier(raw: Any, m: int, n_points: int, *, method: str, mask: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Normalise vectorised solver results or a sequence of MIQPSolution objects."""
    try:
        q_raw = _get(raw, "q_bps")
        cert_raw = _get(raw, "certified", "certified_optimal")
        gap_raw = _get(raw, "gap", "annualized_volatility_gap")
        q = np.asarray(q_raw)
        cert = np.asarray(cert_raw)
        gap = np.asarray(gap_raw)
    except ReleaseContractError:
        points = _get(raw, "solutions", "points", "results") if not isinstance(raw, (list, tuple)) else raw
        if not points:
            raise ReleaseContractError(f"{method}/{mask:02d}: empty frontier result")
        q = np.asarray([_get(p, "q_bps") for p in points])
        cert = np.asarray([_get(p, "certified", "certified_optimal") for p in points])
        gap = np.asarray([_get(p, "gap", "annualized_volatility_gap") for p in points])

    # A genuinely single-feasible-point frontier may be broadcast to the slider grid.
    if q.shape == (1, m) and cert.shape == (1,) and gap.shape == (1,):
        q = np.repeat(q, n_points, axis=0)
        cert = np.repeat(cert, n_points)
        gap = np.repeat(gap, n_points)
    if q.shape != (n_points, m) or cert.shape != (n_points,) or gap.shape != (n_points,):
        raise ReleaseContractError(f"{method}/{mask:02d}: solver output has inconsistent shape "
                                   f"q={q.shape}, cert={cert.shape}, gap={gap.shape}")
    if not np.issubdtype(q.dtype, np.integer):
        raise ReleaseContractError(f"{method}/{mask:02d}: solver did not return integer basis points")
    q = q.astype(np.int64, copy=False)
    if (q < 0).any() or (q > 10000).any() or not np.all(q.sum(axis=1) == 10000):
        raise ReleaseContractError(f"{method}/{mask:02d}: allocation budget/long-only violation")
    if np.any((q > 0) & (q < 10)):
        raise ReleaseContractError(f"{method}/{mask:02d}: below 10-bps position minimum")
    if not np.all(cert == True):  # noqa: E712 -- strict solver-issued true certificate
        raise ReleaseContractError(f"{method}/{mask:02d}: uncertified frontier point(s)")
    if not np.isfinite(gap).all() or np.min(gap) < -1e-9 or np.max(gap) > MAX_GAP + 1e-12:
        raise ReleaseContractError(f"{method}/{mask:02d}: annual volatility gap exceeds 1bp")
    return q, cert.astype(np.bool_), gap.astype(np.float64)


def _solve_frontier(fn: Any, model: Any, mask_id: int, n_points: int, *, method: str, m: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    if mask_id == 0 or not np.any(np.asarray(_get(model, "sleeve_masks"))[mask_id]):
        return (np.zeros((n_points, m), dtype=np.int64), np.zeros(n_points, bool),
                np.full(n_points, np.nan), "infeasible_empty")
    sig = inspect.signature(fn)
    mask_params = ("mask", "mask_id", "category_mask", "sleeve_mask", "active_mask", "eligible_mask")
    which = next((name for name in mask_params if name in sig.parameters), None)
    if which is None:
        raise ReleaseContractError(f"compute_miqp_frontier does not expose an explicit mask selector; "
                                   f"refusing to cache the same frontier under 64 IDs: {sig}")
    active = np.asarray(_get(model, "sleeve_masks"))[mask_id].astype(bool)
    bindings: dict[str, Any] = {
        "model": model, "prepared_model": model, "n_points": n_points,
        "points": n_points, "num_points": n_points,
        "mask": mask_id, "mask_id": mask_id, "category_mask": mask_id,
        "sleeve_mask": mask_id, "active_mask": active, "eligible_mask": active,
    }
    try:
        raw = _make_call(fn, bindings, what="compute_miqp_frontier")
    except Exception as exc:
        # Only specific *documented* infeasibility class may produce a disabled mask.
        if any(cls.__name__ == "SolverInfeasibleError" for cls in type(exc).__mro__):
            return (np.zeros((n_points, m), dtype=np.int64), np.zeros(n_points, bool),
                    np.full(n_points, np.nan), "infeasible_solver")
        raise
    q, cert, gap = _extract_frontier(raw, m, n_points, method=method, mask=mask_id)
    if np.any(q[:, ~active]):
        raise ReleaseContractError(f"{method}/{mask_id:02d}: disabled-sleeve assets have positive weights")
    return q, cert, gap, "certified"


def _reference_weights(ref_path: Path, tickers: tuple[str, ...]) -> dict[str, np.ndarray]:
    obj = json.loads(ref_path.read_text(encoding="utf-8"))
    if "references" in obj:
        obj = obj["references"]
    if set(obj) != set(REFERENCES):
        raise ReleaseContractError(f"Reference keys must be exactly {REFERENCES}; got {tuple(obj)}")
    positions = {ticker: i for i, ticker in enumerate(tickers)}
    refs: dict[str, np.ndarray] = {}
    for name in REFERENCES:
        content = obj[name]
        if isinstance(content, dict) and "q_bps" in content:
            content = content["q_bps"]
        if not isinstance(content, dict):
            raise ReleaseContractError(f"{name}: expected ticker-to-integer-bps JSON mapping")
        q = np.zeros(len(tickers), dtype=np.int64)
        for ticker, bps in content.items():
            if ticker not in positions or not isinstance(bps, int) or isinstance(bps, bool):
                raise ReleaseContractError(f"{name}: unknown ticker or non-integer bps: {ticker}={bps}")
            q[positions[ticker]] = bps
        if q.sum() != 10000 or np.any((q > 0) & (q < 10)) or (q < 0).any():
            raise ReleaseContractError(f"{name}: weights must sum 10,000 bps, each nonzero >= 10 bps")
        refs[name] = q
    return refs


def _wealth_one(w: np.ndarray, model: Any, horizon: int, moment_fn: Any, quantile_fn: Any) -> np.ndarray:
    """Compute annual buy-and-hold moments and moment-matched bands via engine APIs."""
    mu = np.asarray(_get(model, "mu_log_ann"), dtype=np.float64)
    cov = np.asarray(_get(model, "cov_ann"), dtype=np.float64)
    c_mat, u_mat = _get(model, "param_uncertainty")
    c = float(w @ np.asarray(c_mat) @ w)
    u = float(w @ np.asarray(u_mat) @ w)
    kwargs = {
        "weights": w, "w": w, "w0": w, "q_bps": np.rint(w * 10000).astype(np.int64),
        "model": model, "prepared_model": model,
        "mu_log": mu, "mu_log_ann": mu, "log_means": mu,
        "cov_log": cov, "cov_log_ann": cov, "cov_ann": cov, "covariance": cov,
        "n": horizon, "n_periods": horizon, "horizon": horizon,
        "horizon_years": horizon, "years": horizon, "H": horizon,
    }
    raw = _make_call(moment_fn, kwargs, what="accumulating_wealth_moments")
    if isinstance(raw, (tuple, list)) and len(raw) >= 2:
        mean, var = float(raw[0]), float(raw[1])
    else:
        mean = float(_get(raw, "mean_normalized", "mean", "mean_wealth", "expected_wealth"))
        var = float(_get(raw, "var_normalized", "variance", "var", "variance_wealth"))
    if not (math.isfinite(mean) and mean > 0 and math.isfinite(var) and var >= -1e-12):
        raise ReleaseContractError(f"Invalid buy-and-hold moments H={horizon}: {mean=}, {var=}")
    var = max(0.0, var)
    qkwargs = {
        "mean": mean, "mean_normalized": mean, "mean_wealth": mean,
        "variance": var, "var": var, "var_normalized": var, "variance_wealth": var,
        "horizon": horizon, "n": horizon, "years": horizon, "horizon_years": horizon,
        "c": c, "c_param": c, "c_uncertainty": c, "C": c,
        "u": u, "u_param": u, "u_uncertainty": u, "U": u,
        "param_uncertainty_c": c, "param_uncertainty_u": u,
        "confidence_levels": (0.2, 0.5, 0.84135),
        "quantiles": (0.2, 0.5, 0.84135),
        "probabilities": (0.2, 0.5, 0.84135),
        "p": (0.2, 0.5, 0.84135),
        "w0": 1.0, "initial_wealth": 1.0,
    }
    qr = _make_call(quantile_fn, qkwargs, what="lognormal_wealth_quantiles")
    if isinstance(qr, Mapping):
        low = _get(qr, "p20", "q_p20", "q20", "0.2")
        med = _get(qr, "p50", "q_p50", "q50", "0.5")
        high = _get(qr, "p84_135", "q_p84_135", "q84135", "0.84135")
    elif isinstance(qr, (tuple, list, np.ndarray)):
        if len(qr) != 3:
            raise ReleaseContractError("Quantile engine must return exactly 3 ordered quantiles")
        low, med, high = qr
    else:
        low = _get(qr, "p20", "q_p20")
        med = _get(qr, "p50", "q_p50")
        high = _get(qr, "p84_135", "q_p84_135")
    arr = np.asarray([mean, var, low, med, high], dtype=np.float64)
    if not np.isfinite(arr).all() or arr[2] < 0 or arr[2] > arr[3] or arr[3] > arr[4]:
        raise ReleaseContractError(f"Invalid or unordered wealth quantiles H={horizon}: {arr}")
    return arr


def _moments_batch(qs: np.ndarray, model: Any, horizons: tuple[int, ...], moment_fn: Any, quantile_fn: Any) -> np.ndarray:
    # Shape: (allocations, horizons, metrics). Uses engine's exact moments,
    # rather than substituting rebalanced geometric Brownian-motion formulas.
    result = np.empty((len(qs), len(horizons), 5), dtype=np.float64)
    memo: dict[tuple[int, ...], np.ndarray] = {}
    for idx, q in enumerate(qs):
        key = tuple(int(v) for v in q)
        if key not in memo:
            w = np.asarray(q, dtype=np.float64) / 10000.0
            memo[key] = np.vstack([_wealth_one(w, model, h, moment_fn, quantile_fn) for h in horizons])
        result[idx] = memo[key]
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/release_inputs/market_snapshot.joblib")
    parser.add_argument("--references", type=Path, default=ROOT / "data/release_inputs/reference_portfolios.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data/release")
    parser.add_argument("--masks", default="all", help="Production: all; smoke: comma-separated IDs, e.g. 0,1,63")
    parser.add_argument("--n-points", type=int, default=DEFAULT_N_POINTS)
    parser.add_argument("--horizons", default="1-40", help="Production: 1-40; smoke: comma-separated years")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    masks = tuple(range(64)) if args.masks == "all" else tuple(int(x) for x in args.masks.split(","))
    horizons = DEFAULT_HORIZONS if args.horizons == "1-40" else tuple(int(x) for x in args.horizons.split(","))
    if not masks or len(set(masks)) != len(masks) or any(not (0 <= k <= 63) for k in masks):
        raise ReleaseContractError("Mask IDs must be distinct integers in [0,63]")
    if args.n_points < 1 or not horizons or any(h < 1 or h > 40 for h in horizons):
        raise ReleaseContractError("Invalid horizon or n-points selection")
    production = masks == tuple(range(64)) and args.n_points == 1001 and horizons == DEFAULT_HORIZONS
    out = args.out.resolve()
    if not production and out == (ROOT / "data/release").resolve():
        raise ReleaseContractError("Partial/smoke builds must specify --out outside data/release")
    if out.exists():
        raise ReleaseContractError(f"Refusing to overwrite existing release directory: {out}")
    for path in (args.snapshot, args.references):
        if not path.is_file():
            raise ReleaseContractError(f"Missing trusted release input: {path}")

    from portfolio.model import prepare_model
    from portfolio.optimise_miqp import compute_miqp_frontier
    from portfolio.wealth import accumulating_wealth_moments, lognormal_wealth_quantiles

    snapshot = joblib.load(args.snapshot)  # Trusted repository-local fixtures only.
    tickers = tuple(_get(snapshot, "tickers"))
    references = _reference_weights(args.references, tickers)
    as_of = str(_get(snapshot, "as_of_date"))
    date.fromisoformat(as_of)
    source_sha = {_path_key(args.snapshot): _sha256(args.snapshot),
                  _path_key(args.references): _sha256(args.references)}
    release_id = f"v8_{as_of}_{hashlib.sha256((source_sha[_path_key(args.snapshot)] + source_sha[_path_key(args.references)]).encode()).hexdigest()[:12]}"

    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".v8-release-build-", dir=out.parent))
    artifacts: dict[str, str] = {}
    mask_status: dict[str, dict[str, str]] = {}
    try:
        for method in METHODS:
            print(f"Building V8 release: route={method}", flush=True)
            model = prepare_model(snapshot, method=method)
            m = _model_validation(model, method, tickers)
            joblib.dump(model, staging / f"prepared_{method}.joblib", compress=3)
            mask_status[method] = {}
            all_refs = np.stack([references[x] for x in REFERENCES])
            _write_npz(staging / f"wealth/{method}/references.npz",
                       q_bps=all_refs, strategy=np.asarray(REFERENCES),
                       horizons=np.asarray(horizons, dtype=np.int16),
                       metrics=np.asarray(("mean", "variance", "p20", "p50", "p84_135")),
                       moments=_moments_batch(all_refs, model, horizons,
                                              accumulating_wealth_moments, lognormal_wealth_quantiles))
            for mask in masks:
                q, cert, gap, status = _solve_frontier(compute_miqp_frontier, model, mask, args.n_points,
                                                       method=method, m=m)
                _write_npz(staging / f"frontiers/{method}/{mask:02d}.npz",
                           q_bps=q, certified=cert, gap=gap, status=np.asarray(status))
                mask_status[method][f"{mask:02d}"] = status
                if status == "certified":
                    values = _moments_batch(q, model, horizons,
                                            accumulating_wealth_moments, lognormal_wealth_quantiles)
                else:
                    values = np.full((args.n_points, len(horizons), 5), np.nan, dtype=np.float64)
                _write_npz(staging / f"wealth/{method}/{mask:02d}.npz",
                           horizons=np.asarray(horizons, dtype=np.int16),
                           metrics=np.asarray(("mean", "variance", "p20", "p50", "p84_135")),
                           moments=values)
                print(f"  mask={mask:02d}: {status}", flush=True)

        for path in sorted(staging.rglob("*")):
            if path.is_file():
                artifacts[path.relative_to(staging).as_posix()] = _sha256(path)
        manifest = {
            "schema_id": "pcl_v8_release_v1", "release_id": release_id, "as_of": as_of,
            "reporting_currency": "GBP", "tickers": list(tickers),
            "references": {name: references[name].tolist() for name in REFERENCES},
            "methods": list(METHODS), "masks": list(masks), "n_points": args.n_points,
            "horizons_years": list(horizons), "wealth_metrics": ["mean", "variance", "p20", "p50", "p84_135"],
            "wealth_quantile_method": "engine_log_normal_moment_match_not_exact_sum_distribution",
            "vol_gap_tolerance_ann": MAX_GAP, "mask_status": mask_status,
            "production_complete": production, "input_sha256": source_sha,
            "sha256": artifacts, "manifest_self_hash_excluded": True,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # Final integrity readback before making release visible.
        for relative, digest in artifacts.items():
            if _sha256(staging / relative) != digest:
                raise ReleaseContractError(f"Hash mismatch before publish: {relative}")
        if out.exists():
            raise ReleaseContractError(f"Output appeared during build: {out}")
        staging.rename(out)
        print(f"Release built: {out} [{len(artifacts)} hashed artifacts; {release_id}]", flush=True)
        return 0
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _path_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReleaseContractError, FileNotFoundError) as exc:
        print(f"RELEASE BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
