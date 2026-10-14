"""Public iShares embedded issuer series; strict ISIN and currency reconciliation.

Use the issuer's performance index, not exchange close-price tables. Data remains
native-currency evidence until actual GBP FX alignment and share-class conventions
are established. No automatic admission is implied by parsing a product page.
"""
from html.parser import HTMLParser
import json
import numpy as np
import pandas as pd
from portfolio.data import DataError


class Components(HTMLParser):
    def __init__(self):
        super().__init__()
        self.components = {}

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'componentprops' and value:
                try:
                    data = json.loads(value)
                except ValueError:
                    continue
                if isinstance(data, dict) and 'componentId' in data:
                    # Responsive pages repeat components; an empty final copy
                    # must not erase the complete data-bearing component.
                    previous = self.components.get(data['componentId'], {})
                    if len(json.dumps(data)) > len(json.dumps(previous)):
                        self.components[data['componentId']] = data


def _series(point):
    dates = pd.to_datetime([str(v) for v in point['asOfDate']], format='%Y%m%d', errors='raise')
    series = pd.Series(pd.to_numeric(point['value'], errors='raise'), index=dates, dtype=float)
    if series.index.has_duplicates or not series.index.is_monotonic_increasing or not np.isfinite(series).all() or (series <= 0).any():
        raise DataError('Invalid ordered positive issuer series.')
    return series


def parse_ishares(raw, expected_isin):
    parser = Components()
    parser.feed(raw.decode('utf-8'))
    try:
        facts = parser.components['keyFundFacts']['containersByNameMap']['default']['dataPointsByNameMap']
        values = {key: point.get('value') for key, point in facts.items()}
        if values.get('isin') != expected_isin:
            raise DataError('Issuer page ISIN differs from selected share class.')
        chart = parser.components['performance']['containersByNameMap']['chart']['dataPointsByNameMap']
        currency = chart['currencySymbol']['value']
        # Physical ETCs have a base currency and launch date, no fund share class.
        share_currency = values.get('seriesBaseCurrencyCode', values.get('baseCurrencyCode'))
        if currency != share_currency:
            raise DataError('Issuer performance and share-class currencies differ.')
        index = _series(chart['performanceData'])
        nav = _series(chart['navData'])
        fee_percent = values.get('emeaMgt')
        metadata = {'isin': expected_isin, 'native_currency': currency,
                    'inception': pd.to_datetime(str(values.get('inceptionDate', values.get('launchDate'))), format='%Y%m%d').date().isoformat(),
                    'use_of_income': values.get('useOfProfitsCode'), 'structure': values.get('productStructure'),
                    'ucits': values.get('ucitsCompliantFlag') == 'Yes',
                    'ongoing_charge': None if fee_percent is None else float(fee_percent) / 100,
                    'history_start': index.index[0].date().isoformat(), 'history_end': index.index[-1].date().isoformat(),
                    'history_type': 'Issuer native-currency performance index; GBP conversion and convention reconciliation pending',
                    'admitted': False}
        risk = parser.components.get('fundamentalsAndRisk', {}).get('containersByNameMap', {}).get('default', {}).get('dataPointsByNameMap', {})
        ytm, duration = risk.get('yieldToWorst', {}), risk.get('modelOad', {})
        if ytm.get('value') is not None and duration.get('value') is not None and ytm.get('asOfDate') == duration.get('asOfDate') and ytm.get('asOfDate'):
            values = [float(ytm['value']), float(duration['value'])]
            if not np.isfinite(values).all() or values[1] < 0:
                raise DataError('Invalid issuer bond characteristics.')
            metadata['bond_characteristics'] = {
                'yield': values[0] / 100, 'duration': values[1],
                'date': pd.to_datetime(str(ytm['asOfDate']), format='%Y%m%d').date().isoformat(),
                'yield_label': ytm.get('label'), 'duration_label': duration.get('label')}
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError('Issuer embedded schema/identity/series changed: ' + str(exc)) from exc
    # Only complete months, after a real preceding month-end, before current month.
    levels = index.groupby(index.index.to_period('M')).last()
    returns = levels.pct_change(fill_method=None).dropna()
    returns = returns[returns.index < pd.Timestamp.today().to_period('M')]
    return metadata, index, nav, returns
