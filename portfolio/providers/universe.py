"""Execute the researched public source requests and publish validated inputs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile
import numpy as np
import pandas as pd

from portfolio.providers.cache import fetch
from portfolio.providers.issuers import acquire, ISHARES
from portfolio.providers.boe import sonia_html_url, parse_sonia_html, sonia_months
from portfolio.providers.ecb import XML_URL, parse_ecb_xml, monthly_fx
from portfolio.providers.french import BASE, FILES, parse_french, regional_gbp
from portfolio.providers.savings import refresh_quote
from portfolio.snapshot import SCHEMA_VERSION, load_snapshot


def fx_panel(raw):
    """Retain both actual GBP/USD and GBP/EUR rates; no currency guesses."""
    import xml.etree.ElementTree as ET
    usd=parse_ecb_xml(raw)
    rows=[]
    for day in ET.fromstring(raw).iter():
        if 'time' not in day.attrib: continue
        quotes={c.attrib.get('currency'):c.attrib.get('rate') for c in day}
        rows.append((pd.Timestamp(day.attrib['time']),float(quotes['GBP'])))
    eur=pd.Series(dict(rows),name='GBP_per_EUR').sort_index()
    return {'USD':monthly_fx(usd),'EUR':monthly_fx(eur)}


def build_universe(root, workers=5):
    root=Path(root);cache=root/'.cache';raw_cache=cache/'raw';raw_cache.mkdir(parents=True,exist_ok=True)
    schedule=pd.read_csv(root/'instruments.csv').set_index('ticker',drop=False)
    ledger=pd.read_csv(root/'evidence-ledger-2026-10-14.csv').set_index('identity')
    sources=[]
    # The dated research ledger is input evidence, not a fresh issuer fee quote.
    ledger_raw=(root/'evidence-ledger-2026-10-14.csv').read_bytes();digest=sha256(ledger_raw).hexdigest()
    (raw_cache/digest).write_bytes(ledger_raw)
    sources.append(dict(id='research:ledger',url='https://github.com/Robert-Study/Fama-French-Portfolio-Research/blob/main/data/research/evidence-ledger-2026-10-14.csv',
                        sha256=digest,retrieved_utc=datetime.now(timezone.utc).isoformat(),licence='User-provided factual issuer research ledger; cited original URLs',redistribution=True))
    panels={}
    for region,filename in FILES.items():
        raw,source=fetch(BASE+filename,raw_cache,'Kenneth French public research data; raw redistribution not established',False,max_age_days=7)
        source['id']='french:'+region;sources.append(source);panels[region]=parse_french(raw,region)
    raw,source=fetch(XML_URL,raw_cache,'ECB public reference rates; cite ECB',False,max_age_days=1)
    source['id']='ecb:fx';sources.append(source);fx=fx_panel(raw)
    try:
        raw,source=fetch(sonia_html_url(),raw_cache,'Source: Bank of England. Contains public sector information licensed under OGL v3.0.',True,max_age_days=1)
        daily_sonia=parse_sonia_html(raw)
    except Exception as exc:
        # Use the supplied actual dated BoE observations, never US RF or an
        # invented series. Keep the failed live refresh visible in provenance.
        imported=root/'sonia-daily-boe-2026-10-13.csv'
        if not imported.exists():raise
        raw=imported.read_bytes();digest=sha256(raw).hexdigest();(raw_cache/digest).write_bytes(raw)
        table=pd.read_csv(imported,parse_dates=['date']).set_index('date')
        daily_sonia=table.sonia_percent_per_annum
        if daily_sonia.index.has_duplicates or not daily_sonia.index.is_monotonic_increasing or not np.isfinite(daily_sonia).all():
            raise ValueError('Invalid imported actual SONIA observations')
        source=dict(url='https://github.com/Robert-Study/Fama-French-Portfolio-Research/blob/main/data/research/sonia-daily-boe-2026-10-13.csv',
                    original_url=sonia_html_url(),sha256=digest,retrieved_utc='2026-10-13T00:00:00+00:00',
                    licence='Source: Bank of England. Delayed SONIA under OGL v3.0; research acquisition CSV retained.',
                    redistribution=True,refresh_error=type(exc).__name__+': '+str(exc),last_observation=daily_sonia.index[-1].date().isoformat())
    source['id']='boe:sonia';sources.append(source);sonia=sonia_months(daily_sonia)
    common=sonia.index.intersection(fx['USD'].index).intersection(panels['US'].index)
    cash_fx=pd.DataFrame({'GBP_RF':sonia.loc[common],'USD_GBP':fx['USD'].loc[common]})
    factors=regional_gbp(panels,cash_fx)
    end=factors.dropna().index[-1]
    bank=refresh_quote(root);sources+=bank['sources']
    evidence={'GBP_BANK_SAVINGS':bank['evidence']}; histories={}; audit=[]; acquired={};holdings=[]
    for ident in schedule.index:
        if ident=='T212_GBP_CASH':continue
        row=ledger.loc[ident]
        e=dict(isin=schedule.loc[ident,'isin'],identity_source='research:ledger',
               identity_evidence_basis='Dated supplied issuer research; acquisition independently gated',
               history_acquired=False,forward_model_blocker='Full actual history has not been acquired',
               broker_listing_status='Public Invest catalogue checked; individual-account eligibility unverified')
        if pd.notna(row.ongoing_fee_percent_pa):
            e.update(fee_source='research:ledger',fee=float(row.ongoing_fee_percent_pa)/100)
        structure=str(row.legal_structure)
        if structure and not structure.startswith('null'):e['legal_structure']=structure
        try:
            inception=pd.to_datetime(row.inception,dayfirst=True)
            if pd.notna(inception):e['inception']=inception.date().isoformat()
        except (ValueError,TypeError):pass
        evidence[ident]=e
    def download(ident):
        return acquire(ident,schedule.loc[ident,'isin'],raw_cache)
    # Isolated acquisition failures do not replace good data with invented data.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(download,i):i for i in schedule.index if i!='T212_GBP_CASH'}
        for future in as_completed(futures):
            ident=futures[future]
            try:
                item=future.result();acquired[ident]=item;sources+=item.sources
            except Exception as exc:
                audit.append(dict(ticker=ident,history='Unavailable',error=type(exc).__name__+': '+str(exc)))
    for ident,item in acquired.items():
        meta=item.metadata;row=ledger.loc[ident];native=meta['native_currency']
        returns=item.returns.loc[:end]
        if native not in ('GBP','USD','EUR'):
            audit.append(dict(ticker=ident,history='Acquired',error='Unsupported/unverified native currency '+str(native)));continue
        if native!='GBP':
            aligned=returns.index.intersection(fx[native].index)
            returns=(1+returns.loc[aligned])*(1+fx[native].loc[aligned])-1
        reconciled=bool(item.audit.get('reconciliation_passed'))
        if reconciled:
            histories[ident]=returns
        fee=meta.get('ongoing_charge')
        from_ledger=fee is None
        if from_ledger: fee=float(row.ongoing_fee_percent_pa)/100
        sid=item.sources[0]['id']
        e=dict(isin=schedule.loc[ident,'isin'],legal_structure=meta.get('structure') or str(row.legal_structure),
               native_currency=native,currency='GBP',price_unit='GBP',inception=meta['inception'],hedge=meta.get('hedge','unverified'),
               fee=fee,fee_source='research:ledger' if from_ledger else sid,identity_source=sid,
               fee_evidence_basis='Dated user-provided issuer research; not a fresh fee quote' if from_ledger else 'Current issuer facts',
               return_source=sid,return_type='actual_share_class_net_total' if reconciled else 'unreconciled_NAV_or_growth',
               distribution_split_reconciled=reconciled,
               reconciliation=item.audit['series_basis'],history_audit=item.audit,
               history_acquired=True,history_observations=len(item.nav),
               broker_listing_status='Public Invest catalogue checked; individual-account eligibility not established')
        if meta.get('use_of_income'): e['use_of_income']=meta['use_of_income']
        if not item.holdings.empty:holdings.append(item.holdings)
        if item.audit.get('holdings_acquisition'):e['holdings_acquisition']=item.audit['holdings_acquisition']
        if item.audit.get('reconciliation_warning'):e['reconciliation_warning']=item.audit['reconciliation_warning']
        if ident=='IWFS':
            # A historical risk panel remains useful; the old factor strategy
            # does not establish a stable current expected-return exposure.
            e['forward_model_blocker']='Index/strategy regime change requires current-regime calibration audit'
        category=schedule.loc[ident,'category']
        if category=='Bonds' and 'bond_characteristics' in meta:
            b=meta['bond_characteristics']; label=str(b['yield_label'])
            if 'Maturity' in label or 'YTM' in label:
                e.update(yield_kind='nominal',duration=b['duration'],bond_date=b['date'],bond_source=sid,
                         yield_convention='Issuer '+label+'; constant-yield carry; zero assumed roll-down', **{'yield':b['yield']})
            else:e['forward_model_blocker']='Issuer yield definition is unresolved: '+label
        # Precise unresolved mechanics remain blockers rather than fake terms.
        if ident=='VAGS':e['forward_model_blocker']='Pre/post-hedge issuer yield convention and credit-loss assumptions unresolved; actual benchmark history available'
        if ident in ('COPA','AIGA','CRUD','CMOP'):e['forward_model_blocker']='Futures index/roll/collateral and separate swap charge reconciliation pending'
        if ident in ('XS2D','3LUS'):e['forward_model_blocker']='Daily funding/reset, corporate-action and stressed overlap validation pending; actual history acquired'
        evidence[ident]=e
        folder=cache/'issuer-histories'/ident;folder.mkdir(parents=True,exist_ok=True)
        item.nav.to_csv(folder/'native-levels.csv',index_label='Date');returns.to_csv(folder/'gbp-monthly-returns.csv',index_label='Month')
        audit.append(dict(ticker=ident,history='Acquired',native_currency=native,first_complete_month=str(returns.dropna().index[0]),
                          last_complete_month=str(returns.dropna().index[-1]),months=len(returns.dropna()),
                          missing_months=[str(m) for m in returns.index[returns.isna()]],
                          reconciliation='Passed stated checks' if e['distribution_split_reconciled'] else 'Pending',
                          details=item.audit,error=e.get('forward_model_blocker','')))
    returns=pd.DataFrame(histories);returns.index.name='Month';cash_fx.index.name='Month';factors.index.name='Month'
    policy=dict(status='ACTUAL GBP HISTORIES AND SONIA — CONDITIONAL FORWARD ASSUMPTIONS',
                cash_reference='Actual Bank of England SONIA, ACT/365 with accrued-level boundary ratios',
                historical_sonia_actual=True,actual_gbp_history=True,
                currency_policy='Actual ECB reference FX; month-end fixing/NAV timing mismatch remains',
                bond_carry_assumed=False,forward_cash_policy='Latest SONIA flat by assumption, separately from savings AER')
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        folder=Path(temp)
        for name,frame in [('returns.csv',returns),('factors.csv',factors),('cash_fx.csv',cash_fx)]:frame.to_csv(folder/name,index_label='Month')
        if holdings:pd.concat(holdings,ignore_index=True).to_csv(folder/'holdings.csv',index=False)
        (folder/'evidence.json').write_text(json.dumps(evidence,indent=2,allow_nan=False))
        manifest=dict(schema_version=SCHEMA_VERSION,created_utc=datetime.now(timezone.utc).isoformat(),status=policy['status'],
                      provisional_policy=policy,forward_sonia_annual=float(daily_sonia.iloc[-1])/100,
                      forward_sonia_date=daily_sonia.index[-1].date().isoformat(),sources=sources,
                      files={p.name:sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
                      factor_vintages={r:dict(start=str(p.index[0]),end=str(p.index[-1])) for r,p in panels.items()})
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        ident=sha256((folder/'manifest.json').read_bytes()).hexdigest();dest=cache/'snapshots'/ident
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(folder,dest,dirs_exist_ok=True)
        candidate=folder/'candidate';(candidate/'.cache').mkdir(parents=True)
        for name in ('instruments.csv','cash-policy.json'):shutil.copy(root/name,candidate/name)
        (candidate/'.cache/raw').symlink_to(raw_cache.resolve(),target_is_directory=True)
        (candidate/'.cache/snapshots').symlink_to(dest.parent.resolve(),target_is_directory=True)
        (candidate/'.cache/current.json').write_text(json.dumps({'snapshot':ident}))
        from portfolio.research import prepare_model,solve_run
        from portfolio.portable import save_derived_model
        model=prepare_model(load_snapshot(candidate));run=solve_run(model)
        if 'VWRP' not in model.ids:raise ValueError('VWRP calibration did not pass; last good snapshot retained: '+str(model.snapshot.status.loc['VWRP'].to_dict()))
        save_derived_model(model,root)
        pointer=cache/'current.tmp';pointer.write_text(json.dumps({'snapshot':ident}));pointer.replace(cache/'current.json')
        model.snapshot.status.to_csv(root/'admission-status.csv')
        (root/'acquisition-audit.json').write_text(json.dumps(sorted(audit,key=lambda r:r['ticker']),indent=2,allow_nan=False))
        (root/'calibration-summary.json').write_text(json.dumps(dict(model_version=__import__('portfolio').__version__,
                 cut_off=str(end),admitted=model.ids,by_category=model.snapshot.instruments.loc[model.ids].category.value_counts().to_dict(),
                 diagnostics=model.diagnostics.to_dict(orient='records'),risk_months=len(model.history),run_id=run.run_id),indent=2))
    return dict(snapshot=ident,actual_histories=len(acquired),reconciled=sum(bool(v.audit.get('reconciliation_passed')) for v in acquired.values()),
                admitted=model.ids,cut_off=str(end),unavailable=[r for r in audit if r['history']=='Unavailable'])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='data/research');parser.add_argument('--workers',type=int,default=5)
    args=parser.parse_args();print(json.dumps(build_universe(args.root,args.workers),indent=2))
