"""V7 orchestration. No legacy fallback or pre-inception manufactured observations."""
from dataclasses import dataclass, field
from hashlib import sha256
import json

import numpy as np
import pandas as pd

from portfolio import __version__
from portfolio.models.bonds import bond_forecast, bond_stress
from portfolio.models.cash import cash_monthly
from portfolio.models.commodities import commodity_forecast
from portfolio.models.equity import fit_equity, specifications_for
from portfolio.models.leveraged import LeverageTerms, daily_leverage, overlap_error
from portfolio.optimise import efficient_frontier, Frontier
from portfolio.premiums import estimate_premiums, premium_sensitivities, block_indices, shrink
from portfolio.risk import shrunk_covariance, portfolio_metrics
from portfolio.scenarios import joint_daily_months
from portfolio.validation import CATEGORIES, REGIONS, BENCHMARKS, check_covariance
from portfolio.validation import age_days


@dataclass
class Model:
    ids: list
    mean: np.ndarray
    covariance: np.ndarray
    history: pd.DataFrame
    fees: pd.Series
    financing: pd.Series
    leverage: pd.Series
    betas: pd.DataFrame
    diagnostics: pd.DataFrame
    premiums: pd.DataFrame
    snapshot: object
    mean_draws: np.ndarray | None
    limitations: list
    stress: pd.DataFrame
    daily_months: np.ndarray | None = None
    source_month: str | None = None
    daily_config: dict | None = None
    historical_references: dict = field(default_factory=dict)
    covariance_windows: dict = field(default_factory=dict)


def risk_window_covariances(model):
    windows=dict(model.covariance_windows)
    risky=[j for j,i in enumerate(model.ids) if i!='GBP_BANK_SAVINGS']
    if model.daily_config is None and risky:
        for months in (72,120):
            if len(model.history)>=months:
                covariance=np.zeros_like(model.covariance)
                covariance[np.ix_(risky,risky)],_=shrunk_covariance(model.history.iloc[-months:,risky].to_numpy())
                windows[str(months)]=covariance
    return windows


@dataclass
class ResearchRun:
    run_id: str
    model: Model
    frontier: Frontier
    constraints: dict
    available_ids: list
    benchmarks: dict


def prepare_model(snapshot, bootstrap_paths=200, seed=212):
    if 'derived_model_inputs' in snapshot.manifest:
        from portfolio.portable import load_derived_model
        return load_derived_model(snapshot)
    status = snapshot.status.copy()
    eligible = status.index[status.Status.eq('Evidence eligible')].tolist()
    evidence = snapshot.evidence
    ids, means, fees, financing, levels, diagnostics, fitted = [], [], [], [], [], [], {}
    premium_fit = None
    if not snapshot.factors.empty:
        if not {'GBP_RF', 'USD_GBP'}.issubset(snapshot.cash_fx):
            raise ValueError('Compounded SONIA/GBP-per-USD FX input required for regional calibration.')
        if age_days(snapshot.factors.index[-1].end_time.date().isoformat()) > 90:
            raise ValueError('Published-factor vintage older than 90 days; refresh required.')
        premium_fit = estimate_premiums(snapshot.factors)
    limitations = ['Forecasts exclude unverified dealing spreads/trading costs and personal tax.',
                   'Present-day source backfills are not point-in-time historical vintages.',
                   'Savings/forward cash rates and bond/commodity policy assumptions are held constant in the displayed horizon paths; future variable-rate uncertainty remains unquantified.']
    broker_cash = evidence.get('GBP_BANK_SAVINGS', {})
    # Wholesale forward cash is distinct from the retail account quote.
    forward = snapshot.manifest.get('forward_sonia_annual')
    if snapshot.manifest.get('provisional_policy') and not snapshot.manifest['provisional_policy'].get('historical_sonia_actual') and broker_cash.get('aer') is not None:
        forward_monthly = cash_monthly(broker_cash['aer'])
        limitations.append('PROVISIONAL: ' + snapshot.manifest['provisional_policy']['cash_reference'])
        limitations.append(snapshot.manifest['provisional_policy']['currency_policy'])
    elif forward is None and not snapshot.cash_fx.empty:
        forward_monthly = float(snapshot.cash_fx.GBP_RF.iloc[-1])
        limitations.append('Forward wholesale cash held at latest compounded SONIA month; variable-rate sensitivity required.')
    elif forward is not None:
        # SONIA is an ACT/365 simple annual quote, not an effective savings AER.
        forward_monthly = forward / 12
        limitations.append('Latest actual SONIA held flat by assumption, dated '+str(snapshot.manifest.get('forward_sonia_date'))+'; not an observed forward curve.')
    else:
        forward_monthly = None
    for ident in eligible:
        row, e = snapshot.instruments.loc[ident], evidence[ident]
        try:
            if row.category == CATEGORIES[-1]:
                continue  # Admission below uses actual daily overlap and shared scenarios.
            fee = 0.0 if row.category == CATEGORIES[0] else float(e['fee'])
            if row.category == CATEGORIES[0]:
                mean = cash_monthly(e['aer'])
            elif row.category in CATEGORIES[3:5]:
                if premium_fit is None or forward_monthly is None:
                    raise ValueError('Published regional factors/SONIA/FX unavailable')
                regions = REGIONS.get(ident, ['Developed'])
                specs = specifications_for(regions, e.get('momentum_columns', []))
                result = fit_equity(snapshot.returns[ident], snapshot.factors, snapshot.cash_fx.GBP_RF, specs)
                fitted[ident] = result
                mean = forward_monthly + float(result.betas @ premium_fit.estimates.loc[result.betas.index]) / 12 - fee / 12
                diagnostics.append({'instrument': ident, **result.diagnostic,
                                    'factor_currency': 'USD native proxy' if e.get('provisional_native_risk') else 'GBP converted',
                                    'cash_reference': snapshot.manifest.get('provisional_policy', {}).get('cash_reference', 'Compounded SONIA'),
                                    'factor_vintage': json.dumps(snapshot.manifest.get('factor_vintages', {}), sort_keys=True),
                                    'source_reconciliation': e.get('reconciliation_warning', 'Input evidence reviewed')})
            elif row.category == 'Bonds':
                if snapshot.manifest.get('provisional_policy') and e.get('forecast_policy') == 'cash_plus_zero_term_premium':
                    if forward_monthly is None:
                        raise ValueError('Provisional bond carry prior needs a dated cash reference')
                    mean = forward_monthly + (e['term_premium_annual'] - fee) / 12
                    limitations.append(ident + ': ' + e['assumption_label'])
                else:
                    mean = bond_forecast(e['yield'], fee, yield_kind=e['yield_kind'], inflation=e.get('inflation'),
                                         expected_loss=e.get('expected_loss', 0), hedge_cost=e.get('hedge_cost', 0),
                                         hedge_embedded=e.get('hedge_embedded', False))
            else:
                if forward_monthly is None:
                    raise ValueError('Wholesale cash reference unavailable for neutral commodity prior')
                mean = commodity_forecast(forward_monthly, fee)
            ids.append(ident)
            means.append(mean)
            fees.append(fee)
            financing.append(0.0)
            levels.append(0.0 if row.category in CATEGORIES[:1] else 1.0)
        except (KeyError, ValueError) as exc:
            status.loc[ident, ['Status', 'Reason']] = ['Blocked', str(exc)]
    risky = [i for i in ids if i != 'GBP_BANK_SAVINGS']
    # All realised-risk/chart inputs end at the latest common completed model month.
    cutoffs = [snapshot.returns.index[-1]] if len(snapshot.returns) else []
    if fitted:
        cutoffs += [f.residuals.index[-1] for f in fitted.values()]
    if forward_monthly is not None and not snapshot.cash_fx.empty:
        cutoffs.append(snapshot.cash_fx.index[-1])
    return_panel = snapshot.returns.loc[:min(cutoffs)] if cutoffs else snapshot.returns
    history = return_panel.reindex(columns=risky).dropna()
    if risky and len(history) < 36:
        for i in risky:
            status.loc[i, ['Status', 'Reason']] = ['Blocked', 'Fewer than 36 common actual GBP risk months; validated proxy extension required']
        keep = [ids.index('GBP_BANK_SAVINGS')] if 'GBP_BANK_SAVINGS' in ids else []
        ids = [ids[i] for i in keep]
        means = [means[i] for i in keep]
        fees, financing, levels = [[v[i] for i in keep] for v in (fees, financing, levels)]
        risky, history = [], pd.DataFrame()
    if not ids:
        snapshot.status = status
        raise ValueError('No instrument passes current data, cost and model admission gates.')
    means = np.asarray(means)
    cov = np.zeros((len(ids), len(ids)))
    if risky:
        risky_cov, _ = shrunk_covariance(history.to_numpy())
        pos = [ids.index(i) for i in risky]
        cov[np.ix_(pos, pos)] = risky_cov
    # Append deterministic cash only after shrinking the risky panel.
    history = history.reindex(columns=ids)
    if 'GBP_BANK_SAVINGS' in ids:
        history['GBP_BANK_SAVINGS'] = means[ids.index('GBP_BANK_SAVINGS')]
    daily_months = None
    daily_config = None
    leverage_ids = [i for i in eligible if snapshot.instruments.loc[i, 'category'] == CATEGORIES[-1]]
    if leverage_ids:
        try:
            if snapshot.daily.empty:
                raise ValueError('Actual synchronised daily core/underlying/funding/FX panel unavailable')
            specs = []
            # Every risky core must have daily net GBP observations for coherent joint moments.
            if any(i not in snapshot.daily for i in risky):
                raise ValueError('Missing actual daily core asset data for shared leverage covariance')
            core_forward = {i: means[ids.index(i)] / 21 for i in risky}
            for ident in leverage_ids:
                e = evidence[ident]
                terms = LeverageTerms(**e['terms'])
                if abs(terms.annual_fee - e['fee']) > 1e-12:
                    raise ValueError('Issuer daily product expense and displayed ongoing fee disagree')
                native_col = e['underlying']
                if native_col not in snapshot.daily:
                    raise ValueError('Missing native underlying daily returns')
                native_forward = e.get('underlying_forward_daily')
                if native_forward is None:
                    raise ValueError('Calibrated native underlying forward mean required')
                core_forward[native_col] = native_forward
                funding = snapshot.daily[e['funding']].to_numpy()
                fx = None if e.get('fx') is None else snapshot.daily[e['fx']].to_numpy()
                actual = snapshot.daily[e['actual_daily_column']].to_numpy()
                modelled = daily_leverage(snapshot.daily[native_col].to_numpy(), funding, terms, fx)
                check = overlap_error(modelled, actual)
                if check['daily_rmse'] > e['overlap_tolerance']:
                    raise ValueError(f'{ident} actual overlap fails documented tolerance')
                diagnostics.append({'instrument': ident, **check})
                specs.append(dict(underlying=native_col, funding=e['funding'], fx=e.get('fx'), terms=terms))
            # The frontier needs next-period moments, before future absorbing states.
            joint = joint_daily_months(snapshot.daily, core_forward, specs, months=1,
                                      paths=snapshot.manifest.get('joint_calibration_paths', 5000))
            # Native auxiliary underlyings remain diagnostic; select only portfolio assets.
            selected = [list(core_forward).index(i) for i in risky] + list(range(len(core_forward), len(core_forward) + len(specs)))
            joint = joint[..., selected]
            joint_ids = risky + leverage_ids
            joint_mean = joint.mean(axis=(0, 1))
            joint_cov = np.cov(joint.reshape(-1, len(joint_ids)), rowvar=False, ddof=1)
            joint_cov = np.atleast_2d(joint_cov)
            core_difference = float(np.linalg.norm(joint_cov[:len(risky), :len(risky)] - cov[np.ix_([ids.index(i) for i in risky], [ids.index(i) for i in risky])]))
            diagnostics.append({'instrument': 'joint_daily', 'core_covariance_difference_frobenius': core_difference})
            empirical = cov[np.ix_([ids.index(i) for i in risky], [ids.index(i) for i in risky])]
            mean_difference = np.max(np.abs(joint_mean[:len(risky)] - np.array([means[ids.index(i)] for i in risky]))) if risky else 0
            relative_covariance_difference = core_difference / max(float(np.linalg.norm(empirical)), 1e-12)
            if mean_difference > snapshot.manifest.get('joint_core_monthly_mean_tolerance', .001) or relative_covariance_difference > snapshot.manifest.get('joint_core_covariance_relative_tolerance', .25):
                raise ValueError('Joint daily core monthly moments fail forward-mean/empirical-covariance reconciliation')
            cash_included = 'GBP_BANK_SAVINGS' in ids
            cash_mean = means[ids.index('GBP_BANK_SAVINGS')] if cash_included else None
            ids = joint_ids + (['GBP_BANK_SAVINGS'] if cash_included else [])
            means = np.r_[joint_mean, cash_mean] if cash_included else joint_mean
            cov = np.zeros((len(ids), len(ids)))
            cov[:len(joint_ids), :len(joint_ids)] = joint_cov
            daily_months = np.concatenate([joint, np.full((*joint.shape[:2], 1), cash_mean)], axis=-1) if cash_included else joint
            daily_config = dict(core_forward=core_forward, specs=specs, selected=selected, cash_mean=cash_mean)
            fees = [float(evidence[i].get('fee', 0)) for i in ids]
            financing = [float(evidence[i].get('annual_financing', 0)) for i in ids]
            levels = [float(evidence[i].get('terms', {}).get('leverage', 0 if i == 'GBP_BANK_SAVINGS' else 1)) for i in ids]
            history = return_panel.reindex(columns=joint_ids).dropna().reindex(columns=ids)
            if cash_included:
                history['GBP_BANK_SAVINGS'] = cash_mean
            limitations.append('Daily joint scenarios use 21 trading days per model month; intraday evidence gates still apply.')
        except (KeyError, ValueError) as exc:
            for ident in leverage_ids:
                status.loc[ident, ['Status', 'Reason']] = ['Blocked', str(exc)]
    check_covariance(cov)
    # Jointly resample exposures/premiums, freeze specification selection and prior.
    mean_draws = None
    active_fits = {i: fit for i, fit in fitted.items() if i in ids}
    if active_fits and daily_months is None:
        rng = np.random.default_rng(seed)
        draw_values = []
        common = snapshot.factors.index.intersection(snapshot.cash_fx.index)
        panel = snapshot.factors.loc[common]
        premium_indices = block_indices(len(panel), len(panel), bootstrap_paths, 12, rng)
        for ix in premium_indices:
            sampled_mean = panel.to_numpy()[ix].mean(axis=0) * 12
            p, _, _ = shrink(sampled_mean, premium_fit.sampling_covariance, premium_fit.prior_scales)
            draw = means.copy()
            # Same sampled calendar months drive each fund's exposure fit where present.
            for ident, fit in active_fits.items():
                dates = fit.residuals.index
                sampled_dates = common[ix]
                dates_draw = sampled_dates[sampled_dates.isin(dates)]
                if len(dates_draw) < 36:
                    dates_draw = dates[block_indices(len(dates), len(dates), 1, 12, rng)[0]]
                from sklearn.pipeline import make_pipeline
                from sklearn.preprocessing import StandardScaler
                from sklearn.linear_model import Ridge
                columns = fit.betas.index
                x = snapshot.factors.loc[dates_draw, columns].to_numpy()
                y = snapshot.returns.loc[dates_draw, ident].to_numpy() - snapshot.cash_fx.loc[dates_draw, 'GBP_RF'].to_numpy()
                m = make_pipeline(StandardScaler(), Ridge(alpha=fit.penalty)).fit(x, y)
                beta = m.named_steps['ridge'].coef_ / m.named_steps['standardscaler'].scale_
                locations = panel.columns.get_indexer(columns)
                draw[ids.index(ident)] = forward_monthly + beta @ p[locations] / 12 - evidence[ident]['fee'] / 12
            draw_values.append(draw)
        mean_draws = np.asarray(draw_values)
    if mean_draws is None:
        limitations.append('Estimation bands unavailable for this model; market-only ranges must be labelled explicitly.')
    else:
        limitations.append('Bootstrap estimation covers equity exposures/premiums only; cash-rate, bond-carry and commodity-prior assumptions remain conditional fixed inputs.')
    betas = pd.DataFrame({i: f.betas for i, f in active_fits.items()}).T
    premiums = pd.DataFrame() if premium_fit is None else premium_sensitivities(premium_fit)
    if premium_fit is not None:
        premiums['prior_std'] = premium_fit.prior_scales
        premiums['sample_start'] = str(snapshot.factors.index[0])
        premiums['sample_end'] = str(snapshot.factors.index[-1])
        premiums['mean_covariance_regularisation'] = premium_fit.regularisation
    stresses = []
    for ident in ids:
        e = evidence[ident]
        if snapshot.instruments.loc[ident, 'category'] == 'Bonds' and 'duration' in e:
            for shift in (-.01, .01):
                shock = bond_stress(e['duration'], shift, e.get('convexity', 0))
                new_carry = bond_forecast(e['yield'] + shift, e['fee'], yield_kind=e['yield_kind'],
                                         inflation=e.get('inflation'), expected_loss=e.get('expected_loss', 0),
                                         hedge_cost=e.get('hedge_cost', 0), hedge_embedded=e.get('hedge_embedded', False))
                stresses.append({'instrument': ident, 'scenario': f'yield {shift:+.0%}',
                                 'return_shock': shock, 'one_year_return_approx': 12 * new_carry + shock,
                                 'as_of': e['bond_date'],
                                 'basis': 'Dated current duration, parallel yield shock plus shifted carry/costs once; first-order if convexity absent; not a backtest'})
        # These are isolated currency translation shocks, not causal macro forecasts.
        native = e.get('native_currency', 'GBP' if ident == 'GBP_BANK_SAVINGS' else None)
        if native == 'GBP' or (native == 'USD' and e.get('hedge') == 'unhedged'):
            for shift in (-.1, .1):
                stresses.append({'instrument': ident, 'scenario': f'GBP per USD {shift:+.0%}',
                                 'return_shock': shift if native == 'USD' else 0.0,
                                 'basis': 'FX-only instantaneous translation; native NAV/rates held fixed; no price correlation/carry forecast'})
        if ident in active_fits:
            beta = sum(v for key, v in active_fits[ident].betas.items() if key.endswith(':Mkt-RF'))
            for shift in (-.2, .2):
                stresses.append({'instrument': ident, 'scenario': f'equity market factor {shift:+.0%}',
                                 'return_shock': float(beta * shift),
                                 'basis': 'Fitted regional market beta; other style shocks/residual held zero; linear approximation, not a causal guarantee'})
    # Complete isolated-channel scenarios only by stating what is held fixed.
    # Missing equity betas or bond durations remain unavailable, never guessed.
    scenario_names = {row['scenario'] for row in stresses}
    existing = {(row['instrument'], row['scenario']) for row in stresses}
    for scenario_name in scenario_names:
        for ident in ids:
            if (ident, scenario_name) in existing:
                continue
            category = snapshot.instruments.loc[ident, 'category']
            fixed_other = ((scenario_name.startswith('yield') and category != 'Bonds') or
                           (scenario_name.startswith('equity market') and category not in CATEGORIES[3:]))
            if fixed_other:
                stresses.append({'instrument': ident, 'scenario': scenario_name, 'return_shock': 0.0,
                                 'basis': 'Isolated channel: non-target asset prices held fixed by assumption; not a full macro stress'})
    snapshot.status = status
    for ident in ids:
        snapshot.status.loc[ident, 'Status'] = 'Admitted provisional model' if snapshot.manifest.get('provisional_policy') else 'Admitted research model'
        if 'Expected return model' in snapshot.status:
            snapshot.status.loc[ident,'Expected return model']='Executed calibrated FF5' if ident in active_fits else 'Explicit cash/carry/premium assumption'
            snapshot.status.loc[ident,'Risk model']='Joint actual GBP covariance' if ident!='GBP_BANK_SAVINGS' else 'Deterministic nominal savings scenario'
    return Model(ids, means, cov, history, pd.Series(fees, index=ids), pd.Series(financing, index=ids),
                 pd.Series(levels, index=ids), betas, pd.DataFrame(diagnostics), premiums, snapshot, mean_draws,
                 limitations, pd.DataFrame(stresses), daily_months,
                 str(history.index[-1]) if len(history) else None, daily_config)


def solve_run(model, constraints=None, targets_monthly=None, *, frontier_points=101):
    if not model.historical_references:
        from portfolio.references import historical_references
        model.historical_references=historical_references(model.snapshot)
    policy = dict(allow_cash=True, allow_commodities=True, allow_leverage=False,
                  leverage_cap=.25, gross_cap=1.5, fund_cap=1.0, category_caps={})
    policy.update(constraints or {})
    if not 0 <= policy['leverage_cap'] <= 1 or not 0 <= policy['gross_cap'] <= 5:
        raise ValueError('Invalid leverage/gross research constraints.')
    categories = model.snapshot.instruments.loc[model.ids, 'category']
    mask = np.ones(len(model.ids), dtype=bool)
    for category, key in [(CATEGORIES[0], 'allow_cash'), (CATEGORIES[1], 'allow_commodities'), (CATEGORIES[-1], 'allow_leverage')]:
        if not policy[key]:
            mask &= categories.ne(category).to_numpy()
    # A zero cap excludes assets before solving, never passes a rejected zero bound.
    for category, cap in policy['category_caps'].items():
        if not 0 <= cap <= 1:
            raise ValueError('Category caps must lie between zero and one.')
        if cap == 0:
            mask &= categories.ne(category).to_numpy()
    if policy['leverage_cap'] == 0:
        mask &= categories.ne(CATEGORIES[-1]).to_numpy()
    if not mask.any():
        raise ValueError('No admitted instrument remains under these switches.')
    indices = np.flatnonzero(mask)
    selected_categories = categories.iloc[indices]
    exposure = [(selected_categories == CATEGORIES[-1]).to_numpy(float), model.leverage.iloc[indices].to_numpy()]
    limits = [policy['leverage_cap'], policy['gross_cap']]
    for category, cap in policy['category_caps'].items():
        if cap > 0:
            exposure.append((selected_categories == category).to_numpy(float))
            limits.append(cap)
    f = efficient_frontier(model.mean[indices], model.covariance[np.ix_(indices, indices)], cap=policy['fund_cap'],
                           exposure=exposure, limits=limits, targets_monthly=targets_monthly, points=frontier_points)
    full = np.zeros((len(f.weights), len(model.ids)))
    full[:, indices] = f.weights
    frontier = Frontier(full, f.returns, f.volatilities, f.targets, f.solvers, f.max_violation)
    identity = {'version': __version__, 'snapshot': model.snapshot.fingerprint, 'constraints': policy,
                'mean': model.mean.tolist(), 'covariance': model.covariance.tolist(), 'ids': model.ids,
                'frontier_points':frontier_points}
    if targets_monthly is not None:
        identity['requested_targets'] = np.asarray(targets_monthly).tolist()
    run_id = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12]
    benchmarks = {}
    for label, allocation in BENCHMARKS.items():
        missing = [i for i in allocation if i not in model.ids]
        if missing:
            benchmarks[label] = {'available': False, 'reason': '; '.join(i + ': ' + model.snapshot.status.loc[i, 'Reason'] for i in missing)}
        else:
            w = np.array([allocation.get(i, 0.0) for i in model.ids])
            mean, vol, _ = portfolio_metrics(w, model.mean, model.covariance)
            benchmarks[label] = dict(available=True, weights=w, mean=mean, volatility=vol,
                                     outside_constraints=True)
        benchmarks[label]['historical']=model.historical_references.get(label,dict(available=False,reason='Historical source data unavailable'))
    return ResearchRun(run_id, model, frontier, policy, [model.ids[i] for i in indices], benchmarks)


def categories_for(run, weights):
    category = run.model.snapshot.instruments.loc[run.model.ids, 'category']
    return pd.Series(weights, index=run.model.ids).groupby(category).sum().reindex(CATEGORIES, fill_value=0)


def full_weights(run, point):
    return pd.Series(run.frontier.weights[point], index=run.model.ids).reindex(run.model.snapshot.instruments.index, fill_value=0)


def universe_usefulness(runs, inclusion=.01):
    """Predeclared scenario runs only; no tuned artificial inclusion caps."""
    if not runs:
        raise ValueError('At least one predefined run is required.')
    ids=runs[0].model.snapshot.instruments.index
    # Align once per run instead of building a 50-row Series separately for
    # every instrument, position and scenario (tens of thousands of copies).
    weights=np.concatenate([pd.DataFrame(r.frontier.weights,columns=r.model.ids)
                            .reindex(columns=ids,fill_value=0).to_numpy() for r in runs])
    maximum=weights.max(axis=0)
    return pd.DataFrame({'instrument':ids,'max_weight':maximum,
                         'frequency_above_1pct':(weights>=inclusion).mean(axis=0),
                         'review':np.where(maximum<inclusion,'No meaningful inclusion; removal sensitivity still required',
                                           'Removal/bootstrap stability review required')})
