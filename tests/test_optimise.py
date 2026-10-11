import numpy as np
import pytest

from portfolio.optimise import efficient_frontier
from portfolio.risk import factor_covariance, portfolio_metrics, shrunk_covariance


def test_two_asset_frontier_matches_analytic_solution():
    mu = np.array([0.04, 0.10]) / 12
    cov = np.diag([0.10**2, 0.20**2]) / 12
    result = efficient_frontier(mu, cov, points=11)
    assert result.weights[0] == pytest.approx([0.8, 0.2], abs=1e-5)
    assert result.weights[-1] == pytest.approx([0, 1], abs=1e-5)
    assert (np.diff(result.returns) >= -1e-8).all()
    assert (np.diff(result.volatilities) >= -1e-8).all()
    for w, target in zip(result.weights, result.targets):
        assert w.sum() == pytest.approx(1)
        assert w @ mu >= target - 1e-7


def test_caps_and_infeasible_constraints():
    mu, cov = np.array([0.01, 0.02, 0.03]), np.eye(3) * 0.01
    f = efficient_frontier(mu, cov, cap=0.6, exposure=[[0, 1, 1]], limits=[0.5], points=9)
    assert f.weights.max() <= 0.6 + 1e-6
    assert (f.weights[:, 1:].sum(axis=1) <= 0.5 + 1e-6).all()
    with pytest.raises(ValueError, match="infeasible"):
        efficient_frontier(mu, cov, cap=0.3)


def test_equal_returns_have_a_single_efficient_portfolio():
    f = efficient_frontier([0.01, 0.01], np.eye(2))
    assert len(f.weights) == 1
    assert f.weights[0] == pytest.approx([0.5, 0.5])


def test_identical_return_series_do_not_create_diversification():
    x = np.random.default_rng(11).normal(0, 0.04, (120, 2))
    original, _ = shrunk_covariance(x)
    copied, _ = shrunk_covariance(np.column_stack([x, x[:, 0]]))
    assert np.array([0.6, 0.4]) @ original @ [0.6, 0.4] == pytest.approx(
        np.array([0.3, 0.4, 0.3]) @ copied @ [0.3, 0.4, 0.3])


def test_factor_covariance_retains_ridge_cross_terms():
    rng = np.random.default_rng(7)
    f = rng.normal(0, 0.02, (120, 5))
    beta = rng.normal(size=(3, 5))
    residual = f @ beta.T * 0.4 + rng.normal(0, 0.01, (120, 3))
    cov, _ = factor_covariance(f, beta, residual)
    joint, _ = shrunk_covariance(np.column_stack([f, residual]))
    expected = beta @ joint[:5, :5] @ beta.T + joint[5:, 5:]
    expected += beta @ joint[:5, 5:] + joint[5:, :5] @ beta.T
    np.testing.assert_allclose(cov, expected)
    assert np.linalg.eigvalsh(cov).min() >= -1e-12
    _, vol, contributions = portfolio_metrics([0.2, 0.3, 0.5], [0, 0, 0], cov)
    assert contributions.sum() == pytest.approx(vol)


def test_materially_indefinite_covariance_is_rejected():
    with pytest.raises(ValueError, match="positive semidefinite"):
        efficient_frontier([0.01, 0.02], [[1, 2], [2, 1]])
