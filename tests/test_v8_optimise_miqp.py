"""Unit tests for Module 4: MIQP Portfolio Optimization Engine.

Validates:
- Case 5 from 04_validation_cases.json (semi-continuous 10 bps minimum position gate)
- Sum of basis points invariant (sum q_j = 10,000)
- Semi-continuous gate invariants (q_j == 0 or 10 <= q_j <= 10000)
- Certified Annual Volatility Gap (Delta sigma_gap <= 0.0001 / 1 bp)
- Sleeve mask active universe restrictions
- Boundary cases: infeasible target returns, single-asset maximum return corner solutions
- Frontier generation across target returns
"""

import json
from pathlib import Path

import numpy as np
import pytest

from portfolio.model import PreparedModel
from portfolio.optimise_miqp import (
    MIQPFrontier,
    MIQPResult,
    check_position_feasibility,
    compute_miqp_frontier,
    project_candidate_to_miqp,
    solve_miqp_point,
)



@pytest.fixture
def validation_case_5() -> dict:
    """Load Case 5 from 04_validation_cases.json fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "04_validation_cases.json"
    if not fixture_path.exists():
        fixture_path = (
            Path(__file__).parent.parent
            / "docs"
            / "04_validation_cases.json"
        )
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("validation_cases", data)
    return cases["case_miqp_minimum_position"]


@pytest.fixture
def sample_prepared_model() -> PreparedModel:
    """Construct a clean 3-asset PreparedModel for MIQP testing."""
    m_count = 3
    asset_ids = np.array([0, 1, 2], dtype=np.uint16)
    qc = ["GBP", "GBP", "GBP"]
    # Monthly returns [0.008, 0.006, 0.004] -> annualized [0.096, 0.072, 0.048]
    mu_mo = np.array([0.008, 0.006, 0.004], dtype=np.float64)
    mu_ann = mu_mo * 12.0
    mu_log = np.log(1.0 + mu_ann)

    cov_mo = np.diag([0.0025, 0.0016, 0.0009]).astype(np.float64)
    cov_ann = cov_mo * 12.0

    c_mat = np.eye(m_count, dtype=np.float64) * 0.0001
    u_mat = np.eye(m_count, dtype=np.float64) * 0.00001
    dist_pol = (np.zeros(m_count, dtype=bool), np.zeros(m_count, dtype=np.float64))

    # Sleeve masks: mask 0 is all False; mask 1 enables asset 0; mask 7 enables all 3
    sleeve_masks = np.zeros((64, m_count), dtype=bool)
    sleeve_masks[1, 0] = True
    sleeve_masks[3, [0, 1]] = True
    sleeve_masks[7, :] = True
    sleeve_masks[63, :] = True

    return PreparedModel(
        asset_ids=asset_ids,
        quote_currency=qc,
        mu_arith_ann=mu_ann,
        mu_log_ann=mu_log,
        cov_ann=cov_ann,
        cov_monthly=cov_mo,
        param_uncertainty=(c_mat, u_mat),
        dist_policy=dist_pol,
        sleeve_masks=sleeve_masks,
    )


def test_case_5_position_feasibility_check(validation_case_5):
    """Validate semi-continuous feasibility check against Case 5 unconstrained candidate."""
    inp = validation_case_5["inputs"]
    exp = validation_case_5["expected_outputs"]
    fund_ids = inp["fund_ids"]

    # 1. Unconstrained candidate [5002, 4994, 4] has a 4 bps micro-weight (< 10 bps)
    unc_bps = inp["unconstrained_candidate_bps"]
    is_feas, reason = check_position_feasibility(unc_bps, min_pos_bps=10, fund_ids=fund_ids)
    assert is_feas is False
    assert exp["violation_reason"].lower() in reason.lower() or "below minimum 10 bps" in reason

    # 2. Optimal integer basis points [5005, 4985, 10] are fully feasible
    opt_bps = exp["optimal_miqp_integer_bps"]
    is_feas_opt, reason_opt = check_position_feasibility(opt_bps, min_pos_bps=10, fund_ids=fund_ids)
    assert is_feas_opt is True
    assert reason_opt is None


def test_case_5_miqp_point_solve(validation_case_5):
    """Validate exact Case 5 optimal integer allocation and variance comparison."""
    inp = validation_case_5["inputs"]
    exp = validation_case_5["expected_outputs"]

    mu = np.array(inp["monthly_mean"], dtype=np.float64)
    cov = np.array(inp["monthly_covariance"], dtype=np.float64)
    unc_bps = inp["unconstrained_candidate_bps"]

    # Solve point with candidate resolution
    res = solve_miqp_point(
        mu=mu,
        cov=cov,
        target_return=0.006999,  # Achieved return target of Case 5
        min_pos_bps=10,
        unconstrained_candidate_bps=unc_bps,
        fund_ids=inp["fund_ids"],
    )

    assert res.status == "optimal"
    assert np.array_equal(res.q_bps, exp["optimal_miqp_integer_bps"])
    assert np.array_equal(res.z_inclusion, exp["optimal_miqp_boolean_inclusion"])
    assert np.allclose(res.weights, exp["optimal_miqp_weights_decimal"], atol=1e-12)
    assert int(np.sum(res.q_bps)) == exp["sum_of_basis_points"]
    assert abs(res.achieved_return - exp["achieved_monthly_return"]) <= 1e-6
    assert abs(res.monthly_variance - exp["optimal_monthly_variance"]) <= 1e-7
    assert abs(res.annualised_volatility - exp["optimal_annualised_volatility"]) <= 1e-4

    # Two-asset alternative check
    two_asset_bps = np.array(exp["two_asset_support_alternative_bps"], dtype=np.float64)
    w_2a = two_asset_bps / 10000.0
    var_2a = float(w_2a @ cov @ w_2a)
    assert abs(var_2a - exp["two_asset_support_monthly_variance"]) <= 1e-12

    # 3-asset allocation strictly outperforms 2-asset support
    assert res.monthly_variance < var_2a

    # Certified volatility gap <= 1 bp (1e-4)
    assert res.volatility_gap <= 0.0001
    assert res.certified_optimal is True

    # Validate direct project_candidate_to_miqp details dictionary
    res_proj, details = project_candidate_to_miqp(
        unconstrained_candidate_bps=unc_bps,
        mu=mu,
        cov=cov,
        min_pos_bps=10,
        fund_ids=inp["fund_ids"],
    )
    assert details["unconstrained_candidate_is_feasible"] == exp["unconstrained_candidate_is_feasible"]
    assert details["optimal_miqp_integer_bps"] == exp["optimal_miqp_integer_bps"]
    assert details["two_asset_support_alternative_bps"] == exp["two_asset_support_alternative_bps"]
    assert abs(details["two_asset_support_monthly_variance"] - exp["two_asset_support_monthly_variance"]) <= 1e-12
    assert details["certified_annual_volatility_gap_le_1e4"] == exp["certified_annual_volatility_gap_le_1e4"]



def test_semi_continuous_gates_and_sum_invariants():
    """Verify semi-continuous coupling constraints and exact basis-point sum."""
    np.random.seed(42)
    mu = np.array([0.012, 0.009, 0.007, 0.005, 0.003], dtype=np.float64)
    cov_diag = np.array([0.0036, 0.0025, 0.0016, 0.0009, 0.0004], dtype=np.float64)
    cov = np.diag(cov_diag)

    for target_ret in [0.005, 0.007, 0.009]:
        res = solve_miqp_point(mu=mu, cov=cov, target_return=target_ret, min_pos_bps=10)
        assert res.status == "optimal"
        assert int(np.sum(res.q_bps)) == 10000
        for q in res.q_bps:
            assert q == 0 or 10 <= q <= 10000
        assert res.achieved_return >= target_ret - 1e-9
        assert res.certified_optimal is True


def test_sleeve_mask_restrictions(sample_prepared_model):
    """Verify that disabled assets in sleeve masks receive strictly 0 basis points."""
    mu = sample_prepared_model.mu_arith_ann / 12.0
    cov = sample_prepared_model.cov_monthly

    # Mask 1: only Asset 0 enabled
    mask_1 = sample_prepared_model.sleeve_masks[1]
    res_1 = solve_miqp_point(mu=mu, cov=cov, target_return=0.007, mask=mask_1)
    assert res_1.status == "optimal"
    assert res_1.q_bps[0] == 10000
    assert res_1.q_bps[1] == 0
    assert res_1.q_bps[2] == 0

    # Mask 3: Assets 0 and 1 enabled, Asset 2 disabled
    mask_3 = sample_prepared_model.sleeve_masks[3]
    res_3 = solve_miqp_point(mu=mu, cov=cov, target_return=0.0065, mask=mask_3)
    assert res_3.status == "optimal"
    assert res_3.q_bps[2] == 0
    assert res_3.z_inclusion[2] is False or res_3.z_inclusion[2] == 0
    assert int(np.sum(res_3.q_bps)) == 10000


def test_boundary_infeasible_and_corner_solutions(sample_prepared_model):
    """Verify solver behavior on boundary conditions and infeasible return targets."""
    mu = sample_prepared_model.mu_arith_ann / 12.0
    cov = sample_prepared_model.cov_monthly
    max_ret = float(np.max(mu))

    # Infeasible: target return higher than maximum asset return
    res_inf = solve_miqp_point(mu=mu, cov=cov, target_return=max_ret + 0.005)
    assert res_inf.status == "infeasible"
    assert int(np.sum(res_inf.q_bps)) == 0
    assert res_inf.certified_optimal is False

    # Corner: target return exactly equal to maximum asset return
    res_corner = solve_miqp_point(mu=mu, cov=cov, target_return=max_ret)
    assert res_corner.status == "optimal"
    max_idx = int(np.argmax(mu))
    assert res_corner.q_bps[max_idx] == 10000
    assert int(np.sum(res_corner.q_bps)) == 10000


def test_compute_miqp_frontier(sample_prepared_model):
    """Verify efficient frontier generation across multiple target return points."""
    # Mask 0 (sentinel) returns empty frontier
    frontier_0 = compute_miqp_frontier(sample_prepared_model, mask_idx=0, num_points=11)
    assert len(frontier_0.results) == 0
    assert len(frontier_0.target_returns) == 0

    # Mask 7 (all 3 assets enabled)
    frontier_7 = compute_miqp_frontier(sample_prepared_model, mask_idx=7, num_points=5)
    assert len(frontier_7.results) == 5
    assert len(frontier_7.target_returns) == 5
    assert frontier_7.mask_idx == 7

    q_mat = frontier_7.q_bps_matrix
    assert q_mat.shape == (5, 3)
    for q_row in q_mat:
        assert int(np.sum(q_row)) == 10000
        for q in q_row:
            assert q == 0 or 10 <= q <= 10000

    # Check non-decreasing return property
    achieved = frontier_7.achieved_returns
    assert achieved[-1] >= achieved[0]
