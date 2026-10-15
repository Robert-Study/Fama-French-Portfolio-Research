"""Predeclared useful-universe screen. Thresholds are judgements, not advice."""
from dataclasses import replace
import numpy as np
import pandas as pd
from portfolio.research import solve_run, universe_usefulness, risk_window_covariances
from portfolio.risk import shrunk_covariance
from portfolio.validation import CATEGORIES


def screen_signature(run,bootstrap_draws=20):
    """Bind a precomputed diagnostic to the actual math, inputs and policy."""
    from hashlib import sha256
    from pathlib import Path
    import json
    from portfolio import __version__
    model=run.model
    code=sha256()
    for name in ('sensitivity.py','research.py','optimise.py','risk.py'):
        code.update((Path(__file__).parent/name).read_bytes())
    cases={name:dict(ids=m.ids,mean=m.mean.tolist(),covariance=m.covariance.tolist())
           for name,m in predefined_models(model).items()}
    value=dict(version=__version__,code=code.hexdigest(),constraints=run.constraints,cases=cases,
               universe=model.snapshot.instruments.index.tolist(),
               categories=model.snapshot.instruments.loc[model.ids,'category'].tolist(),
               leverage=model.leverage.to_numpy(dtype=float).tolist(),bootstrap_draws=bootstrap_draws,
               mean_draws=None if model.mean_draws is None else model.mean_draws[:bootstrap_draws].tolist())
    return sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def save_screen_cache(run,table,folder,bootstrap_draws=20):
    from pathlib import Path
    from hashlib import sha256
    import json
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    raw=table.to_csv().encode()
    value=dict(signature=screen_signature(run,bootstrap_draws),sha256=sha256(raw).hexdigest(),
               rows=len(table),policy='Exact predefined target solves; no approximate interpolation. Failed removals remain incomplete.')
    data=folder/'universe-screen.csv';meta=folder/'universe-screen.json'
    temp=data.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(data)
    temp=meta.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(meta)


def load_screen_cache(run,folder,bootstrap_draws=20):
    from pathlib import Path
    from hashlib import sha256
    from io import BytesIO
    import json
    folder=Path(folder)
    try:
        meta=json.loads((folder/'universe-screen.json').read_text());raw=(folder/'universe-screen.csv').read_bytes()
        if meta['signature']!=screen_signature(run,bootstrap_draws) or meta['sha256']!=sha256(raw).hexdigest():return None
        table=pd.read_csv(BytesIO(raw),index_col='instrument')
        if len(table)!=meta['rows'] or table.index.tolist()!=run.model.snapshot.instruments.index.tolist():return None
        if not {'max_weight','frequency_above_1pct','review','removal_cases_failed'}.issubset(table):return None
        return table
    except (OSError,ValueError,KeyError,TypeError):
        return None


def predefined_models(model):
    candidates={'central':model}
    if model.daily_config is not None:
        return candidates # Leverage cases must regenerate the joint daily moments.
    betas=model.betas.reindex(model.ids,fill_value=0).fillna(0)
    if not betas.empty and not model.premiums.empty:
        central=model.premiums.central
        for label in ['zero_styles','unshrunk','prior_0.5x','prior_2x','market_-0.02','market_+0.02']:
            if label in model.premiums:
                # Use the same contiguous layout after JSON restoration; BLAS
                # reduction order otherwise changes the cache key by a few ulps.
                delta=np.ascontiguousarray(betas.to_numpy(dtype=float)) @ np.ascontiguousarray(
                    (model.premiums[label]-central).reindex(betas.columns).to_numpy(dtype=float))
                candidates[label]=replace(model,mean=model.mean+delta/12)
    categories=model.snapshot.instruments.loc[model.ids,'category']
    for shift in (-.05,.05):
        delta=(categories==CATEGORIES[1]).to_numpy()*shift/12
        candidates[f'commodity_{shift:+g}']=replace(model,mean=model.mean+delta)
    # Wholesale-rate stresses are conditional assumptions, not fitted OIS paths.
    if model.snapshot.manifest.get('provisional_policy',{}).get('historical_sonia_actual'):
        for shift in (-.02,-.01,.01,.02):
            affected=categories.isin([CATEGORIES[1],CATEGORIES[3],CATEGORIES[4]]).to_numpy()
            candidates[f'flat_sonia_{shift:+g}']=replace(model,mean=model.mean+affected*shift/12)
    for months,covariance in risk_window_covariances(model).items():
        candidates[f'covariance_{months}m']=replace(model,covariance=covariance)
    return candidates


def useful_universe(run, bootstrap_draws=20):
    runs=[solve_run(model,run.constraints) for model in predefined_models(run.model).values()]
    for switch in ('allow_cash','allow_commodities','allow_leverage'):
        policy={**run.constraints,switch:not run.constraints[switch]}
        try:runs.append(solve_run(run.model,policy))
        except ValueError:pass # Empty class exclusions can make the universe infeasible.
    table=universe_usefulness(runs).set_index('instrument')
    boot=[]
    if run.model.mean_draws is not None:
        for mean in run.model.mean_draws[:bootstrap_draws]:
            # The diagnostic uses only position 50. A three-target curve has
            # the identical GMV, midpoint and endpoint targets as the 101 curve.
            try:boot.append(solve_run(replace(run.model,mean=mean),run.constraints,frontier_points=3).frontier.weights)
            except ValueError:continue
    if boot:
        # Same 0–100 targets within each bootstrap run, not identical allocations.
        values=np.array([b[len(b)//2] for b in boot])
        table['bootstrap_position50_weight_std']=pd.Series(values.std(axis=0),index=run.model.ids)
    table['bootstrap_requested_draws']=min(bootstrap_draws,0 if run.model.mean_draws is None else len(run.model.mean_draws))
    table['bootstrap_solved_draws']=len(boot)
    for ident in run.model.ids:
        maximum_vol_improvement=0.
        maximum_return_loss=0.
        skipped=solved=0
        failures=[]
        for baseline in runs:
            model=baseline.model
            position=model.ids.index(ident)
            if np.all(baseline.frontier.weights[:,position]==0):
                # Every baseline optimum remains feasible after removal. The
                # reduced feasible set cannot improve the optimum, so its
                # minimum variance and maximum return are unchanged at these
                # exact sampled targets. No threshold of "small" holdings is used.
                skipped+=1
                continue
            remaining=[i for i in model.ids if i!=ident]
            if not remaining:
                failures.append('Removal leaves no instrument');continue
            idx=[model.ids.index(i) for i in remaining]
            reduced=replace(model,ids=remaining,mean=model.mean[idx],covariance=model.covariance[np.ix_(idx,idx)],
                            fees=model.fees.loc[remaining],financing=model.financing.loc[remaining],leverage=model.leverage.loc[remaining],
                            betas=model.betas.reindex(remaining),history=model.history.reindex(columns=remaining))
            try:
                # Only the maximum feasible return is needed before solving the
                # original comparable targets; avoid a redundant 101-point curve.
                reduced_run=solve_run(reduced,baseline.constraints,frontier_points=2)
                maximum_return_loss=max(maximum_return_loss,12*(baseline.frontier.returns[-1]-reduced_run.frontier.returns[-1]))
                candidates=[p for p in range(len(baseline.frontier.weights))
                            if baseline.frontier.returns[p]<=reduced_run.frontier.returns[-1]+1e-8]
                if candidates:
                    exact=solve_run(reduced,baseline.constraints,targets_monthly=baseline.frontier.returns[candidates])
                    diff=(exact.frontier.volatilities-baseline.frontier.volatilities[candidates])*np.sqrt(12)
                    maximum_vol_improvement=max(maximum_vol_improvement,float(diff.max()))
                solved+=1
            except ValueError as exc:
                failures.append(str(exc))
                continue
        table.loc[ident,'max_removal_annual_volatility_increase']=maximum_vol_improvement
        table.loc[ident,'max_removal_max_return_loss']=maximum_return_loss
        table.loc[ident,'removal_cases_total']=len(runs)
        table.loc[ident,'removal_cases_proved_unchanged']=skipped
        table.loc[ident,'removal_cases_solved']=solved
        table.loc[ident,'removal_cases_failed']=len(failures)
        table.loc[ident,'removal_status']='Complete' if not failures else '; '.join(sorted(set(failures)))
        if failures:
            table.loc[ident,'review']='Incomplete removal assessment: infeasible or failed cases are listed; measured changes are lower bounds'
        elif table.loc[ident,'max_weight']<.01 and max(maximum_vol_improvement,maximum_return_loss)<.0005:
            table.loc[ident,'review']='Review: never reaches 1%, no measured frontier improvement >=5bp'
        else:
            table.loc[ident,'review']='Meaningful in at least one predefined case; not proof of future benefit'
    unmodelled=table.index.difference(run.model.ids)
    table.loc[unmodelled,'review']='Unavailable: evidence/model gates prevent usefulness assessment'
    return table
