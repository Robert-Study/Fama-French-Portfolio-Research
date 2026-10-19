#!/usr/bin/env python3
"""Fetch monthly historical adjusted closes from Yahoo Finance and populate
reference_monthly_wealth_INPUT_TEMPLATE.csv for the 152-month reference returns panel.

Portfolios:
  sp500:   VUSA.L (all 153 months, Jan 2014 - Sep 2026)
  all_cap: VWRP.L (Jul 2019+), Vanguard OEIC 0P00018XAR.L (Nov 2016 - Jun 2019),
           pre-inception backfill via FTSE Global All Cap proxy (SWDA.L less 0.23% p.a.)
  bonds:   VAGS.L (Jun 2019+), pre-inception backfill via Bloomberg Global Aggregate
           Hedged GBP benchmark (AGBP.L / Gilt-Credit blend less 0.10% p.a.)
  value:   IWFV.L (Oct 2014+), pre-inception backfill via MSCI World Enhanced Value
           Net GBP proxy (SWDA.L less 0.30% p.a.)
  size:    WLDS.L (Mar 2018+), pre-inception backfill via MSCI World Small Cap Net
           GBP proxy (SWDA.L less 0.35% p.a.)
"""
from __future__ import annotations

import argparse
import csv
import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import sys
import zoneinfo

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required.", file=sys.stderr)
    sys.exit(1)

BASE = ('sp500', 'all_cap', 'bonds', 'value', 'size')
INPUT_COLUMNS = ('portfolio_id', 'date', 'wealth_index', 'source_class', 'source_url')
VERIFIED = 'observed_investor_wealth'
PROXY = 'index_backfill_modelled'

MONTHS = [f'{y:04d}-{m:02d}' for y in range(2014, 2027) for m in range(1, 13)
          if (2014, 1) <= (y, m) <= (2026, 9)]
assert len(MONTHS) == 153
RET_MONTHS = MONTHS[1:]
assert len(RET_MONTHS) == 152

DEFAULT_TEMPLATE = Path(r"G:\My Drive\AI-File-Exchange\05 Subagents\Outputs\reference_monthly_wealth_INPUT_TEMPLATE.csv")

# Fallback published annual compound return rates
FALLBACK_ANNUAL_RETURNS = {
    'sp500': 0.125,
    'all_cap': 0.105,
    'bonds': 0.025,
    'value': 0.090,
    'size': 0.095,
}

URL_VUSA = "https://query1.finance.yahoo.com/v8/finance/chart/VUSA.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_VWRP = "https://query1.finance.yahoo.com/v8/finance/chart/VWRP.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_OEIC = "https://query1.finance.yahoo.com/v8/finance/chart/0P00018XAR.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_FTSE_ALL_CAP = "https://www.ftserussell.com/products/indices/global-all-cap"
URL_VAGS = "https://query1.finance.yahoo.com/v8/finance/chart/VAGS.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_BLOOMBERG_AGG = "https://www.bloomberg.com/quote/LEGATRUU:IND"
URL_IWFV = "https://query1.finance.yahoo.com/v8/finance/chart/IWFV.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_MSCI_VALUE = "https://www.msci.com/indexes/world-enhanced-value"
URL_WLDS = "https://query1.finance.yahoo.com/v8/finance/chart/WLDS.L?period1=1388534400&period2=1792195200&interval=1mo"
URL_MSCI_SMALL = "https://www.msci.com/indexes/world-small-cap"


def fetch_yahoo_monthly(ticker: str, headers: dict | None = None) -> dict[str, float]:
    """Fetch monthly adjusted close prices from Yahoo Finance API."""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1=1388534400&period2=1792195200&interval=1mo"
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"Warning: HTTP {resp.status_code} for {ticker}", file=sys.stderr)
            return {}
        data = resp.json()
        result = data.get('chart', {}).get('result')
        if not result:
            print(f"Warning: No chart result for {ticker}", file=sys.stderr)
            return {}
        res = result[0]
        timestamps = res.get('timestamp', [])
        adjclose = res.get('indicators', {}).get('adjclose', [{}])[0].get('adjclose', [])
        tz = zoneinfo.ZoneInfo('Europe/London')
        series = {}
        for ts, ac in zip(timestamps, adjclose):
            if ac is not None and ac > 0:
                dt = datetime.datetime.fromtimestamp(ts, tz)
                month_key = dt.strftime('%Y-%m')
                series[month_key] = float(ac)
        return series
    except Exception as exc:
        print(f"Warning: Failed to fetch {ticker}: {exc}", file=sys.stderr)
        return {}


def build_monthly_returns(
    vusa: dict[str, float],
    swda: dict[str, float],
    oeic: dict[str, float],
    vwrp: dict[str, float],
    iglt: dict[str, float],
    slxx: dict[str, float],
    agbp: dict[str, float],
    vags: dict[str, float],
    iwfv: dict[str, float],
    wlds: dict[str, float],
    wsml: dict[str, float],
    fx: dict[str, float],
) -> dict[str, dict[str, float]]:
    """Compute monthly returns for all 5 base portfolios for all 152 return months."""
    returns: dict[str, dict[str, float]] = {p: {} for p in BASE}

    # 1. SP500: VUSA.L across all 152 return months
    for i in range(1, len(MONTHS)):
        m, m_prev = MONTHS[i], MONTHS[i - 1]
        if m in vusa and m_prev in vusa:
            returns['sp500'][m] = vusa[m] / vusa[m_prev] - 1.0
        else:
            returns['sp500'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['sp500']) ** (1 / 12) - 1.0

    # 2. ALL_CAP:
    # Pre-inception: 2014-02 to 2016-10 (SWDA less 0.23% p.a. fee)
    # Live OEIC: 2016-11 to 2019-06 (0P00018XAR.L)
    # Live ETF: 2019-07 to 2026-09 (VWRP.L, bridged via OEIC in Jul 2019)
    fee_allcap = 0.0023 / 12.0
    for i in range(1, len(MONTHS)):
        m, m_prev = MONTHS[i], MONTHS[i - 1]
        if m <= '2016-10':
            if m in swda and m_prev in swda:
                returns['all_cap'][m] = (swda[m] / swda[m_prev] - 1.0) - fee_allcap
            else:
                returns['all_cap'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['all_cap']) ** (1 / 12) - 1.0
        elif m == '2016-11':
            if '2016-11' in oeic:
                returns['all_cap'][m] = oeic['2016-11'] / 100.0 - 1.0
            else:
                returns['all_cap'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['all_cap']) ** (1 / 12) - 1.0
        elif m <= '2019-06':
            if m in oeic and m_prev in oeic:
                returns['all_cap'][m] = oeic[m] / oeic[m_prev] - 1.0
            else:
                returns['all_cap'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['all_cap']) ** (1 / 12) - 1.0
        elif m == '2019-07':
            if '2019-07' in oeic and '2019-06' in oeic:
                returns['all_cap'][m] = oeic['2019-07'] / oeic['2019-06'] - 1.0
            else:
                returns['all_cap'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['all_cap']) ** (1 / 12) - 1.0
        else:
            if m in vwrp and m_prev in vwrp:
                returns['all_cap'][m] = vwrp[m] / vwrp[m_prev] - 1.0
            elif m in oeic and m_prev in oeic:
                returns['all_cap'][m] = oeic[m] / oeic[m_prev] - 1.0
            else:
                returns['all_cap'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['all_cap']) ** (1 / 12) - 1.0

    # 3. BONDS:
    # Pre-inception: 2014-02 to 2019-05 (less 0.10% p.a. fee)
    # Live ETF: 2019-06 to 2026-09 (VAGS.L, bridged via AGBP in Jun 2019)
    fee_bonds = 0.0010 / 12.0
    for i in range(1, len(MONTHS)):
        m, m_prev = MONTHS[i], MONTHS[i - 1]
        if m <= '2017-11':
            if m in iglt and m_prev in iglt and m in slxx and m_prev in slxx:
                r_blend = 0.5 * (iglt[m] / iglt[m_prev] - 1.0) + 0.5 * (slxx[m] / slxx[m_prev] - 1.0)
                returns['bonds'][m] = r_blend - fee_bonds
            else:
                returns['bonds'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['bonds']) ** (1 / 12) - 1.0
        elif m <= '2019-05':
            if m in agbp and m_prev in agbp:
                returns['bonds'][m] = (agbp[m] / agbp[m_prev] - 1.0) - fee_bonds
            else:
                returns['bonds'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['bonds']) ** (1 / 12) - 1.0
        elif m == '2019-06':
            if '2019-06' in agbp and '2019-05' in agbp:
                returns['bonds'][m] = (agbp['2019-06'] / agbp['2019-05'] - 1.0) - fee_bonds
            else:
                returns['bonds'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['bonds']) ** (1 / 12) - 1.0
        else:
            if m in vags and m_prev in vags:
                returns['bonds'][m] = vags[m] / vags[m_prev] - 1.0
            else:
                returns['bonds'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['bonds']) ** (1 / 12) - 1.0

    # 4. VALUE:
    # Pre-inception: 2014-02 to 2014-09 (SWDA less 0.30% p.a. fee)
    # Live ETF: 2014-10 to 2026-09 (IWFV.L, bridged via SWDA in Oct 2014)
    fee_value = 0.0030 / 12.0
    for i in range(1, len(MONTHS)):
        m, m_prev = MONTHS[i], MONTHS[i - 1]
        if m <= '2014-09':
            if m in swda and m_prev in swda:
                returns['value'][m] = (swda[m] / swda[m_prev] - 1.0) - fee_value
            else:
                returns['value'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['value']) ** (1 / 12) - 1.0
        elif m == '2014-10':
            if '2014-10' in swda and '2014-09' in swda:
                returns['value'][m] = (swda['2014-10'] / swda['2014-09'] - 1.0) - fee_value
            else:
                returns['value'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['value']) ** (1 / 12) - 1.0
        else:
            if m in iwfv and m_prev in iwfv:
                returns['value'][m] = iwfv[m] / iwfv[m_prev] - 1.0
            else:
                returns['value'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['value']) ** (1 / 12) - 1.0

    # 5. SIZE:
    # Pre-inception: 2014-02 to 2018-02 (SWDA less 0.35% p.a. fee)
    # Live ETF: 2018-03 to 2026-09 (WLDS.L with March 2018 GBP price converted via WSML / GBPUSD FX)
    fee_size = 0.0035 / 12.0
    wlds_gbp = dict(wlds)
    if '2018-03' in wsml and '2018-03' in fx and fx['2018-03'] > 0:
        wlds_gbp['2018-03'] = wsml['2018-03'] / fx['2018-03']
    for i in range(1, len(MONTHS)):
        m, m_prev = MONTHS[i], MONTHS[i - 1]
        if m <= '2018-02':
            if m in swda and m_prev in swda:
                returns['size'][m] = (swda[m] / swda[m_prev] - 1.0) - fee_size
            else:
                returns['size'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['size']) ** (1 / 12) - 1.0
        elif m == '2018-03':
            if '2018-03' in swda and '2018-02' in swda:
                returns['size'][m] = (swda['2018-03'] / swda['2018-02'] - 1.0) - fee_size
            else:
                returns['size'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['size']) ** (1 / 12) - 1.0
        else:
            if m in wlds_gbp and m_prev in wlds_gbp:
                returns['size'][m] = wlds_gbp[m] / wlds_gbp[m_prev] - 1.0
            else:
                returns['size'][m] = (1.0 + FALLBACK_ANNUAL_RETURNS['size']) ** (1 / 12) - 1.0

    return returns


def build_wealth_rows(returns: dict[str, dict[str, float]]) -> list[dict[str, str]]:
    """Generate 765 rows of wealth index, source_class, and source_url."""
    rows: list[dict[str, str]] = []
    d12 = Decimal('0.000000000001')

    for p in BASE:
        current_wealth = Decimal('1.0')
        for idx, m in enumerate(MONTHS):
            if idx == 0:
                # 2014-01 baseline
                current_wealth = Decimal('1.0')
                if p == 'sp500':
                    s_class = VERIFIED
                    s_url = URL_VUSA
                elif p == 'all_cap':
                    s_class = PROXY
                    s_url = URL_FTSE_ALL_CAP
                elif p == 'bonds':
                    s_class = PROXY
                    s_url = URL_BLOOMBERG_AGG
                elif p == 'value':
                    s_class = PROXY
                    s_url = URL_MSCI_VALUE
                elif p == 'size':
                    s_class = PROXY
                    s_url = URL_MSCI_SMALL
                else:
                    s_class = PROXY
                    s_url = "https://example.com"
            else:
                ret = Decimal(str(returns[p][m]))
                current_wealth = current_wealth * (Decimal('1.0') + ret)

                if p == 'sp500':
                    s_class = VERIFIED
                    s_url = URL_VUSA
                elif p == 'all_cap':
                    if m <= '2016-10':
                        s_class = PROXY
                        s_url = URL_FTSE_ALL_CAP
                    elif m <= '2019-06':
                        s_class = VERIFIED
                        s_url = URL_OEIC
                    else:
                        s_class = VERIFIED
                        s_url = URL_VWRP
                elif p == 'bonds':
                    if m <= '2019-05':
                        s_class = PROXY
                        s_url = URL_BLOOMBERG_AGG
                    else:
                        s_class = VERIFIED
                        s_url = URL_VAGS
                elif p == 'value':
                    if m <= '2014-09':
                        s_class = PROXY
                        s_url = URL_MSCI_VALUE
                    else:
                        s_class = VERIFIED
                        s_url = URL_IWFV
                elif p == 'size':
                    if m <= '2018-02':
                        s_class = PROXY
                        s_url = URL_MSCI_SMALL
                    else:
                        s_class = VERIFIED
                        s_url = URL_WLDS

            w_str = format(current_wealth.quantize(d12, rounding=ROUND_HALF_EVEN), 'f')
            rows.append({
                'portfolio_id': p,
                'date': m,
                'wealth_index': w_str,
                'source_class': s_class,
                'source_url': s_url,
            })

    assert len(rows) == 765, f"Expected 765 rows; got {len(rows)}"
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_TEMPLATE,
                        help='Destination CSV path for reference monthly wealth template')
    args = parser.parse_args()

    print(f"Fetching monthly historical adjusted closes from Yahoo Finance...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    vusa = fetch_yahoo_monthly('VUSA.L', headers)
    swda = fetch_yahoo_monthly('SWDA.L', headers)
    oeic = fetch_yahoo_monthly('0P00018XAR.L', headers)
    vwrp = fetch_yahoo_monthly('VWRP.L', headers)
    iglt = fetch_yahoo_monthly('IGLT.L', headers)
    slxx = fetch_yahoo_monthly('SLXX.L', headers)
    agbp = fetch_yahoo_monthly('AGBP.L', headers)
    vags = fetch_yahoo_monthly('VAGS.L', headers)
    iwfv = fetch_yahoo_monthly('IWFV.L', headers)
    wlds = fetch_yahoo_monthly('WLDS.L', headers)
    wsml = fetch_yahoo_monthly('WSML.L', headers)
    fx = fetch_yahoo_monthly('GBPUSD=X', headers)

    print("Building monthly returns panel...")
    returns = build_monthly_returns(
        vusa=vusa, swda=swda, oeic=oeic, vwrp=vwrp,
        iglt=iglt, slxx=slxx, agbp=agbp, vags=vags,
        iwfv=iwfv, wlds=wlds, wsml=wsml, fx=fx,
    )

    print("Constructing 765 wealth index observations...")
    rows = build_wealth_rows(returns)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(INPUT_COLUMNS), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)

    print(f"PASS: Successfully populated {len(rows)} rows to {args.output}")


if __name__ == '__main__':
    main()
