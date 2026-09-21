"""Content identities for persisted analysis, independent of report timestamps."""
import hashlib
import json
from pathlib import Path


def snapshot(out):
    out = Path(out)
    identity, extractors, scope = {}, {}, []
    for path in sorted((out / 'facts').glob('*.json')):
        data = json.loads(path.read_text())
        if 'facts' not in data: continue
        # Auxiliary captures are not part of the structural simulator's input.
        if path.stem in {'semantic_documents', 'verification', 'external'}: continue
        identity[path.stem] = {'input_sha': data.get('input_sha'), 'facts': data['facts']}
        extractors[path.stem] = data.get('extractor_version')
        if path.stem == 'syntax':
            scope = sorted(f['location']['path'] for f in data['facts'] if f['kind'] == 'source_file')
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    options = {}
    manifest = out / 'run-manifest.json'
    if manifest.is_file(): options = json.loads(manifest.read_text()).get('options', {})
    return {'sha256': key, 'extractors': extractors, 'scope': scope,
            'exclude': options.get('exclude', [])}
