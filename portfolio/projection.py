import numpy as np
import pandas as pd
from scipy.stats import norm


def buy_and_hold_projection(weights, mean, covariance, investment=10000.0, years=20):
    """Exact first two moments under IID monthly simple returns; approximate wealth quantiles."""
    w, mu, cov = map(lambda x: np.asarray(x, dtype=float), (weights, mean, covariance))
    if mu.shape != w.shape or cov.shape != (len(w), len(w)):
        raise ValueError("Projection inputs have inconsistent dimensions.")
    if not all(np.isfinite(x).all() for x in (w, mu, cov)) or not np.isfinite(investment):
        raise ValueError("Projection inputs must be finite.")
    if (w < 0).any() or not np.isclose(w.sum(), 1) or investment <= 0 or not 1 <= years <= 40:
        raise ValueError("Use long-only weights summing to 100%, a positive investment and 1–40 years.")
    keep = w > 0
    w, mu, cov = w[keep], mu[keep], cov[np.ix_(keep, keep)]
    gross = 1 + mu
    paired = np.outer(gross, gross) + cov
    if (gross <= 0).any() or (paired <= 0).any():
        raise ValueError("These moments are inconsistent with positive gross wealth.")
    rows = []
    for year in range(years + 1):
        months = 12 * year
        expected = investment * float(w @ gross**months)
        second = investment**2 * float(w @ (paired**months) @ w)
        variance = second - expected**2
        if not np.isfinite(second) or variance < -1e-10 * expected**2:
            raise ValueError("Projection moments are unstable for these assumptions.")
        variance = max(variance, 0.0)
        log_variance = np.log1p(variance / expected**2)
        log_mean = np.log(expected) - log_variance / 2
        quantiles = np.exp(log_mean + norm.ppf([0.2, 0.5, 0.8]) * np.sqrt(log_variance))
        rows.append([year, expected, variance, *quantiles])
    return pd.DataFrame(rows, columns=["Year", "Expected wealth", "Variance", "P20", "Median", "P80"])
