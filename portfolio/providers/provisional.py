"""Actual issuer/French calibration with explicit, user-authorised research proxies.

No hypothetical observations are inserted into actual return files. USD RF is a
rate proxy only, never labelled SONIA. If ECB access fails, native-currency fits
remain available but no GBP-converted return history is fabricated.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile
import numpy as np
import pandas as pd

from portfolio.providers.cache import fetch
from portfolio.providers.ecb import XML_URL as ECB_URL, parse_ecb_xml, monthly_fx
from portfolio.providers.french import BASE, FILES, parse_french, regional_gbp
from portfolio.providers.ishares import parse_ishares
from portfolio.providers.pilots import PILOTS
from portfolio.providers.savings import refresh_quote
from portfolio.snapshot import SCHEMA_VERSION


def build_provisional(root):
    root=Path(root);cache=root/'.cache';cache.mkdir(parents=True,exist_ok=True)
    panels={};sources=[]
    for region,filename in FILES.items():
        raw,source=fetch(BASE+filename,cache/'raw','Kenneth French public research data; redistribution terms not established',False)
        source['id']='french:'+region;sources.append(source);panels[region]=parse_french(raw,region)
    bank=refresh_quote(root);sources+=bank['sources']
    fx_available=True
    try:
        raw,source=fetch(ECB_URL,cache/'raw','ECB public reference exchange rates; cite source',False)
        source['id']='ecb:fx';sources.append(source)
        fx=monthly_fx(parse_ecb_xml(raw))
        from portfolio.validation import age_days
        if age_days(fx.index[-1].end_time.date().isoformat()) > 90:
            raise ValueError('ECB response is stale; cannot supply contemporary GBP FX')
        end=min(fx.index[-1],panels['US'].index[-1])
    except Exception as exc:
        fx_available=False
        end=panels['US'].index[-1]
        fx_error=str(exc)
    evidence={'GBP_BANK_SAVINGS':bank['evidence']};native={};derived={};issuer_gaps={}
    for ident in ('IWFV','SGLN','IGLT'):
        url,isin=PILOTS[ident]
        raw,source=fetch(url,cache/'raw','Issuer public net-performance data; full-history redistribution not established',False)
        source['id']='issuer:'+ident;sources.append(source)
        meta,index,nav,returns=parse_ishares(raw,isin)
        if meta['use_of_income'] in ('Accumulating', 'No Income'):
            # No distribution cash flow needs reinvestment. Actual issuer NAV
            # includes product expenses; never subtract TER from this history.
            levels = nav.groupby(nav.index.to_period('M')).last()
            returns = levels.pct_change(fill_method=None).dropna()
            returns = returns[returns.index < pd.Timestamp.today().to_period('M')]
        returns=returns.loc[:end]
        native[ident]=returns
        if fx_available:
            common=returns.index.intersection(fx.index)
            if meta['native_currency'] == 'GBP':
                derived[ident]=returns.loc[common]
            elif meta['native_currency'] == 'USD':
                derived[ident]=(1+returns.loc[common])*(1+fx.loc[common])-1
            else:
                raise ValueError('Unsupported verified issuer currency; no guessed conversion')
        # Actual share class is evidenced by ISIN and official net-performance index.
        # The data contract explicitly records the alternative cash and FX basis.
        e=dict(legal_structure='UCITS ETF' if meta['ucits'] else 'Physical metal ETC',
               native_currency=meta['native_currency'],
               currency='GBP' if fx_available else meta['native_currency'], price_unit='GBP' if fx_available else meta['native_currency'],
               inception=meta['inception'],hedge='unhedged',fee=meta['ongoing_charge'],fee_source=source['id'],identity_source=source['id'],
               return_source=source['id'],return_type='actual_share_class_net_total',distribution_split_reconciled=True,
               reconciliation='Issuer net-performance index with reinvestment; accumulator NAV overlap checked, no pre-inception data; native price histories retained',
               calibration_policy='PROVISIONAL: USD RF proxies missing GBP SONIA; forward cash uses public bank AER')
        if ident in ('IWFV','SGLN'):
            # Reconcile the normalised NAV with the issuer performance index across
            # all overlapping dates. Gold has no distributions; IWFV accumulates.
            common=index.index.intersection(nav.index)
            a=index.loc[common]/index.loc[common].iloc[0]
            b=nav.loc[common]/nav.loc[common].iloc[0]
            relative_error=float(np.max(np.abs(a/b-1)))
            e['nav_reconciliation_max_relative_error']=relative_error
            if relative_error>.001:
                e['reconciliation_status']='issuer_total_return_index_provisional'
                e['reconciliation_warning']='Issuer performance-index/NAV divergence requires review; actual accumulating/no-income NAV is used, with no invented distributions or adjustments'
                issuer_gaps[ident]='Performance/NAV overlap differs by more than 10bp'
            e['historical_return_policy']='Actual issuer accumulating/no-income NAV changes, net of product costs; full corporate-action reconciliation remains provisional'
        if ident=='IGLT':
            # Explicit forecast assumption, not a fabricated current bond yield.
            e.update(forecast_policy='cash_plus_zero_term_premium',forecast_assumption_date=datetime.now(timezone.utc).date().isoformat(),
                     forecast_source=bank['evidence']['rate_source'], term_premium_annual=0.0,
                     assumption_label='No verified current yield/duration: cash-equivalent gross carry prior; historical gilt rate risk retained; no duration stress claimed')
            if 'bond_characteristics' in meta:
                facts = meta['bond_characteristics']
                e.pop('forecast_policy')
                e.update(yield_kind='nominal', bond_date=facts['date'], bond_source=source['id'],
                         duration=facts['duration'], **{'yield': facts['yield']},
                         yield_convention='Issuer '+str(facts['yield_label'])+' used as annual carry approximation; flat yields and zero unsupported roll-down',
                         duration_convention=facts['duration_label'],
                         assumption_label='Current issuer YTM carry, less ongoing charge once; constant yield approximation; no verified convexity')
        evidence[ident]=e
    if fx_available:
        months=fx.index.intersection(panels['US'].index)
        cash_fx=pd.DataFrame({'GBP_RF':panels['US'].loc[months,'RF'],'USD_GBP':fx.loc[months]})
        cash_fx.index.name='Month'
        factors=regional_gbp(panels,cash_fx)
        returns=pd.DataFrame(derived);returns.index.name='Month'
        currency_policy='Actual issuer native net total returns converted with ECB month-end GBP-per-USD reference rates; NAV/FX fixing-time mismatch remains'
    else:
        # A native calibration is diagnostic only. Zero FX observations are never
        # inserted into a file labelled actual GBP history.
        months=panels['US'].index
        for panel in panels.values():
            months=months.intersection(panel.index)
        cash_fx=pd.DataFrame({'GBP_RF':panels['US'].loc[months,'RF'],'USD_GBP':np.nan},index=months)
        factors=pd.concat([p.rename(columns=lambda c:r+':'+c) for r,p in panels.items()],axis=1)
        factors=factors[[c for c in factors if not c.endswith(':RF')]].loc[months]
        returns=pd.DataFrame(native);returns.index.name='Month'
        currency_policy='Native USD calibration/risk proxy only; GBP reporting assumes zero FX drift/variance; actual GBP replay unavailable'
        for e in evidence.values():
            if e.get('return_type'):
                e['provisional_native_risk']=True
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        folder=Path(temp)
        for name,frame in [('returns.csv',returns),('factors.csv',factors),('cash_fx.csv',cash_fx)]:
            frame.to_csv(folder/name,index_label='Month')
        (folder/'evidence.json').write_text(json.dumps(evidence,indent=2))
        policy={'status':'PROVISIONAL CALIBRATION — PUBLISHED DATA WITH EXPLICIT PROXIES',
                'cash_reference':'Published US RF is a proxy for unavailable GBP SONIA; historical interest-rate differential is assumed zero',
                'currency_policy':currency_policy, 'actual_gbp_history':fx_available,
                'forward_cash_policy':'Public UK bank AER as conditional forward cash; no invented wholesale rate',
                'bond_policy':('IGLT issuer dated YTM carry approximation and effective-duration stress; flat yields/no roll-down; convexity unavailable'
                               if 'yield' in evidence['IGLT'] else 'IGLT cash-equivalent carry prior with zero term premium; not a current yield estimate'),
                'bond_carry_assumed':'yield' not in evidence['IGLT'],
                'fx_error':None if fx_available else fx_error,'issuer_gaps':issuer_gaps}
        manifest={'schema_version':SCHEMA_VERSION,'created_utc':datetime.now(timezone.utc).isoformat(),
                  'status':policy['status'],'provisional_policy':policy,'sources':sources,
                  'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
                  'factor_vintages':{r:{'start':str(p.index[0]),'end':str(p.index[-1])} for r,p in panels.items()}}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        ident=sha256((folder/'manifest.json').read_bytes()).hexdigest()
        dest=cache/'snapshots'/ident;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copytree(folder,dest)
        # Fully validate the candidate and exercise its model before publishing pointer.
        candidate=folder/'candidate';(candidate/'.cache').mkdir(parents=True)
        for name in ('instruments.csv','cash-policy.json'):
            shutil.copy(root/name,candidate/name)
        (candidate/'.cache/raw').symlink_to((cache/'raw').resolve(),target_is_directory=True)
        (candidate/'.cache/snapshots').symlink_to(dest.parent.resolve(),target_is_directory=True)
        (candidate/'.cache/current.json').write_text(json.dumps({'snapshot':ident}))
        from portfolio.snapshot import load_snapshot
        from portfolio.research import prepare_model,solve_run
        model=prepare_model(load_snapshot(candidate))
        if 'IWFV' not in model.ids:
            raise ValueError('Provisional actual-data equity calibration failed admission; last good snapshot retained')
        solve_run(model)
        temp_pointer=cache/'current.tmp';temp_pointer.write_text(json.dumps({'snapshot':ident}));temp_pointer.replace(cache/'current.json')
        from portfolio.portable import save_derived_model
        save_derived_model(model, root)
    return {'snapshot':ident,'policy':policy,'admitted':model.ids,'diagnostics':model.diagnostics.to_dict(orient='records')}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='data/research')
    # Backwards-compatible CLI used by saved environment setup instructions.
    # It must refresh the integrated universe rather than downgrade to pilots.
    from portfolio.providers.universe import build_universe
    print(json.dumps(build_universe(parser.parse_args().root),indent=2))
