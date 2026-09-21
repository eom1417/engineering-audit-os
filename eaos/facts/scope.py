"""What the project declared out of scope for analysis.

Reading a declared field is extraction, not policy interpretation, so it belongs in this layer:
every collector gets the same answer without the facts layer depending on the ledger.
"""
import json
from pathlib import Path

FILENAME = 'eaos.policy.json'


def declared_exclusions(target, path=None):
    candidate = Path(path) if path else Path(target) / FILENAME
    if not candidate.is_file(): return []
    try:
        policy = json.loads(candidate.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return []
    patterns = ((policy.get('analysis') or {}).get('exclude')) or []
    if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
        raise ValueError('analysis.exclude must be an array of path patterns')
    return sorted({item.strip('/') for item in patterns if item.strip('/')})
