import numpy as np
from sklearn.covariance import LedoitWolf


def shrunk_covariance(observations: np.ndarray) -> tuple[np.ndarray, float]:
    x = np.asarray(observations, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("Covariance needs a finite observations-by-assets matrix.")
    # An identity shrinkage target must not give two copies of one series independent risk.
    unique, inverse = np.unique(x.T, axis=0, return_inverse=True)
    fit = LedoitWolf().fit(unique.T)
    return fit.covariance_[np.ix_(inverse, inverse)], float(fit.shrinkage_)


def portfolio_metrics(weights, mean, covariance):
    w, mu, cov = map(np.asarray, (weights, mean, covariance))
    variance = float(w @ cov @ w)
    volatility = np.sqrt(max(variance, 0.0))
    contributions = w * (cov @ w) / volatility if volatility > 0 else np.zeros_like(w)
    return float(w @ mu), float(volatility), contributions


def factor_covariance(factors, betas, residuals):
    factors, betas, residuals = map(np.asarray, (factors, betas, residuals))
    joint, shrinkage = shrunk_covariance(np.column_stack([factors, residuals]))
    transform = np.column_stack([betas, np.eye(len(betas))])
    covariance = transform @ joint @ transform.T
    return (covariance + covariance.T) / 2, shrinkage
