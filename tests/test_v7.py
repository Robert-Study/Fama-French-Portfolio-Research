"""Synthetic fixtures are restricted to tests; production never loads them."""
from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import json
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from portfolio.bundle import FACTORS, convert_factors_to_gbp
from portfolio.holdings import effective_companies
from portfolio.models.bonds import bond_forecast, bond_stress
from portfolio.models.cash import cash_monthly
from portfolio.models.commodities import commodity_forecast
from portfolio.models.equity import fit_equity, specifications_for
from portfolio.models.leveraged import LeverageTerms, daily_leverage, overlap_error
from portfolio.optimise import efficient_frontier
from portfolio.premiums import estimate_premiums, shrink, premium_sensitivities
from portfolio.providers.french import parse_french, regional_gbp
from portfolio.providers.history import total_returns, to_gbp, monthly_returns, compounded_sonia
from portfolio.research import Model, solve_run, full_weights, categories_for, prepare_model
from portfolio.research_export import research_zip, holdings_table, comparison_table
from portfolio.scenarios import iid_band, monthly_scenarios, horizon_quantiles, compound_summary, joint_daily_months, leveraged_horizon_scenarios
from portfolio.snapshot import load_snapshot, Snapshot
from portfolio.validation import CATEGORIES, admission, check_covariance

ROOT = Path(__file__).resolve().parents[1]


def zip_csv(text):
    output = BytesIO()
    with ZipFile(output, 'w') as z:
        z.writestr('factors.csv', text)
    return output.getvalue()


def test_french_monthly_percentage_missing_codes_and_annual_rows():
    raw = zip_csv('Description\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n199001,1,-99.99,3,4,5,.1\n199002,1,2,3,4,5,.1\n199003,2,3,4,5,6,.2\n\nAnnual Factors\n1990,12,2,3,4,5,.5\n')
    result = parse_french(raw, 'Emerging')
    assert len(result) == 2
    assert str(result.index[0]) == '1990-02'
    assert result.iloc[0]['Mkt-RF'] == .01
    assert result.iloc[0].RF == .001
    assert result.attrs['region'] == 'Emerging'
    with pytest.raises(ValueError, match='Interior'):
        parse_french(zip_csv('199001,1,2,3,4,5,.1\n199002,-999,2,3,4,5,.1\n199003,1,2,3,4,5,.1\n'), 'Emerging')


def test_fx_long_short_not_standalone_fx_and_region_ids():
    index = pd.period_range('2020-01', periods=2, freq='M')
    usd = pd.DataFrame([[.1,.02,.03,.04,.05,.001]] * 2, index=index, columns=FACTORS + ['RF'])
    fx = pd.DataFrame({'GBP_RF': [.002,.003], 'USD_GBP': [.1,-.1]}, index=index)
    gbp = convert_factors_to_gbp(usd, fx)
    assert gbp.iloc[0].SMB == pytest.approx(.022)
    assert gbp.iloc[0]['Mkt-RF'] == pytest.approx(1.101 * 1.1 - 1 - .002)
    joint = regional_gbp({'Developed':usd, 'Emerging':usd}, fx)
    assert 'Developed:HML' in joint and 'Emerging:HML' in joint


def test_distribution_split_and_gbx_currency_conventions():
    dates = pd.date_range('2020-01-01', periods=3)
    nav = pd.Series([10000,5100,5100], index=dates)
    income = pd.Series([0,0,100], index=dates)
    split = pd.Series([1,2,1], index=dates)
    actual = total_returns(nav, income, split, unit='GBX')
    np.testing.assert_allclose(actual, [.02,100/5100])
    pd.testing.assert_series_equal(to_gbp(actual, 'GBX'), actual)
    with pytest.raises(ValueError, match='twice'):
        to_gbp(actual, 'GBP', actual)
    np.testing.assert_allclose(to_gbp(actual, 'USD', pd.Series(.1,index=actual.index)), (1 + actual) * 1.1 - 1)


def test_sonia_calendar_day_compounding():
    dates = pd.to_datetime(['2026-08-03','2026-08-04'])
    rates = pd.Series(.04,index=dates)
    days = pd.Series([1,3],index=dates)
    result = compounded_sonia(rates,days)
    assert result.iloc[0] == pytest.approx((1 + .04/365) * (1 + .04*3/365) - 1)


def test_equity_selection_never_uses_final_holdout_and_retains_region():
    rng = np.random.default_rng(91)
    dates = pd.period_range('2016-09',periods=120,freq='M')
    columns = ['Developed:' + f for f in FACTORS]
    x = pd.DataFrame(rng.normal(0,.03,(120,5)),index=dates,columns=columns)
    cash = pd.Series(.001,index=dates)
    returns = cash + x.iloc[:,0] * .8 + x.iloc[:,1] * .3 + rng.normal(0,.003,120)
    specs = specifications_for(['Developed'])
    a = fit_equity(returns,x,cash,specs)
    changed = returns.copy(); changed.iloc[-12:] += 1
    b = fit_equity(changed,x,cash,specs)
    assert (a.specification,a.penalty) == (b.specification,b.penalty)
    assert a.diagnostic['validation_rmse'] == b.diagnostic['validation_rmse']
    assert a.diagnostic['holdout_rmse'] != b.diagnostic['holdout_rmse']
    assert all(c.startswith('Developed:') for c in a.betas.index)
    assert a.diagnostic['months'] == 120
    with pytest.raises(ValueError,match='72'):
        fit_equity(returns.iloc[-60:],x,cash,specs)


def test_prior_shrinkage_preserves_sign_and_correlated_uncertainty():
    sample = np.array([-.03,.04]); covariance = np.array([[.01,.002],[.002,.02]])
    estimates, posterior, regularisation = shrink(sample,covariance,[.05,.02])
    assert estimates[0] < 0
    assert np.linalg.eigvalsh(posterior).min() > 0 and regularisation > 0
    prior = np.diag(np.square([.05,.02]))
    expected = np.linalg.solve(np.linalg.inv(covariance + np.eye(2)*regularisation) + np.linalg.inv(prior), np.linalg.solve(covariance + np.eye(2)*regularisation,sample))
    np.testing.assert_allclose(estimates,expected)
    x = pd.DataFrame(np.random.default_rng(1).normal(0,.03,(180,2)),columns=['Europe:Mkt-RF','Europe:HML'])
    p = estimate_premiums(x,paths=500)
    assert p.prior_scales.tolist() == [.05,.02]
    assert 'market_+0.02' in premium_sensitivities(p)


def test_cash_bond_and_commodity_fees_charged_once():
    assert (1 + cash_monthly(.05))**12 == pytest.approx(1.05)
    assert bond_forecast(.04,.002,expected_loss=.005) == pytest.approx(.033/12)
    assert bond_forecast(.01,.002,yield_kind='real',inflation=.03) == pytest.approx((1.01*1.03-1-.002)/12)
    with pytest.raises(ValueError,match='inflation'):
        bond_forecast(.01,.002,yield_kind='real')
    with pytest.raises(ValueError,match='twice'):
        bond_forecast(.04,.002,hedge_cost=.003,hedge_embedded=True)
    assert bond_stress(10,.01,80) == pytest.approx(-.096)
    assert bond_stress(10,-.01,80) > 0
    assert commodity_forecast(.003,.002) == pytest.approx(.003-.002/12)


def test_daily_leverage_same_endpoint_currency_funding_and_absorbing_loss():
    r = np.array([.1, 1/1.1-1])
    assert np.prod(1+r) == pytest.approx(1)
    for level, loss in [(2,-.01818181818),(3,-.05454545455)]:
        terms = LeverageTerms(level,0,365)
        out = daily_leverage(r,0,terms)
        assert np.prod(1+out)-1 == pytest.approx(loss)
    fx = np.array([.1,-.02])
    out = daily_leverage(r,0,LeverageTerms(2,0,365),fx)
    assert out[0] == pytest.approx(1.2*1.1-1)
    assert out[0] != pytest.approx(2*((1.1*1.1)-1))
    terminated = daily_leverage([-.6,.5,.2],0,LeverageTerms(2,0,365))
    np.testing.assert_allclose(terminated,[-1,0,0])
    assert np.prod(1+terminated) == 0
    with pytest.raises(ValueError,match='twice'):
        daily_leverage(r,.0001,LeverageTerms(2,0,365,funding_embedded=True))
    with pytest.raises(ValueError,match='Intraday'):
        daily_leverage(r,0,LeverageTerms(2,0,365,intraday_reset=True))
    fees = daily_leverage(np.zeros(60),.0001,LeverageTerms(2,.00365,365))
    np.testing.assert_allclose(fees,-.00011)
    assert overlap_error(fees,fees)['daily_rmse'] == 0


def test_daily_joint_cross_covariance_and_long_horizon_no_resurrection():
    rng = np.random.default_rng(9)
    panel = pd.DataFrame({'U':rng.normal(.0002,.01,500), 'B':rng.normal(0,.002,500), 'F':np.full(500,.0001)})
    spec = dict(underlying='U', funding='F', terms=LeverageTerms(2,.001,365))
    joint = joint_daily_months(panel,{'U':.0002,'B':.0001},[spec],paths=300,months=12)
    assert joint.shape == (300,12,3)
    c = np.cov(joint.reshape(-1,3),rowvar=False)
    assert c[0,2] > 0
    check_covariance(c)
    config = dict(core_forward={'U':.0002,'B':.0001}, specs=[spec],selected=[0,1,2],cash_mean=None)
    model = SimpleNamespace(ids=['U','B','L'],daily_config=config,snapshot=SimpleNamespace(daily=panel))
    result = leveraged_horizon_scenarios(model,1,paths=50,selected_weights=[[0,0,1]])
    assert result.horizon_averages.shape == (50,3)
    assert result.selected_paths.shape == (50,12,1)


def test_horizon_average_not_cagr_volatility_unchanged_and_estimation_floor():
    assert iid_band(.07,.18,1) == pytest.approx((-.11,.25))
    assert iid_band(.07,.18,20) == pytest.approx((.029750776,.110249224))
    rng = np.random.default_rng(12)
    history = rng.normal(0,.04,(300,1))
    draws = rng.normal(.005,.002,(3000,1))
    one = monthly_scenarios(history,[.005],1,paths=5000,block=1,mean_draws=draws)
    twenty = monthly_scenarios(history,[.005],20,paths=5000,block=1,mean_draws=draws)
    assert twenty.horizon_averages.std() > .02
    # IID monthly path variance / M plus a mean draw fixed for the whole horizon.
    expected = 12 * np.sqrt(history.var() / 240 + draws.var())
    assert twenty.horizon_averages.std() == pytest.approx(expected, rel=.06)
    assert twenty.horizon_averages.std() > one.horizon_averages.std()/np.sqrt(20)*1.15
    same = monthly_scenarios(history,[.005],1,paths=500,selected_weights=[[1],[1]])
    np.testing.assert_allclose(same.selected_paths[:,:,0],same.selected_paths[:,:,1])
    summary = compound_summary(np.full((500,12,1),.01),1)
    assert summary.iloc[0]['Median CAGR'] == pytest.approx(1.01**12-1)
    assert summary.iloc[0]['Median CAGR'] != pytest.approx(.12)


def test_synchronised_blocks_preserve_serial_dependence():
    x = np.repeat(np.array([-.04,.04]*20),12).reshape(-1,1)
    a = monthly_scenarios(x,[0],1,paths=3000,block=1)
    b = monthly_scenarios(x,[0],1,paths=3000,block=12)
    assert b.horizon_averages.std() > a.horizon_averages.std()*1.5


def test_effective_company_count_duplicate_funds_and_coverage():
    today = date.today().isoformat()
    h = pd.DataFrame({'instrument':['A']*100, 'company_id':[str(i) for i in range(100)], 'weight':[.01]*100,'as_of':[today]*100})
    a, _ = effective_companies(h,{'A':1},['A'])
    assert a['effective_companies'] == pytest.approx(100)
    second = h.copy(); second.instrument='B'
    merged = pd.concat([h,second])
    b,_ = effective_companies(merged,{'A':.5,'B':.5},['A','B'],{'A':2,'B':2})
    assert b['effective_companies'] == pytest.approx(100)
    small = h.iloc[:3].copy(); small.weight=[.5,.25,.25]
    c,_ = effective_companies(small,{'A':.5,'CASH':.5},['A'])
    assert c['effective_companies'] == pytest.approx(8/3)
    low = h.iloc[:90]
    d,_ = effective_companies(low,{'A':1},['A'])
    assert d['effective_companies'] is None and d['coverage'] == pytest.approx(.9)
    non_equity,_ = effective_companies(h,{'CASH':1},['A'])
    assert non_equity['effective_companies'] is None and non_equity['coverage'] is None


@pytest.fixture
def model():
    snapshot = load_snapshot(ROOT/'data/research')
    ids = ['GBP_BANK_SAVINGS','SGLN','VAGS','VWRP','XS2D']
    mean = np.array([.03,.04,.045,.08,.11])/12
    c = np.diag(np.square([0,.15,.07,.18,.35]))/12
    rng=np.random.default_rng(21)
    history=pd.DataFrame(rng.multivariate_normal(mean,c,120),index=pd.period_range('2016-09',periods=120,freq='M'),columns=ids)
    snapshot.status.loc[ids,'Status']='Admitted research model'
    snapshot.status.loc[ids,'Reason']=''
    return Model(ids,mean,c,history,pd.Series([0,.001,.002,.002,.006],index=ids),pd.Series(0.,index=ids),
                 pd.Series([0,1,1,1,2],index=ids),pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),snapshot,None,
                 ['Synthetic test fixture only'],pd.DataFrame(),source_month='2026-08')


def test_switches_gross_caps_cash_endpoint_benchmarks_and_full50(model):
    run=solve_run(model,{'allow_leverage':True})
    assert run.frontier.weights[0,0] == pytest.approx(1,abs=1e-6)
    assert run.frontier.volatilities[0] == pytest.approx(0,abs=1e-9)
    assert run.frontier.weights[:,4].max() <= .25+1e-6
    assert (run.frontier.weights @ model.leverage <= 1.5+1e-6).all()
    assert len(run.frontier.weights)==101
    assert full_weights(run,50).shape==(50,)
    assert categories_for(run,run.frontier.weights[50]).sum()==pytest.approx(1)
    excluded=solve_run(model,{'allow_cash':False,'allow_commodities':False})
    assert np.all(excluded.frontier.weights[:,[0,1,4]]==0)
    assert excluded.benchmarks['2× US equities']['available']
    assert excluded.benchmarks['Savings / cash']['available']
    assert excluded.run_id != run.run_id
    with pytest.raises(ValueError):
        solve_run(model,{'fund_cap':.1})
    assert run.frontier.targets[-1]==pytest.approx(run.frontier.returns[-1],abs=1e-7)


def test_highest_return_deterministic_minimum_variance_tiebreak():
    f=efficient_frontier([.001,.002],np.zeros((2,2)))
    assert len(f.weights)==1
    np.testing.assert_allclose(f.weights[0],[0,1],atol=1e-7)


def test_complete_nonzero_holdings_and_export_reproduces_all_solved_points(model,tmp_path):
    run=solve_run(model,{'allow_leverage':True})
    s=monthly_scenarios(model.history.to_numpy(),model.mean,1,paths=300,selected_weights=[run.frontier.weights[50],run.frontier.weights[100]])
    raw=research_zip(run,50,100,1,s)
    with ZipFile(BytesIO(raw)) as z:
        assert {'README.md','methods.md','portfolio.csv','frontier_weights.csv','assumptions.json','horizon_quantiles.csv','reproduce.py'}.issubset(z.namelist())
        z.extractall(tmp_path)
        portfolio=pd.read_csv(BytesIO(z.read('portfolio.csv')),index_col=0)
        assert len(portfolio)==50
        np.testing.assert_allclose(portfolio.weight,full_weights(run,50))
        matrix=pd.read_csv(BytesIO(z.read('covariance.csv')),index_col=0)
        np.testing.assert_allclose(matrix,model.covariance)
        assumptions=json.loads(z.read('assumptions.json'))
        assert assumptions['position_B']==100 and assumptions['model_version']=='0.2.0'
    result=subprocess.run([sys.executable,str(tmp_path/'reproduce.py')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    table=holdings_table(run,50)
    assert set(table[table.weight>0].index)==set(full_weights(run,50)[lambda w:w>0].index)
    assert comparison_table(run,50,50).loc['Portfolio A','annual_arithmetic_return']==comparison_table(run,50,50).loc['Portfolio B','annual_arithmetic_return']


def test_missing_snapshot_never_substitutes_legacy_estimates(tmp_path,monkeypatch):
    import shutil
    import streamlit as st
    import portfolio.snapshot as snapshot_module
    for name in ('instruments.csv','cash-policy.json'):
        shutil.copy(ROOT/'data/research'/name,tmp_path/name)
    snapshot=load_snapshot(tmp_path)
    assert len(snapshot.instruments)==50
    assert snapshot.returns.empty
    assert snapshot.status.Status.eq('Blocked').all()
    with pytest.raises(ValueError,match='No instrument'):
        prepare_model(snapshot)
    st.cache_data.clear()
    monkeypatch.setattr(snapshot_module,'load_snapshot',lambda *a,**k:snapshot)
    app=AppTest.from_file(ROOT/'app.py',default_timeout=30).run()
    assert not app.exception
    assert all(m.value=='Unavailable' for m in app.metric)
    app.radio[0].set_value('Methods').run()
    assert not app.exception
    assert any('Efficient-frontier research' in md.value for md in app.markdown)
    assert not app.metric
    st.cache_data.clear()


def test_slider_numeric_sync_single_and_no_refit_on_slider(model,tmp_path):
    # Exercise actual UI with a synthetic model only through a test harness.
    harness=tmp_path/'ui_test.py'
    harness.write_text('''import streamlit as st
from ui.pages import position_control
position_control('A')
position_control('B')
''')
    app=AppTest.from_file(harness).run()
    for value in (0,50,100):
        app.number_input[0].set_value(value).run()
        assert app.slider[0].value==value
        app.slider[1].set_value(value).run()
        assert app.number_input[1].value==value
    assert not app.exception
    harness.write_text("from ui.pages import position_control\nposition_control('only',single=True)\n")
    single=AppTest.from_file(harness).run()
    assert single.slider[0].disabled and single.number_input[0].disabled


def test_admission_rejects_preinception_fee_unknown_and_cash_quote():
    snapshot=load_snapshot(ROOT/'data/research')
    row=snapshot.instruments.loc['VWRP']
    dates=pd.period_range('2020-09',periods=72,freq='M')
    returns=pd.DataFrame({'VWRP':np.zeros(72)},index=dates)
    e=dict(legal_structure='UCITS',currency='GBP',price_unit='GBX',inception='2020-09-01',hedge='unhedged',fee=.002,
           fee_source='test',identity_source='test',return_source='test',return_type='actual_share_class_net_total',distribution_split_reconciled=True)
    assert any('inception' in reason for reason in admission(row,e,returns,{'test'},date(2026,10,12)))
    e['inception']='2020-08-01'
    assert admission(row,e,returns,{'test'},date(2026,10,12))==[]
    e['fee']=None
    assert any('charge' in reason for reason in admission(row,e,returns,{'test'},date(2026,10,12)))
    cash=snapshot.instruments.loc['GBP_BANK_SAVINGS']
    ce=dict(facility_type='uk_bank_deposit',provider='Synthetic test bank',eligibility='UK adult residents',
            instant_access=True,unlimited_withdrawals=True,introductory_bonus=False,
            linked_current_account_required=False,quote_date='2026-10-01',aer=.03,terms_source='test',rate_source='test')
    assert admission(cash,ce,returns,{'test'},date(2026,10,12))==[]
    assert admission(cash,ce,returns,{'test'},date(2026,12,12))


def test_boe_calendar_accrual_splits_month_boundaries_and_ecb_quotes():
    from portfolio.providers.boe import cash_fx_months, parse_boe
    from portfolio.providers.ecb import parse_ecb, monthly_fx
    dates=pd.bdate_range('2026-07-01','2026-09-02')
    daily=pd.DataFrame({'GBP_per_USD':.75,'SONIA_annual_percent':4.},index=dates)
    result=cash_fx_months(daily)
    assert list(result.index.astype(str))==['2026-08'] # first FX return requires preceding month
    expected=1.
    for start,stop in zip(dates[:-1],dates[1:]):
        days=(stop-start).days
        count=sum(day.month==8 for day in pd.date_range(start,periods=days))
        expected*=(1+.04*days/365)**(count/days)
    assert result.GBP_RF.iloc[0]==pytest.approx(expected-1)
    csv=b'Date,USD,GBP\n2026-08-03,1.2,0.8\n2026-08-04,1.25,0.81\n'
    rates=parse_ecb(csv)
    assert rates.iloc[0]==pytest.approx(.8/1.2)
    with pytest.raises(ValueError):
        parse_ecb(b'Date,USD,GBP\n2026-08-02,1.2,0.8\n')


def test_provisional_policies_are_explicit_and_strict_mode_stays_blocked():
    snapshot=load_snapshot(ROOT/'data/research')
    row=snapshot.instruments.loc['IGLT']
    dates=pd.period_range('2020-09',periods=72,freq='M')
    returns=pd.DataFrame({'IGLT':np.zeros(72)},index=dates)
    e=dict(legal_structure='UCITS',currency='GBP',price_unit='GBP',inception='2006-12-01',hedge='unhedged',fee=.001,
           fee_source='test',identity_source='test',return_source='test',return_type='actual_share_class_net_total',distribution_split_reconciled=True,
           forecast_policy='cash_plus_zero_term_premium',forecast_source='test',forecast_assumption_date='2026-10-12',term_premium_annual=0.)
    strict=admission(row,e,returns,{'test'},date(2026,10,12))
    assert any('bond yield' in reason for reason in strict)
    assert admission(row,e,returns,{'test'},date(2026,10,12),provisional=True)==[]


def test_savings_parser_keeps_notice_rates_separate_and_requires_no_bonus_terms():
    from portfolio.providers.savings import parse_htb
    text='''<p>Easy Access Online Saver (Issue 99) AER 4.18 % Min investment £ 1 Max investment £ 250,000
Unlimited withdrawals managed variable rate permanent resident of the United Kingdom minimum balance
nominated bank account Financial Services Compensation Scheme</p><p>95 Day Online Notice 5.50%</p>'''
    quote=parse_htb(text.encode(), '2026-10-12')
    assert quote['aer']==.0418 and quote['maximum_balance']==250000
    assert quote['introductory_bonus'] is False
    with pytest.raises(ValueError):
        parse_htb(text.replace('Unlimited withdrawals','bonus 12 months').encode(),'2026-10-12')


def test_full_four_page_ui_uses_same_run_exports_only_on_demand(model,monkeypatch):
    import streamlit as st
    import portfolio.snapshot as snapshot_module
    import portfolio.research as research_module
    st.cache_data.clear()
    monkeypatch.setattr(snapshot_module,'load_snapshot',lambda *a,**k:model.snapshot)
    monkeypatch.setattr(research_module,'prepare_model',lambda *a,**k:model)
    app=AppTest.from_file(ROOT/'app.py',default_timeout=30).run()
    assert not app.exception
    assert len(app.metric)==4
    first=app.session_state['active_run_v7'].run_id
    for value in (0,50,100):
        app.number_input[-1].set_value(value).run()
        assert not app.exception
        assert app.slider[0].value==value
        assert app.session_state['active_run_v7'].run_id==first
    assert not app.get('download_button')
    app.radio[0].set_value('Holdings').run()
    assert not app.exception
    assert len(app.dataframe[0].value)>0
    app.radio[0].set_value('Compare').run()
    assert not app.exception
    app.number_input[-1].set_value(0).run()
    assert app.slider[-1].value==0
    app.radio[0].set_value('Methods').run()
    assert not app.exception
    assert any('Efficient-frontier research' in item.value for item in app.markdown)
    # The on-demand ZIP runs sensitivity solves; shared CI runners need more time.
    app.button[0].click().run(timeout=90)
    assert not app.exception
    assert len(app.get('download_button'))==1
    st.cache_data.clear()


def test_comparable_return_solve_and_universe_screen(model):
    from portfolio.sensitivity import useful_universe
    run=solve_run(model)
    targets=run.frontier.returns[[0,50,100]]
    exact=solve_run(model,targets_monthly=targets)
    np.testing.assert_allclose(exact.frontier.volatilities,run.frontier.volatilities[[0,50,100]],atol=1e-7)
    with pytest.raises(ValueError,match='infeasible'):
        solve_run(model,targets_monthly=[model.mean.max()+.1])
    screen=useful_universe(run,bootstrap_draws=0)
    assert len(screen)==50
    assert 'max_removal_annual_volatility_increase' in screen
    assert screen.loc['EMIM','review'].startswith('Unavailable')


def test_recursive_holdings_company_shareclass_merging_and_unknown_coverage():
    from portfolio.holdings import expand_company_holdings
    today=date.today().isoformat()
    graph={'WRAPPER':{'FUND':1.0},'FUND':{'A1':.5,'A2':.25,'B':.2}}
    rows=expand_company_holdings(['WRAPPER'],graph,{'A1':'A','A2':'A','B':'B'},today)
    result,_=effective_companies(rows,{'WRAPPER':1},['WRAPPER'],{'WRAPPER':3})
    assert result['coverage']==pytest.approx(.95)
    assert result['effective_companies']==pytest.approx(1/((.75/.95)**2+(.2/.95)**2))
    with pytest.raises(ValueError,match='Cyclic'):
        expand_company_holdings(['A'],{'A':{'B':1},'B':{'A':1}},{},today)


def test_ecb_xml_cross_rate_preserves_real_gbp_currency_units():
    from portfolio.providers.ecb import parse_ecb_xml,monthly_fx
    xml=b'<Envelope><Cube><Cube time="2026-08-31"><Cube currency="USD" rate="1.2"/><Cube currency="GBP" rate="0.8"/></Cube><Cube time="2026-09-30"><Cube currency="USD" rate="1.25"/><Cube currency="GBP" rate="0.81"/></Cube></Cube></Envelope>'
    levels=parse_ecb_xml(xml)
    assert levels.iloc[0]==pytest.approx(.8/1.2)
    assert monthly_fx(levels).iloc[0]==pytest.approx((.81/1.25)/(.8/1.2)-1)


def test_derived_matrix_checkout_reproduces_risk_and_labels_approximation(model,tmp_path):
    import shutil
    from dataclasses import replace
    from portfolio.portable import save_derived_model
    from portfolio.scenarios import matrix_scenarios
    model=replace(model,ids=model.ids[:4],mean=model.mean[:4],covariance=model.covariance[:4,:4],
                  history=model.history.iloc[:,:4],fees=model.fees.iloc[:4],financing=model.financing.iloc[:4],leverage=model.leverage.iloc[:4])
    for name in ('instruments.csv','cash-policy.json'):
        shutil.copy(ROOT/'data/research'/name,tmp_path/name)
    save_derived_model(model,tmp_path)
    restored=prepare_model(load_snapshot(tmp_path))
    assert restored.history.empty
    np.testing.assert_allclose(restored.mean,model.mean)
    np.testing.assert_allclose(restored.covariance,model.covariance)
    run=solve_run(restored)
    same=solve_run(model)
    np.testing.assert_allclose(run.frontier.weights,same.frontier.weights,atol=1e-8)
    scenarios=matrix_scenarios(restored.mean,restored.covariance,1,paths=3000,selected_weights=[[0,0,0,1]])
    assert 'IID Gaussian' in scenarios.estimation
    assert scenarios.horizon_averages[:,3].std()==pytest.approx(.18,rel=.06)


def test_committed_dashboard_without_raw_cache(tmp_path, monkeypatch):
    """Exercise the actual shipped inputs, not the synthetic model fixture."""
    import shutil
    import streamlit as st
    import portfolio.portable as portable
    from portfolio.validation import age_days
    monkeypatch.setattr(portable, 'age_days', lambda value: age_days(value, date(2026,10,12)))
    for folder in ('portfolio', 'ui', 'docs'):
        shutil.copytree(ROOT/folder, tmp_path/folder, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(ROOT/'app.py', tmp_path/'app.py')
    data = tmp_path/'data/research'
    data.mkdir(parents=True)
    for source in (ROOT/'data/research').iterdir():
        if source.is_file():
            shutil.copy(source, data/source.name)
    assert not (data/'.cache').exists()
    snapshot = load_snapshot(data)
    assert snapshot.evidence['IWFV']['fee'] > 0
    assert snapshot.status.loc['IWFV', 'Status'] == 'Calibration supplied; validation pending'
    st.cache_data.clear()
    app = AppTest.from_file(tmp_path/'app.py', default_timeout=60).run()
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 4
    assert all(metric.value != 'Unavailable' for metric in app.metric[:3])
    assert len(app.session_state['active_run_v7'].model.ids) == 4
    st.cache_data.clear()
    import portfolio.research as research
    def fail_solve(*args, **kwargs):
        raise RuntimeError('injected hosted solver failure')
    monkeypatch.setattr(research, 'solve_run', fail_solve)
    failed = AppTest.from_file(tmp_path/'app.py', default_timeout=60).run()
    assert not failed.exception
    assert 'solving the constrained frontier: RuntimeError: injected hosted solver failure' in failed.error[0].value
    assert 'Prior result retained' not in failed.error[0].value
    assert 'No portfolio has been calculated' in failed.error[0].value
    status = load_snapshot(data).status
    assert status.loc['SGLN', 'Reason'] == ''
    st.cache_data.clear()


def test_already_leveraged_net_funding_index_is_not_multiplied_or_financed_twice():
    terms=LeverageTerms(2,.00365,365,funding_embedded=True,input_kind='leveraged_index_net_funding')
    out=daily_leverage([.2,-.1],0,terms)
    np.testing.assert_allclose(out,[.19999,-.10001])
    with pytest.raises(ValueError,match='twice'):
        daily_leverage([.2,-.1],.0001,terms)


def test_signed_hedge_carry_and_post_termination_portfolio_rebalance():
    from portfolio.scenarios import survivor_rebalanced_paths
    assert bond_forecast(.04,.002,hedge_cost=-.003)==pytest.approx(.041/12)
    paths=np.array([[[.001,-1],[.001,0],[.001,0]]])
    actual=survivor_rebalanced_paths(paths,[[.5,.5],[0,1],[1,0]])
    np.testing.assert_allclose(actual[0,:,0],[-.4995,.001,.001])
    np.testing.assert_allclose(actual[0,:,1],[-1,0,0])
    assert np.prod(1+actual[0,:,1])==0
    assert np.prod(1+actual[0,:,0])==pytest.approx(.5005*1.001**2)


def test_dated_issuer_bond_characteristics_and_stress_coverage(model):
    from html import escape
    from portfolio.providers.ishares import parse_ishares
    from portfolio.research_export import stress_comparison
    facts={'isin':{'value':'TEST'},'seriesBaseCurrencyCode':{'value':'GBP'},'inceptionDate':{'value':20200101},
           'emeaMgt':{'value':.07},'useOfProfitsCode':{'value':'Distributing'}}
    series={'asOfDate':[20260803,20260804],'value':[100,101]}
    components=[{'componentId':'keyFundFacts','containersByNameMap':{'default':{'dataPointsByNameMap':facts}}},
                {'componentId':'performance','containersByNameMap':{'chart':{'dataPointsByNameMap':{'currencySymbol':{'value':'GBP'},'performanceData':series,'navData':series}}}},
                {'componentId':'fundamentalsAndRisk','containersByNameMap':{'default':{'dataPointsByNameMap':{'yieldToWorst':{'value':5.2,'asOfDate':20261009,'label':'Weighted Average YTM'},'modelOad':{'value':6.93642,'asOfDate':20261009,'label':'Effective Duration'}}}}}]
    html=''.join('<walrus componentprops="'+escape(json.dumps(c),quote=True)+'"></walrus>' for c in components)
    meta,*_=parse_ishares(html.encode(),'TEST')
    assert meta['bond_characteristics']['yield']==pytest.approx(.052)
    assert meta['bond_characteristics']['duration']==pytest.approx(6.93642)
    assert meta['bond_characteristics']['date']=='2026-10-09'
    model.stress=pd.DataFrame({'instrument':['VWRP'],'scenario':['equity -20%'],'return_shock':[-.2]})
    run=solve_run(model)
    table=stress_comparison(run,0,100)
    assert table.loc[table.portfolio.eq('A'),'instantaneous_price_shock'].isna().all()
    assert table.loc[table.portfolio.eq('B'),'instantaneous_price_shock'].iloc[0]==pytest.approx(-.2)
