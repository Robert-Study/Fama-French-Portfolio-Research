"""Derived model inputs for private checkouts without redistributing raw histories."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
import pandas as pd
from portfolio import __version__
from portfolio.validation import age_days, check_covariance


def frame_payload(frame):
    return json.loads(frame.to_json(orient='split'))


def payload_frame(value):
    return pd.DataFrame(value['data'],index=value['index'],columns=value['columns'])


def save_derived_model(model, root):
    root=Path(root)
    if model.daily_config is not None or (model.leverage > 1).any():
        raise ValueError('Admitted daily leverage requires its daily source cache; matrix-only portability is not supported.')
    code=sha256()
    for path in sorted((Path(__file__).parent).rglob('*.py')):
        code.update(path.name.encode());code.update(path.read_bytes())
    value={'schema_version':2,'model_version':__version__,'created_utc':datetime.now(timezone.utc).isoformat(),
           'source_snapshot_sha256':model.snapshot.fingerprint,'model_source_sha256':code.hexdigest(),
           'ids':model.ids,'monthly_mean':model.mean.tolist(),'monthly_covariance':model.covariance.tolist(),
           'annual_fees':model.fees.tolist(),'annual_financing':model.financing.tolist(),'gross_exposure':model.leverage.tolist(),
           'factor_betas':frame_payload(model.betas),'diagnostics':frame_payload(model.diagnostics),
           'premiums':frame_payload(model.premiums),'stress':frame_payload(model.stress),
           'bootstrap_mean_draws':None if model.mean_draws is None else model.mean_draws.tolist(),
           'source_month':model.source_month,'limitations':model.limitations,
           'evidence':model.snapshot.evidence,'source_manifest':model.snapshot.manifest,
           'status':frame_payload(model.snapshot.status),
           'portability_policy':'Derived calibrated matrices/coefficient/mean-draw statistics only; raw price/return histories are not redistributed. Historical replay requires refreshed source cache. Matrix-only horizon paths use an explicitly labelled IID Gaussian joint-risk approximation.'}
    path=root/'model-inputs.json';tmp=root/'model-inputs.tmp'
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False));tmp.replace(path)
    return value


def load_derived_model(snapshot):
    from portfolio.research import Model
    value=snapshot.manifest['derived_model_inputs']
    if value['schema_version']!=2 or value['model_version']!=__version__:
        raise ValueError('Derived model schema/version differs; refresh required.')
    ids=value['ids']
    if len(ids)!=len(set(ids)) or not set(ids).issubset(snapshot.instruments.index) or not ids:
        raise ValueError('Unknown/duplicate derived model instrument identities.')
    if any(snapshot.instruments.loc[i,'category'] == 'Leveraged ETFs / ETPs' for i in ids):
        raise ValueError('Leveraged products require actual daily mechanics/cache; matrix-only restore is prohibited.')
    mu=np.array(value['monthly_mean'],float);cov=np.array(value['monthly_covariance'],float)
    if mu.shape!=(len(ids),) or cov.shape!=(len(ids),len(ids)) or not np.isfinite(mu).all():
        raise ValueError('Invalid derived model dimensions/means.')
    check_covariance(cov)
    if age_days(pd.Period(value['source_month'],freq='M').end_time.date().isoformat())>90:
        raise ValueError('Derived model return vintage older than 90 days; refresh required.')
    cash=value['evidence'].get('GBP_BANK_SAVINGS',{})
    if 'GBP_BANK_SAVINGS' in ids and age_days(cash.get('quote_date'))>30:
        raise ValueError('Derived model bank quote older than 30 days; refresh required.')
    current=snapshot.evidence.get('GBP_BANK_SAVINGS',{})
    if current and (current.get('aer')!=cash.get('aer') or current.get('provider')!=cash.get('provider')):
        raise ValueError('Bank quote changed since calibration; refresh derived model.')
    fees, financing, gross=[pd.Series(value[k],index=ids,dtype=float) for k in ['annual_fees','annual_financing','gross_exposure']]
    if not np.isfinite(np.column_stack([fees,financing,gross])).all() or (fees<0).any() or (financing<0).any() or (gross<0).any():
        raise ValueError('Invalid derived costs/exposures.')
    draws=None if value['bootstrap_mean_draws'] is None else np.array(value['bootstrap_mean_draws'],float)
    if draws is not None and (draws.ndim!=2 or draws.shape[1]!=len(ids) or not np.isfinite(draws).all()):
        raise ValueError('Invalid derived joint mean draws.')
    snapshot.evidence=value['evidence']
    snapshot.status=payload_frame(value['status'])
    limitations=value['limitations']+[value['portability_policy']]
    return Model(ids,mu,cov,pd.DataFrame(columns=ids),fees,financing,gross,payload_frame(value['factor_betas']),
                 payload_frame(value['diagnostics']),payload_frame(value['premiums']),snapshot,draws,limitations,
                 payload_frame(value['stress']),source_month=value['source_month'])
