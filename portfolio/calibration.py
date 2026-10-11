from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from portfolio.bundle import FACTORS
from portfolio.risk import factor_covariance, shrunk_covariance


@dataclass
class Calibration:
    betas: pd.DataFrame
    diagnostics: pd.DataFrame
    covariance: np.ndarray
    direct_covariance: np.ndarray
    joint_shrinkage: float
    sample_start: str
    sample_end: str
    months: int


def fit_ff5(returns: pd.DataFrame, factors: pd.DataFrame, cash: pd.Series) -> Calibration:
    if len(returns) < 72 or not returns.index.isin(factors.index).all() or not returns.index.isin(cash.index).all():
        raise ValueError("FF5 calibration needs at least 60 training months and 12 holdout months.")
    x = factors.loc[returns.index, FACTORS].to_numpy()
    y = returns.sub(cash.loc[returns.index], axis=0).to_numpy()
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (x.std(axis=0) <= 1e-12).any():
        raise ValueError("FF5 calibration needs finite data and varying factor series.")
    train = len(x) - 12
    splits = TimeSeriesSplit(n_splits=min(5, (train - 36) // 12), test_size=12)
    betas, residuals, diagnostics = [], [], []
    for j, name in enumerate(returns.columns):
        search = GridSearchCV(make_pipeline(StandardScaler(), Ridge()),
                              {"ridge__alpha": [0.0, 0.1, 1.0, 10.0, 100.0]},
                              cv=splits, scoring="neg_mean_squared_error", n_jobs=1)
        search.fit(x[:train], y[:train, j])
        holdout = y[train:, j]
        errors = holdout - search.predict(x[train:])
        market = Ridge(alpha=0).fit(x[:train, :1], y[:train, j])
        market_errors = holdout - market.predict(x[train:, :1])
        ols = Ridge(alpha=0).fit(x[:train], y[:train, j])
        ols_errors = holdout - ols.predict(x[train:])
        denominator = np.sum((holdout - y[:train, j].mean()) ** 2)
        alpha = float(search.best_params_["ridge__alpha"])

        # Assess the untouched holdout first, then refit the chosen specification for current exposures.
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(x, y[:, j])
        scaler, ridge = model.named_steps["standardscaler"], model.named_steps["ridge"]
        beta = ridge.coef_ / scaler.scale_
        intercept = float(ridge.intercept_ - beta @ scaler.mean_)
        residuals.append(y[:, j] - model.predict(x))
        betas.append(beta)
        rmse = float(np.sqrt(np.mean(errors**2)))
        market_rmse = float(np.sqrt(np.mean(market_errors**2)))
        diagnostics.append({"ETF_ID": name, "ridge_penalty": alpha, "fitted_net_alpha_monthly": intercept,
                            "holdout_rmse": rmse, "market_only_rmse": market_rmse,
                            "ols_ff5_rmse": float(np.sqrt(np.mean(ols_errors**2))),
                            "holdout_r2_vs_training_mean": 1 - float(errors @ errors) / denominator if denominator > 0 else None,
                            "review_flag": "FF5 did not improve on market-only" if rmse > market_rmse else "Review fit and input evidence"})
    betas = np.asarray(betas)
    covariance, shrinkage = factor_covariance(x, betas, np.column_stack(residuals))
    direct, _ = shrunk_covariance(y)
    return Calibration(pd.DataFrame(betas, index=returns.columns, columns=FACTORS),
                       pd.DataFrame(diagnostics).set_index("ETF_ID"), covariance, direct, shrinkage,
                       str(returns.index[0]), str(returns.index[-1]), len(returns))


def expected_returns(betas, premiums_monthly, cash_monthly, annual_fees):
    b, p, fees = map(np.asarray, (betas, premiums_monthly, annual_fees))
    if b.ndim != 2 or p.shape != (b.shape[1],) or fees.shape != (b.shape[0],):
        raise ValueError("Betas, premiums and fees have inconsistent dimensions.")
    if not all(np.isfinite(x).all() for x in (b, p, fees)) or not np.isfinite(cash_monthly):
        raise ValueError("Return assumptions must be finite.")
    if (fees < 0).any():
        raise ValueError("Fees cannot be negative.")
    # This starts with a gross factor forecast. Historical net means and fitted alpha are not added.
    return cash_monthly + b @ p - fees / 12
