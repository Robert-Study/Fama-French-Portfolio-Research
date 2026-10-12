"""Content-addressed, TLS-verified public downloads; never replace a last good file."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
import json
import requests

from portfolio.data import DataError


def fetch(url, cache: Path, licence, redistribution=False):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not licence:
        raise DataError('HTTPS source and explicit licence/use terms are required.')
    from urllib.parse import parse_qs
    credential_fields = {'token', 'api_key', 'apikey', 'access_token', 'signature', 'authorization', 'credential'}
    if parsed.username or parsed.password or credential_fields.intersection(k.lower() for k in parse_qs(parsed.query)):
        raise DataError('Public-source URLs must not embed credentials; use supported scoped authentication.')
    response = requests.get(url, timeout=(15, 60))
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
                  licence=licence, redistribution=redistribution, file=digest)
    (cache / (digest + '.json')).write_text(json.dumps(record, indent=2))
    return raw, record
