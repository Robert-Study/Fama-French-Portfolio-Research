"""Refresh the six specified pilots from official public sources, retaining gaps."""
from pathlib import Path
import json
from portfolio.providers.cache import fetch
from portfolio.providers.ishares import parse_ishares
from portfolio.providers.boe import csv_url, parse_boe, cash_fx_months

PILOTS = {
    'IWFV': ('https://www.ishares.com/uk/individual/en/products/270048/ishares-msci-world-value-factor-ucits-etf', 'IE00BP3QZB59'),
    'IGLT': ('https://www.ishares.com/uk/individual/en/products/251806/ishares-uk-gilts-ucits-etf', 'IE00B1FZSB30'),
    'SGLN': ('https://www.ishares.com/uk/individual/en/products/258441/ishares-physical-gold-etc-fund', 'IE00B4ND3602'),
    'VWRP': ('https://www.vanguard.co.uk/uk-fund-directory/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating', 'IE00BK5BQT80'),
    'XS2D': ('https://etf.dws.com/en-fi/LU0411078552-s-p-500-2x-leveraged-daily-swap-ucits-etf-1c/', 'LU0411078552'),
    'T212_GBP_CASH': ('https://helpcentre.trading212.com/hc/en-us/articles/15475153380637-What-is-interest-on-cash', None),
}


def refresh_pilots(root):
    root = Path(root)
    cache = root / '.cache'
    sources, records = [], []
    for ident, (url, isin) in PILOTS.items():
        record = {'instrument': ident, 'url': url, 'admitted': False}
        try:
            raw, source = fetch(url, cache / 'raw', 'Issuer public product information; redistribution permission not established', False)
            source['id'] = 'issuer:' + ident
            sources.append(source)
            if ident in ('IWFV', 'IGLT', 'SGLN'):
                meta, index, nav, monthly = parse_ishares(raw, isin)
                record.update(meta)
                folder = cache / 'pilots' / ident
                folder.mkdir(parents=True, exist_ok=True)
                index.to_csv(folder / 'native_performance_index.csv')
                nav.to_csv(folder / 'native_nav.csv')
                monthly.to_csv(folder / 'native_monthly_returns.csv')
                record['parsed_months'] = len(monthly)
                record['remaining_gate'] = 'Actual GBP cash/FX alignment; issuer total-return conventions and split/distribution reconciliation; dated holdings/bond evidence where relevant'
            elif ident == 'T212_GBP_CASH':
                record['remaining_gate'] = 'Public terms retained; applicable Invest account AER, quote date and eligibility/bonus terms required'
            elif ident == 'XS2D':
                record['remaining_gate'] = 'Issuer site supplies a client-rendered shell; exact funding/reset/termination terms, native underlying and actual daily overlap required'
            else:
                record['remaining_gate'] = 'Issuer page retained; reconciled share-class daily/monthly total returns and GBP FX evidence required'
        except Exception as exc:
            record['remaining_gate'] = str(exc)
        records.append(record)
    boe_url = csv_url(end='31/Aug/2026')
    try:
        raw, source = fetch(boe_url, cache / 'raw', 'Bank of England public statistical database; review use terms', False)
        source['id'] = 'boe:cash_fx'
        sources.append(source)
        cash_fx = cash_fx_months(parse_boe(raw))
        cash_fx.to_csv(cache / 'pilots/cash_fx.csv')
        boe = {'url':boe_url,'status':'Parsed official daily SONIA/FX','months':len(cash_fx)}
    except Exception as exc:
        boe = {'url':boe_url,'status':'Unavailable','reason':str(exc)}
    report = {'sources':sources,'pilots':records,'cash_fx':boe,'snapshot_replaced':False}
    (cache / 'pilot-report.json').write_text(json.dumps(report,indent=2))
    return report


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser();p.add_argument('--root',default='data/research')
    print(json.dumps(refresh_pilots(p.parse_args().root),indent=2))
