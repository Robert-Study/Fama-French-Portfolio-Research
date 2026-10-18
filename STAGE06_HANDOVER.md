# Portfolio Construction Lab V8 — Stage 06 Release Pipeline

## Delivery

- `scripts/build_v8_release.py`: candidate integration script (Python 3.14 syntax compatible; compile verified with Python 3.13).
- `tests/test_v8_release_builder.py`: isolated deterministic engine-mock smoke tests.
- **NOT a certified production release**: this execution environment cannot access `C:\Users\home\Documents\AI-Disk-Access\Gemini-Efficient-Frontier`, its implemented local V8 modules, its empirical input snapshot, or its test fixtures. No simulated outputs are delivered as real investment results.

## Exact trusted input contract

`data/release_inputs/market_snapshot.joblib` must be an actual, internally verified `portfolio.contracts.MarketSnapshot`, with a full 68-instrument ordered universe and aligned empirical data. `prepare_model(snapshot, method='holdings'|'etf')` must accept this object, and output `PreparedModel` with `metadata.canonical_tickers`, `metadata.cash_index`, `mu_arith_ann`, `mu_log_ann`, `cov_ann`, `param_uncertainty`, and `sleeve_masks` of shape `(64,68)`.

`data/release_inputs/reference_portfolios.json` must specify the six **externally certified**, long-only benchmark strategies; no guessed ticker allocations are baked into the builder:

```
{
  "sp500": {"<verified LSE ticker>": 10000},
  "all_cap": {"<verified ticker>": 10000},
  "global_6040": {"<verified equity ticker>": 6000, "<verified bond ticker>": 4000},
  "bonds": {"<verified bond ticker>": 10000},
  "value": {"<verified factor ticker>": 10000},
  "size": {"<verified factor ticker>": 10000}
}
```

The above strings are illustrative placeholders, **not authorized actual allocations**. Resolve from the canonical Execution Plan / research ledger before production use.

### Live backend API expectations

- `compute_miqp_frontier` must expose an explicit integer `mask`/`mask_id`/`category_mask`/`sleeve_mask`, or boolean `active_mask`/`eligible_mask` selector. This is intentionally a hard integration gate; otherwise all masks might wrongly cache identical results.
- The solver must return `q_bps`, `certified`/`certified_optimal`, and **annualized absolute volatility** `gap`/`annualized_volatility_gap`, or iterable per-point solution objects with those fields. A relative MIP objective gap is **not** an annual volatility certificate.
- `accumulating_wealth_moments` and `lognormal_wealth_quantiles` must accept recognisable named parameters; unknown API signatures cause explicit errors, not silent guessed calculations. P20/P50/P84.135 remain lognormal **moment-matching approximations**, not exact quantiles of a leveraged multi-asset sum-of-lognormals.
- Full precision, GBP-correct, income/distribution assumptions must be validated against Stage 04 before sign-off.

## Output and integrity

Default command from repo root: `python scripts/build_v8_release.py`.
Output target: `data/release/`, created **only on a successful complete run**. No existing release is deleted or overwritten.

For each route and mask:
- `frontiers/<route>/<mask:02d>.npz`: `q_bps (1001,68) int64`, `certified (1001,) bool`, `gap (1001,) float64`, `status`.
- `wealth/<route>/<mask:02d>.npz`: `moments (1001,40,5)` with `[mean,variance,P20,P50,P84.135]`, and `horizons, metrics`.
- `wealth/<route>/references.npz`: `q_bps (6,68)`, `moments (6,40,5)` plus labels.
- `prepared_holdings.joblib` and `prepared_etf.joblib`.
- `manifest.json`: release ID, as-of date, ticker order, strategy allocations, masks, horizons, statuses, snapshot/reference input hashes, and SHA-256 for **260 artifacts**. The manifest excludes its own hash to avoid the circular self-hash problem.

Mask 0 and genuinely infeasible masks use `status=infeasible...`, all-zero `q_bps`, `certified=False`, and `gap=NaN`; this deliberately does *not* claim a feasible full-investment frontier in an empty sleeve universe.

## Validation observed in this isolated session

- `python -m py_compile scripts/build_v8_release.py`: PASS.
- `pytest -q tests/test_v8_release_builder.py`: **5 passed** (synthetic backend only).
- `python scripts/build_v8_release.py`: **BLOCKED** because empirical `market_snapshot.joblib` is unavailable in this sandbox.
- `pytest tests/test_v8_contracts.py`: **NOT RUN** (the local test path is not accessible in the sandbox; Github has an older snapshot of this repository).
- `data/release/manifest.json` production integrity and full 128-mask certification: **NOT VERIFIED**.

## Local finishing actions for Antigravity / Codex

1. Copy `scripts/` and `tests/` from this package into the active local repository without overwriting existing V8 modules.
2. Confirm the actual local `compute_miqp_frontier`, `accumulating_wealth_moments`, `lognormal_wealth_quantiles` signatures. Adapt the narrow wrappers if needed; don't weaken the certification and mask gates.
3. Materialize the verified `MarketSnapshot` and all six canonical reference strategy allocations in `data/release_inputs/`.
4. Run `python scripts/build_v8_release.py`, `pytest tests/test_v8_contracts.py`, and `pytest tests/test_v8_release_builder.py` with Python 3.14.
5. Verify all 260 artifact hashes and every feasible point's true solver-issued annualized volatility gap <=1e-4 before declaring production PASS.
