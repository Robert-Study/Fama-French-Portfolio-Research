"""Shared market draws; arithmetic horizon averages and compounded outcomes differ."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from portfolio.premiums import block_indices
from portfolio.models.leveraged import daily_leverage

QUANTILES = [0.1587, 0.5, 0.8413]


@dataclass
class Scenarios:
    horizon_averages: np.ndarray
    selected_paths: np.ndarray | None
    seed: int
    years: int
    paths: int
    block: int
    estimation: str
    portfolio_averages: np.ndarray | None = None
    portfolio_weights: np.ndarray | None = None


def iid_band(annual_mean, annual_volatility, years):
    if years <= 0 or annual_volatility < 0:
        raise ValueError('Positive horizon and nonnegative annual volatility required.')
    width = annual_volatility / np.sqrt(years)
    return annual_mean - width, annual_mean + width


def monthly_scenarios(history, mean, years, paths=2000, block=12, seed=212,
                      mean_draws=None, selected_weights=None):
    x, mu = np.asarray(history, float), np.asarray(mean, float)
    if x.ndim != 2 or mu.shape != (x.shape[1],) or len(x) < block or not np.isfinite(x).all() or not np.isfinite(mu).all() or years not in (1, 5, 10, 20, 30):
        raise ValueError('Finite aligned history, forward means and supported horizon required.')
    rng = np.random.default_rng(seed)
    if mean_draws is None:
        # Never invent an estimation floor. The caller must supply jointly refitted draws.
        draws = np.broadcast_to(mu, (paths, len(mu)))
        estimation = 'Market-path uncertainty only; estimation draws unavailable'
    else:
        samples = np.asarray(mean_draws, float)
        if samples.ndim != 2 or samples.shape[1] != len(mu) or not np.isfinite(samples).all():
            raise ValueError('Joint bootstrap mean-return draws required.')
        draws = samples[rng.integers(0, len(samples), paths)]
        estimation = 'Joint bootstrap estimation draws fixed across each full horizon; no second posterior add-on'
    centered = x - x.mean(axis=0)
    months = 12 * years
    averages = np.empty((paths, len(mu)))
    weights = None if selected_weights is None else np.atleast_2d(selected_weights)
    selected = None if weights is None else np.empty((paths, months, len(weights)))
    for start in range(0, paths, 100):
        stop = min(paths, start + 100)
        ix = block_indices(len(x), months, stop - start, block, rng)
        batch = centered[ix] + draws[start:stop, None, :]
        if (batch < -1).any():
            raise ValueError('Additive forecast shift creates impossible returns; revise the path model.')
        averages[start:stop] = batch.mean(axis=1) * 12
        if weights is not None:
            selected[start:stop] = batch @ weights.T
    return Scenarios(averages, selected, seed, years, paths, block, estimation)


def horizon_quantiles(scenarios, weights):
    if scenarios.portfolio_averages is not None:
        if not np.array_equal(np.atleast_2d(weights), scenarios.portfolio_weights):
            raise ValueError('Termination-aware quantiles require the portfolios generated with these paths.')
        outcomes = scenarios.portfolio_averages
    else:
        outcomes = scenarios.horizon_averages @ np.atleast_2d(weights).T
    return np.quantile(outcomes, QUANTILES, axis=0).T


def compound_summary(monthly_paths, years):
    paths = np.asarray(monthly_paths)
    if paths.ndim == 2:
        paths = paths[..., None]
    if (paths < -1).any() or not np.isfinite(paths).all():
        raise ValueError('Invalid compounded-return paths.')
    wealth = np.concatenate([np.ones((len(paths), 1, paths.shape[-1])), np.cumprod(1 + paths, axis=1)], axis=1)
    terminal = wealth[:, -1]
    cagr = terminal**(1 / years) - 1
    peak = np.maximum.accumulate(wealth, axis=1)
    dd = (wealth / peak - 1).min(axis=1)
    return pd.DataFrame({'CAGR P15.87': np.quantile(cagr, .1587, axis=0),
                         'Median CAGR': np.median(cagr, axis=0), 'CAGR P84.13': np.quantile(cagr, .8413, axis=0),
                         'Terminal 100 P15.87': np.quantile(terminal * 100, .1587, axis=0),
                         'Terminal 100 median': np.median(terminal * 100, axis=0),
                         'Terminal 100 P84.13': np.quantile(terminal * 100, .8413, axis=0),
                         'Probability of loss': (terminal < 1).mean(axis=0),
                         'Drawdown P5': np.quantile(dd, .05, axis=0)})


def historical_replay(returns, weights):
    monthly = returns.to_numpy() @ np.atleast_2d(weights).T
    wealth = np.vstack([np.ones(monthly.shape[1]), np.cumprod(1 + monthly, axis=0)]) * 100
    drawdown = wealth / np.maximum.accumulate(wealth, axis=0) - 1
    return wealth, drawdown


def joint_daily_months(core_daily, core_forward_daily, leverage_specs, *, paths=2000, months=12,
                       block=20, seed=212):
    """All core assets, funding and FX share block indices; leverage resets natively.

    Specs reference actual panel columns for underlying, funding and FX. Core means
    are shifted before the native leverage reset. No independent variance grafting.
    Output axis is paths × months × (core assets + leveraged products).
    """
    panel = core_daily.to_numpy(float)
    if not np.isfinite(panel).all() or len(panel) < block:
        raise ValueError('Complete synchronised actual daily evidence required.')
    rng = np.random.default_rng(seed)
    output = []
    core_columns = list(core_forward_daily)
    positions = core_daily.columns.get_indexer(core_columns)
    if (positions < 0).any():
        raise ValueError('Missing core daily columns.')
    for start in range(0, paths, 50):
        count = min(50, paths - start)
        ix = block_indices(len(panel), months * 21, count, block, rng)
        batch = panel[ix]
        core = batch[..., positions] - panel[:, positions].mean(axis=0) + np.array(list(core_forward_daily.values()))
        if (core < -1).any():
            raise ValueError('Core forward shift creates invalid daily returns.')
        series = [core[..., j] for j in range(len(positions))]
        for spec in leverage_specs:
            if spec['underlying'] not in core_columns:
                raise ValueError('Underlying must share the calibrated core forward paths.')
            native = core[..., core_columns.index(spec['underlying'])]
            funding = batch[..., core_daily.columns.get_loc(spec['funding'])]
            fx = None if spec.get('fx') is None else batch[..., core_daily.columns.get_loc(spec['fx'])]
            series.append(daily_leverage(native, funding, spec['terms'], fx))
        daily = np.stack(series, axis=-1).reshape(count, months, 21, len(series))
        output.append(np.prod(1 + daily, axis=2) - 1)
    return np.concatenate(output)


def convergence(first, second, weights, threshold=0.005):
    delta = np.abs(horizon_quantiles(first, weights) - horizon_quantiles(second, weights))
    return {'max_quantile_difference': float(delta.max()), 'threshold': threshold, 'passed': bool(delta.max() <= threshold)}


def leveraged_horizon_scenarios(model, years, paths=2000, seed=212, selected_weights=None, block=20, frontier_weights=None):
    """Regenerate full daily horizons in batches so terminated NAV cannot resurrect."""
    if years not in (1, 5, 10, 20, 30) or model.daily_config is None:
        raise ValueError('Verified daily mechanics configuration and supported horizon required.')
    config = model.daily_config
    months = years * 12
    averages = np.empty((paths, len(model.ids)))
    weights = None if selected_weights is None else np.atleast_2d(selected_weights)
    selected_paths = None if weights is None else np.empty((paths, months, len(weights)))
    frontier = None if frontier_weights is None else np.atleast_2d(frontier_weights)
    frontier_averages = None if frontier is None else np.empty((paths, len(frontier)))
    for start in range(0, paths, 25):
        count = min(25, paths - start)
        joint = joint_daily_months(model.snapshot.daily, config['core_forward'], config['specs'],
                                  paths=count, months=months, seed=seed + start, block=block)
        joint = joint[..., config['selected']]
        if config['cash_mean'] is not None:
            joint = np.concatenate([joint, np.full((*joint.shape[:2], 1), config['cash_mean'])], axis=-1)
        averages[start:start + count] = joint.mean(axis=1) * 12
        if weights is not None:
            selected_paths[start:start + count] = survivor_rebalanced_paths(joint, weights)
        if frontier is not None:
            frontier_averages[start:start + count] = survivor_rebalanced_paths(joint, frontier).mean(axis=1) * 12
    return Scenarios(averages, selected_paths, seed, years, paths, block,
                     'Market-path uncertainty only; native daily reset/absorbing termination; after termination rebalance proportionally among surviving original sleeves (initial caps may no longer hold); joint estimation refits unavailable',
                     frontier_averages, frontier)


def survivor_rebalanced_paths(asset_paths, weights):
    """A zero-NAV product cannot receive a new allocation at the next rebalance.

    Research stress policy: reweight surviving original sleeves proportionally.
    A portfolio with no surviving sleeve remains worthless, with no resurrection.
    This exception can depart from original per-fund/category caps after failure.
    """
    returns = np.asarray(asset_paths, float)
    weights = np.atleast_2d(weights)
    if returns.ndim != 3 or returns.shape[2] != weights.shape[1] or not np.isfinite(returns).all() or (returns < -1).any():
        raise ValueError('Aligned finite monthly asset paths and weights required.')
    if not (returns <= -1 + 1e-12).any():
        return returns @ weights.T
    alive = np.ones((len(returns), returns.shape[2]), dtype=bool)
    output = np.zeros((len(returns), returns.shape[1], len(weights)))
    for month in range(returns.shape[1]):
        allocation = weights[None, :, :] * alive[:, None, :]
        total = allocation.sum(axis=2, keepdims=True)
        allocation = np.divide(allocation, total, out=np.zeros_like(allocation), where=total > 0)
        output[:, month] = np.einsum('pa,pba->pb', returns[:, month], allocation)
        alive &= returns[:, month] > -1 + 1e-12
    return output


def matrix_scenarios(mean, covariance, years, paths=2000, seed=212, mean_draws=None, selected_weights=None):
    """Labelled IID Gaussian approximation for a derived-matrix-only checkout.

    Generates model paths, never actual return observations. Leverage must use
    the daily mechanics route instead. Estimation draws are retained derived
    bootstrap statistics, not an invented fixed uncertainty floor.
    """
    from portfolio.validation import check_covariance
    mu,cov=map(np.asarray,(mean,covariance))
    check_covariance(cov)
    if years not in (1,5,10,20,30) or mu.shape!=(len(cov),) or not np.isfinite(mu).all():
        raise ValueError('Supported horizon and finite aligned matrix inputs required.')
    rng=np.random.default_rng(seed)
    draws=np.broadcast_to(mu,(paths,len(mu)))
    if mean_draws is not None:
        samples=np.asarray(mean_draws,float)
        if samples.ndim!=2 or samples.shape[1]!=len(mu) or not np.isfinite(samples).all():
            raise ValueError('Invalid joint bootstrap mean draws.')
        draws=samples[rng.integers(0,len(samples),paths)]
    weights=None if selected_weights is None else np.atleast_2d(selected_weights)
    months=12*years
    average=np.empty((paths,len(mu)))
    selected=None if weights is None else np.empty((paths,months,len(weights)))
    for start in range(0,paths,100):
        stop=min(paths,start+100)
        shocks=rng.multivariate_normal(np.zeros(len(mu)),cov,size=(stop-start,months),check_valid='raise')
        batch=shocks+draws[start:stop,None,:]
        if (batch < -1).any():
            raise ValueError('Gaussian approximation generates impossible losses; source-path model required.')
        average[start:stop]=batch.mean(axis=1)*12
        if weights is not None:selected[start:stop]=batch @ weights.T
    estimation='equity bootstrap estimation included' if mean_draws is not None else 'estimation draws unavailable'
    return Scenarios(average,selected,seed,years,paths,1,
                     'Matrix-only IID Gaussian joint-risk approximation; serial dependence unavailable; '+estimation)
