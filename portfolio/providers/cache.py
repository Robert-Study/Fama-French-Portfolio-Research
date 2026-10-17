"""Content-addressed, TLS-verified public downloads; never replace a last good file."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
import json
import requests

from portfolio.data import DataError


def fetch(url, cache: Path, licence, redistribution=False, *, method='GET', json_body=None, headers=None, max_age_days=0):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not licence:
        raise DataError('HTTPS source and explicit licence/use terms are required.')
    from urllib.parse import parse_qs
    credential_fields = {'token', 'api_key', 'apikey', 'access_token', 'signature', 'authorization', 'credential'}
    if parsed.username or parsed.password or credential_fields.intersection(k.lower() for k in parse_qs(parsed.query)):
        raise DataError('Public-source URLs must not embed credentials; use supported scoped authentication.')
    if method not in ('GET', 'POST') or set(headers or {}) - {'Content-Type', 'X-Consumer-ID'}:
        raise DataError('Only public GET/POST acquisition and public client headers are supported.')
    request_key = sha256(json.dumps([url, method, json_body, headers], sort_keys=True).encode()).hexdigest()
    cache = Path(cache)
    index = cache / ('request-' + request_key + '.json')
    if max_age_days and index.exists():
        record = json.loads(index.read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(record['retrieved_utc'])).total_seconds() / 86400
        path = cache / record['sha256']
        if 0 <= age <= max_age_days and path.exists():
            raw = path.read_bytes()
            if sha256(raw).hexdigest() == record['sha256']:
                return raw, record
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=.5,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET', 'POST'])))
    with session:
        response = session.request(method, url, json=json_body, headers=headers, timeout=(15, 60))
    response.raise_for_status()
    raw = response.content
    if not raw or len(raw) > 50_000_000:
        raise DataError('Empty or oversized public-source response.')
    digest = sha256(raw).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / digest
    if not path.exists():
        tmp = cache / (digest + '.tmp')
        tmp.write_bytes(raw)
        tmp.replace(path)
    record = dict(url=url, sha256=digest, bytes=len(raw), retrieved_utc=datetime.now(timezone.utc).isoformat(),
                  licence=licence, redistribution=redistribution, file=digest,
                  method=method, request_body=json_body, content_type=response.headers.get('Content-Type'),
                  resolved_url=response.url)
    (cache / (digest + '.json')).write_text(json.dumps(record, indent=2))
    temp_index = index.with_suffix('.tmp')
    temp_index.write_text(json.dumps(record, indent=2)); temp_index.replace(index)
    return raw, record
