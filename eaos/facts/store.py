"""Fact sets on disk. Files carry content only; run timestamps live apart so reruns stay byte-identical."""
from datetime import datetime, timezone
import json
from pathlib import Path
from . import SCHEMA_VERSION, digest


def facts_dir(out):
    path = Path(out) / 'facts'
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialise(payload): return json.dumps(payload, ensure_ascii=False, indent=2) + '\n'


def write_set(out, name, extractor, version, facts, input_sha, limitations, summary=None, available=True, reason=None):
    payload = {'schema_version': SCHEMA_VERSION, 'extractor': extractor, 'extractor_version': version,
               'available': available, 'input_sha': input_sha, 'limitations': list(limitations),
               'summary': summary or {}, 'facts': facts}
    if reason: payload['reason'] = reason
    text = serialise(payload)
    (facts_dir(out) / (name + '.json')).write_text(text, encoding='utf-8')
    return {'set': name, 'extractor': extractor, 'extractor_version': version, 'available': available,
            'facts': len(facts), 'content_sha256': digest(text.encode('utf-8'))}


def read_set(out, name): return json.loads((facts_dir(out) / (name + '.json')).read_text(encoding='utf-8'))


def write_index(out, target, entries):
    """index.json is content-addressed; run.json carries the non-deterministic provenance."""
    index = {'schema_version': SCHEMA_VERSION, 'sets': sorted(entries, key=lambda e: e['set'])}
    (facts_dir(out) / 'index.json').write_text(serialise(index), encoding='utf-8')
    (facts_dir(out) / 'run.json').write_text(serialise(
        {'target': str(target), 'produced_at': datetime.now(timezone.utc).isoformat(),
         'sets': [e['set'] for e in index['sets']]}), encoding='utf-8')
    return index
