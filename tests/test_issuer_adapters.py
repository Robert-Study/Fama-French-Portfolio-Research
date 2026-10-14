"""Issuer identity/units and cash accrual tests; fixtures are synthetic only."""
from io import BytesIO
import json
import numpy as np
import pandas as pd
import pytest

from portfolio.providers.boe import parse_sonia_html, sonia_months
from portfolio.providers.issuers import (positive_levels, complete_nav_returns, distribution_amount,
    parse_vanguard, parse_spdr, parse_dws, reconcile_dws_chart, parse_ishares_holdings)
from portfolio.references import historical_references


def test_levels_do_not_align_excel_row_numbers_to_dates():
    levels=positive_levels(pd.Series(['2026-01-02','2026-01-05'],index=[6,7]),pd.Series([10,11],index=[6,7]))
    assert levels.tolist()==[10,11]
    with pytest.raises(ValueError,match='unique'):
        positive_levels(['2026-01-02']*2,[10,11])


def test_missing_month_is_not_a_multi_month_return_or_zero():
    nav=positive_levels(['2026-01-30','2026-03-31','2026-04-30'],[10,12,13])
    result=complete_nav_returns(nav,'2025-01-01')
    assert np.isnan(result.loc['2026-02']) and np.isnan(result.loc['2026-03'])
    assert result.loc['2026-04']==pytest.approx(13/12-1)


def test_distribution_total_is_not_added_to_tax_components():
    item={'taxDetails':[dict(currencyCode='USD',totalDistributionAmount=1,distributionAmount=.8),
                        dict(currencyCode='USD',totalDistributionAmount=1,distributionAmount=.2)]}
    assert distribution_amount(item,'USD')==1
    with pytest.raises(ValueError,match='currency'):
        distribution_amount(item,'GBP')
    item['taxDetails'][1]['totalDistributionAmount']=2
    with pytest.raises(ValueError,match='Ambiguous'):
        distribution_amount(item,'USD')


def test_sonia_html_units_and_month_boundary_accrued_levels():
    raw=b'<table><tr><td>02 Jan 26</td><td>4.00</td></tr><tr><td>05 Jan 26</td><td>4.10</td></tr></table>'
    rates=parse_sonia_html(raw)
    assert rates.iloc[0]==4.0 # annual percent, not decimal yet
    with pytest.raises(ValueError,match='Duplicate'):
        parse_sonia_html(raw.replace(b'</table>',b'<tr><td>02 Jan 26</td><td>4.00</td></tr></table>'))
    # Jan 31, 2025 is Friday. Its 3-day simple accrual straddles February.
    dates=pd.bdate_range('2025-01-01','2025-03-03')
    data=pd.Series(4.,index=dates)
    cash=sonia_months(data)
    expected=(1+.04*3/365)/(1+.04/365) # February 1–2, accrued-level ratio
    for start,stop in zip(dates[:-1],dates[1:]):
        if start.month!=2:continue
        days=min((stop-start).days,(pd.Timestamp('2025-03-01')-start).days)
        expected*=1+.04*days/365
    assert cash.loc['2025-02']==pytest.approx(expected-1,abs=1e-14)
    assert pd.Period('2025-03',freq='M') not in cash.index


def test_excel_parsers_require_selected_isin_and_explicit_nav_column():
    workbook=BytesIO()
    pd.DataFrame([['ISIN:','IE0000000001'],['NAV Currency:','USD'],['Date','NAV'],
                  ['05-Jan-2026',11],['02-Jan-2026',10]]).to_excel(workbook,index=False,header=False)
    series,_=parse_spdr(workbook.getvalue(),'IE0000000001')
    assert series.tolist()==[10,11]
    with pytest.raises(ValueError,match='ISIN'):
        parse_spdr(workbook.getvalue(),'IE0000000002')
    workbook=BytesIO()
    pd.DataFrame([['Date','Index Level','NAV'],['05.01.2026',999,11],['02.01.2026',888,10]]).to_excel(workbook,index=False,header=False)
    assert parse_dws(workbook.getvalue(),'LU0000000001').tolist()==[10,11]


def test_leveraged_history_reconciliation_is_separate_from_forward_terms():
    dates=pd.bdate_range('2026-01-01',periods=70)
    nav=pd.Series(np.linspace(100,110,70),index=dates)
    chart={'seriesConfiguration':[{'chartType':'Nav','identifier':'NAV (USD)'},
                                  {'chartType':'Index','identifier':'Index'}],
           'values':[[int(d.timestamp()*1000),[[float(v),float(v),0],[999,999,0]]] for d,v in nav.items()],
           'flags':[]}
    audit=reconcile_dws_chart(nav,json.dumps(chart).encode())
    assert audit['reconciliation_passed'] and audit['nav_chart_overlap_days']==70
    chart['flags']=['possible corporate action']
    assert not reconcile_dws_chart(nav,json.dumps(chart).encode())['reconciliation_passed']


def test_holdings_security_keys_do_not_invent_company_ids():
    raw=b'Fund Holdings as of,13/Oct/2026\nTicker,Name,Asset Class,Weight (%),Exchange,Market Currency\nABC,Example,Equity,90,LSE,GBP\nCASH,Cash,Cash,10,-,GBP\n'
    book=parse_ishares_holdings(raw,'SWDA')
    assert book.company_id.isna().all() and len(book)==1
    assert book.weight.iloc[0]==.9 and book.security_key.iloc[0]=='ABC|LSE|GBP'


def test_historical_benchmark_does_not_require_admitted_forward_model():
    from types import SimpleNamespace
    returns=pd.DataFrame({'VWRP':np.tile([.01,-.005,.02],12),'VAGS':np.tile([.002,-.001,.003],12)},
                         index=pd.period_range('2023-01',periods=36,freq='M'))
    snapshot=SimpleNamespace(returns=returns,evidence={i:dict(distribution_split_reconciled=True) for i in returns})
    references=historical_references(snapshot)
    assert references['Bonds']['available']
    assert references['Global 60/40']['available']
    actual=.6*returns.VWRP+.4*returns.VAGS
    assert references['Global 60/40']['annual_arithmetic_mean']==pytest.approx(actual.mean()*12)
