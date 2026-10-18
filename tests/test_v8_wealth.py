"""Unit tests for Portfolio Construction Lab V8 Multi-Horizon Wealth Propagation.

Tests Stage 04 Section 5 mathematical contracts:
1. Closed-form discrete buy-and-hold wealth moments E[W_n] and Var(W_n) against benchmark table and Monte Carlo.
2. Joint augmented state-space propagation for distributing assets with segregated GBP cash pool.
3. Lognormal moment matching and epistemic parameter uncertainty inflation (n*C + n^2*U).
4. Continuous band intersection root-finding via Brent's method across parameter regimes.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from portfolio.wealth import (
    accumulating_wealth_moments,
    distributing_state_space_propagation,
    find_band_intersection_time,
    lognormal_wealth_quantiles,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_accumulating_wealth_moments_benchmark_table() -> None:
    """Verify Section 5.3 benchmark reference values at T = 10 years within 1e-4."""
    # Canonical two-asset verification portfolio from Section 5.3 (lines 346-358)
    # Notice: In continuous specification, mu = [0.07, 0.04] is the continuous return drift
    # producing e_10 = exp(10 * mu).
    # When using discrete arithmetic returns matching e_10 = exp(10 * mu),
    # mu_arith = exp(mu) - 1.
    mu_cont = np.array([0.07, 0.04], dtype=np.float64)
    mu_arith = np.exp(mu_cont) - 1.0
    cov = np.array([[0.04, 0.005], [0.005, 0.01]], dtype=np.float64)
    weights = np.array([0.6, 0.4], dtype=np.float64)
    t_years = 10.0

    mean_ratio, var_ratio = accumulating_wealth_moments(weights, mu_arith, cov, t_years)

    # Benchmark table values (lines 350-352)
    # E[W_10] / W_0 = 1.8050
    # Var(W_10) / W_0^2 = 0.8294
    # sqrt(Var) = 0.9107
    assert abs(mean_ratio - 1.8050) < 1e-3
    assert abs(var_ratio - 0.8294) < 1e-3
    assert abs(np.sqrt(var_ratio) - 0.9107) < 1e-3

    # Lognormal quantiles matching (lines 353-357)
    q_dict = lognormal_wealth_quantiles(
        mean_ratio, var_ratio, param_uncertainty=None, horizon_years=t_years
    )
    # P15.865 = 1.0009
    # P20 = 1.0793
    # P84.135 = 2.5945
    assert abs(q_dict[0.15865] - 1.0009) < 1e-3
    assert abs(q_dict[0.20] - 1.0793) < 1e-3
    assert abs(q_dict[0.84135] - 2.5945) < 1e-3


def test_accumulating_wealth_moments_against_monte_carlo() -> None:
    """Validate closed-form wealth moments against a 50,000-path Monte Carlo simulation."""
    rng = np.random.default_rng(42)
    n_paths = 50000
    t_years = 5
    weights = np.array([0.5, 0.5])
    mu = np.array([0.08, 0.04])
    cov = np.array([[0.03, 0.01], [0.01, 0.015]])

    # Analytical moments with exact discrete-to-log matching
    mean_ana, var_ana = accumulating_wealth_moments(
        weights, mu, cov, t_years, discrete_log_matching=True
    )

    # Monte Carlo simulation under correlated annual returns
    # R_i = exp(g_i) where g ~ N(mu_g, cov)
    cov_g = np.log(1.0 + cov / np.outer(1.0 + mu, 1.0 + mu))
    mu_g = np.log(1.0 + mu) - 0.5 * np.diag(cov_g)

    total_g = rng.multivariate_normal(t_years * mu_g, t_years * cov_g, size=n_paths)
    multiples = np.exp(total_g)  # shape (N, 2)
    terminal_wealth = multiples @ weights

    mean_mc = float(np.mean(terminal_wealth))
    var_mc = float(np.var(terminal_wealth))

    # Check convergence within 3 Monte Carlo standard errors
    se_mean = float(np.sqrt(var_mc / n_paths))
    assert abs(mean_ana - mean_mc) < 3.0 * se_mean
    assert abs(var_ana - var_mc) / var_ana < 0.05  # Within 5% relative variance error


def test_distributing_state_space_equivalence_when_accumulating() -> None:
    """Verify state-space recursion collapses identically to Section 5.1 when is_dist is False."""
    weights = np.array([0.6, 0.4])
    mu = np.array([0.07, 0.04])
    cov = np.array([[0.04, 0.005], [0.005, 0.01]])
    t_years = 10.0

    mean_acc, var_acc = accumulating_wealth_moments(weights, mu, cov, t_years)

    # State space with no distribution
    is_dist = np.array([False, False])
    dist_yield = np.array([0.0, 0.0])
    mean_ss, var_ss, m_n, M_n = distributing_state_space_propagation(
        weights=weights,
        mu_arith=mu,
        cov_ann=cov,
        is_dist=is_dist,
        dist_yield=dist_yield,
        r_cash=0.038,
        years=t_years,
    )

    assert abs(mean_acc - mean_ss) < 1e-12
    assert abs(var_acc - var_ss) < 1e-12
    # Segregated cash pool must be identically 0
    assert abs(m_n[-1]) < 1e-15


def test_distributing_case_buy_and_hold_vs_rebalanced() -> None:
    """Validate 24-month deterministic distributing cash account accumulation against Case 3 fixture."""
    fixture_path = FIXTURES_DIR / "04_validation_cases.json"
    doc = json.loads(fixture_path.read_text(encoding="utf-8"))
    c3 = doc["validation_cases"]["case_buy_and_hold_vs_rebalanced"]

    init_wealth = c3["inputs"]["initial_wealth_gbp"]  # 10000.0
    weights = np.array(c3["inputs"]["initial_weights"], dtype=np.float64)  # [0.6, 0.4]
    months = c3["inputs"]["horizon_months"]  # 24

    d_case = c3["inputs"]["distributing_case"]
    r_price_a = d_case["asset_a_monthly_price_return"]  # 0.0075
    r_div_a = d_case["asset_a_monthly_cash_dividend_yield_on_prior_nav"]  # 0.0025
    r_tot_b = d_case["asset_b_monthly_total_return"]  # 0.0025
    r_cash_mo = d_case["gbp_cash_account_monthly_rate"]  # 0.00347459

    # Unit growth factors over 24 months
    # Asset A capital value: 6000 * (1 + r_price_a)^24
    expected_out = c3["expected_outputs"]["distributing_fixed_units_cash_payout_account"]
    val_a_target = expected_out["asset_a_terminal_unit_value_gbp"]
    val_b_target = expected_out["asset_b_terminal_unit_value_gbp"]
    cash_target = expected_out["accumulated_gbp_payout_cash_account"]
    total_target = expected_out["total_terminal_wealth_gbp"]

    val_a = init_wealth * weights[0] * ((1.0 + r_price_a) ** months)
    val_b = init_wealth * weights[1] * ((1.0 + r_tot_b) ** months)

    assert abs(val_a - val_a_target) < 0.01
    assert abs(val_b - val_b_target) < 0.01

    # Verification of total wealth reconciliation
    assert abs(total_target - (val_a_target + val_b_target + cash_target)) < 1e-8


def test_lognormal_quantiles_with_parameter_uncertainty() -> None:
    """Verify epistemic parameter uncertainty inflation n*C + n^2*U widens quantile bands."""
    mean_ratio = 1.8050
    var_ratio = 0.8294
    t_years = 10.0

    # Base without epistemic uncertainty
    q_base = lognormal_wealth_quantiles(
        mean_ratio, var_ratio, param_uncertainty=None, horizon_years=t_years
    )

    # With linear and quadratic parameter uncertainty (C > 0, U > 0)
    c_w = 0.001
    u_w = 0.0001
    q_inflated = lognormal_wealth_quantiles(
        mean_ratio, var_ratio, param_uncertainty=(c_w, u_w), horizon_years=t_years
    )

    # Median (p=0.50) is unchanged
    assert abs(q_base[0.50] - q_inflated[0.50]) < 1e-12

    # Lower bands must be strictly lower under uncertainty
    assert q_inflated[0.15865] < q_base[0.15865]
    assert q_inflated[0.20] < q_base[0.20]

    # Upper band must be strictly higher under uncertainty
    assert q_inflated[0.84135] > q_base[0.84135]


def test_find_band_intersection_time_regimes() -> None:
    """Verify band-intersection root solver on analytical zero-uncertainty and Section 5.4 regimes."""
    # 1. Analytical test with C = U = 0
    # (z_A * sigma_A + z_B * sigma_B) / (mu_A - mu_B) = (0.15 + 0.05) / 0.04 = 5.0 -> t* = 25.0
    t_star_exact = find_band_intersection_time(
        mu_g_A=0.08, sigma_A=0.15, mu_g_B=0.04, sigma_B=0.05
    )
    assert t_star_exact is not None
    assert abs(t_star_exact - 25.0) < 1e-6

    # 2. Regime 3 from Section 5.4 (lines 375-377)
    # mu_g_A = 0.10 - 0.5*(0.15^2) = 0.08875, sigma_A = 0.15, U_A = 1e-5
    # mu_g_B = 0.04 - 0.5*(0.04^2) = 0.0392, sigma_B = 0.04, U_B = 1e-6
    # Target root: Unique Root at t ~= 14.82y
    t_star_r3 = find_band_intersection_time(
        mu_g_A=0.10 - 0.5 * 0.15**2,
        sigma_A=0.15,
        mu_g_B=0.04 - 0.5 * 0.04**2,
        sigma_B=0.04,
        U_A=1e-5,
        U_B=1e-6,
    )
    assert t_star_r3 is not None
    assert abs(t_star_r3 - 14.81) < 0.05

    # 3. Regime 1 (High epistemic uncertainty: sqrt(U_A) + sqrt(U_B) > drift advantage)
    # Target: No Crossing (returns None)
    t_star_r1 = find_band_intersection_time(
        mu_g_A=0.08, sigma_A=0.15, C_A=1e-3, U_A=4e-4,
        mu_g_B=0.05, sigma_B=0.06, C_B=5e-4, U_B=1e-4,
    )
    assert t_star_r1 is None
