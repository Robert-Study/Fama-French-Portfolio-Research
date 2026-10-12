"""Versioned, immutable snapshot loading and admission diagnostics."""
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
import pandas as pd

from portfolio.data import DataError
from portfolio.validation import CATEGORIES, admission

SCHEMA_VERSION = 2


@dataclass
class Snapshot:
    instruments: pd.DataFrame
    returns: pd.DataFrame
    factors: pd.DataFrame
    cash_fx: pd.DataFrame
    daily: pd.DataFrame
    holdings: pd.DataFrame
    evidence: dict
    manifest: dict
    fingerprint: str
    status: pd.DataFrame = field(default_factory=pd.DataFrame)


def snapshot_fingerprint(folder):
    folder = Path(folder)
    digest = sha256()
    for file in sorted(folder.rglob('*')):
        if file.is_file() and '.cache' not in file.parts:
            digest.update(str(file.relative_to(folder)).encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def _monthly(path):
    if not path.exists():
        return pd.DataFrame(index=pd.PeriodIndex([], freq='M', name='Month'))
    frame = pd.read_csv(path).set_index('Month')
    frame.index = pd.PeriodIndex(frame.index, freq='M', name='Month')
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise DataError('Snapshot months must be ordered and unique.')
    frame = frame.apply(pd.to_numeric, errors='raise')
    if np.isinf(frame.to_numpy()).any():
        raise DataError('Infinite snapshot observations.')
    return frame


def load_snapshot(root, today=None):
    root = Path(root)
    instruments = pd.read_csv(root / 'instruments.csv').set_index('ticker', drop=False).fillna('')
    policy_file = root / 'cash-policy.json'
    if policy_file.exists():
        policy = json.loads(policy_file.read_text())
        # The original supplied schedule is retained verbatim. Apply the user's
        # explicit later bank-savings override as a separate audited identity.
        if 'T212_GBP_CASH' in instruments.index:
            instruments = instruments.rename(index={'T212_GBP_CASH': policy['id']})
            for column, value in {'ticker': policy['id'], 'name': policy['name'],
                                  'listing': 'UK bank account outside Trading 212',
                                  'model': 'variable_rate_bank_savings',
                                  'broker_source': 'Outside broker scope; bank-quote.json contains official bank source URLs',
                                  'broker_status': 'Outside broker scope; UK bank eligibility applies',
                                  'calibration_status': policy['status']}.items():
                instruments.loc[policy['id'], column] = value
    if len(instruments) != 50 or instruments.index.has_duplicates or set(instruments.category) != set(CATEGORIES):
        raise DataError('The selected universe must retain all 50 unique identities and six categories.')
    current = root / '.cache/current.json'
    if not current.exists():
        snapshot = Snapshot(instruments, _monthly(root / '_absent'), _monthly(root / '_absent'),
                            _monthly(root / '_absent'), pd.DataFrame(), pd.DataFrame(), {},
                            {'schema_version': SCHEMA_VERSION, 'status': 'NO VERIFIED SNAPSHOT', 'sources': []},
                            snapshot_fingerprint(root))
        quote_file = root / 'bank-quote.json'
        if quote_file.exists():
            quote = json.loads(quote_file.read_text())
            snapshot.evidence['GBP_BANK_SAVINGS'] = quote['evidence']
            snapshot.manifest['sources'] = quote['sources']
            snapshot.manifest['status'] = 'DATED PUBLIC BANK QUOTE; SECURITIES NOT CALIBRATED'
            snapshot.instruments.loc['GBP_BANK_SAVINGS', 'name'] = quote['evidence']['provider'] + ' ' + quote['evidence']['product']
        inventory = root / 'source-inventory.json'
        if inventory.exists():
            snapshot.manifest['public_source_inventory'] = json.loads(inventory.read_text())
        model_file = root / 'model-inputs.json'
        if model_file.exists():
            derived = json.loads(model_file.read_text())
            snapshot.manifest = {**derived['source_manifest'], 'derived_model_inputs': derived,
                                 'runtime_history_status': 'Derived matrices only; refresh to restore actual histories'}
            snapshot.fingerprint = snapshot_fingerprint(root)
    else:
        pointer = json.loads(current.read_text())
        name = pointer['snapshot']
        if not name.isalnum():
            raise DataError('Invalid snapshot pointer.')
        folder = root / '.cache/snapshots' / name
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest.get('schema_version') != SCHEMA_VERSION:
            raise DataError('Unsupported snapshot schema.')
        for name, digest in manifest['files'].items():
            path = folder / name
            if path.parent != folder or sha256(path.read_bytes()).hexdigest() != digest:
                raise DataError('Snapshot file hash mismatch: ' + name)
        sources = manifest.get('sources', [])
        ids = [s['id'] for s in sources]
        if len(ids) != len(set(ids)):
            raise DataError('Source identifiers must be unique.')
        for source in sources:
            if not all(source.get(k) for k in ['id', 'url', 'sha256', 'retrieved_utc', 'licence']):
                raise DataError('Source inventory missing provenance fields.')
            raw_path = root / '.cache/raw' / source['sha256']
            if not raw_path.is_file() or sha256(raw_path.read_bytes()).hexdigest() != source['sha256']:
                raise DataError('Retained raw source missing/hash mismatch: ' + source['id'])
        daily = pd.read_csv(folder / 'daily.csv', index_col='Date', parse_dates=True) if (folder / 'daily.csv').exists() else pd.DataFrame()
        if not daily.empty and (daily.index.has_duplicates or not daily.index.is_monotonic_increasing or not np.isfinite(daily.to_numpy()).all()):
            raise DataError('Daily panel must contain finite synchronised observations.')
        holdings = pd.read_csv(folder / 'holdings.csv') if (folder / 'holdings.csv').exists() else pd.DataFrame()
        snapshot = Snapshot(instruments, _monthly(folder / 'returns.csv'), _monthly(folder / 'factors.csv'),
                            _monthly(folder / 'cash_fx.csv'), daily, holdings,
                            json.loads((folder / 'evidence.json').read_text()), manifest,
                            sha256((folder / 'manifest.json').read_bytes()).hexdigest())
        if (snapshot.returns.dropna(how='all') < -1).any().any():
            raise DataError('Invalid actual monthly returns.')
    source_ids = {s['id'] for s in snapshot.manifest['sources']}
    bank_evidence = snapshot.evidence.get('GBP_BANK_SAVINGS', {})
    if bank_evidence.get('provider') and bank_evidence.get('product'):
        snapshot.instruments.loc['GBP_BANK_SAVINGS', 'name'] = bank_evidence['provider'] + ' ' + bank_evidence['product']
    rows = []
    for ident, row in instruments.iterrows():
        reasons = admission(row, snapshot.evidence.get(ident, {}), snapshot.returns, source_ids, today,
                            provisional=bool(snapshot.manifest.get('provisional_policy')))
        rows.append({'ticker': ident, 'Name': row['name'], 'Category': row.category,
                     'Status': 'Blocked' if reasons else 'Evidence eligible',
                     'Reason': '; '.join(reasons), 'Owner': 'Public-data adapter / issuer evidence' if row.category != CATEGORIES[0] else 'Public bank rate and terms verification'})
    snapshot.status = pd.DataFrame(rows).set_index('ticker')
    return snapshot
