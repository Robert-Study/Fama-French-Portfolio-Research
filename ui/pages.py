"""Only the active page executes. Widget callbacks share one frontier position."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from portfolio.holdings import effective_companies
from portfolio.research import categories_for, full_weights
from portfolio.research_export import holdings_table, comparison_table, stress_comparison
from portfolio.scenarios import horizon_quantiles, compound_summary, historical_replay
from portfolio.validation import CATEGORIES, COLOURS
from ui.charts import frontier_chart, composition_chart, allocation_bar


def _sync(source, target, canonical):
    st.session_state[target] = st.session_state[source]
    st.session_state[canonical] = st.session_state[source]


def position_control(prefix, single=False):
    canonical, slider, numeric = prefix + '_position', prefix + '_slider', prefix + '_numeric'
    if canonical not in st.session_state:
        st.session_state[canonical] = 0 if single else 50
    if single:
        st.session_state[canonical] = 0
    for key in (slider, numeric):
        if key not in st.session_state:
            st.session_state[key] = st.session_state[canonical]
    st.caption(f'Frontier position {st.session_state[canonical]} / 100' + (' · single distinct portfolio' if single else ''))
    a, b = st.columns([5, 1])
    a.slider('Frontier position', 0, 100, key=slider, disabled=single,
             on_change=_sync, args=(slider, numeric, canonical), label_visibility='collapsed')
    b.number_input('Frontier position (numeric)', 0, 100, step=1, key=numeric, disabled=single,
                   on_change=_sync, args=(numeric, slider, canonical), label_visibility='collapsed')
    return 0 if single else st.session_state[canonical]


def show_benchmark_status(run=None, status=None):
    from portfolio.validation import BENCHMARKS
    if run is not None:
        unavailable = {label: r['reason'] for label, r in run.benchmarks.items() if not r['available']}
    else:
        unavailable = {label: 'Missing verified model inputs: ' + ', '.join(ids) for label, ids in BENCHMARKS.items()}
    if unavailable:
        with st.expander('Fixed reference availability', expanded=run is None):
            for label, reason in unavailable.items():
                st.write(label + ' — unavailable: ' + reason)
    st.caption('Fixed references remain independent of the portfolio switches and caps.')


def diversity_for(run, point):
    m = run.model
    equity = m.snapshot.instruments.index[m.snapshot.instruments.category.isin(CATEGORIES[3:])]
    return effective_companies(m.snapshot.holdings, full_weights(run, point), equity, m.leverage.to_dict())


def dashboard(run, point, scenarios, years):
    m = run.model
    w = run.frontier.weights[point]
    diversity, _ = diversity_for(run, point)
    metrics = st.columns(4)
    metrics[0].metric('Expected return, net (% p.a.)', f'{run.frontier.returns[point] * 12:.2%}', help='12 × monthly arithmetic mean, after modelled product expenses/financing; not CAGR. Unverified dealing spreads excluded.')
    metrics[1].metric('Annual volatility (%)', f'{run.frontier.volatilities[point] * np.sqrt(12):.2%}', help='One-period volatility; it does not shrink with display horizon.')
    metrics[2].metric('Ongoing product fees (% p.a.)', f'{w @ m.fees:.2%}', help=f'Included once in forecast. Modelled financing: {w @ m.financing:.2%} p.a.; underlying-fund costs reconciled separately.')
    diversity_value = 'N/A' if diversity['coverage'] is None else ('Insufficient coverage' if diversity['effective_companies'] is None else f"{diversity['effective_companies']:.1f}")
    metrics[3].metric('Effective companies', diversity_value, help='Equity sleeve only. ' + diversity['status'])
    left, right = st.columns([.65, .35])
    quantiles = None if scenarios is None else horizon_quantiles(scenarios, run.frontier.weights)
    with left:
        event = st.plotly_chart(frontier_chart(run, point, quantiles), use_container_width=True, on_select='rerun', selection_mode='points', key='frontier_' + run.run_id)
        # Selection is a rerun request, applied by the caller before widgets on next run.
        if event and event.selection.points:
            selected = event.selection.points[0]
            if selected.get('curve_number') == (2 if quantiles is not None else 0):
                target = int(selected['customdata'])
                selection_key = 'applied_chart_selection_' + run.run_id
                if target != point and st.session_state.get(selection_key) != target:
                    st.session_state[selection_key] = target
                    st.session_state['pending_curve_position'] = target
                    st.rerun()
        elif event:
            st.session_state.pop('applied_chart_selection_' + run.run_id, None)
        if scenarios is not None:
            st.caption(f'68% modelled range of horizon-average annual returns · {years} years · {scenarios.estimation}')
        else:
            st.caption('Horizon band unavailable: validated joint scenario evidence is required.')
    with right:
        values = categories_for(run, w)
        st.plotly_chart(allocation_bar(values), use_container_width=True)
        for category, value, colour in zip(CATEGORIES, values, COLOURS):
            label = 'Leveraged' if category == CATEGORIES[-1] else category
            st.markdown(f'<span style="color:{colour}">●</span> **{label}** {value:.2%}', unsafe_allow_html=True)
            st.progress(float(np.clip(value, 0, 1)))
    position_control(run.run_id + '_A', len(run.frontier.weights) == 1)
    st.plotly_chart(composition_chart(run), use_container_width=True)
    coverage = 'Unavailable' if diversity['coverage'] is None else f"{diversity['coverage']:.1%}"
    cash = m.snapshot.evidence.get('GBP_BANK_SAVINGS', {})
    st.caption(f"Common return month: {m.source_month or 'N/A'} · holdings: {diversity['as_of'] or 'unavailable'}, mapped equity coverage {coverage} · cash quote: {cash.get('quote_date', 'unavailable')}")
    show_benchmark_status(run)


def holdings(run, point):
    table = holdings_table(run, point)
    table = table.loc[table.weight > 0].sort_values('weight', ascending=False)
    st.subheader('Complete non-zero holdings')
    formatted = table.copy()
    formatted['weight'] = formatted.weight.map(lambda x: '<0.01%' if 0 < x < .0001 else f'{x:.2%}')
    for column in ['ongoing_charge', 'financing', 'annual_volatility_contribution']:
        formatted[column] = formatted[column].map(lambda x: f'{x:.2%}' if pd.notna(x) else 'Unknown')
    st.dataframe(formatted, width='stretch')
    st.caption('Solver dust below 1e-10 is removed and constraints rechecked. No positive holding is truncated.')
    diversity, exposure = diversity_for(run, point)
    with st.expander('Underlying companies and coverage'):
        st.write(diversity)
        st.dataframe(exposure.to_frame('Economic equity exposure'), width='stretch')
    with st.expander('Bond duration and factor diagnostics'):
        st.dataframe(run.model.betas, width='stretch')
        st.dataframe(run.model.diagnostics, width='stretch')
        st.dataframe(run.model.stress, width='stretch')


def compare(run, point, other, scenarios, years):
    st.subheader('Same-run portfolios and fixed references')
    st.dataframe(comparison_table(run, point, other).style.format(
        {name:'{:.2%}' for name in ['annual_arithmetic_return','annual_volatility','ongoing_fees','financing']},
        na_rep='Unavailable'), width='stretch')
    m = run.model
    weights = [run.frontier.weights[point], run.frontier.weights[other]]
    labels = ['Portfolio A', 'Portfolio B']
    for label, ref in run.benchmarks.items():
        if ref['available']:
            labels.append(label)
            weights.append(ref['weights'])
    actual_gbp = m.snapshot.manifest.get('provisional_policy', {}).get('actual_gbp_history', True)
    if len(m.history) and actual_gbp:
        wealth, drawdown = historical_replay(m.history, weights)
        dates = [str(m.history.index[0] - 1)] + list(m.history.index.astype(str))
        for title, values in [('Historical replay — index starts at 100', wealth), ('Historical drawdown', drawdown * 100)]:
            fig = go.Figure([go.Scatter(x=dates, y=values[:, j], name=label) for j, label in enumerate(labels)])
            fig.update_layout(title=title, height=280, margin=dict(t=40, b=0), legend=dict(itemclick=False, itemdoubleclick=False))
            st.plotly_chart(fig, use_container_width=True)
        st.caption('Replay of today’s fixed weights, rebalanced monthly over a common actual-data period; this is not a rolling out-of-sample strategy.')
    else:
        if not actual_gbp:
            st.info('Actual GBP historical replay unavailable: the model uses an explicitly labelled native-currency risk proxy.')
        else:
            st.info('Actual historical replay requires the source cache; this checkout retains calibrated matrices and diagnostics. Run the explicit refresh job to restore histories.')
    if scenarios is not None and scenarios.selected_paths is not None:
        summary = compound_summary(scenarios.selected_paths, years)
        summary.index = labels
        formatting = {column: ('{:.1f}' if column.startswith('Terminal') else '{:.1%}') for column in summary.columns}
        st.dataframe(summary.style.format(formatting), width='stretch')
        growth = go.Figure()
        for j, label in enumerate(labels):
            row = summary.iloc[j]
            growth.add_trace(go.Scatter(x=[label], y=[row['Terminal 100 median']], error_y=dict(type='data', symmetric=False, array=[row['Terminal 100 P84.13'] - row['Terminal 100 median']], arrayminus=[row['Terminal 100 median'] - row['Terminal 100 P15.87']]), mode='markers', name=label))
        growth.update_layout(title=f'{years}-year compounded terminal index · median and central 68% range', showlegend=False, height=280)
        st.plotly_chart(growth, use_container_width=True)
        a = np.prod(1 + scenarios.selected_paths[:, :, 0], axis=1)
        b = np.prod(1 + scenarios.selected_paths[:, :, 1], axis=1)
        difference = np.quantile((a - b) * 100, [.1587, .5, .8413])
        st.caption(f'Matching paths: probability A finishes below B {np.mean(a < b):.1%}; terminal-index difference P15.87/median/P84.13 {difference.round(2).tolist()}. Compounded CAGR differs from the arithmetic frontier band.')
    else:
        st.info('Compounded scenarios unavailable: joint validated paths required.')
    st.dataframe(m.stress, width='stretch')
    st.dataframe(stress_comparison(run,point,other).style.format(
        {'instantaneous_price_shock':'{:.1%}','known_weight_coverage':'{:.1%}'},na_rep='Unavailable'),width='stretch')
    st.caption('Stresses are isolated price channels, with non-target prices held fixed and explicit coverage. They are not full macro forecasts or backtest performance.')


def methods(root, snapshot, run=None):
    if (root / 'data/research/cash-policy.json').exists():
        st.info('Cash scope updated at the user’s request: the active reference is a separate UK bank savings account, outside Trading 212. The supplied report below describes the original planning cash facility; the source inventory records the current policy.')
    if snapshot.manifest.get('provisional_policy'):
        st.caption('Current provisional implementation: US RF proxies missing SONIA. ' + snapshot.manifest['provisional_policy']['bond_policy'] + '. The report is followed by actual calibration diagnostics and source limitations.')
    if snapshot.manifest.get('derived_model_inputs'):
        st.caption('This checkout retains derived calibrated inputs. Horizon paths use a labelled IID Gaussian joint-risk approximation; source refresh restores the synchronised-block path model and historical replay.')
    report = (root / 'docs/v7-methods-report.md').read_text()
    # Preserve the supplied equations, adapting only delimiters to Streamlit's KaTeX.
    report = report.replace('\\[', '$$').replace('\\]', '$$').replace('\\(', '$').replace('\\)', '$')
    st.markdown(report)
    with st.expander('Source inventory and admission gates', expanded=True):
        st.dataframe(snapshot.status, width='stretch')
        st.json(snapshot.manifest)
    if run is not None:
        with st.expander('Calibration, premiums and numerical diagnostics'):
            st.dataframe(run.model.diagnostics, width='stretch')
            st.dataframe(run.model.premiums, width='stretch')
            st.json(run.constraints)
            st.write(f'Maximum solver violation: {run.frontier.max_violation:.3g}')
            for limitation in run.model.limitations:
                st.write(limitation)
