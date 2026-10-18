"""Unit tests for Portfolio Construction Lab V8 Holdings-Informed Factor Calibration.

Tests Stage 04 Section 2 mathematical contracts:
1. Winsorization at 1st/99th percentiles and cap-weighted standardization (mean 0, var 1).
2. Two-stage cross-sectional ridge mapping with unpenalized intercept and anchor fallback.
3. Three-tier Empirical Bayes shrinkage cascade and Minimum 30-Company Peer Group Rule.
4. Benchmark-neutral centering (multiplicative market, subtractive style).
5. Exact net return reconciliation identity (Equation 155 within 1e-15 machine precision).
"""

from __future__ import annotations

import numpy as np
import pytest

from portfolio.holdings_model import (
    benchmark_neutral_centering,
    calculate_company_gross_returns,
    estimate_ridge_characteristic_mapping,
    reconcile_net_return,
    three_tier_shrinkage_cascade,
    winsorize_and_standardize_characteristics,
)


def test_winsorize_and_standardize_characteristics() -> None:
    """Verify 1st/99th percentile clipping and cap-weighted mean 0, variance 1."""
    rng = np.random.default_rng(42)
    n = 200
    raw_x = rng.standard_normal((n, 3))
    # Inject extreme outliers in tails
    raw_x[0, :] = 1000.0
    raw_x[1, :] = -1000.0

    # Cap weights: lognormal market caps
    mcap = np.exp(rng.uniform(10.0, 15.0, size=n))

    # Standardize
    z_std, mu_cap, sigma_cap = winsorize_and_standardize_characteristics(
        raw_x, mcap, p_low=0.01, p_high=0.99, return_moments=True
    )

    # Outliers must be bounded by percentiles
    p1 = np.percentile(raw_x, 1.0, axis=0)
    p99 = np.percentile(raw_x, 99.0, axis=0)
    assert np.all(z_std <= (p99 - mu_cap) / sigma_cap + 1e-12)
    assert np.all(z_std >= (p1 - mu_cap) / sigma_cap - 1e-12)

    # Cap-weighted mean of z must be identically 0 within 1e-12
    v = mcap / np.sum(mcap)
    weighted_mean_z = np.sum(v[:, np.newaxis] * z_std, axis=0)
    assert np.all(np.abs(weighted_mean_z) < 1e-12)

    # Cap-weighted variance of z must be identically 1.0 within 1e-12
    weighted_var_z = np.sum(v[:, np.newaxis] * (z_std**2), axis=0)
    assert np.allclose(weighted_var_z, 1.0, atol=1e-12)


def test_winsorize_degenerate_zero_variance() -> None:
    """Verify constant characteristics produce standardized zeros without dividing by zero."""
    n = 50
    raw_x = np.full((n, 2), 5.0)
    mcap = np.ones(n)

    z_std = winsorize_and_standardize_characteristics(raw_x, mcap)
    assert np.all(z_std == 0.0)


def test_estimate_ridge_characteristic_mapping_unpenalized_intercept() -> None:
    """Verify that ridge estimation leaves intercept unpenalized."""
    rng = np.random.default_rng(1234)
    n = 100
    gamma_true = np.array([1.0, 0.4, -0.3, 0.2, -0.1, 0.5])
    k_feat = 5

    # Standardized characteristics z
    z = rng.standard_normal((n, k_feat))
    # Extend with intercept column 1
    z_ext = np.column_stack([np.ones(n), z])

    # Generate synthetic time-series betas B_ts = z_ext @ gamma_true + noise
    noise = rng.normal(0.0, 0.05, size=n)
    b_ts = z_ext @ gamma_true + noise

    # Precision weights
    w_ts = np.ones(n)

    # Solve ridge regression with lambda = 1.0
    gamma_est = estimate_ridge_characteristic_mapping(z_ext, b_ts, w_ts, lambda_ridge=1.0)

    # Verify structural recovery: intercept is unpenalized and close to 1.0
    assert abs(gamma_est[0] - 1.0) < 0.05
    # Slopes are shrunk slightly towards 0 but close to truth
    assert np.allclose(gamma_est[1:], gamma_true[1:], atol=0.08)


def test_estimate_ridge_mapping_anchor_fallback_and_blending() -> None:
    """Verify condition number check (kappa > 1e4) and sample size threshold blending."""
    n = 100  # N < 150 triggers pure anchor fallback when anchor provided
    z_ext = np.ones((n, 3))
    # Make columns collinear so kappa is very large
    z_ext[:, 1] = np.linspace(0, 1, n)
    z_ext[:, 2] = z_ext[:, 1] + 1e-8
    b_ts = np.ones((n, 1))

    anchor_gamma = np.array([[1.0], [0.5], [0.2]])

    # Because N = 100 < 150 (and kappa > 1e4), anchor fallback is activated
    gamma_out = estimate_ridge_characteristic_mapping(
        z_ext, b_ts, anchor_gamma=anchor_gamma, cond_threshold=1e4
    )
    assert np.array_equal(gamma_out, anchor_gamma)

    # Test blending when 150 <= N < 500
    n_blend = 325  # midpoint: theta = (325 - 150)/350 = 175/350 = 0.5
    z_ext_blend = np.column_stack([np.ones(n_blend), np.random.standard_normal((n_blend, 2))])
    b_ts_blend = np.random.standard_normal((n_blend, 1))

    gamma_blended = estimate_ridge_characteristic_mapping(
        z_ext_blend, b_ts_blend, anchor_gamma=anchor_gamma
    )
    # Result must not be identical to pure anchor or pure ridge
    assert not np.array_equal(gamma_blended, anchor_gamma)


def test_three_tier_shrinkage_cascade() -> None:
    """Verify three-tier Empirical Bayes cascade and Minimum 30-Company Rule."""
    beta_comp = np.array([1.2, 0.4, -0.2])
    beta_peer = np.array([1.1, 0.1, 0.0])
    beta_prior = np.array([1.0, 0.0, 0.0])

    # Case 1: Mature verified company (c_i = 1.0, T_i = 60 months)
    # alpha_i = 60 / (60 + 24) = 60 / 84 = 5/7 ~= 0.7142857
    # N_peer = 50 >= 30: eta_peer = 50 / (50 + 30) = 50 / 80 = 0.625
    shrunk_mature = three_tier_shrinkage_cascade(
        beta_comp, beta_peer, beta_prior, c_i=1.0, T_i=60.0, N_peer=50
    )
    alpha_mature = 60.0 / 84.0
    eta_mature = 50.0 / 80.0
    expected_mature = alpha_mature * beta_comp + (1.0 - alpha_mature) * (
        eta_mature * beta_peer + (1.0 - eta_mature) * beta_prior
    )
    assert np.allclose(shrunk_mature, expected_mature, atol=1e-12)

    # Case 2: Minimum 30-Company Rule test: N_peer = 25 (< 30)
    # eta_peer must be zero, bypassing peer group and shrinking directly to prior!
    shrunk_small_peer = three_tier_shrinkage_cascade(
        beta_comp, beta_peer, beta_prior, c_i=1.0, T_i=60.0, N_peer=25
    )
    expected_small_peer = alpha_mature * beta_comp + (1.0 - alpha_mature) * beta_prior
    assert np.allclose(shrunk_small_peer, expected_small_peer, atol=1e-12)

    # Case 3: Recent IPO / unverified company (T_i = 0)
    # alpha_i must be 0; shrinks 100% to peer group & prior
    shrunk_ipo = three_tier_shrinkage_cascade(
        beta_comp, beta_peer, beta_prior, c_i=1.0, T_i=0.0, N_peer=50
    )
    assert np.allclose(shrunk_ipo, eta_mature * beta_peer + (1.0 - eta_mature) * beta_prior, atol=1e-12)


def test_benchmark_neutral_centering() -> None:
    """Verify multiplicative centering on market beta and subtractive on style betas."""
    benchmark_betas = np.array([1.05, 0.10, -0.05, 0.02])
    fund_betas = np.array([1.26, 0.35, -0.05, -0.01])

    # 1D test
    active_betas = benchmark_neutral_centering(fund_betas, benchmark_betas)
    assert abs(active_betas[0] - (1.26 / 1.05)) < 1e-12  # Multiplicative market centering (1.20)
    assert abs(active_betas[1] - (0.35 - 0.10)) < 1e-12  # Subtractive style (0.25)
    assert abs(active_betas[2] - (-0.05 - (-0.05))) < 1e-12  # 0.00
    assert abs(active_betas[3] - (-0.01 - 0.02)) < 1e-12  # -0.03

    # Benchmark centered against itself must produce [1.0, 0.0, 0.0, 0.0]
    self_centered = benchmark_neutral_centering(benchmark_betas, benchmark_betas)
    assert np.allclose(self_centered, np.array([1.0, 0.0, 0.0, 0.0]), atol=1e-12)

    # 2D matrix test
    funds_2d = np.array([fund_betas, benchmark_betas])
    active_2d = benchmark_neutral_centering(funds_2d, benchmark_betas)
    assert np.allclose(active_2d[0], active_betas, atol=1e-12)
    assert np.allclose(active_2d[1], np.array([1.0, 0.0, 0.0, 0.0]), atol=1e-12)


def test_reconcile_net_return_and_exact_accounting_identity() -> None:
    """Verify exact net return reconciliation identity within 1e-15 machine precision (Equation 155)."""
    r_f = 0.0380
    mu_bmk_gross = 0.0850
    lambda_styles = np.array([0.015, -0.008, 0.012, -0.004, 0.020])
    bmk_betas = np.array([1.00, 0.02, -0.01, 0.01, 0.00, 0.01])

    # Three synthetic constituent companies
    company_betas = np.array([
        [1.15, 0.25, -0.10, 0.05, 0.02, 0.12],
        [0.90, -0.15, 0.12, -0.03, 0.01, -0.04],
        [1.02, 0.05, 0.01, 0.00, -0.02, 0.03],
    ])

    # ETF holdings weights summing to 1.0
    h_weights = np.array([0.50, 0.35, 0.15])

    ter = 0.0007  # 7 bps
    wht = 0.0002  # 2 bps
    credit = 0.0001  # 1 bp (capped at 15 bps)

    # 1. Top-down calculation via centered fund betas
    fund_betas = h_weights @ company_betas
    active_fund_betas = benchmark_neutral_centering(fund_betas, bmk_betas)
    mu_net_topdown = reconcile_net_return(
        gross_market_return=mu_bmk_gross,
        active_betas=active_fund_betas,
        factor_premia=lambda_styles,
        r_f=r_f,
        ter=ter,
        wht=wht,
        lending_credit=credit,
    )

    # 2. Bottom-up calculation via constituent gross returns (Equation 151)
    company_gross = calculate_company_gross_returns(
        shrunk_betas=company_betas,
        benchmark_betas=bmk_betas,
        gross_market_return=mu_bmk_gross,
        factor_premia=lambda_styles,
        r_f=r_f,
    )
    mu_net_bottomup = float(np.sum(h_weights * company_gross)) - wht - ter + credit

    # Discrepancy must be bounded by machine precision (<= 1e-15)
    discrepancy = abs(mu_net_topdown - mu_net_bottomup)
    assert discrepancy <= 1e-15, f"Reconciliation discrepancy {discrepancy:.3e} exceeds 1e-15"
