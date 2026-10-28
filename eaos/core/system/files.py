"""Reading what EAOS and the projects keep in files: the one JSON reader every layer calls, and the one reader of JSON lines
(M15.3)."""
import json
from pathlib import Path


def read_json(path, default=None):
    """The JSON value a file holds; `default` when the file is missing, unreadable or not JSON."""
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def json_rows(raw):
    """The JSON objects of the whole lines of `raw` (bytes or text); a line that is not one is left out."""
    text = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
    rows = []
    for line in text.splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict): rows.append(row)
    return rows
