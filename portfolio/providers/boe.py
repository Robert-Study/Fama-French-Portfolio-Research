"""Official BoE database CSV adapter. Access denial is reported, never bypassed."""
from io import BytesIO
import numpy as np
import pandas as pd
from portfolio.data import DataError

BASE = 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp'


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


def cash_fx_months(daily):
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
        # A single rate for n actual days accrues 1 + rate*n/365, not
        # (1 + rate/365)**n. Allocate geometrically across calendar boundaries.
        accrual = np.expm1(np.log1p(rate * count / 365) / count)
        for day in pd.date_range(start, periods=count, freq='D'):
            dates.append(day); rates.append(accrual)
    accrual = pd.Series(rates,index=pd.DatetimeIndex(dates))
    months = accrual.index.to_period('M')
    cash = (1+accrual).groupby(months).prod()-1
    coverage = accrual.groupby(months).size()
    cash = cash.loc[[m for m in cash.index if coverage[m] == m.days_in_month]]
    fx_levels = daily.GBP_per_USD.groupby(daily.index.to_period('M')).last()
    fx = fx_levels.pct_change(fill_method=None)
    common = cash.index.intersection(fx.dropna().index)
    out = pd.DataFrame({'GBP_RF':cash.loc[common],'USD_GBP':fx.loc[common]})
    out.index.name='Month'
    return out
