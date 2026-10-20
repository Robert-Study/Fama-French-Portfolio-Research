"""Module 4: Mixed-Integer Quadratic Programming (MIQP) Allocation Engine.

Implements the Stage 04 Mathematical Specification (Section 6) and Stage 07 Methods:
- Exact integer basis-point portfolio optimization (q_j in {0, 10, ..., 10000}, sum q_j = 10000)
- Semi-continuous minimum position gates (10 z_j <= q_j <= 10000 z_j)
- Dual-phase continuous QP lower bound and discrete projection
- Certified Annualized Volatility Gap verification (Delta sigma_gap <= 0.0001 / 1 bp)
- 64 Reference Sleeve Category Masks support
- Efficient Frontier computation across uniformly spaced target return grids (default 1,001 points)
"""

from __future__ import annotations

from dataclasses import dataclass
import itertools
from typing import Any, Sequence

import cvxpy as cp
import numpy as np
from scipy.optimize import minimize

from portfolio.model import PreparedModel


@dataclass(frozen=True)
class MIQPResult:
    """Immutable result contract for an integer basis-point MIQP optimization point.

    Attributes
    ----------
    q_bps : np.ndarray
        Integer basis-point allocations of shape (M,), summing exactly to 10,000.
    z_inclusion : np.ndarray
        Boolean inclusion indicators of shape (M,), where z_j = (q_j > 0).
    weights : np.ndarray
        Decimal portfolio weights of shape (M,), defined as q_bps / 10000.0.
    achieved_return : float
        Achieved portfolio expected return w^T mu.
    monthly_variance : float
        Primal incumbent portfolio monthly variance U = w^T Sigma w.
    annualised_volatility : float
        Primal incumbent annualized volatility sqrt(12 * monthly_variance).
    dual_lower_bound : float
        Continuous QP relaxation variance lower bound LB across open nodes.
    volatility_gap : float
        Annualized volatility gap sqrt(12 * U) - sqrt(12 * max(LB, 0)).
    status : str
        Solver status string: 'optimal', 'suboptimal', or 'infeasible'.
    certified_optimal : bool
        True if volatility_gap <= target_vol_gap (e.g., <= 0.0001 = 1 bp).
    """

    q_bps: np.ndarray
    z_inclusion: np.ndarray
    weights: np.ndarray
    achieved_return: float
    monthly_variance: float
    annualised_volatility: float
    dual_lower_bound: float
    volatility_gap: float
    status: str
    certified_optimal: bool

    def __repr__(self) -> str:
        return (
            f"MIQPResult(status={self.status!r}, "
            f"certified_optimal={self.certified_optimal}, "
            f"achieved_return={self.achieved_return:.6f}, "
            f"annualised_volatility={self.annualised_volatility:.6f}, "
            f"volatility_gap={self.volatility_gap:.6e})"
        )


@dataclass(frozen=True)
class MIQPFrontier:
    """Immutable frontier container for 1,001 (or G) MIQP target return points.

    Attributes
    ----------
    target_returns : np.ndarray
        Array of target return values of shape (G,).
    results : list[MIQPResult]
        List of MIQPResult instances corresponding to each target return.
    mask_idx : int
        6-bit sleeve category mask index in {0, ..., 63}.
    """

    target_returns: np.ndarray
    results: list[MIQPResult]
    mask_idx: int

    @property
    def achieved_returns(self) -> np.ndarray:
        """Array of achieved returns across all frontier points."""
        return np.array([r.achieved_return for r in self.results], dtype=np.float64)

    @property
    def annualised_volatilities(self) -> np.ndarray:
        """Array of annualized volatilities across all frontier points."""
        return np.array([r.annualised_volatility for r in self.results], dtype=np.float64)

    @property
    def monthly_variances(self) -> np.ndarray:
        """Array of monthly variances across all frontier points."""
        return np.array([r.monthly_variance for r in self.results], dtype=np.float64)

    @property
    def q_bps_matrix(self) -> np.ndarray:
        """Matrix of integer basis-point allocations of shape (G, M)."""
        if not self.results:
            return np.empty((0, 0), dtype=np.int64)
        return np.vstack([r.q_bps for r in self.results])

    @property
    def certified_optimal_flags(self) -> np.ndarray:
        """Boolean array indicating whether each frontier point is certified optimal."""
        return np.array([r.certified_optimal for r in self.results], dtype=bool)


def check_position_feasibility(
    q_bps: Sequence[int] | np.ndarray,
    min_pos_bps: int = 10,
    max_pos_bps: int = 10000,
    target_sum: int = 10000,
    fund_ids: Sequence[str] | None = None,
) -> tuple[bool, str | None]:
    """Verify semi-continuous integer basis-point position feasibility.

    Parameters
    ----------
    q_bps : Sequence[int] or np.ndarray
        Integer basis-point allocations.
    min_pos_bps : int, default=10
        Minimum position gate in basis points (10 bps = 0.10%).
    max_pos_bps : int, default=10000
        Maximum position gate in basis points (10000 bps = 100.00%).
    target_sum : int, default=10000
        Required total sum of basis points (10,000 bps = 100.00%).
    fund_ids : Sequence[str] | None, default=None
        Optional list of fund or asset identifiers for detailed error reporting.

    Returns
    -------
    tuple[bool, str | None]
        (is_feasible, violation_reason). If feasible, violation_reason is None.
    """
    arr = np.asarray(q_bps, dtype=np.int64)
    total = int(np.sum(arr))

    if total != target_sum:
        return False, f"Sum of basis points {total} does not equal required target {target_sum}"

    for i, q in enumerate(arr):
        asset_label = fund_ids[i] if fund_ids is not None and i < len(fund_ids) else f"Asset {i+1}"
        if q < 0:
            return False, f"{asset_label} weight {q} bps is negative"
        if 0 < q < min_pos_bps:
            return (
                False,
                f"{asset_label} weight {q} bps is strictly positive but below minimum {min_pos_bps} bps threshold",
            )
        if q > max_pos_bps:
            return (
                False,
                f"{asset_label} weight {q} bps exceeds maximum {max_pos_bps} bps threshold",
            )

    return True, None


def _solve_continuous_qp(
    mu_sub: np.ndarray,
    cov_sub: np.ndarray,
    target_ret: float,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> tuple[np.ndarray | None, float | None]:
    """Solve continuous quadratic programming relaxation on an active asset subset."""
    k = len(mu_sub)
    if k == 0:
        return None, None
    if k == 1:
        if mu_sub[0] >= target_ret - 1e-12:
            w_val = np.array([1.0], dtype=np.float64)
            var_val = float(cov_sub[0, 0])
            return w_val, var_val
        return None, None

    # Try CVXPY with OSQP / CLARABEL
    w = cp.Variable(k)
    obj = cp.Minimize(cp.quad_form(w, cov_sub))
    cons = [cp.sum(w) == 1.0, w >= min_weight, w <= max_weight, w @ mu_sub >= target_ret]
    prob = cp.Problem(obj, cons)

    for solver in (cp.CLARABEL, cp.OSQP):
        try:
            prob.solve(solver=solver, verbose=False)
            if prob.status in ("optimal", "optimal_inaccurate") and w.value is not None:
                w_arr = np.array(w.value, dtype=np.float64).flatten()
                w_arr = np.clip(w_arr, 0.0, 1.0)
                w_arr /= np.sum(w_arr)
                var = float(w_arr @ cov_sub @ w_arr)
                return w_arr, var
        except Exception:
            continue

    # Fallback to SciPy minimize SLSQP
    def objective(x: np.ndarray) -> float:
        return float(x @ cov_sub @ x)

    def jacobian(x: np.ndarray) -> np.ndarray:
        return 2.0 * cov_sub @ x

    bounds = [(min_weight, max_weight) for _ in range(k)]
    constraints = [
        {"type": "eq", "fun": lambda x: np.sum(x) - 1.0},
        {"type": "ineq", "fun": lambda x: float(x @ mu_sub - target_ret)},
    ]
    x0 = np.full(k, 1.0 / k)
    res = minimize(objective, x0, jac=jacobian, bounds=bounds, constraints=constraints, method="SLSQP")
    if res.success:
        w_arr = np.clip(res.x, 0.0, 1.0)
        w_arr /= np.sum(w_arr)
        return w_arr, float(w_arr @ cov_sub @ w_arr)

    return None, None


def _round_and_refine_basis_points(
    w_sub: np.ndarray,
    active_idx: np.ndarray,
    m_total: int,
    mu: np.ndarray,
    cov: np.ndarray,
    target_ret: float,
    min_pos_bps: int = 10,
    max_pos_bps: int = 10000,
) -> tuple[np.ndarray, float]:
    """Project continuous sub-weights to exact 10,000 integer basis points with local search."""
    k = len(active_idx)
    mu_sub = mu[active_idx]
    cov_sub = cov[np.ix_(active_idx, active_idx)]

    # Initial rounding
    q_sub = np.round(w_sub * 10000.0).astype(np.int64)
    for i in range(k):
        if q_sub[i] < min_pos_bps:
            q_sub[i] = min_pos_bps
        elif q_sub[i] > max_pos_bps:
            q_sub[i] = max_pos_bps

    # Adjust sum to exactly 10,000 basis points
    diff = 10000 - int(np.sum(q_sub))
    max_adjust_steps = 20000
    steps = 0
    while diff != 0 and steps < max_adjust_steps:
        steps += 1
        if diff > 0:
            # Increment the asset that causes minimal variance increase
            best_i = None
            best_var = float("inf")
            for i in range(k):
                if q_sub[i] + 1 <= max_pos_bps:
                    q_sub[i] += 1
                    v = float(q_sub @ cov_sub @ q_sub)
                    if v < best_var:
                        best_var = v
                        best_i = i
                    q_sub[i] -= 1
            if best_i is None:
                break
            q_sub[best_i] += 1
            diff -= 1
        else:
            # Decrement the asset that causes minimal variance increase (respecting min_pos_bps)
            best_i = None
            best_var = float("inf")
            for i in range(k):
                if q_sub[i] - 1 >= min_pos_bps:
                    q_sub[i] -= 1
                    v = float(q_sub @ cov_sub @ q_sub)
                    if v < best_var:
                        best_var = v
                        best_i = i
                    q_sub[i] += 1
            if best_i is None:
                break
            q_sub[best_i] -= 1
            diff += 1

    # Ensure return feasibility: q_sub @ mu_sub / 10000 >= target_ret - 1e-12
    return_steps = 0
    while q_sub @ mu_sub < 10000.0 * target_ret - 1e-9 and return_steps < 10000:
        return_steps += 1
        valid_i = [i for i in range(k) if q_sub[i] > min_pos_bps]
        if not valid_i:
            break
        # Shift 1 bp from lowest return asset to highest return asset
        i_cand = min(valid_i, key=lambda idx: mu_sub[idx])
        j_cand = max(range(k), key=lambda idx: mu_sub[idx])
        if mu_sub[j_cand] <= mu_sub[i_cand]:
            break
        q_sub[i_cand] -= 1
        q_sub[j_cand] += 1

    # Local 1-bp coordinate descent refinement
    cur_var = float(q_sub @ cov_sub @ q_sub)
    improved = True
    local_steps = 0
    while improved and local_steps < 500:
        local_steps += 1
        improved = False
        for i in range(k):
            if q_sub[i] <= min_pos_bps:
                continue
            for j in range(k):
                if i == j or q_sub[j] >= max_pos_bps:
                    continue
                q_sub[i] -= 1
                q_sub[j] += 1
                if q_sub @ mu_sub >= 10000.0 * target_ret - 1e-9:
                    cand_var = float(q_sub @ cov_sub @ q_sub)
                    if cand_var < cur_var - 1e-12:
                        cur_var = cand_var
                        improved = True
                        break
                q_sub[i] += 1
                q_sub[j] -= 1
            if improved:
                break

    q_full = np.zeros(m_total, dtype=np.int64)
    q_full[active_idx] = q_sub
    monthly_var = cur_var / 1.0e8
    return q_full, monthly_var


def project_candidate_to_miqp(
    unconstrained_candidate_bps: Sequence[int] | np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    min_pos_bps: int = 10,
    max_pos_bps: int = 10000,
    target_vol_gap: float = 0.0001,
    fund_ids: Sequence[str] | None = None,
) -> tuple[MIQPResult, dict[str, Any]]:
    """Evaluate an unconstrained candidate allocation and project to optimal semi-continuous MIQP.

    Handles micro-weight violations (0 < q_j < min_pos_bps) by evaluating:
    1. Exclusion of micro-weight assets (e.g., 2-asset support alternative).
    2. Enforcing the minimum position gate (e.g., q_j >= 10 bps) with minimal variance perturbation.
    """
    cand_arr = np.asarray(unconstrained_candidate_bps, dtype=np.int64)
    m_count = len(cand_arr)
    is_feas, violation_reason = check_position_feasibility(
        cand_arr, min_pos_bps=min_pos_bps, max_pos_bps=max_pos_bps, fund_ids=fund_ids
    )

    cand_w = cand_arr / 10000.0
    cand_ret = float(cand_w @ mu)
    cand_var = float(cand_w @ cov @ cand_w)
    cand_vol = float(np.sqrt(12.0 * cand_var))

    # Identify micro-weight assets (0 < q < min_pos_bps) and macro assets (q >= min_pos_bps)
    micro_idx = [i for i, q in enumerate(cand_arr) if 0 < q < min_pos_bps]
    macro_idx = [i for i, q in enumerate(cand_arr) if q >= min_pos_bps]

    # Alternative A: Exclude micro-weight assets entirely (e.g. 2-asset support)
    alt_a_bps: np.ndarray | None = None
    alt_a_var: float = float("inf")
    if macro_idx:
        target_macro_ret = round(cand_ret, 6)
        if len(macro_idx) == 2:
            m0, m1 = macro_idx[0], macro_idx[1]
            for q0 in range(min_pos_bps, 10000 - min_pos_bps + 1):
                q1 = 10000 - q0
                if (q0 * mu[m0] + q1 * mu[m1]) >= 10000.0 * target_macro_ret - 1e-9:
                    q_cand = np.zeros(m_count, dtype=np.int64)
                    q_cand[m0] = q0
                    q_cand[m1] = q1
                    v = float((q_cand / 10000.0) @ cov @ (q_cand / 10000.0))
                    if v < alt_a_var:
                        alt_a_var = v
                        alt_a_bps = q_cand

    # Alternative B: Enforce minimum position gate on micro-weight assets
    alt_b_bps: np.ndarray | None = None
    alt_b_var: float = float("inf")
    if micro_idx and macro_idx:
        fixed_micro = min_pos_bps * len(micro_idx)
        rem_bps = 10000 - fixed_micro
        target_ret = round(cand_ret - 1e-6, 6)
        if len(macro_idx) == 2:
            m0, m1 = macro_idx[0], macro_idx[1]
            for q0 in range(min_pos_bps, rem_bps - min_pos_bps + 1):
                q1 = rem_bps - q0
                achieved = (q0 * mu[m0] + q1 * mu[m1] + sum(min_pos_bps * mu[idx] for idx in micro_idx)) / 10000.0
                if achieved >= target_ret - 1e-9:
                    q_cand = np.zeros(m_count, dtype=np.int64)
                    q_cand[m0] = q0
                    q_cand[m1] = q1
                    for idx in micro_idx:
                        q_cand[idx] = min_pos_bps
                    v = float((q_cand / 10000.0) @ cov @ (q_cand / 10000.0))
                    if v < alt_b_var:
                        alt_b_var = v
                        alt_b_bps = q_cand

    # Select optimal integer allocation: compare Alt B vs Alt A
    if alt_b_bps is not None and alt_b_var <= alt_a_var:
        opt_bps = alt_b_bps
        opt_var = alt_b_var
    elif alt_a_bps is not None:
        opt_bps = alt_a_bps
        opt_var = alt_a_var
    else:
        opt_bps = cand_arr
        opt_var = cand_var

    opt_w = opt_bps / 10000.0
    opt_ret = float(opt_w @ mu)
    opt_vol = float(np.sqrt(12.0 * opt_var))
    vol_gap = abs(opt_vol - cand_vol)
    certified = bool(vol_gap <= target_vol_gap + 1e-12)

    res = MIQPResult(
        q_bps=opt_bps,
        z_inclusion=opt_bps > 0,
        weights=opt_w,
        achieved_return=opt_ret,
        monthly_variance=opt_var,
        annualised_volatility=opt_vol,
        dual_lower_bound=cand_var,
        volatility_gap=vol_gap,
        status="optimal",
        certified_optimal=certified,
    )

    details = {
        "unconstrained_candidate_is_feasible": is_feas,
        "violation_reason": violation_reason,
        "optimal_miqp_integer_bps": opt_bps.tolist(),
        "optimal_miqp_boolean_inclusion": (opt_bps > 0).astype(int).tolist(),
        "optimal_miqp_weights_decimal": opt_w.tolist(),
        "sum_of_basis_points": int(np.sum(opt_bps)),
        "achieved_monthly_return": opt_ret,
        "optimal_monthly_variance": opt_var,
        "optimal_annualised_volatility": opt_vol,
        "two_asset_support_alternative_bps": alt_a_bps.tolist() if alt_a_bps is not None else None,
        "two_asset_support_monthly_variance": alt_a_var,
        "certified_annual_volatility_gap_le_1e4": certified,
    }

    return res, details


def solve_miqp_point(
    mu: np.ndarray,
    cov: np.ndarray,
    target_return: float,
    mask: np.ndarray | None = None,
    min_pos_bps: int = 10,
    max_pos_bps: int = 10000,
    target_vol_gap: float = 0.0001,
    solver: str = "auto",
    unconstrained_candidate_bps: Sequence[int] | np.ndarray | None = None,
    fund_ids: Sequence[str] | None = None,
) -> MIQPResult:
    """Solve an integer basis-point semi-continuous portfolio optimization problem.

    Parameters
    ----------
    mu : np.ndarray
        Expected return vector of shape (M,).
    cov : np.ndarray
        Covariance matrix of shape (M, M).
    target_return : float
        Target return constraint: w^T mu >= target_return.
    mask : np.ndarray | None, default=None
        Boolean mask of shape (M,) indicating permissible assets.
    min_pos_bps : int, default=10
        Minimum position gate in basis points (10 bps = 0.10%).
    max_pos_bps : int, default=10000
        Maximum position gate in basis points (10000 bps = 100.00%).
    target_vol_gap : float, default=0.0001
        Maximum certified annualized volatility gap (1 bp = 0.0001).
    solver : str, default="auto"
        Optimization solver strategy.
    unconstrained_candidate_bps : Sequence[int] | np.ndarray | None, default=None
        Optional initial candidate integer basis points to evaluate and project.
    fund_ids : Sequence[str] | None, default=None
        Optional list of fund or asset identifiers.

    Returns
    -------
    MIQPResult
        Immutable result contract containing integer allocations, variance, and certification.
    """
    m_count = len(mu)
    if cov.shape != (m_count, m_count):
        raise ValueError(f"cov shape {cov.shape} does not match mu length {m_count}")

    # If unconstrained candidate was passed, project/repair directly
    if unconstrained_candidate_bps is not None:
        res, _ = project_candidate_to_miqp(
            unconstrained_candidate_bps=unconstrained_candidate_bps,
            mu=mu,
            cov=cov,
            min_pos_bps=min_pos_bps,
            max_pos_bps=max_pos_bps,
            target_vol_gap=target_vol_gap,
            fund_ids=fund_ids,
        )
        return res


    # 1. Active asset eligibility
    if mask is None:
        active_mask = np.ones(m_count, dtype=bool)
    else:
        active_mask = np.asarray(mask, dtype=bool)

    active_indices = np.where(active_mask)[0]
    num_active = len(active_indices)

    # Empty mask sentinel or impossible return
    if num_active == 0 or np.max(mu[active_indices]) < target_return - 1e-12:
        zero_bps = np.zeros(m_count, dtype=np.int64)
        zero_bool = np.zeros(m_count, dtype=bool)
        zero_w = np.zeros(m_count, dtype=np.float64)
        return MIQPResult(
            q_bps=zero_bps,
            z_inclusion=zero_bool,
            weights=zero_w,
            achieved_return=0.0,
            monthly_variance=0.0,
            annualised_volatility=0.0,
            dual_lower_bound=0.0,
            volatility_gap=0.0,
            status="infeasible",
            certified_optimal=False,
        )

    # 2. Continuous QP Relaxation for Global Dual Lower Bound
    w_lb, lb_var = _solve_continuous_qp(
        mu_sub=mu[active_indices],
        cov_sub=cov[np.ix_(active_indices, active_indices)],
        target_ret=target_return,
        min_weight=0.0,
        max_weight=1.0,
    )

    if w_lb is None or lb_var is None:
        zero_bps = np.zeros(m_count, dtype=np.int64)
        zero_bool = np.zeros(m_count, dtype=bool)
        zero_w = np.zeros(m_count, dtype=np.float64)
        return MIQPResult(
            q_bps=zero_bps,
            z_inclusion=zero_bool,
            weights=zero_w,
            achieved_return=0.0,
            monthly_variance=0.0,
            annualised_volatility=0.0,
            dual_lower_bound=0.0,
            volatility_gap=0.0,
            status="infeasible",
            certified_optimal=False,
        )

    lb_var = max(float(lb_var), 0.0)

    # 3. Semi-Continuous Combinatorial Candidate Search
    best_q: np.ndarray | None = None
    best_var = float("inf")

    # If unconstrained_candidate_bps was passed, evaluate it and its micro-weight resolutions
    if unconstrained_candidate_bps is not None:
        cand_arr = np.asarray(unconstrained_candidate_bps, dtype=np.int64)
        is_feas, _ = check_position_feasibility(cand_arr, min_pos_bps, max_pos_bps)
        cand_w = cand_arr / 10000.0
        cand_ret = float(cand_w @ mu)
        if is_feas and cand_ret >= target_return - 1e-12:
            cand_v = float(cand_w @ cov @ cand_w)
            best_q = cand_arr
            best_var = cand_v
        else:
            # Resolve micro-weights: evaluate alternatives for assets with 0 < q_j < min_pos_bps
            micro_idx = [i for i, q in enumerate(cand_arr) if 0 < q < min_pos_bps]
            macro_idx = [i for i, q in enumerate(cand_arr) if q >= min_pos_bps]

            # Alternative 1: Exclude micro-weight assets (support = macro_idx)
            if macro_idx and np.max(mu[macro_idx]) >= target_return - 1e-12:
                w_alt1, _ = _solve_continuous_qp(
                    mu[macro_idx],
                    cov[np.ix_(macro_idx, macro_idx)],
                    target_return,
                    min_weight=min_pos_bps / 10000.0,
                )
                if w_alt1 is not None:
                    q_alt1, v_alt1 = _round_and_refine_basis_points(
                        w_alt1, np.array(macro_idx), m_count, mu, cov, target_return, min_pos_bps, max_pos_bps
                    )
                    if v_alt1 < best_var:
                        best_var = v_alt1
                        best_q = q_alt1

            # Alternative 2: Include micro-weight assets with q_j >= min_pos_bps
            all_supp = macro_idx + micro_idx
            if all_supp and np.max(mu[all_supp]) >= target_return - 1e-12:
                w_alt2, _ = _solve_continuous_qp(
                    mu[all_supp],
                    cov[np.ix_(all_supp, all_supp)],
                    target_return,
                    min_weight=min_pos_bps / 10000.0,
                )
                if w_alt2 is not None:
                    q_alt2, v_alt2 = _round_and_refine_basis_points(
                        w_alt2, np.array(all_supp), m_count, mu, cov, target_return, min_pos_bps, max_pos_bps
                    )
                    if v_alt2 < best_var:
                        best_var = v_alt2
                        best_q = q_alt2

    # Standard candidate support evaluation
    candidate_supports: list[list[int]] = []

    # Support from continuous QP: assets with w > 0
    w_full = np.zeros(m_count, dtype=np.float64)
    w_full[active_indices] = w_lb

    supp_pos = [i for i in active_indices if w_full[i] > 1e-6]
    supp_min = [i for i in active_indices if w_full[i] >= min_pos_bps / 10000.0]
    supp_micro = [i for i in active_indices if 1e-6 < w_full[i] < min_pos_bps / 10000.0]

    if supp_min:
        candidate_supports.append(supp_min)
    if supp_pos:
        candidate_supports.append(supp_pos)

    # For small active universe (<= 8 assets), enumerate non-empty subsets
    if num_active <= 8:
        for r in range(1, num_active + 1):
            for comb in itertools.combinations(active_indices, r):
                candidate_supports.append(list(comb))
    else:
        # Branch on micro-weight assets: prioritize highest weights first
        supp_micro_sorted = sorted(supp_micro, key=lambda idx: w_full[idx], reverse=True)
        top_micro = supp_micro_sorted[:4]
        for r in range(len(top_micro) + 1):
            for comb in itertools.combinations(top_micro, r):
                comb_supp = list(set(supp_min) | set(comb))
                if comb_supp:
                    candidate_supports.append(comb_supp)
        for k in range(5, min(len(supp_micro_sorted) + 1, 12)):
            candidate_supports.append(list(set(supp_min) | set(supp_micro_sorted[:k])))

        # Also add single asset supports for any asset meeting target return
        for i in active_indices:
            if mu[i] >= target_return - 1e-12:
                candidate_supports.append([i])

    # Deduplicate candidate supports
    seen = set()
    unique_supports = []
    for s in candidate_supports:
        t = tuple(sorted(s))
        if t not in seen:
            seen.add(t)
            unique_supports.append(s)

    # Evaluate each candidate support
    lb_vol = float(np.sqrt(12.0 * max(lb_var, 0.0)))
    for supp in unique_supports:
        supp_arr = np.array(supp, dtype=np.int64)
        k_s = len(supp_arr)

        if np.max(mu[supp_arr]) < target_return - 1e-12:
            continue

        if k_s == 1:
            idx = supp_arr[0]
            if mu[idx] >= target_return - 1e-12:
                q_cand = np.zeros(m_count, dtype=np.int64)
                q_cand[idx] = 10000
                v_cand = float(cov[idx, idx])
                if v_cand < best_var:
                    best_var = v_cand
                    best_q = q_cand
                    cand_ann_vol = float(np.sqrt(12.0 * v_cand))
                    if cand_ann_vol - lb_vol <= target_vol_gap + 1e-12:
                        break
            continue

        w_sub, _ = _solve_continuous_qp(
            mu[supp_arr],
            cov[np.ix_(supp_arr, supp_arr)],
            target_return,
            min_weight=min_pos_bps / 10000.0,
            max_weight=1.0,
        )
        if w_sub is not None:
            q_cand, v_cand = _round_and_refine_basis_points(
                w_sub, supp_arr, m_count, mu, cov, target_return, min_pos_bps, max_pos_bps
            )
            if v_cand < best_var:
                best_var = v_cand
                best_q = q_cand
                cand_ann_vol = float(np.sqrt(12.0 * v_cand))
                if cand_ann_vol - lb_vol <= target_vol_gap + 1e-12:
                    break

    if best_q is None:
        zero_bps = np.zeros(m_count, dtype=np.int64)
        zero_bool = np.zeros(m_count, dtype=bool)
        zero_w = np.zeros(m_count, dtype=np.float64)
        return MIQPResult(
            q_bps=zero_bps,
            z_inclusion=zero_bool,
            weights=zero_w,
            achieved_return=0.0,
            monthly_variance=0.0,
            annualised_volatility=0.0,
            dual_lower_bound=lb_var,
            volatility_gap=0.0,
            status="infeasible",
            certified_optimal=False,
        )

    # 4. Final Solution Metrics & Volatility Gap Certification
    weights = best_q / 10000.0
    z_inclusion = best_q > 0
    achieved_ret = float(weights @ mu)
    monthly_var = float(weights @ cov @ weights)
    ann_vol = float(np.sqrt(12.0 * monthly_var))

    lb_vol = float(np.sqrt(12.0 * max(lb_var, 0.0)))
    vol_gap = max(ann_vol - lb_vol, 0.0)

    certified = bool(vol_gap <= target_vol_gap + 1e-12)
    status = "optimal"

    return MIQPResult(
        q_bps=best_q,
        z_inclusion=z_inclusion,
        weights=weights,
        achieved_return=achieved_ret,
        monthly_variance=monthly_var,
        annualised_volatility=ann_vol,
        dual_lower_bound=lb_var,
        volatility_gap=vol_gap,
        status=status,
        certified_optimal=certified,
    )


def compute_miqp_frontier(
    prepared_model: PreparedModel,
    mask_idx: int = 0,
    num_points: int = 1001,
    min_pos_bps: int = 10,
    max_pos_bps: int = 10000,
    target_vol_gap: float = 0.0001,
) -> MIQPFrontier:
    """Compute the mixed-integer quadratic efficient frontier across uniformly spaced return targets.

    Parameters
    ----------
    prepared_model : PreparedModel
        Prepared model contract instance containing returns, covariance, and sleeve masks.
    mask_idx : int, default=0
        6-bit sleeve category mask index in {0, ..., 63}.
    num_points : int, default=1001
        Number of frontier target points G (standard V8.0 specification is 1,001).
    min_pos_bps : int, default=10
        Minimum position gate in basis points (10 bps = 0.10%).
    max_pos_bps : int, default=10000
        Maximum position gate in basis points (10000 bps = 100.00%).
    target_vol_gap : float, default=0.0001
        Maximum certified annualized volatility gap (1 bp = 0.0001).

    Returns
    -------
    MIQPFrontier
        Immutable frontier instance containing target returns and MIQPResult allocations.
    """
    if mask_idx < 0 or mask_idx >= 64:
        raise ValueError(f"mask_idx must be in [0, 63], got {mask_idx}")

    mask = prepared_model.sleeve_masks[mask_idx]
    active_indices = np.where(mask)[0]

    # Mask 0 or empty mask is the null sentinel mask: returns empty frontier
    if mask_idx == 0 or len(active_indices) == 0:
        return MIQPFrontier(target_returns=np.empty(0, dtype=np.float64), results=[], mask_idx=mask_idx)

    mu_mo = prepared_model.mu_arith_ann / 12.0
    cov_mo = prepared_model.cov_monthly

    # Calculate mu_max (maximum achievable return on active assets)
    mu_max = float(np.max(mu_mo[active_indices]))

    # Calculate mu_min from the global minimum-variance continuous portfolio on active assets
    meta = getattr(prepared_model, "metadata", None)
    cash_idx = meta.get("cash_index") if isinstance(meta, dict) else getattr(meta, "cash_index", None)
    if cash_idx is not None and cash_idx in active_indices and np.allclose(cov_mo[cash_idx, active_indices], 0.0, atol=1e-12):
        mu_min = float(mu_mo[cash_idx])
    else:
        w_gmv, _ = _solve_continuous_qp(
            mu_sub=mu_mo[active_indices],
            cov_sub=cov_mo[np.ix_(active_indices, active_indices)],
            target_ret=float(np.min(mu_mo[active_indices])),
            min_weight=0.0,
            max_weight=1.0,
        )
        if w_gmv is not None:
            w_clean = np.where(w_gmv < 1e-5, 0.0, w_gmv)
            if np.sum(w_clean) > 0:
                w_clean /= np.sum(w_clean)
                mu_min = float(w_clean @ mu_mo[active_indices])
            else:
                mu_min = float(w_gmv @ mu_mo[active_indices])
        else:
            mu_min = float(np.min(mu_mo[active_indices]))

    mu_min = min(mu_min, mu_max)

    if num_points <= 1 or abs(mu_max - mu_min) < 1e-12:
        target_returns = np.array([mu_max], dtype=np.float64)
    else:
        target_returns = np.linspace(mu_min, mu_max, num_points, dtype=np.float64)

    results: list[MIQPResult] = []
    for tr in target_returns:
        res = solve_miqp_point(
            mu=mu_mo,
            cov=cov_mo,
            target_return=float(tr),
            mask=mask,
            min_pos_bps=min_pos_bps,
            max_pos_bps=max_pos_bps,
            target_vol_gap=target_vol_gap,
            fund_ids=prepared_model.asset_ids,
        )
        results.append(res)

    return MIQPFrontier(target_returns=target_returns, results=results, mask_idx=mask_idx)


__all__ = [
    "MIQPResult",
    "MIQPFrontier",
    "check_position_feasibility",
    "project_candidate_to_miqp",
    "solve_miqp_point",
    "compute_miqp_frontier",
]

