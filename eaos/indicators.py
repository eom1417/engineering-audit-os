"""Reading a report's records: one JSON file, and every fact of the fact sets (of one kind, or all)."""
import json
from pathlib import Path


def load(out, name, default=None):
    path = Path(out) / name
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def facts(out, kind=None):
    rows = []
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        data = load(out, 'facts/' + path.name, {})
        rows += [row for row in (data.get('facts') or []) if isinstance(row, dict)]
    return [row for row in rows if kind is None or row.get('kind') == kind]
