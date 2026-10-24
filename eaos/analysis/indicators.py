"""Reading a report's records: one JSON file (the facts are read through eaos/facts/store.py)."""
import json
from pathlib import Path


def load(out, name, default=None):
    path = Path(out) / name
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


