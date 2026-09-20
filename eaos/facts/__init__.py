"""Deterministic fact extraction. A fact is a reproducible observation, never a model output."""
import hashlib
import json

SCHEMA_VERSION = 1


def digest(data): return hashlib.sha256(data).hexdigest()


def make(kind, extractor, version, input_sha, location, value, resolution=None, limitations=()):
    """Build a fact whose identity is a pure function of its content, so reruns are comparable."""
    payload = json.dumps([kind, extractor, version, input_sha, location, value], sort_keys=True, ensure_ascii=False)
    row = {'id': 'FACT-' + digest(payload.encode('utf-8'))[:16], 'kind': kind, 'extractor': extractor,
           'extractor_version': version, 'input_sha': input_sha, 'location': location, 'value': value}
    if resolution: row['resolution'] = resolution
    if limitations: row['limitations'] = list(limitations)
    return row
