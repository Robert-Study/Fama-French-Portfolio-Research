"""Portfolio Construction Lab V8: Holdings-Informed Factor Calibration.

Authoritative implementation of Stage 04 Mathematical Specification (Section 2).
Implements bottom-up constituent characteristics Winsorization, cap-weighted
standardization, two-stage cross-sectional ridge mapping, three-tier hierarchical
shrinkage, benchmark-neutral centering, and exact net return reconciliation.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import scipy.sparse as sp


def winsorize_and_standardize_characteristics(
    raw_x: np.ndarray,
    mcap_weights: np.ndarray,
    p_low: float = 0.01,
    p_high: float = 0.99,
    return_moments: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Winsorize raw characteristics at regional percentiles and standardize by market capitalization.

    Implements Section 2.1:
    1. Unweighted empirical percentile clipping:
       x_clip = min(P_99, max(P_1, x_raw))
    2. Free-float capitalization-weighted mean and variance:
       mu_k = sum(v_i * x_clip_i), sigma_k = sqrt(sum(v_i * (x_clip_i - mu_k)^2))
    3. Standardization:
       z_i,k = (x_clip_i,k - mu_k) / sigma_k

    Parameters
    ----------
    raw_x : np.ndarray
        Array of shape (N, K) or (N,) containing raw characteristics.
    mcap_weights : np.ndarray
        Array of shape (N,) containing non-negative market capitalizations or weights.
    p_low : float, default=0.01
        Lower unweighted percentile for clipping (e.g. 0.01 for 1st percentile).
    p_high : float, default=0.99
        Upper unweighted percentile for clipping (e.g. 0.99 for 99th percentile).
    return_moments : bool, default=False
        If True, return tuple of (z_std, mu_cap, sigma_cap). Otherwise return z_std.

    Returns
    -------
    z_std : np.ndarray
        Standardized characteristics with zero cap-weighted mean and unit variance.
    mu_cap : np.ndarray, optional
        Cap-weighted mean vector (if return_moments=True).
    sigma_cap : np.ndarray, optional
        Cap-weighted standard deviation vector (if return_moments=True).
    """
    x_arr = np.asarray(raw_x, dtype=np.float64)
    w_arr = np.asarray(mcap_weights, dtype=np.float64)

    is_1d = x_arr.ndim == 1
    if is_1d:
        x_2d = x_arr[:, np.newaxis]
    elif x_arr.ndim == 2:
        x_2d = x_arr
    else:
        raise ValueError(f"raw_x must be 1D or 2D array, got shape {x_arr.shape}")

    n_obs, _ = x_2d.shape
    if w_arr.ndim != 1 or len(w_arr) != n_obs:
        raise ValueError(f"mcap_weights must be 1D array of length {n_obs}, got shape {w_arr.shape}")

    if not (0.0 <= p_low < p_high <= 1.0):
        raise ValueError(f"Percentile bounds must satisfy 0 <= p_low < p_high <= 1, got ({p_low}, {p_high})")

    sum_w = float(np.sum(w_arr))
    if sum_w <= 0.0 or not np.isfinite(sum_w):
        raise ValueError("Sum of mcap_weights must be positive and finite")
    v = w_arr / sum_w

    # 1. Unweighted regional empirical percentiles
    p_low_val = np.percentile(x_2d, p_low * 100.0, axis=0)
    p_high_val = np.percentile(x_2d, p_high * 100.0, axis=0)
    x_clip = np.clip(x_2d, p_low_val, p_high_val)

    # 2. Cap-weighted mean and variance
    mu_cap = np.sum(v[:, np.newaxis] * x_clip, axis=0)
    dev = x_clip - mu_cap
    var_cap = np.sum(v[:, np.newaxis] * (dev**2), axis=0)
    sigma_cap = np.sqrt(np.maximum(var_cap, 0.0))

    # 3. Standardization with zero-division safeguard
    with np.errstate(divide="ignore", invalid="ignore"):
        z_std = np.where(sigma_cap > 1e-12, dev / sigma_cap, 0.0)

    if is_1d:
        z_out = z_std.squeeze(axis=-1)
        mu_out = mu_cap.squeeze(axis=-1)
        sigma_out = sigma_cap.squeeze(axis=-1)
    else:
        z_out = z_std
        mu_out = mu_cap
        sigma_out = sigma_cap

    if return_moments:
        return z_out, mu_out, sigma_out
    return z_out


def estimate_ridge_characteristic_mapping(
    Z_ext: np.ndarray,
    B_ts: np.ndarray,
    W_ts: np.ndarray | None = None,
    lambda_ridge: float = 1.0,
    anchor_gamma: np.ndarray | None = None,
    cond_threshold: float = 1e4,
    min_obs_threshold: int = 150,
    blend_obs_threshold: int = 500,
) -> np.ndarray:
    """Estimate two-stage cross-sectional ridge mapping from characteristics to factor betas.

    Solves the penalized normal equations with unpenalized intercept (Section 2.2):
    Gamma = (Z_ext^T W Z_ext + lambda_ridge * I_pen)^(-1) Z_ext^T W B_ts
    where I_pen = diag(0, 1, 1, 1, 1, 1).

    Applies the Characteristic-Sorted Portfolio Anchor Fallback and smooth convex
    blending when sample size N < 500 or condition number kappa > 1e4 (Section 2.3).

    Parameters
    ----------
    Z_ext : np.ndarray
        Design matrix of shape (N, D) where column 0 is ones (intercept).
    B_ts : np.ndarray
        Response matrix of shape (N, K) containing time-series factor loadings.
    W_ts : np.ndarray | None, default=None
        Precision weights of shape (N,) or (N, N). If None, uniform weights are applied.
    lambda_ridge : float, default=1.0
        Ridge shrinkage hyperparameter lambda >= 0.
    anchor_gamma : np.ndarray | None, default=None
        Portfolio anchor mapping matrix of shape (D, K) for ill-conditioned fallbacks.
    cond_threshold : float, default=1e4
        Condition number threshold triggering portfolio anchor fallback.
    min_obs_threshold : int, default=150
        Sample count below which pure anchor mapping is used.
    blend_obs_threshold : int, default=500
        Sample count above which pure single-stock ridge mapping is used.

    Returns
    -------
    Gamma : np.ndarray
        Cross-sectional mapping matrix of shape (D, K).
    """
    z_mat = np.asarray(Z_ext, dtype=np.float64)
    b_mat = np.asarray(B_ts, dtype=np.float64)
    n_obs, d_feat = z_mat.shape

    is_1d_b = b_mat.ndim == 1
    if is_1d_b:
        b_mat = b_mat[:, np.newaxis]

    if b_mat.shape[0] != n_obs:
        raise ValueError(f"B_ts rows ({b_mat.shape[0]}) must match Z_ext rows ({n_obs})")

    if lambda_ridge < 0.0:
        raise ValueError(f"lambda_ridge must be non-negative, got {lambda_ridge}")

    # Build penalty matrix I_pen leaving intercept at [0, 0] unpenalized
    i_pen = np.eye(d_feat, dtype=np.float64)
    i_pen[0, 0] = 0.0

    # Weighting normal equations
    if W_ts is None:
        a_mat = z_mat.T @ z_mat
        r_mat = z_mat.T @ b_mat
    elif W_ts.ndim == 1:
        if len(W_ts) != n_obs:
            raise ValueError(f"W_ts length ({len(W_ts)}) must match N ({n_obs})")
        w_diag = W_ts[:, np.newaxis]
        zw = z_mat.T * w_diag.T
        a_mat = zw @ z_mat
        r_mat = zw @ b_mat
    elif W_ts.ndim == 2:
        if W_ts.shape != (n_obs, n_obs):
            raise ValueError(f"W_ts shape {W_ts.shape} must be ({n_obs}, {n_obs})")
        zw = z_mat.T @ W_ts
        a_mat = zw @ z_mat
        r_mat = zw @ b_mat
    else:
        raise ValueError(f"W_ts must be 1D or 2D array, got {W_ts.shape}")

    # Condition number check on unpenalized cross-product
    kappa = float(np.linalg.cond(a_mat))

    # Regularized normal equations
    a_reg = a_mat + lambda_ridge * i_pen
    gamma_est = np.linalg.solve(a_reg, r_mat)

    # Anchor fallback and blending (Section 2.3)
    if anchor_gamma is not None:
        anchor_mat = np.asarray(anchor_gamma, dtype=np.float64)
        if anchor_mat.shape != gamma_est.shape:
            raise ValueError(f"anchor_gamma shape {anchor_mat.shape} must match Gamma {gamma_est.shape}")

        if kappa > cond_threshold or n_obs < min_obs_threshold:
            gamma_est = anchor_mat.copy()
        elif n_obs < blend_obs_threshold:
            theta = float(n_obs - min_obs_threshold) / float(blend_obs_threshold - min_obs_threshold)
            gamma_est = theta * gamma_est + (1.0 - theta) * anchor_mat

    if is_1d_b:
        return gamma_est.squeeze(axis=-1)
    return gamma_est


def three_tier_shrinkage_cascade(
    beta_comp: np.ndarray,
    beta_peer: np.ndarray,
    beta_prior: np.ndarray,
    c_i: float,
    T_i: float,
    N_peer: int,
    kappa_comp: float = 24.0,
    kappa_peer: float = 30.0,
) -> np.ndarray:
    """Evaluate three-tier Empirical Bayes shrinkage cascade for company factor loadings.

    Implements Section 2.4:
    alpha_i = (c_i * T_i) / (T_i + kappa_comp)
    eta_peer = (N_peer / (N_peer + kappa_peer)) if N_peer >= 30 else 0.0
    beta_shrunk = alpha_i * beta_comp + (1 - alpha_i) * [eta_peer * beta_peer + (1 - eta_peer) * beta_prior]

    Parameters
    ----------
    beta_comp : np.ndarray
        Tier 1 company loading vector, shape (K,).
    beta_peer : np.ndarray
        Tier 2 peer-group characteristic-implied loading vector, shape (K,).
    beta_prior : np.ndarray
        Tier 3 regional equilibrium prior vector (e.g. [1, 0, 0, 0, 0, 0]), shape (K,).
    c_i : float
        Characteristic completeness in [0, 1].
    T_i : float
        Trailing return history length in months (T_i >= 0).
    N_peer : int
        Peer group company count. Must be >= 30 to activate peer-group shrinkage.
    kappa_comp : float, default=24.0
        Company half-saturation constant in months.
    kappa_peer : float, default=30.0
        Peer-group half-saturation constant in company count.

    Returns
    -------
    beta_shrunk : np.ndarray
        Composite shrunk factor loading vector of shape (K,).
    """
    b_comp = np.asarray(beta_comp, dtype=np.float64)
    b_peer = np.asarray(beta_peer, dtype=np.float64)
    b_prior = np.asarray(beta_prior, dtype=np.float64)

    if b_comp.shape != b_peer.shape or b_comp.shape != b_prior.shape:
        raise ValueError(
            f"Beta vectors must share identical shapes, got {b_comp.shape}, {b_peer.shape}, {b_prior.shape}"
        )

    # 1. Company shrinkage weight alpha_i
    c_clamped = float(np.clip(c_i, 0.0, 1.0))
    t_clamped = max(0.0, float(T_i))
    if t_clamped + kappa_comp > 0.0:
        alpha_i = (c_clamped * t_clamped) / (t_clamped + kappa_comp)
    else:
        alpha_i = 0.0
    alpha_i = float(np.clip(alpha_i, 0.0, 1.0))

    # 2. Peer group shrinkage weight eta_peer (Minimum 30-Company Peer Group Rule)
    if N_peer >= 30 and (N_peer + kappa_peer) > 0.0:
        eta_peer = float(N_peer) / float(N_peer + kappa_peer)
    else:
        eta_peer = 0.0
    eta_peer = float(np.clip(eta_peer, 0.0, 1.0))

    # 3. Composite Empirical Bayes cascade
    peer_blend = eta_peer * b_peer + (1.0 - eta_peer) * b_prior
    beta_shrunk = alpha_i * b_comp + (1.0 - alpha_i) * peer_blend
    return beta_shrunk


def benchmark_neutral_centering(
    fund_betas: np.ndarray,
    benchmark_betas: np.ndarray,
) -> np.ndarray:
    """Center active fund factor exposures relative to designated benchmark index.

    Implements Section 2.5:
    - Market factor (index 0): Multiplicative centering around unity
      b_active[0] = b_fund[0] / b_bmk[0]
    - Style factors (indices >= 1): Subtractive centering
      b_active[k] = b_fund[k] - b_bmk[k]

    Guarantees that an exact benchmark replica satisfies b_active[0] == 1.0
    and b_active[k] == 0.0 across all non-market style factors.

    Parameters
    ----------
    fund_betas : np.ndarray
        Array of shape (K,) or (M, K) containing raw fund or portfolio factor loadings.
    benchmark_betas : np.ndarray
        Array of shape (K,) containing aggregated benchmark factor loadings.

    Returns
    -------
    active_betas : np.ndarray
        Active centered factor loadings, shape matching fund_betas.
    """
    f_betas = np.asarray(fund_betas, dtype=np.float64)
    bmk_betas = np.asarray(benchmark_betas, dtype=np.float64)

    if bmk_betas.ndim != 1:
        raise ValueError(f"benchmark_betas must be 1D array of shape (K,), got {bmk_betas.shape}")

    k_factors = len(bmk_betas)
    if bmk_betas[0] == 0.0:
        raise ValueError("Benchmark market beta (index 0) cannot be zero for multiplicative centering")

    if f_betas.ndim == 1:
        if len(f_betas) != k_factors:
            raise ValueError(f"fund_betas length ({len(f_betas)}) must match benchmark length ({k_factors})")
        b_act = np.zeros_like(f_betas)
        b_act[0] = f_betas[0] / bmk_betas[0]
        b_act[1:] = f_betas[1:] - bmk_betas[1:]
        return b_act

    if f_betas.ndim == 2:
        if f_betas.shape[1] != k_factors:
            raise ValueError(f"fund_betas columns ({f_betas.shape[1]}) must match benchmark length ({k_factors})")
        b_act = np.zeros_like(f_betas)
        b_act[:, 0] = f_betas[:, 0] / bmk_betas[0]
        b_act[:, 1:] = f_betas[:, 1:] - bmk_betas[1:]
        return b_act

    raise ValueError(f"fund_betas must be 1D or 2D array, got {f_betas.shape}")


def reconcile_net_return(
    gross_market_return: float,
    active_betas: np.ndarray,
    factor_premia: np.ndarray,
    r_f: float,
    ter: float,
    wht: float = 0.0,
    lending_credit: float = 0.0,
) -> float:
    """Calculate ETF net expected return enforcing exact fund-level accounting identity.

    Implements Section 2.6 (Equation 145):
    mu_net = r_f + b_act[MKT] * (mu_B_gross - r_f) + sum_{k>=2} (b_act[k] * lambda_k)
             - WHT - TER + delta_TD

    Parameters
    ----------
    gross_market_return : float
        Annualized gross expected return of the regional benchmark in GBP (mu_B_gross).
    active_betas : np.ndarray
        Centered factor loading vector of shape (K,), where index 0 is centered market beta.
    factor_premia : np.ndarray
        Annualized factor risk premia. Shape (K-1,) for style factors or (K,) including market ERP.
    r_f : float
        GBP risk-free cash reference rate.
    ter : float
        Fund Total Expense Ratio / Ongoing Charges Figure plus transaction drag.
    wht : float, default=0.0
        Dividend withholding tax drag.
    lending_credit : float, default=0.0
        Securities lending or swap enhancement credit (bounded at +0.0015 p.a.).

    Returns
    -------
    mu_net : float
        Annualized net expected arithmetic total return in GBP.
    """
    b_act = np.asarray(active_betas, dtype=np.float64)
    premia = np.asarray(factor_premia, dtype=np.float64)

    if b_act.ndim != 1:
        raise ValueError(f"active_betas must be 1D array of shape (K,), got {b_act.shape}")

    k_factors = len(b_act)
    if len(premia) == k_factors - 1:
        # premia contains style factors only
        style_contrib = float(np.sum(b_act[1:] * premia))
    elif len(premia) == k_factors:
        # premia contains all K factors; index 0 is market ERP
        style_contrib = float(np.sum(b_act[1:] * premia[1:]))
    else:
        raise ValueError(
            f"factor_premia length ({len(premia)}) must be either "
            f"{k_factors - 1} (style only) or {k_factors} (all factors)"
        )

    # Lending credit is bounded above by +0.15% (15 bps p.a.) as per Section 2.6
    capped_credit = min(max(0.0, float(lending_credit)), 0.0015)

    market_equity_risk_premium = float(gross_market_return) - float(r_f)
    gross_expected_return = float(r_f) + b_act[0] * market_equity_risk_premium + style_contrib
    net_expected_return = gross_expected_return - float(wht) - float(ter) + capped_credit
    return net_expected_return


def calculate_company_gross_returns(
    shrunk_betas: np.ndarray,
    benchmark_betas: np.ndarray,
    gross_market_return: float,
    factor_premia: np.ndarray,
    r_f: float,
) -> np.ndarray:
    """Calculate gross expected return for each constituent company (Equation 151).

    mu_company,i = r_f + (beta_i,MKT / b_bmk,MKT) * (mu_B_gross - r_f)
                   + sum_{k>=2} (beta_i,k - b_bmk,k) * lambda_k
    """
    betas_mat = np.asarray(shrunk_betas, dtype=np.float64)
    bmk = np.asarray(benchmark_betas, dtype=np.float64)
    premia = np.asarray(factor_premia, dtype=np.float64)

    if betas_mat.ndim == 1:
        betas_mat = betas_mat[np.newaxis, :]

    n_comp, k_factors = betas_mat.shape
    if len(bmk) != k_factors:
        raise ValueError(f"benchmark_betas length ({len(bmk)}) must match beta columns ({k_factors})")

    if len(premia) == k_factors - 1:
        style_premia = premia
    elif len(premia) == k_factors:
        style_premia = premia[1:]
    else:
        raise ValueError(f"factor_premia length mismatch: got {len(premia)}, expected {k_factors - 1} or {k_factors}")

    market_prem = float(gross_market_return) - float(r_f)
    mkt_term = (betas_mat[:, 0] / bmk[0]) * market_prem
    style_term = (betas_mat[:, 1:] - bmk[1:]) @ style_premia
    gross_returns = float(r_f) + mkt_term + style_term
    return gross_returns


__all__ = [
    "winsorize_and_standardize_characteristics",
    "estimate_ridge_characteristic_mapping",
    "three_tier_shrinkage_cascade",
    "benchmark_neutral_centering",
    "reconcile_net_return",
    "calculate_company_gross_returns",
]
