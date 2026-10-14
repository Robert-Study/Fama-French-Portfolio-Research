"""Official BoE database CSV adapter. Access denial is reported, never bypassed."""
from io import BytesIO
import numpy as np
import pandas as pd
from portfolio.data import DataError

BASE = 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp'


def sonia_html_url(end=None):
    from datetime import date
    from urllib.parse import urlencode
    end = date.today() if end is None else end
    return 'https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?' + urlencode({
        'CSVF':'TT','DAT':'RNG','FD':1,'FM':'Jan','FY':1997,'SeriesCodes':'IUDSOIA',
        'TD':end.day,'TM':end.strftime('%b'),'TY':end.year,'UsingCodes':'Y','html.x':66,'html.y':26})


def parse_sonia_html(raw):
    from html.parser import HTMLParser
    import re
    class Cells(HTMLParser):
        def __init__(self):
            super().__init__(); self.rows=[]; self.row=[]; self.cell=None
        def handle_starttag(self, tag, attrs):
            if tag=='tr': self.row=[]
            if tag in ('td','th'): self.cell=''
        def handle_data(self, data):
            if self.cell is not None: self.cell+=data
        def handle_endtag(self, tag):
            if tag in ('td','th') and self.cell is not None:
                self.row.append(self.cell.strip()); self.cell=None
            if tag=='tr': self.rows.append(self.row)
    parser=Cells(); parser.feed(raw.decode('utf-8'))
    rows=[]
    for cells in parser.rows:
        if len(cells)>=2 and re.fullmatch(r'\d{1,2} [A-Za-z]{3} \d{2,4}', cells[0]):
            rows.append((pd.to_datetime(cells[0],dayfirst=True),float(cells[1].replace(',',''))))
    if not rows:
        raise DataError('BoE HTML has no dated SONIA observations.')
    result=pd.Series(dict(rows),name='SONIA_annual_percent',dtype=float).sort_index()
    if len(result)!=len(rows) or not np.isfinite(result).all() or (result.index.dayofweek>=5).any() or (result < -100).any():
        raise DataError('Duplicate/nonfinite/invalid SONIA observations.')
    return result


def sonia_months(rates):
    return _monthly_accrual(pd.DataFrame({'SONIA_annual_percent':rates})).rename('GBP_RF')


def csv_url(start='01/Jan/1997', end='now'):
    from urllib.parse import urlencode
    return BASE + '?' + urlencode({'csv.x':'yes','Datefrom':start,'Dateto':end,'SeriesCodes':'IUDERB6,IUDSOIA','CSVF':'TN','UsingCodes':'Y','VPD':'Y','VFD':'N'})


def parse_boe(raw):
    frame = pd.read_csv(BytesIO(raw))
    frame.columns = frame.columns.str.strip()
    if not {'DATE','IUDERB6','IUDSOIA'}.issubset(frame):
        raise DataError('BoE daily GBP-per-USD and SONIA database columns required.')
    dates = pd.to_datetime(frame.DATE,dayfirst=True,errors='raise')
    result = frame[['IUDERB6','IUDSOIA']].apply(pd.to_numeric,errors='raise')
    result.index = pd.DatetimeIndex(dates)
    result = result.sort_index()
    if result.index.has_duplicates or not np.isfinite(result.to_numpy()).all() or (result.IUDERB6 <= 0).any():
        raise DataError('Incomplete/invalid BoE observations; do not silently interpolate.')
    result.columns=['GBP_per_USD','SONIA_annual_percent']
    return result


def _monthly_accrual(daily):
    """Explicit calendar accrual and complete month-end FX levels.

    SONIA accrues to the next observation date at actual/365. Month boundaries
    split non-business-day accruals; the final rate needs a following date.
    """
    rates = []
    dates = []
    for i in range(len(daily)-1):
        start, stop = daily.index[i], daily.index[i+1]
        count = (stop-start).days
        if count < 1 or count > 7:
            raise DataError('Unexpected SONIA observation gap; verify calendar coverage.')
        rate = daily.iloc[i].SONIA_annual_percent / 100
        # Split by the ratio of accrued levels. The simple ACT/365 accrual
        # from the observation date telescopes exactly across month boundaries.
        for offset, day in enumerate(pd.date_range(start, periods=count, freq='D')):
            increment = (1 + rate * (offset+1) / 365) / (1 + rate * offset / 365) - 1
            dates.append(day); rates.append(increment)
    accrual = pd.Series(rates,index=pd.DatetimeIndex(dates))
    months = accrual.index.to_period('M')
    cash = (1+accrual).groupby(months).prod()-1
    coverage = accrual.groupby(months).size()
    cash = cash.loc[[m for m in cash.index if coverage[m] == m.days_in_month]]
    return cash


def cash_fx_months(daily):
    """Complete actual SONIA months and observed month-end GBP/USD returns."""
    cash = _monthly_accrual(daily)
    fx_levels = daily.GBP_per_USD.groupby(daily.index.to_period('M')).last()
    fx = fx_levels.pct_change(fill_method=None)
    common = cash.index.intersection(fx.dropna().index)
    out = pd.DataFrame({'GBP_RF':cash.loc[common],'USD_GBP':fx.loc[common]})
    out.index.name='Month'
    return out
