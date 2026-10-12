"""Regional specification selection with an untouched final assessment year."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class EquityFit:
    betas: pd.Series
    diagnostic: dict
    residuals: pd.Series
    specification: str
    penalty: float


def fit_equity(returns, factors, cash, specifications):
    common = returns.dropna().index.intersection(factors.dropna().index).intersection(cash.dropna().index)
    common = common[-120:]
    if len(common) < 72 or not common.equals(pd.period_range(common[0], common[-1], freq='M')):
        raise ValueError('Equity fit requires 72 actual contiguous compatible months, preferably 120.')
    y = returns.loc[common].to_numpy() - cash.loc[common].to_numpy()
    f = factors.loc[common]
    if not np.isfinite(y).all() or not np.isfinite(f.to_numpy()).all():
        raise ValueError('Nonfinite regression observations.')
    train = len(common) - 12
    folds = [(end, min(end + 12, train)) for end in range(36, train, 12) if end + 12 <= train]
    candidates = []
    for label, columns in specifications.items():
        x = f[columns].to_numpy()
        if (x.std(axis=0) <= 1e-12).any():
            raise ValueError('Factor series must vary.')
        penalties = [0.0] if label.endswith('market') or label.endswith('ols') else [0.0, 0.1, 1.0, 10.0, 100.0]
        for penalty in penalties:
            errors = []
            for end, stop in folds:
                model = make_pipeline(StandardScaler(), Ridge(alpha=penalty)).fit(x[:end], y[:end])
                errors.extend(y[end:stop] - model.predict(x[end:stop]))
            candidates.append((float(np.mean(np.square(errors))), label, penalty, columns))
    score, label, penalty, columns = min(candidates, key=lambda v: (v[0], v[1], v[2]))
    x = f[columns].to_numpy()
    trained = make_pipeline(StandardScaler(), Ridge(alpha=penalty)).fit(x[:train], y[:train])
    holdout_rmse = float(np.sqrt(np.mean((y[train:] - trained.predict(x[train:]))**2)))
    final = make_pipeline(StandardScaler(), Ridge(alpha=penalty)).fit(x, y)
    scaler, ridge = final.named_steps['standardscaler'], final.named_steps['ridge']
    beta = ridge.coef_ / scaler.scale_
    old_beta = trained.named_steps['ridge'].coef_ / trained.named_steps['standardscaler'].scale_
    residuals = pd.Series(y - final.predict(x), index=common)
    holdout_comparisons = {}
    for specification in specifications:
        candidate = min((c for c in candidates if c[1] == specification), key=lambda c: (c[0], c[2]))
        candidate_x = f[candidate[3]].to_numpy()
        assessed = make_pipeline(StandardScaler(), Ridge(alpha=candidate[2])).fit(candidate_x[:train], y[:train])
        holdout_comparisons[specification] = {
            'validation_selected_penalty': candidate[2],
            'holdout_rmse': float(np.sqrt(np.mean((y[train:] - assessed.predict(candidate_x[train:]))**2)))}
    diagnostic = dict(specification=label, ridge_penalty=penalty, validation_rmse=np.sqrt(score),
                      holdout_rmse=holdout_rmse, holdout_start=str(common[-12]),
                      fitted_net_alpha_monthly=float(ridge.intercept_ - beta @ scaler.mean_),
                      residual_annual_volatility=float(residuals.std(ddof=1) * np.sqrt(12)),
                      beta_change_l2=float(np.linalg.norm(beta - old_beta)),
                      holdout_comparisons=holdout_comparisons,
                      start=str(common[0]), end=str(common[-1]), months=len(common),
                      candidates=[{'specification': c[1], 'penalty': c[2], 'validation_rmse': np.sqrt(c[0])} for c in candidates])
    return EquityFit(pd.Series(beta, index=columns), diagnostic, residuals, label, penalty)


def specifications_for(regions, momentum_columns=()):
    columns = [region + ':' + factor for region in regions for factor in ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']]
    market = [c for c in columns if c.endswith(':Mkt-RF')]
    result = {'market': market, 'ff5_ols': columns, 'ff5_ridge': columns}
    if len(regions) > 1:
        result['developed_only_ridge'] = [c for c in columns if c.startswith('Developed:')]
    if momentum_columns:
        result['ff5_mom_ridge'] = columns + list(momentum_columns)
    return result
