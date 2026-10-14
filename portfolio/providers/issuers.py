"""Public issuer histories. Acquisition does not itself admit a forward model."""
from dataclasses import dataclass, field
from io import BytesIO
import json
import numpy as np
import pandas as pd
from portfolio.data import DataError
from portfolio.providers.cache import fetch
from portfolio.providers.ishares import parse_ishares, Components

ISHARES = dict(SGLN=258441, SSLN=258443, IGLS=251804, IGLT=251806,
 INXG=251717, IS15=251840, SLXX=251839, IBTS=251715, IBTM=251716,
 IBTL=272124, ITPG=295697, GHYS=253488, SWDA=251882, EMIM=264659,
 IIND=297617, IASH=273192, IWDP=251801, IWFV=270048, IWFM=270051,
 IWFQ=270054, MVOL=251382, IWFS=270057, WLDS=296576, IUVF=285207,
 IEFV=272058, EMVL=297452)
VANGUARD = dict(VWRP='9679', VAGS='9685', VUSA='9503', VUKE='9509',
 VMID='9525', VERX='9524', VJPN='9504', VAPX='9522', VEMT='9664')
SPDR = dict(USSC='zprv-gy', ZPRX='zprx-gy', GLTL='sybl-gy')
WISDOMTREE = {'COPA':'1000073','AIGA':'1000063','CRUD':'1000076','GGRG':'1000422','3LUS':'1000395'}
NAV_QUERY = '''query HistoricalPricesQuery($portIds: [String!]!) {
 funds(portIds: $portIds) { portId profile { fundCurrency fundInceptionDate fundFullName }
 pricingDetails { navPrices(limit: -1) { items { price currencyCode asOfDate } } } } }'''
RETURN_QUERY = '''query Growth10kQuery($portIds: [String!]!) {
 polarisPerformanceHistory(portIds: $portIds) { monthlyReturns { totalReturns(limit: -1) {
 items { portId effectiveDate CMLT { _1MTH } } } } }
 funds(portIds: $portIds) { profile { fundCurrency fundInceptionDate fundFullName
 distributionStrategy currencyHedgingStrategy } } }'''
DISTRIBUTION_QUERY = '''query DistributionHistoryQuery($portIds: [String!]!, $startDate: String) {
 funds(portIds: $portIds) { portId distributionDetails { periodicDistributions(limit: 0, startDate: $startDate) {
 items { asOfDate exDividendDate recordDate payableDate reinvestPrice reinvestmentDate
 taxDetails { totalDistributionTypeName distributionLevelCode totalDistributionAmount distributionAmount
 distributionType { distCode distDesc } currencyCode } } } } } }'''


@dataclass
class IssuerHistory:
    metadata: dict
    nav: pd.Series
    returns: pd.Series
    sources: list
    audit: dict = field(default_factory=dict)
    holdings: pd.DataFrame = field(default_factory=pd.DataFrame)


def holdings_link(raw, url):
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urlparse
    class Anchors(HTMLParser):
        def __init__(self): super().__init__(); self.links=[]
        def handle_starttag(self,tag,attrs):
            href=dict(attrs).get('href','')
            if tag=='a' and urlparse(href).path.endswith('/latest-holdings.csv'):
                self.links.append(urljoin(url,href))
    parser=Anchors();parser.feed(raw.decode('utf-8'))
    return next(iter(parser.links),None)


def parse_ishares_holdings(raw, instrument):
    import csv
    from io import StringIO
    rows=list(csv.reader(StringIO(raw.decode('utf-8-sig'))))
    header=next((i for i,row in enumerate(rows) if 'Ticker' in row and 'Weight (%)' in row and 'Asset Class' in row),None)
    if header is None:raise DataError('iShares full holdings schema missing.')
    date=None
    for row in rows[:header]:
        if row and 'holdings as of' in row[0].lower() and len(row)>1:
            date=pd.to_datetime(row[1].replace('Sept','Sep'),dayfirst=True,errors='raise').date().isoformat()
    if date is None:raise DataError('Holdings economic date missing.')
    names=rows[header];records=[]
    for row in rows[header+1:]:
        if len(row)!=len(names):continue
        item=dict(zip(names,row))
        if item['Asset Class']!='Equity':continue
        weight=float(item['Weight (%)'].replace(',',''))/100
        if not np.isfinite(weight) or weight<0:raise DataError('Invalid equity holdings weight.')
        records.append(dict(instrument=instrument,company_id=None,weight=weight,as_of=date,
                            security_key='|'.join(item.get(k,'') for k in ('Ticker','Exchange','Market Currency')),
                            security_name=item.get('Name'),mapping_status='Unmapped; security key is not a company ID'))
    result=pd.DataFrame(records)
    if len(result) and result.weight.sum()>1.02:raise DataError('Holdings exceed fund equity exposure; reconciliation required.')
    # Rounded public weights can marginally exceed 100%; keep evidence out of
    # company calculations until reconciled rather than normalising it silently.
    if len(result) and result.weight.sum()>1+1e-6:raise DataError('Rounded book above 100%; exact economic weights needed for company coverage.')
    return result


def positive_levels(dates, values, date_format=None):
    index=pd.to_datetime(dates, format=date_format, errors='raise')
    levels=pd.Series(np.asarray(pd.to_numeric(values,errors='raise')),index=index,dtype=float).sort_index()
    if levels.index.has_duplicates or not np.isfinite(levels).all() or (levels<=0).any():
        raise DataError('Issuer levels must be unique, finite and positive.')
    return levels


def complete_nav_returns(nav, inception):
    levels=nav.groupby(nav.index.to_period('M')).last()
    # pct_change must not leap over a missing economic month.
    levels=levels.reindex(pd.period_range(levels.index[0],levels.index[-1],freq='M'))
    result=levels.pct_change(fill_method=None)
    result=result[(result.index>pd.Period(inception,freq='M')) &
                  (result.index<pd.Timestamp.today().to_period('M'))]
    return result


def vanguard_payload(raw):
    value=json.loads(raw)
    if value.get('errors') or not value.get('data'):
        raise DataError('Vanguard GraphQL rejected the verified public query: '+str(value.get('errors')))
    return value['data']


def ishares_annual_audit(parser, returns, currency):
    calendar=parser.components['performance']['containersByNameMap'].get('returns',{}).get('subContainersByNameMap',{}).get('calendar',{}).get('dataPointsByNameMap',{})
    types=calendar.get('returnTypes',{}).get('value',[])
    currencies=calendar.get('returnsByCurrency',{}).get('value',{})
    if 'annualNav' not in types or currencies.get('annualNav')!=currency:
        return dict(reconciliation_passed=False,annual_errors=[],reconciliation_warning='Published annual NAV return/currency schema unavailable')
    position=types.index('annualNav');errors=[]
    for name,point in calendar.items():
        if not name.endswith('Year') or not point.get('asOfDate'): continue
        year=int(str(point['asOfDate'])[:4]); months=returns.loc[returns.index.year==year]
        values=point.get('value')
        if len(months)!=12 or months.isna().any() or not isinstance(values,list) or len(values)<=position: continue
        try: official=float(values[position])/100
        except (ValueError,TypeError): continue
        realised=float((1+months).prod()-1)
        errors.append(dict(year=year,issuer_return=official,computed_return=realised,error_bp=(realised-official)*10000))
    maximum=max((abs(v['error_bp']) for v in errors),default=None)
    return dict(annual_errors=errors,annual_max_error_bp=maximum,
                reconciliation_passed=len(errors)>=3 and maximum<=10,
                reconciliation_warning=None if len(errors)>=3 and maximum<=10 else 'Annual issuer reconciliation exceeds 10bp trigger or fewer than three complete years; investigate valuation/corporate actions')


def distribution_amount(item, currency):
    rows=item['taxDetails']
    if any(r['currencyCode']!=currency for r in rows):raise DataError('Distribution currency mismatch.')
    totals={float(r['totalDistributionAmount']) for r in rows if r.get('totalDistributionAmount') is not None}
    if len(totals)>1:raise DataError('Ambiguous multiple distribution totals.')
    if totals:return totals.pop()
    # A single income row is unambiguous. Multiple tax components require a
    # documented total rather than guessing which amounts overlap.
    if len(rows)!=1 or rows[0].get('distributionAmount') is None:
        raise DataError('No unambiguous distribution total.')
    return float(rows[0]['distributionAmount'])


def parse_vanguard(nav_raw, return_raw, port, distribution_raw=None):
    nav_data=vanguard_payload(nav_raw); total_data=vanguard_payload(return_raw)
    fund=next(f for f in nav_data['funds'] if str(f['portId'])==str(port))
    # Both requests use one exact portId; a multi-port caller must join profiles.
    if len(total_data['funds']) != 1:
        raise DataError('Expected one Vanguard share class per request.')
    profile=total_data['funds'][0]['profile']
    points=fund['pricingDetails']['navPrices']['items']
    currencies={p['currencyCode'] for p in points}
    if currencies!={profile['fundCurrency']} or fund['profile']['fundInceptionDate']!=profile['fundInceptionDate']:
        raise DataError('Vanguard NAV/profile currency or inception mismatch.')
    nav=positive_levels([p['asOfDate'] for p in points],[p['price'] for p in points])
    points=[p for book in total_data['polarisPerformanceHistory'] for p in book['monthlyReturns']['totalReturns']['items'] if str(p['portId'])==str(port)]
    series=pd.Series([np.nan if p['CMLT']['_1MTH'] is None else float(p['CMLT']['_1MTH'])/100 for p in points],
                     index=pd.PeriodIndex([p['effectiveDate'] for p in points],freq='M')).sort_index()
    if series.index.has_duplicates or np.isinf(series).any() or (series<=-1).any():
        raise DataError('Invalid Vanguard monthly actual total returns.')
    inception=profile['fundInceptionDate']
    series=series[(series.index>pd.Period(inception,freq='M')) & (series.index<pd.Timestamp.today().to_period('M'))]
    accumulating=profile['distributionStrategy']=='Accumulating Income'
    check=complete_nav_returns(nav,inception).dropna()
    distribution_audit={}
    if not accumulating and distribution_raw is not None:
        from portfolio.providers.history import total_returns
        rows=vanguard_payload(distribution_raw)['funds'][0]['distributionDetails']['periodicDistributions']['items']
        payouts=pd.Series(0.0,index=nav.index);seen=set();outside=0
        for item in rows:
            date=pd.Timestamp(item['exDividendDate'])
            if date in seen: raise DataError('Duplicate distribution ex-date.')
            seen.add(date)
            if date<nav.index[0] or date>nav.index[-1]:outside+=1;continue
            if date not in nav.index:raise DataError('Distribution ex-date absent from NAV history.')
            if pd.Timestamp(item['reinvestmentDate'])!=date:raise DataError('Issuer reinvestment/ex-date convention differs.')
            payouts.loc[date]=distribution_amount(item,profile['fundCurrency'])
        daily=total_returns(nav,payouts,unit=profile['fundCurrency'])
        check=(1+daily).groupby(daily.index.to_period('M')).prod()-1
        check=check[(check.index>nav.index[0].to_period('M')) & (check.index<pd.Timestamp.today().to_period('M'))]
        distribution_audit=dict(distribution_records=len(rows),records_before_nav_coverage=outside,
                                income_policy='Ex-date closing NAV reinvestment; total rows not added to tax components')
    common=check.index.intersection(series.index)
    discrepancy=float((check.loc[common]-series.loc[common]).abs().max()) if len(common) else None
    metadata=dict(native_currency=profile['fundCurrency'],inception=inception,
                  use_of_income='Accumulating' if accumulating else 'Distributing',
                  hedge='hedged' if profile['currencyHedgingStrategy']=='Full Portfolio Hedge' else 'unhedged',
                  structure='UCITS ETF',fund_name=profile['fundFullName'])
    audit=dict(series_basis='Issuer own-share-class monthly total returns; percent divided once',
               nav_overlap_months=len(common),nav_max_monthly_difference=discrepancy,
               reconciliation_passed=bool((accumulating or distribution_raw is not None) and len(common)>=36 and discrepancy is not None and discrepancy<=.001),
               reconciliation_warning=None if accumulating or distribution_raw is not None else 'Distributing class: income/ex-date and issuer annual-return reconciliation pending',**distribution_audit)
    return metadata,nav,series,audit


def parse_spdr(raw, isin):
    book=pd.read_excel(BytesIO(raw),header=None)
    text=' '.join(str(v) for v in book.iloc[:8].to_numpy().ravel())
    if isin not in text:
        raise DataError('SPDR workbook ISIN mismatch.')
    header=next((i for i,row in book.iterrows() if 'Date' in row.values and 'NAV' in row.values),None)
    if header is None: raise DataError('SPDR NAV header missing.')
    cols=list(book.iloc[header]); date_col=cols.index('Date'); nav_col=cols.index('NAV')
    rows=book.iloc[header+1:]
    valid=rows.iloc[:,date_col].astype(str).str.fullmatch(r'\d{2}-[A-Za-z]{3}-\d{4}')
    rows=rows.loc[valid]
    return positive_levels(rows.iloc[:,date_col],rows.iloc[:,nav_col],'%d-%b-%Y'),text


def parse_spdr_holdings(raw, isin, instrument):
    book=pd.read_excel(BytesIO(raw),header=None)
    if isin not in ' '.join(str(v) for v in book.iloc[:5].to_numpy().ravel()):
        raise DataError('SPDR holdings share-class ISIN mismatch.')
    date=next((row[1] for row in book.itertuples(index=False,name=None) if str(row[0]).strip()=='Holdings As Of:'),None)
    if date is None:raise DataError('SPDR holdings date missing.')
    as_of=pd.to_datetime(date,format='%d-%b-%Y').date().isoformat()
    header=next((i for i,row in book.iterrows() if 'ISIN' in row.values and 'Percent of Fund' in row.values),None)
    if header is None:raise DataError('SPDR holdings columns missing.')
    data=book.iloc[header+1:].copy();data.columns=book.iloc[header]
    data=data.loc[data['ISIN'].astype(str).str.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]')]
    weights=pd.to_numeric(data['Percent of Fund'],errors='raise')/100
    if not np.isfinite(weights).all() or (weights<0).any() or weights.sum()>1+1e-6:
        raise DataError('Invalid SPDR holdings weights.')
    return pd.DataFrame(dict(instrument=instrument,company_id=None,weight=weights.to_numpy(),as_of=as_of,
                             security_key=data['ISIN'].to_numpy(),security_name=data['Security Name'].to_numpy(),
                             mapping_status='Unmapped security ISIN; company/share-class consolidation required'))


def parse_invesco(raw, isin):
    value=json.loads(raw)
    if value.get('isin')!=isin: raise DataError('Invesco ISIN mismatch.')
    series=next(p for p in value['lineChartData'] if p['type']=='Shareclass')
    nav=positive_levels([p['date'] for p in series['data']],[p['value'] for p in series['data']])
    return nav,value


def parse_wisdomtree(raw):
    book=pd.read_excel(BytesIO(raw),header=None)
    rows=[]
    for row in book.itertuples(index=False,name=None):
        cells=[v for v in row if pd.notna(v)]
        if len(cells)>=2 and isinstance(cells[0],str) and len(cells[0])==10:
            try:
                date=pd.to_datetime(cells[0],format='%Y-%m-%d',errors='raise')
            except ValueError: continue
            rows.append((date,float(cells[1])))
    if not rows: raise DataError('WisdomTree NAV rows absent.')
    return positive_levels([p[0] for p in rows],[p[1] for p in rows])


def parse_dws(raw, isin):
    book=pd.ExcelFile(BytesIO(raw)); levels=None
    for sheet in book.sheet_names:
        frame=pd.read_excel(book,sheet_name=sheet,header=None)
        for i,row in frame.iterrows():
            if 'Date' in row.values and 'NAV' in row.values:
                cols=list(row); data=frame.iloc[i+1:]; dc=cols.index('Date'); nc=cols.index('NAV')
                data=data.loc[data.iloc[:,dc].astype(str).str.fullmatch(r'\d{2}\.\d{2}\.\d{4}')]
                levels=positive_levels(data.iloc[:,dc],data.iloc[:,nc],'%d.%m.%Y')
                break
    if levels is None: raise DataError('DWS actual NAV table absent.')
    # The exact ISIN is in the HTTPS resource; retain it in source identity.
    return levels


def reconcile_dws_chart(nav, raw):
    value=json.loads(raw)
    configs=value['seriesConfiguration']
    columns=[i for i,c in enumerate(configs) if c['chartType']=='Nav' and c['identifier']=='NAV (USD)']
    if len(columns)!=1:raise DataError('DWS exact USD fund NAV chart column not identified.')
    col=columns[0];rows=value['values']
    chart=positive_levels(pd.to_datetime([r[0] for r in rows],unit='ms'),[r[1][col][0] for r in rows])
    common=nav.index.intersection(chart.index)
    error=float((nav.loc[common]/chart.loc[common]-1).abs().max()) if len(common) else None
    max_move=float(nav.pct_change(fill_method=None).abs().max())
    # Four early workbook/chart quotes differ by <=0.0004 USD (<=0.386bp).
    # Declare a conservative 1bp NAV consistency trigger, retain the observed
    # discrepancy, and do not describe this as an exact equality audit.
    tolerance=.0001
    passed=bool(len(common)>=60 and error is not None and error<=tolerance and not value.get('flags') and max_move<=.5)
    return dict(reconciliation_passed=passed,nav_chart_overlap_days=len(common),nav_chart_max_relative_error=error,
                maximum_absolute_daily_move=max_move,issuer_chart_flags=value.get('flags'),
                nav_consistency_tolerance=tolerance,
                series_basis='Capitalising own fund NAV; issuer USD NAV chart/workbook consistency within declared 1bp trigger; net product costs unchanged',
                reconciliation_warning='Issuer chart consistency and anomaly screen do not establish a complete independent corporate-action audit; forecast mechanics remain unavailable')


def acquire(ident, isin, cache):
    sources=[]
    def get(url, **kwargs):
        raw,source=fetch(url,cache,'Issuer public fund data; raw redistribution not established',False,max_age_days=7,**kwargs)
        source['id']='issuer:'+ident+':'+str(len(sources)); sources.append(source); return raw
    if ident in ISHARES:
        url=f'https://www.ishares.com/uk/individual/en/products/{ISHARES[ident]}/'
        raw=get(url)
        meta,index,nav,returns=parse_ishares(raw,isin)
        parser=Components(); parser.feed(raw.decode())
        accumulating=meta['use_of_income'] in ('Accumulating','No Income')
        if accumulating: returns=complete_nav_returns(nav,meta['inception'])
        audit=ishares_annual_audit(parser,returns,meta['native_currency'])
        audit['series_basis']='Accumulating/no-income NAV' if accumulating else 'Issuer reinvested fund growth; published annual fund returns checked'
        meta['hedge']='hedged' if ident in ('ITPG','GHYS') else 'unhedged'
        book=pd.DataFrame();link=holdings_link(raw,url)
        if link and ident not in ('SGLN','SSLN'):
            try:
                book=parse_ishares_holdings(get(link),ident)
                audit['holdings_acquisition']=dict(url=link,rows=len(book),company_mapping='Unavailable',
                                                  as_of=None if book.empty else book.as_of.iloc[0])
            except Exception as exc:
                audit['holdings_acquisition']=dict(url=link,error=type(exc).__name__+': '+str(exc),company_mapping='Unavailable')
        return IssuerHistory(meta,nav,returns,sources,audit,book)
    if ident in VANGUARD:
        url='https://www.vanguard.co.uk/gpx/graphql';port=VANGUARD[ident]
        args=dict(method='POST',headers={'Content-Type':'application/json','X-Consumer-ID':'uk2'})
        a=get(url,json_body={'query':NAV_QUERY,'variables':{'portIds':[port]}},**args)
        b=get(url,json_body={'query':RETURN_QUERY,'variables':{'portIds':[port]}},**args)
        profile=vanguard_payload(b)['funds'][0]['profile']
        distribution=None
        if profile['distributionStrategy']!='Accumulating Income':
            distribution=get(url,json_body={'query':DISTRIBUTION_QUERY,'variables':{'portIds':[port],'startDate':'1990-01-01'}},**args)
        meta,nav,returns,audit=parse_vanguard(a,b,port,distribution)
        return IssuerHistory(meta,nav,returns,sources,audit)
    if ident in SPDR:
        raw=get(f'https://www.ssga.com/library-content/products/fund-data/etfs/emea/navhist-emea-en-{SPDR[ident]}.xlsx')
        nav,text=parse_spdr(raw,isin)
        currency=next((c for c in ('GBP','USD','EUR') if c in text),None)
        if currency is None: raise DataError('SPDR NAV currency absent.')
        meta=dict(native_currency=currency,inception=nav.index[0].date().isoformat(),use_of_income='Distributing' if ident=='GLTL' else 'Accumulating',hedge='unhedged',structure='UCITS ETF')
        audit=dict(reconciliation_passed=ident!='GLTL',series_basis='Own accumulating NAV' if ident!='GLTL' else 'NAV only; missing distributions')
        book=pd.DataFrame();url=f'https://www.ssga.com/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-{SPDR[ident]}.xlsx'
        try:
            book=parse_spdr_holdings(get(url),isin,ident)
            audit['holdings_acquisition']=dict(url=url,rows=len(book),as_of=None if book.empty else book.as_of.iloc[0],company_mapping='Unavailable')
            if ident=='GLTL':book=pd.DataFrame() # Bond issuers are not equity companies.
        except Exception as exc:audit['holdings_acquisition']=dict(url=url,error=type(exc).__name__+': '+str(exc))
        return IssuerHistory(meta,nav,complete_nav_returns(nav,meta['inception']),sources,audit,book)
    if ident in ('CMOP','EQQQ'):
        nav,value=parse_invesco(get(f'https://dng-api.invesco.com/cache/v1/accounts/en_GB/shareclasses/{isin}/performance/rolling?idType=isin&variationType=ALL&baseline=10000'),isin)
        meta=dict(native_currency=value['currency'],inception=value['inceptionDate'][:10],use_of_income='Distributing' if ident=='EQQQ' else 'Accumulating',hedge='unhedged',structure='UCITS ETF')
        return IssuerHistory(meta,nav,complete_nav_returns(nav,meta['inception']),sources,dict(reconciliation_passed=ident=='CMOP',series_basis='Issuer actual share-class growth; annual return/income audit pending'))
    if ident in WISDOMTREE:
        from datetime import date
        raw=get(f'https://www.wisdomtree.com/api/fund-history/{WISDOMTREE[ident]}/historical-data-export',method='POST',headers={'Content-Type':'application/json'},json_body=dict(locale='en-GB',productName=ident,fromDate='1990-01-01',toDate=date.today().isoformat(),includeNav=True,includeAum=False))
        nav=parse_wisdomtree(raw)
        meta=dict(native_currency='USD',inception=nav.index[0].date().isoformat(),hedge='unhedged',structure='Issuer NAV export; legal facts to reconcile')
        return IssuerHistory(meta,nav,complete_nav_returns(nav,meta['inception']),sources,dict(reconciliation_passed=False,series_basis='Rounded native NAV; currency and corporate-action audit pending'))
    if ident=='XS2D':
        from datetime import date
        raw=get(f'https://etf.dws.com/api/pdp/en-gb/etf/{isin}/historicaldata/download?startDate=2010-03-18&endDate={date.today().isoformat()}&includeTax=true')
        nav=parse_dws(raw,isin)
        chart=get(f'https://etf.dws.com/api/pdp/en-gb/etf/{isin}/performancechart')
        meta=dict(native_currency='USD',inception='2010-03-18',hedge='unhedged',use_of_income='Accumulating',structure='UCITS ETF')
        return IssuerHistory(meta,nav,complete_nav_returns(nav,meta['inception']),sources,reconcile_dws_chart(nav,chart))
    raise DataError('Full actual history endpoint remains unresolved for '+ident)
