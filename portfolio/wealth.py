"""Portfolio Construction Lab V8: Multi-Horizon Set-and-Forget Wealth Propagation.

Authoritative implementation of Stage 04 Mathematical Specification (Section 5).
Implements discrete buy-and-hold wealth moments for accumulating assets, joint augmented
state-space propagation for distributing assets with segregated GBP payout cash,
lognormal quantile matching with epistemic parameter uncertainty inflation, and
Brent root-finding for pairwise band-intersection crossover times.
"""

from __future__ import annotations

from typing import Sequence
import numpy as np
import scipy.optimize as opt
import scipy.stats as stats


def accumulating_wealth_moments(
    weights: np.ndarray,
    mu_arith: np.ndarray,
    cov_ann: np.ndarray,
    years: float,
    discrete_log_matching: bool = False,
) -> tuple[float, float]:
    """Compute exact discrete normalized wealth moments E[W_n/W_0] and Var(W_n/W_0).

    Implements Section 5.1 (Equations 299-305):
    - E[W_n/W_0] = sum_j w_j (1 + mu_j)^n = w^T e_n
    - E[(W_n/W_0)^2] = sum_j sum_k w_j w_k exp(n(m_j + m_k) + 0.5*n*(C_jj + C_kk + 2*C_jk))
                     = sum_j sum_k w_j w_k (1 + mu_j)^n (1 + mu_k)^n exp(n*cov_eff_jk)
                     = w^T K_n w
    - Var(W_n/W_0) = E[(W_n/W_0)^2] - (E[W_n/W_0])^2

    When discrete_log_matching=True, evaluates exact discrete-to-log matched covariance
    Sigma_g,ij = ln(1 + cov_ij / ((1 + mu_i)(1 + mu_j))).

    Parameters
    ----------
    weights : np.ndarray
        Portfolio initial allocation vector w_0 of shape (M,), summing to 1.0.
    mu_arith : np.ndarray
        Annualized arithmetic expected net return vector of shape (M,).
    cov_ann : np.ndarray
        Annualized return covariance matrix of shape (M, M).
    years : float
        Holding horizon n in years (n >= 0).
    discrete_log_matching : bool, default=False
        If True, use discrete-to-log matched covariance Sigma_g. If False, use cov_ann directly.

    Returns
    -------
    mean_ratio : float
        Normalized expected terminal wealth E[W_n/W_0].
    var_ratio : float
        Normalized variance of terminal wealth Var(W_n/W_0).
    """
    w = np.asarray(weights, dtype=np.float64)
    mu = np.asarray(mu_arith, dtype=np.float64)
    cov = np.asarray(cov_ann, dtype=np.float64)

    if w.ndim != 1 or mu.ndim != 1 or cov.ndim != 2:
        raise ValueError("Inconsistent array dimensions for accumulating wealth moments")
    m = len(w)
    if len(mu) != m or cov.shape != (m, m):
        raise ValueError(f"Shape mismatch: weights ({m},), mu ({len(mu)},), cov {cov.shape}")

    n = float(years)
    if n <= 0.0:
        return 1.0, 0.0

    # e_n[j] = (1 + mu_j)^n
    e_n = (1.0 + mu) ** n
    mean_ratio = float(np.sum(w * e_n))

    if discrete_log_matching:
        denom = np.outer(1.0 + mu, 1.0 + mu)
        cov_eff = np.log(1.0 + cov / denom)
    else:
        cov_eff = cov

    # Bilinear second moment: K_n[j, k] = e_n[j] * e_n[k] * exp(n * cov_eff[j, k])
    k_n = np.outer(e_n, e_n) * np.exp(n * cov_eff)
    second_moment = float(w @ k_n @ w)
    var_ratio = max(0.0, second_moment - mean_ratio**2)

    return mean_ratio, var_ratio


def distributing_state_space_propagation(
    weights: np.ndarray,
    mu_arith: np.ndarray,
    cov_ann: np.ndarray,
    is_dist: np.ndarray,
    dist_yield: np.ndarray,
    r_cash: float,
    years: float,
    steps: int | None = None,
    periods_per_year: int = 1,
    discrete_log_matching: bool = False,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Propagate joint augmented state-space moments for distributing assets with segregated cash.

    Implements Section 5.2 (Equations 311-327):
    Tracks an (M+1)-dimensional state vector [X_1, ..., X_M, X_cash]^T where:
    - Retained risky asset values: X_{i, tau} = rho_i R_{i, tau}^tot X_{i, tau-1}
    - Segregated GBP cash pool: X_{cash, tau} = (1 + r_cash) X_{cash, tau-1}
                                            + sum_i delta_i R_{i, tau}^tot X_{i, tau-1}
    - rho_i = 1 - d_i * I(i in D), delta_i = d_i * I(i in D)
    - Expected transition matrix: m_tau = E[A_tau] m_{tau-1}
    - Second moment recurrence: M_tau = E[A_tau M_{tau-1} A_tau^T]

    Parameters
    ----------
    weights : np.ndarray
        Initial portfolio weights of shape (M,).
    mu_arith : np.ndarray
        Annualized arithmetic expected total return vector of shape (M,).
    cov_ann : np.ndarray
        Annualized covariance matrix of shape (M, M).
    is_dist : np.ndarray
        Boolean indicator array of shape (M,) identifying distributing assets.
    dist_yield : np.ndarray
        Annualized cash distribution yield d_j in [0, 1) of shape (M,).
    r_cash : float
        Annualized rate for segregated cash compounding (e.g. 0.0380 or 0.0425).
    years : float
        Horizon in years (used when steps is None).
    steps : int | None, default=None
        Explicit discrete step count. If provided, overrides years * periods_per_year.
    periods_per_year : int, default=1
        Compounding steps per year (1 for annual, 12 for monthly).
    discrete_log_matching : bool, default=False
        If True, use discrete-to-log matched covariance.

    Returns
    -------
    mean_wealth : float
        Expected terminal normalized wealth E[W_n/W_0] combining assets and segregated cash.
    var_wealth : float
        Normalized variance of terminal wealth Var(W_n/W_0).
    m_n : np.ndarray
        Terminal state first-moment vector of shape (M+1,).
    M_n : np.ndarray
        Terminal state second-moment matrix of shape (M+1, M+1).
    """
    w = np.asarray(weights, dtype=np.float64)
    mu = np.asarray(mu_arith, dtype=np.float64)
    cov = np.asarray(cov_ann, dtype=np.float64)
    dist_flag = np.asarray(is_dist, dtype=bool)
    d_yield = np.asarray(dist_yield, dtype=np.float64)

    m_assets = len(w)
    if len(mu) != m_assets or cov.shape != (m_assets, m_assets):
        raise ValueError("Inconsistent dimensions in distributing state space propagation")

    if steps is not None:
        n_steps = int(steps)
    else:
        n_steps = int(round(float(years) * periods_per_year))

    if n_steps <= 0:
        m_0 = np.zeros(m_assets + 1, dtype=np.float64)
        m_0[:m_assets] = w
        return 1.0, 0.0, m_0, np.outer(m_0, m_0)

    # Per-step scaling
    dt = 1.0 / float(periods_per_year)
    if periods_per_year == 1:
        mu_step = mu
        cov_step = cov
        d_step = d_yield
        r_step = float(r_cash)
    else:
        mu_step = (1.0 + mu) ** dt - 1.0
        cov_step = cov * dt
        d_step = d_yield * dt
        r_step = (1.0 + float(r_cash)) ** dt - 1.0

    # Initial (M+1) state vector and second moment matrix
    m_0 = np.zeros(m_assets + 1, dtype=np.float64)
    m_0[:m_assets] = w
    m_t = m_0.copy()
    m_mat = np.outer(m_0, m_0)

    # Factor definitions: rho_i and delta_i
    rho = np.where(dist_flag, 1.0 - d_step, 1.0)
    delta = np.where(dist_flag, d_step, 0.0)

    # Expected step returns e_1 and second cross-moment factors K_1
    e_1 = 1.0 + mu_step
    if discrete_log_matching:
        denom = np.outer(1.0 + mu_step, 1.0 + mu_step)
        cov_eff = np.log(1.0 + cov_step / denom)
    else:
        cov_eff = cov_step

    k_1 = np.outer(e_1, e_1) * np.exp(cov_eff)

    # Expected transition matrix A_bar
    a_bar = np.zeros((m_assets + 1, m_assets + 1), dtype=np.float64)
    for i in range(m_assets):
        a_bar[i, i] = rho[i] * e_1[i]
        a_bar[m_assets, i] = delta[i] * e_1[i]
    a_bar[m_assets, m_assets] = 1.0 + r_step

    # Recurrence update over n_steps
    for _ in range(n_steps):
        # 1. First moment state update: m_t = A_bar @ m_t
        m_t = a_bar @ m_t

        # 2. Second moment matrix update: M_t = E[A_tau M_{tau-1} A_tau^T]
        m_next = np.zeros((m_assets + 1, m_assets + 1), dtype=np.float64)

        # Block 1: 1 <= i, j <= M
        m_next[:m_assets, :m_assets] = np.outer(rho, rho) * k_1 * m_mat[:m_assets, :m_assets]

        # Block 2: 1 <= i <= M, j = M+1
        cross_sum = (k_1 * m_mat[:m_assets, :m_assets]) @ delta
        val_cross = rho * (1.0 + r_step) * e_1 * m_mat[:m_assets, m_assets] + rho * cross_sum
        m_next[:m_assets, m_assets] = val_cross
        m_next[m_assets, :m_assets] = val_cross

        # Block 3: (M+1, M+1)
        term1 = ((1.0 + r_step) ** 2) * m_mat[m_assets, m_assets]
        term2 = 2.0 * (1.0 + r_step) * float(np.sum(delta * e_1 * m_mat[:m_assets, m_assets]))
        term3 = float(delta @ (k_1 * m_mat[:m_assets, :m_assets]) @ delta)
        m_next[m_assets, m_assets] = term1 + term2 + term3

        m_mat = m_next

    mean_wealth = float(np.sum(m_t))
    second_moment_wealth = float(np.sum(m_mat))
    var_wealth = max(0.0, second_moment_wealth - mean_wealth**2)

    return mean_wealth, var_wealth, m_t, m_mat


def lognormal_wealth_quantiles(
    mean_ratio: float,
    var_ratio: float,
    param_uncertainty: tuple[float, float] | float | None = None,
    horizon_years: float = 1.0,
    quantiles: Sequence[float] = (0.20, 0.15865, 0.50, 0.84135),
) -> dict[float, float]:
    """Match lognormal parameters and evaluate wealth quantiles with epistemic uncertainty.

    Implements Section 5.3 (Equations 332-345):
    - v_aleatoric^2 = ln(1 + var_ratio / mean_ratio^2)
    - m_n = ln(mean_ratio) - 0.5 * v_aleatoric^2
    - v_total^2 = v_aleatoric^2 + n * C_w + n^2 * U_w
    - Q(p) = exp(m_n + z_p * sqrt(v_total^2))

    Parameters
    ----------
    mean_ratio : float
        Normalized expected wealth E[W_n/W_0] (> 0).
    var_ratio : float
        Normalized wealth variance Var(W_n/W_0) (>= 0).
    param_uncertainty : tuple[float, float] | float | None, default=None
        Epistemic parameter uncertainty (C_w, U_w) as scalars. If None, (0.0, 0.0) is used.
    horizon_years : float, default=1.0
        Horizon n in years (n >= 0).
    quantiles : Sequence[float], default=(0.20, 0.15865, 0.50, 0.84135)
        Probability levels p in (0, 1).

    Returns
    -------
    quantile_dict : dict[float, float]
        Mapping from probability p to normalized wealth quantile Q_p.
    """
    mu_w = float(mean_ratio)
    if mu_w <= 0.0:
        raise ValueError(f"mean_ratio must be positive, got {mu_w}")

    sigma_sq = max(0.0, float(var_ratio))

    # Parse epistemic uncertainty terms
    if param_uncertainty is None:
        c_w, u_w = 0.0, 0.0
    elif isinstance(param_uncertainty, (int, float)):
        c_w, u_w = float(param_uncertainty), 0.0
    elif isinstance(param_uncertainty, (tuple, list)):
        c_w = float(param_uncertainty[0])
        u_w = float(param_uncertainty[1]) if len(param_uncertainty) > 1 else 0.0
    else:
        c_w, u_w = 0.0, 0.0

    # Lognormal moment matching
    v_aleatoric_sq = np.log1p(sigma_sq / (mu_w**2))
    m_n = np.log(mu_w) - 0.5 * v_aleatoric_sq

    n = max(0.0, float(horizon_years))
    v_total_sq = max(0.0, v_aleatoric_sq + n * c_w + (n**2) * u_w)
    v_total = np.sqrt(v_total_sq)

    results: dict[float, float] = {}
    for p in quantiles:
        p_val = float(p)
        if not (0.0 < p_val < 1.0):
            raise ValueError(f"Quantile probability must be in (0, 1), got {p_val}")

        # Exact canonical standard normal values for critical reporting quantiles
        if abs(p_val - 0.15865) < 1e-4:
            z_p = -1.0
        elif abs(p_val - 0.84135) < 1e-4:
            z_p = +1.0
        elif abs(p_val - 0.20) < 1e-4:
            z_p = -0.8416212335729143
        elif abs(p_val - 0.50) < 1e-4:
            z_p = 0.0
        else:
            z_p = float(stats.norm.ppf(p_val))

        q_val = float(np.exp(m_n + z_p * v_total))
        results[p_val] = q_val

    return results


def find_band_intersection_time(
    mu_g_A: float,
    sigma_A: float,
    mu_g_B: float,
    sigma_B: float,
    z_A: float = 1.0,
    z_B: float = 1.0,
    max_years: float = 100.0,
    C_A: float = 0.0,
    U_A: float = 0.0,
    C_B: float = 0.0,
    U_B: float = 0.0,
) -> float | None:
    """Find continuous-time crossover horizon t* where lower_A(t*) = upper_B(t*).

    Implements Section 5.4 (Equations 361-378):
    f_A,B(t) = [m_A(t) - z_A * v_A(t)] - [m_B(t) + z_B * v_B(t)]
    where m(t) = mu_g * t, v(t) = sqrt(sigma^2 * t + C * t + U * t^2).

    Searches across diagnostic grid {0.25, 0.5, 1, 2, 5, 10, 15, 20, 30, 50, 100}
    and executes scipy.optimize.brentq on the sign-change bracket.

    Returns
    -------
    t_star : float | None
        Crossover horizon in years, or None if bands do not intersect within max_years.
    """
    def f_gap(t: float) -> float:
        t_val = max(1e-12, float(t))
        m_a = float(mu_g_A) * t_val
        v_a = np.sqrt(max(0.0, float(sigma_A)**2 * t_val + float(C_A) * t_val + float(U_A) * t_val**2))
        m_b = float(mu_g_B) * t_val
        v_b = np.sqrt(max(0.0, float(sigma_B)**2 * t_val + float(C_B) * t_val + float(U_B) * t_val**2))
        return (m_a - float(z_A) * v_a) - (m_b + float(z_B) * v_b)

    raw_grid = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0]
    grid = sorted({g for g in raw_grid if g <= max_years} | {max_years})

    # Check immediate non-negative gap at lowest grid point
    if f_gap(grid[0]) >= 0.0:
        if f_gap(1e-4) < 0.0:
            return float(opt.brentq(f_gap, 1e-4, grid[0], xtol=1e-8, rtol=1e-12))
        return 0.0

    # Search for first sign flip across diagnostic brackets
    for i in range(len(grid) - 1):
        t_left, t_right = grid[i], grid[i + 1]
        if f_gap(t_left) < 0.0 <= f_gap(t_right):
            root = opt.brentq(f_gap, t_left, t_right, xtol=1e-8, rtol=1e-12)
            return float(root)

    return None


__all__ = [
    "accumulating_wealth_moments",
    "distributing_state_space_propagation",
    "lognormal_wealth_quantiles",
    "find_band_intersection_time",
]
