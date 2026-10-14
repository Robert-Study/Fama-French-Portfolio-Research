"""Private V7 research app. Public-data refresh is an explicit offline job."""
from pathlib import Path
import platform
import logging

import streamlit as st
from portfolio.deployment import missing_dependencies

st.set_page_config(page_title='Fama–French Portfolio Research', page_icon='📊', layout='wide')
missing = missing_dependencies()
if missing:
    st.error('Incomplete Python environment: ' + ', '.join(missing))
    st.caption(f'Python {platform.python_version()}; deployment target Python 3.14.8. Rebuild the pinned requirements.')
    st.stop()

import numpy as np
from portfolio import __version__
from portfolio.snapshot import load_snapshot, snapshot_fingerprint
from portfolio.research import prepare_model, solve_run
from portfolio.research_export import research_zip
from portfolio.scenarios import monthly_scenarios, matrix_scenarios, leveraged_horizon_scenarios, convergence
from portfolio.validation import CATEGORIES
from portfolio.sensitivity import useful_universe
from ui import pages

ROOT = Path(__file__).resolve().parent


@st.cache_data(show_spinner=False, max_entries=3)
def inputs(key, version):
    return load_snapshot(ROOT / 'data/research')


@st.cache_data(show_spinner=False, max_entries=3)
def fit(key, version, _snapshot):
    return prepare_model(_snapshot)


@st.cache_data(show_spinner=False, max_entries=10)
def solve(key, version, constraints, _model):
    return solve_run(_model, constraints)


@st.cache_data(show_spinner=False, max_entries=6)
def screening(run_id, version, _run):
    return useful_universe(_run)


@st.cache_data(show_spinner=False, max_entries=8)
def scenarios(run_id, years, a, b, paths, version, _run):
    model = _run.model
    if model.ids == ['GBP_BANK_SAVINGS']:
        raise ValueError('Future savings rates are unestimated; horizon ranges unavailable. The cash endpoint is conditional on the dated current rate.')
    weights = None
    if a >= 0:
        weights = [ _run.frontier.weights[a], _run.frontier.weights[b] ]
        weights += [r['weights'] for r in _run.benchmarks.values() if r['available']]
    if model.daily_months is not None:
        return leveraged_horizon_scenarios(model, years, paths=paths, selected_weights=weights,
                                           frontier_weights=_run.frontier.weights)
    if model.history.empty:
        return matrix_scenarios(model.mean, model.covariance, years, paths=paths,
                                mean_draws=model.mean_draws, selected_weights=weights)
    else:
        history = model.history.to_numpy()
    return monthly_scenarios(history, model.mean, years, paths=paths,
                             mean_draws=model.mean_draws, selected_weights=None if weights is None else np.array(weights))


st.markdown('### Fama–French Portfolio Research')
nav, export_col = st.columns([5, 1])
with nav:
    page = st.radio('Pages', ['Dashboard', 'Holdings', 'Compare', 'Methods'], horizontal=True, label_visibility='collapsed', key='page')
with export_col:
    export_requested = st.button('Export ZIP')
controls = st.columns([1, 1, 3])
with controls[0]:
    years = st.selectbox('Horizon (years)', [1, 5, 10, 20, 30], index=3)
with controls[1]:
    with st.popover('Constraints'):
        with st.form('constraints'):
            allow_cash = st.checkbox('Allow savings/cash', True)
            allow_commodities = st.checkbox('Allow commodities', True)
            allow_leverage = st.checkbox('Allow leverage', False)
            leverage_cap = st.number_input('Combined leverage cap (%)', 0.0, 100.0, 25.0) / 100
            gross_cap = st.number_input('Gross risky notional cap (%)', 0.0, 500.0, 150.0) / 100
            fund_cap = st.number_input('Individual fund cap (%)', 1.0, 100.0, 100.0) / 100
            category_caps = {}
            with st.expander('Category caps'):
                for category in CATEGORIES:
                    category_caps[category] = st.number_input(category + ' cap (%)', 0.0, 100.0, 100.0) / 100
            apply = st.form_submit_button('Apply')
requested = dict(allow_cash=allow_cash, allow_commodities=allow_commodities, allow_leverage=allow_leverage,
                 leverage_cap=leverage_cap, gross_cap=gross_cap, fund_cap=fund_cap, category_caps=category_caps)
root = ROOT / 'data/research'
pointer = root / '.cache/current.json'
key = (pointer.read_text() if pointer.exists() else 'no-snapshot') + snapshot_fingerprint(root)
try:
    snapshot = inputs(key, __version__)
except (OSError, ValueError) as exc:
    st.error('Snapshot validation failed: ' + str(exc))
    st.stop()
with controls[2]:
    st.caption(f'V7 · model {__version__} · snapshot {snapshot.fingerprint[:12]} · ' + snapshot.manifest.get('status', 'Dated evidence snapshot'))
run = st.session_state.get('active_run_v7')
if snapshot.manifest.get('provisional_policy'):
    policy = snapshot.manifest['provisional_policy']
    currency_note = 'Actual ECB GBP conversion.' if policy['actual_gbp_history'] else 'FX risk suppressed by assumption.'
    bond_note = 'Gilt carry uses a cash-based prior.' if policy.get('bond_carry_assumed', True) else 'Dated issuer gilt carry/duration.'
    if policy.get('historical_sonia_actual'):
        st.caption('Actual SONIA and GBP histories; forward SONIA held flat by assumption. Details and remaining exclusions on Methods.')
    else:
        st.warning('Provisional calibration: US RF proxies SONIA. ' + bond_note + ' ' + currency_note + ' Details on Methods.')
if apply or run is None or run.model.snapshot.fingerprint != snapshot.fingerprint:
    stage = 'loading calibrated model inputs'
    try:
        model = fit(snapshot.fingerprint, __version__, snapshot)
        stage = 'solving the constrained frontier'
        new_run = solve(snapshot.fingerprint, __version__, requested, model)
        st.session_state.active_run_v7 = new_run
        st.session_state.pop('v7_error', None)
        run = new_run
    except (ValueError, KeyError) as exc:
        st.session_state.v7_error = str(exc)
    except Exception as exc:
        logging.exception('V7 calculation failed')
        retained = ' Prior result retained.' if run is not None else ' No portfolio has been calculated.'
        st.session_state.v7_error = f'Failed while {stage}: {type(exc).__name__}: {exc}.' + retained
if st.session_state.get('v7_error'):
    st.error(st.session_state.v7_error)
    if run is not None:
        st.warning(f'Retained prior run {run.run_id}, with its prior settings: {run.constraints}')
if run is None:
    if page == 'Methods':
        pages.methods(ROOT, snapshot)
    else:
        st.info('No verified production estimates are available. The selected universe remains visible below; legacy demonstration inputs are not substituted.')
        for column, label in zip(st.columns(4), ['Expected return, net (% p.a.)', 'Annual volatility (%)', 'Ongoing product fees (% p.a.)', 'Effective companies']):
            column.metric(label, 'Unavailable')
        st.dataframe(snapshot.status, width='stretch')
        pages.show_benchmark_status()
        pages.position_control('unavailable', single=True)
    if export_requested:
        st.info('Research ZIP unavailable until at least one instrument has an admitted model and verified solve.')
    st.stop()
# A changed dataset must not present old results as its estimates.
snapshot = run.model.snapshot
single = len(run.frontier.weights) == 1
prefix = run.run_id + '_A'
if 'pending_curve_position' in st.session_state:
    selected = st.session_state.pop('pending_curve_position')
    for suffix in ('_position', '_slider', '_numeric'):
        st.session_state[prefix + suffix] = selected
if page == 'Dashboard':
    point = st.session_state.setdefault(prefix + '_position', 0 if single else 50)
else:
    point = pages.position_control(prefix, single)
other = st.session_state.get(run.run_id + '_B_position', 50 if not single else 0)
if page == 'Compare':
    st.caption('Portfolio B · same run, constraints and assumptions')
    other = pages.position_control(run.run_id + '_B', single)
scenario = None
check = None
if page in ('Dashboard', 'Compare') or export_requested:
    try:
        # Dashboard summaries share draws across every point; moving its slider
        # does not regenerate scenarios. Compound only selected portfolios on demand.
        a, b = (point, other) if page == 'Compare' or export_requested else (-1, -1)
        scenario = scenarios(run.run_id, years, a, b, 2000, __version__, run)
        # Required convergence check uses the same policy and independent sample size.
        second = scenarios(run.run_id, years, -1, -1, 5000, __version__, run)
        check = convergence(scenario, second, run.frontier.weights)
        if not check['passed']:
            st.warning('Scenario interval precision is insufficient at 2,000 versus 5,000 paths; range endpoints are provisional.')
        st.caption(scenario.estimation)
    except ValueError as exc:
        st.warning(str(exc))
if page == 'Dashboard':
    pages.dashboard(run, point, scenario, years)
elif page == 'Holdings':
    pages.holdings(run, point)
elif page == 'Compare':
    pages.compare(run, point, other, scenario, years)
else:
    pages.methods(ROOT, snapshot, run)
if export_requested:
    with st.spinner('Preparing reproducible calculations and predefined universe sensitivities…'):
        usefulness = screening(run.run_id, __version__, run)
        content = research_zip(run, point, other, years, scenario, check, usefulness)
    st.download_button('Download research ZIP', content, file_name=f'portfolio_{run.run_id}_{point}_{years}y.zip', mime='application/zip')
