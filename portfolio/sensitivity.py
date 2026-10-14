"""Predeclared useful-universe screen. Thresholds are judgements, not advice."""
from dataclasses import replace
import numpy as np
import pandas as pd
from portfolio.research import solve_run, universe_usefulness
from portfolio.risk import shrunk_covariance
from portfolio.validation import CATEGORIES


def predefined_models(model):
    candidates={'central':model}
    if model.daily_config is not None:
        return candidates # Leverage cases must regenerate the joint daily moments.
    betas=model.betas.reindex(model.ids,fill_value=0).fillna(0)
    if not betas.empty and not model.premiums.empty:
        central=model.premiums.central
        for label in ['zero_styles','unshrunk','prior_0.5x','prior_2x','market_-0.02','market_+0.02']:
            if label in model.premiums:
                delta=betas @ (model.premiums[label]-central).reindex(betas.columns)
                candidates[label]=replace(model,mean=model.mean+delta.to_numpy()/12)
    categories=model.snapshot.instruments.loc[model.ids,'category']
    for shift in (-.05,.05):
        delta=(categories==CATEGORIES[1]).to_numpy()*shift/12
        candidates[f'commodity_{shift:+g}']=replace(model,mean=model.mean+delta)
    # Wholesale-rate stresses are conditional assumptions, not fitted OIS paths.
    if model.snapshot.manifest.get('provisional_policy',{}).get('historical_sonia_actual'):
        for shift in (-.02,-.01,.01,.02):
            affected=categories.isin([CATEGORIES[1],CATEGORIES[3],CATEGORIES[4]]).to_numpy()
            candidates[f'flat_sonia_{shift:+g}']=replace(model,mean=model.mean+affected*shift/12)
    risky=[j for j,i in enumerate(model.ids) if i!='GBP_BANK_SAVINGS']
    if len(model.history)>=120 and risky:
        for months in (72,120):
            covariance=np.zeros_like(model.covariance)
            covariance[np.ix_(risky,risky)],_=shrunk_covariance(model.history.iloc[-months:,risky].to_numpy())
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
            try:boot.append(solve_run(replace(run.model,mean=mean),run.constraints).frontier.weights)
            except ValueError:continue
    if boot:
        # Same 0–100 targets within each bootstrap run, not identical allocations.
        values=np.array([b[len(b)//2] for b in boot])
        table['bootstrap_position50_weight_std']=pd.Series(values.std(axis=0),index=run.model.ids)
    for ident in run.model.ids:
        maximum_vol_improvement=0.
        maximum_return_loss=0.
        for baseline in runs:
            model=baseline.model
            remaining=[i for i in model.ids if i!=ident]
            if not remaining:continue
            idx=[model.ids.index(i) for i in remaining]
            reduced=replace(model,ids=remaining,mean=model.mean[idx],covariance=model.covariance[np.ix_(idx,idx)],
                            fees=model.fees.loc[remaining],financing=model.financing.loc[remaining],leverage=model.leverage.loc[remaining],
                            betas=model.betas.reindex(remaining),history=model.history.reindex(columns=remaining))
            try:
                reduced_run=solve_run(reduced,baseline.constraints)
                maximum_return_loss=max(maximum_return_loss,12*(baseline.frontier.returns[-1]-reduced_run.frontier.returns[-1]))
                candidates=[p for p in range(len(baseline.frontier.weights))
                            if baseline.frontier.returns[p]<=reduced_run.frontier.returns[-1]+1e-8]
                if candidates:
                    exact=solve_run(reduced,baseline.constraints,targets_monthly=baseline.frontier.returns[candidates])
                    diff=(exact.frontier.volatilities-baseline.frontier.volatilities[candidates])*np.sqrt(12)
                    maximum_vol_improvement=max(maximum_vol_improvement,float(diff.max()))
            except ValueError:
                continue
        table.loc[ident,'max_removal_annual_volatility_increase']=maximum_vol_improvement
        table.loc[ident,'max_removal_max_return_loss']=maximum_return_loss
        if table.loc[ident,'max_weight']<.01 and max(maximum_vol_improvement,maximum_return_loss)<.0005:
            table.loc[ident,'review']='Review: never reaches 1%, no measured frontier improvement >=5bp'
        else:
            table.loc[ident,'review']='Meaningful in at least one predefined case; not proof of future benefit'
    unmodelled=table.index.difference(run.model.ids)
    table.loc[unmodelled,'review']='Unavailable: evidence/model gates prevent usefulness assessment'
    return table
