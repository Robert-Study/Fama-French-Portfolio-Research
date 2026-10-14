"""On-demand V7 ZIP: displayed run inputs, no fabricated missing diagnostics."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import inspect
import json
import subprocess
import numpy as np
import pandas as pd

from portfolio import __version__
from portfolio.holdings import effective_companies
from portfolio.research import full_weights, categories_for
from portfolio.risk import portfolio_metrics
from portfolio.scenarios import horizon_quantiles, compound_summary
from portfolio.validation import CATEGORIES
import portfolio.optimise as optimiser


def holdings_table(run, point):
    model = run.model
    weights = full_weights(run, point)
    table = model.snapshot.instruments[['name', 'listing', 'category']].copy()
    table['weight'] = weights
    table['ongoing_charge'] = model.fees.reindex(table.index)
    table['financing'] = model.financing.reindex(table.index)
    _, _, contributions = portfolio_metrics(run.frontier.weights[point], model.mean, model.covariance)
    table['annual_volatility_contribution'] = pd.Series(contributions * np.sqrt(12), index=model.ids).reindex(table.index, fill_value=0)
    table['currency_hedge'] = [model.snapshot.evidence.get(i, {}).get('currency', 'Unknown') + ' / ' + str(model.snapshot.evidence.get(i, {}).get('hedge', 'Unknown')) for i in table.index]
    table['status'] = model.snapshot.status.Status
    table['reason'] = model.snapshot.status.Reason
    return table


def comparison_table(run, a, b):
    rows = []
    weights = [run.frontier.weights[a], run.frontier.weights[b]]
    for label, w in zip(('Portfolio A', 'Portfolio B'), weights):
        mean, vol, _ = portfolio_metrics(w, run.model.mean, run.model.covariance)
        rows.append({'name': label, 'annual_arithmetic_return': mean * 12, 'annual_volatility': vol * np.sqrt(12),
                     'ongoing_fees': w @ run.model.fees, 'financing': w @ run.model.financing, 'status': 'Same run/constraints'})
    for label, ref in run.benchmarks.items():
        row = {'name': label, 'status': 'Fixed reference outside active constraints' if ref['available'] else ref['reason']}
        if ref['available']:
            row.update(annual_arithmetic_return=ref['mean'] * 12, annual_volatility=ref['volatility'] * np.sqrt(12),
                       ongoing_fees=ref['weights'] @ run.model.fees, financing=ref['weights'] @ run.model.financing)
        rows.append(row)
    return pd.DataFrame(rows).set_index('name')


def _safe_csv(frame):
    def escape(v):
        return "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v
    frame = frame.copy().map(escape)
    frame.index = frame.index.map(escape)
    frame.columns = frame.columns.map(escape)
    return frame.to_csv()


def research_zip(run, point, other, years, scenarios=None, convergence_check=None, usefulness=None):
    model, f = run.model, run.frontier
    w = f.weights[point]
    equity = model.snapshot.instruments.index[model.snapshot.instruments.category.isin(CATEGORIES[3:])]
    diversity, exposure = effective_companies(model.snapshot.holdings, full_weights(run, point), equity, model.leverage.to_dict())
    cov = pd.DataFrame(model.covariance, index=model.ids, columns=model.ids)
    vol = np.sqrt(np.diag(model.covariance))
    denominator = np.outer(vol, vol)
    corr = np.divide(model.covariance, denominator, out=np.full_like(model.covariance, np.nan), where=denominator > 0)
    all_weights = pd.DataFrame([full_weights(run, p) for p in range(len(f.weights))])
    all_weights.index.name = 'position'
    categories = categories_for(run, w).to_frame('weight')
    comparisons = comparison_table(run, point, other)
    tables = {'portfolio.csv': holdings_table(run, point), 'categories.csv': categories,
              'comparison.csv': comparisons, 'frontier.csv': pd.DataFrame({'position': np.arange(len(f.weights)),
              'target_monthly': f.targets, 'annual_arithmetic_return': f.returns * 12, 'annual_volatility': f.volatilities * np.sqrt(12), 'solver': f.solvers}),
              'frontier_weights.csv': all_weights, 'expected_returns.csv': pd.DataFrame({'monthly_mean': model.mean}, index=model.ids),
              'covariance.csv': cov, 'correlations.csv': pd.DataFrame(corr, index=model.ids, columns=model.ids),
              'factor_betas.csv': model.betas, 'factor_premiums.csv': model.premiums,
              'calibration_diagnostics.csv': model.diagnostics, 'costs.csv': pd.DataFrame({'fee': model.fees, 'financing': model.financing}),
              'exposures.csv': exposure.to_frame('economic_equity_exposure'), 'diversity.csv': pd.DataFrame([diversity]),
              'stress.csv': model.stress, 'source_status.csv': model.snapshot.status,
              'portfolio_stress.csv': stress_comparison(run, point, other),
              'comparison_weights.csv': pd.DataFrame({'A': full_weights(run, point), 'B': full_weights(run, other)})}
    if usefulness is not None:
        tables['universe_usefulness.csv'] = usefulness
    if model.mean_draws is not None:
        tables['bootstrap_mean_draws.csv'] = pd.DataFrame(model.mean_draws, columns=model.ids)
    if model.stress.empty:
        tables['stress.csv'] = pd.DataFrame({'status': ['Unavailable: verified rate/equity/FX shock exposures have not been supplied; no fabricated stress results']})
    if scenarios is not None:
        quantiles = horizon_quantiles(scenarios, f.weights)
        tables['horizon_quantiles.csv'] = pd.DataFrame(quantiles, columns=['P15.87', 'median', 'P84.13'])
        if scenarios.selected_paths is not None:
            tables['compounded_outcomes.csv'] = compound_summary(scenarios.selected_paths, years)
    else:
        tables['horizon_quantiles.csv'] = pd.DataFrame({'status': ['Unavailable: joint validated scenario inputs required']})
    policy = {'model_version': __version__, 'run_id': run.run_id, 'snapshot': model.snapshot.fingerprint,
              'position_A': point, 'position_B': other, 'years': years, 'return_statistic': '12 × monthly arithmetic mean; not CAGR',
              'rebalancing': 'monthly', 'currency': 'GBP', 'source_month': model.source_month,
              'fees': 'Historical actual net returns unchanged; gross factor forecast incremental fees charged once',
              'limitations': model.limitations, 'solver_max_violation': f.max_violation,
              'dust_tolerance': 1e-10, 'benchmark_policy': 'Fixed references outside active constraints',
              'scenarios': None if scenarios is None else {'seed': scenarios.seed, 'paths': scenarios.paths,
               'block': scenarios.block, 'estimation': scenarios.estimation, 'convergence': convergence_check}}
    policy['historical_reference_statistics']=model.historical_references
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    policy['model_commit'] = commit.stdout.strip() if commit.returncode == 0 else 'Unavailable in this runtime'
    code_digest = __import__('hashlib').sha256()
    for file in sorted((root / 'portfolio').rglob('*.py')):
        code_digest.update(str(file.relative_to(root)).encode()); code_digest.update(file.read_bytes())
    policy['model_python_source_sha256'] = code_digest.hexdigest()
    output = BytesIO()
    reproduction = inspect.getsource(optimiser)
    reproduction += '''\nif __name__ == '__main__':
    from pathlib import Path
    import json
    import pandas as pd
    root = Path(__file__).resolve().parent
    mu = pd.read_csv(root / 'expected_returns.csv', index_col=0).monthly_mean
    cov = pd.read_csv(root / 'covariance.csv', index_col=0).loc[mu.index, mu.index].to_numpy()
    allocation = pd.read_csv(root / 'portfolio.csv', index_col=0).loc[mu.index]
    policy = json.loads((root / 'constraints.json').read_text())
    excluded = {'Instant-access savings / cash': not policy['allow_cash'], 'Commodities': not policy['allow_commodities'], 'Leveraged ETFs / ETPs': not policy['allow_leverage'] or policy['leverage_cap'] == 0}
    excluded.update({c: True for c, cap in policy['category_caps'].items() if cap == 0})
    keep = np.array([not excluded.get(c, False) for c in allocation.category])
    levels = pd.read_csv(root / 'gross_exposures.csv', index_col=0).loc[mu.index].gross.to_numpy()
    cat = allocation.category.to_numpy()[keep]
    exposure = [(cat == 'Leveraged ETFs / ETPs').astype(float), levels[keep]]
    limits = [policy['leverage_cap'], policy['gross_cap']]
    for c, cap in policy['category_caps'].items():
        if cap > 0:
            exposure.append((cat == c).astype(float)); limits.append(cap)
    result = efficient_frontier(mu.to_numpy()[keep], cov[np.ix_(keep, keep)], cap=policy['fund_cap'], exposure=exposure, limits=limits)
    actual = pd.read_csv(root / 'frontier_weights.csv', index_col=0).loc[:, mu.index[keep]].to_numpy()
    np.testing.assert_allclose(result.weights, actual, atol=1e-6)
    print('All solved weights reproduced within 1e-6. Source ingestion/calibration requires original licensed sources.')
'''
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        for name, frame in tables.items():
            z.writestr(name, _safe_csv(frame))
        z.writestr('gross_exposures.csv', model.leverage.to_frame('gross').to_csv())
        z.writestr('assumptions.json', json.dumps(policy, indent=2, allow_nan=False))
        z.writestr('constraints.json', json.dumps(run.constraints, indent=2, allow_nan=False))
        z.writestr('manifest.json', json.dumps(model.snapshot.manifest, indent=2, allow_nan=False))
        public_fields = {'legal_structure','currency','native_currency','price_unit','inception','hedge','hedge_currency',
                         'fee','fee_source','identity_source','return_source','return_type','distribution_split_reconciled',
                         'reconciliation','reconciliation_warning','historical_return_policy','yield','yield_kind','yield_convention',
                         'bond_date','bond_source','duration','duration_convention','convexity','expected_loss','spread_duration',
                         'inflation','hedge_cost','hedge_embedded','provider','product','facility_type','aer','quote_date',
                         'minimum_balance','maximum_balance','instant_access','unlimited_withdrawals','introductory_bonus',
                         'eligibility','withdrawal_timing','rate_policy','protection','terms_source','rate_source',
                         'forecast_policy','term_premium_annual','assumption_label','annual_financing'}
        evidence = {i:{k:v for k,v in record.items() if k in public_fields} for i,record in model.snapshot.evidence.items()}
        z.writestr('asset_evidence.json', json.dumps(evidence,indent=2,allow_nan=False))
        methods = Path(__file__).resolve().parents[1] / 'docs/v7-methods-report.md'
        z.writestr('methods.md', methods.read_text())
        z.writestr('reproduce.py', reproduction)
        z.writestr('README.md', '# Reproduce this solve\n\nInstall the repository requirements on Python 3.14.8, extract this ZIP and run `python reproduce.py`. Matrices and every solved portfolio are included. Source histories are omitted by default because redistribution rights have not been established. The source manifest supplies hashes, URLs and terms. Reproducing the solve is distinct from independently rerunning ingestion and calibration. Horizon quantiles are conditional model outcomes, not confidence guarantees. Zero-volatility cash is conditional, not insured-safety evidence.\n')
    return output.getvalue()


def stress_comparison(run, a, b):
    """Weights applied to explicitly defined price channels; report known coverage."""
    rows=[]
    if run.model.stress.empty:
        return pd.DataFrame({'status':['No verified stress inputs']})
    for name, table in run.model.stress.groupby('scenario'):
        shocks=table.set_index('instrument').return_shock.reindex(run.model.ids)
        for label, point in [('A',a),('B',b)]:
            weights=run.frontier.weights[point]
            coverage=float(weights[shocks.notna().to_numpy()].sum())
            effect=float(weights @ shocks.fillna(0).to_numpy()) if coverage >= 1-1e-8 else None
            rows.append({'portfolio':label,'scenario':name,'instantaneous_price_shock':effect,
                         'known_weight_coverage':coverage,
                         'basis':'Isolated specified channel; non-target prices held fixed; no macro/causal guarantee' if effect is not None else 'Insufficient stress evidence for non-zero holdings'})
    return pd.DataFrame(rows)
