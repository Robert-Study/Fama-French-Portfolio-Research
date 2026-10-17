"""ECB reference rates: observed GBP per USD, no modelled FX observations."""
from io import BytesIO
import numpy as np
import pandas as pd
from portfolio.data import DataError

URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv'


def parse_ecb(raw):
    frame=pd.read_csv(BytesIO(raw))
    frame.columns=frame.columns.str.strip()
    if not {'Date','USD','GBP'}.issubset(frame):
        raise DataError('ECB EUR-base USD and GBP reference-rate columns required.')
    frame.index=pd.to_datetime(frame.Date,errors='raise')
    rates=frame[['USD','GBP']].apply(pd.to_numeric,errors='raise').sort_index()
    if rates.index.has_duplicates or not np.isfinite(rates.to_numpy()).all() or (rates<=0).any().any() or (rates.index.dayofweek >= 5).any():
        raise DataError('ECB reference rates contain missing or invalid observations.')
    return (rates.GBP/rates.USD).rename('GBP_per_USD')


def monthly_fx(levels):
    monthly=levels.groupby(levels.index.to_period('M')).last()
    # A current mid-month fixing is not a completed month-end observation.
    monthly=monthly[monthly.index < pd.Timestamp.today().to_period('M')]
    result=monthly.pct_change(fill_method=None).dropna()
    if result.empty:
        raise DataError('No completed ECB month-end return observations.')
    if not result.index.equals(pd.period_range(result.index[0],result.index[-1],freq='M')):
        raise DataError('Missing ECB FX months.')
    return result


XML_URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'


def parse_ecb_xml(raw):
    import xml.etree.ElementTree as ET
    if b'<!DOCTYPE' in raw.upper():
        raise DataError('Unexpected XML document type.')
    document=ET.fromstring(raw)
    rows=[]
    for element in document.iter():
        if 'time' not in element.attrib:
            continue
        rates={child.attrib.get('currency'):child.attrib.get('rate') for child in element}
        if 'USD' not in rates or 'GBP' not in rates:
            raise DataError('ECB date lacks required USD/GBP reference quotes.')
        rows.append({'Date':element.attrib['time'],'USD':rates['USD'],'GBP':rates['GBP']})
    if not rows:
        raise DataError('No ECB XML rate observations.')
    return parse_ecb(pd.DataFrame(rows).to_csv(index=False).encode())
