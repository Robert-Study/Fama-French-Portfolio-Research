"""Synchronised moving-block uncertainty and explicit normal-prior shrinkage."""
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Premiums:
    estimates: pd.Series
    unshrunk: pd.Series
    sampling_covariance: np.ndarray
    posterior_covariance: np.ndarray
    bootstrap_means: np.ndarray
    prior_scales: np.ndarray
    regularisation: float


def block_indices(length, months, paths, block, rng):
    if min(length, months, paths, block) < 1 or block > length:
        raise ValueError('Invalid block-bootstrap dimensions.')
    starts = rng.integers(0, length - block + 1, (paths, int(np.ceil(months / block))))
    return (starts[..., None] + np.arange(block)).reshape(paths, -1)[:, :months]


def shrink(mean, sampling, scales):
    prior = np.diag(np.square(scales))
    # Equivalent to posterior precision formula, avoiding explicit inversion of V.
    regularisation = max(float(np.trace(sampling)) / len(mean) * 1e-10, 1e-14)
    sampling = sampling + np.eye(len(mean)) * regularisation
    gain = np.linalg.solve((sampling + prior).T, prior.T).T
    posterior = prior - gain @ prior
    return gain @ mean, (posterior + posterior.T) / 2, regularisation


def estimate_premiums(factors, block=12, paths=2000, seed=212, prior_multiplier=1.0):
    x = factors.to_numpy(float)
    if len(x) < 72 or not np.isfinite(x).all() or prior_multiplier <= 0:
        raise ValueError('At least 72 finite compatible published months required.')
    rng = np.random.default_rng(seed)
    indices = block_indices(len(x), len(x), paths, block, rng)
    # Batch means avoid a paths × history × regions array in memory.
    draws = np.vstack([x[ix].mean(axis=1) * 12 for ix in np.array_split(indices, max(1, paths // 100))])
    sampling = np.atleast_2d(np.cov(draws, rowvar=False, ddof=1))
    mean = x.mean(axis=0) * 12
    scales = np.array([0.05 if c.endswith(':Mkt-RF') else 0.02 for c in factors.columns]) * prior_multiplier
    estimates, posterior, regularisation = shrink(mean, sampling, scales)
    return Premiums(pd.Series(estimates, index=factors.columns), pd.Series(mean, index=factors.columns),
                    sampling, posterior, draws, scales, regularisation)


def premium_sensitivities(premiums):
    result = {'central': premiums.estimates, 'unshrunk': premiums.unshrunk}
    for scale in (0.5, 2.0):
        value, _, _ = shrink(premiums.unshrunk.to_numpy(), premiums.sampling_covariance, premiums.prior_scales * scale)
        result[f'prior_{scale:g}x'] = pd.Series(value, index=premiums.estimates.index)
    result['zero_styles'] = premiums.estimates.where(premiums.estimates.index.str.endswith(':Mkt-RF'), 0)
    for shift in (-0.02, 0.02):
        result[f'market_{shift:+g}'] = premiums.estimates + np.where(premiums.estimates.index.str.endswith(':Mkt-RF'), shift, 0)
    return pd.DataFrame(result)
