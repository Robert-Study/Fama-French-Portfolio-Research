"""Explicit refresh job; no network calls from interactive slider events.

python -m portfolio.providers.refresh --root data/research [--config sources.json]
A configured source pack supplies reconciled share-class/cash/FX/issuer data.
No provider credentials, generic close prices or fabricated histories are accepted.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import shutil
import tempfile
from zipfile import ZipFile

from portfolio.providers.cache import fetch
from portfolio.providers.french import BASE, FILES, parse_french, regional_gbp
from portfolio.snapshot import SCHEMA_VERSION, load_snapshot, _monthly

PACK_FILES = {'returns.csv', 'cash_fx.csv', 'daily.csv', 'holdings.csv', 'evidence.json'}


def refresh(root, config=None):
    root = Path(root)
    cache = root / '.cache'
    sources, panels, failures = [], {}, []
    for region, filename in FILES.items():
        try:
            raw, source = fetch(BASE + filename, cache / 'raw', 'Kenneth French public research data; review redistribution terms', False)
            source['id'] = 'french:' + region
            panels[region] = parse_french(raw, region)
            sources.append(source)
        except Exception as exc:
            failures.append({'source': region, 'error': str(exc)})
    # Factors alone are useful retained evidence, but cannot publish a research snapshot.
    if failures or config is None:
        report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'failures': failures,
                  'retained_sources': sources, 'snapshot_replaced': False,
                  'missing_input': 'Configured verified source pack with net total returns, SONIA/FX and issuer evidence' if config is None else None}
        cache.mkdir(parents=True, exist_ok=True)
        (cache / 'refresh-report.json').write_text(json.dumps(report, indent=2))
        return report
    config = json.loads(Path(config).read_text())
    raw, pack_source = fetch(config['url'], cache / 'raw', config['licence'], config.get('redistribution', False))
    pack_source['id'] = config.get('id', 'issuer-pack')
    sources.append(pack_source)
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        stage = Path(temporary)
        with ZipFile(BytesIO(raw)) as z:
            if not set(z.namelist()).issubset(PACK_FILES) or sum(i.file_size for i in z.infolist()) > 50_000_000:
                raise ValueError('Source pack contains unknown files or exceeds 50 MB.')
            for name in z.namelist():
                (stage / name).write_bytes(z.read(name))
        cash_fx = _monthly(stage / 'cash_fx.csv')
        regional_gbp(panels, cash_fx).to_csv(stage / 'factors.csv')
        evidence = json.loads((stage / 'evidence.json').read_text())
        # Every issuer evidence reference must point to a separately retained public source.
        for record in config.get('evidence_sources', []):
            _, source = fetch(record['url'], cache / 'raw', record['licence'], record.get('redistribution', False))
            source['id'] = record['id']
            sources.append(source)
        manifest = {'schema_version': SCHEMA_VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(),
                    'sources': sources, 'files': {p.name: sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},
                    'factor_vintages': {r: {'start': str(p.index[0]), 'end': str(p.index[-1])} for r, p in panels.items()}}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        ident = sha256((stage / 'manifest.json').read_bytes()).hexdigest()
        dest = cache / 'snapshots' / ident
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copytree(stage, dest)
        # Validate using an isolated candidate root before atomic last-good pointer replacement.
        candidate = stage / 'candidate'
        (candidate / '.cache').mkdir(parents=True)
        shutil.copy(root / 'instruments.csv', candidate / 'instruments.csv')
        (candidate / '.cache/snapshots').symlink_to(dest.parent.resolve(), target_is_directory=True)
        (candidate / '.cache/raw').symlink_to((cache / 'raw').resolve(), target_is_directory=True)
        (candidate / '.cache/current.json').write_text(json.dumps({'snapshot': ident}))
        checked = load_snapshot(candidate)
        if not checked.status.Status.eq('Evidence eligible').any():
            raise ValueError('No instrument passes evidence gates; last good snapshot retained.')
        tmp = cache / 'current.tmp'
        tmp.write_text(json.dumps({'snapshot': ident}))
        tmp.replace(cache / 'current.json')
    return {'snapshot': ident, 'snapshot_replaced': True, 'failures': []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='data/research')
    parser.add_argument('--config')
    args = parser.parse_args()
    report = refresh(args.root, args.config)
    print(json.dumps(report, indent=2))
    if not report['snapshot_replaced']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
