"""Reading what EAOS and the projects keep in files: the one JSON reader every layer calls (M15.3)."""
import json
from pathlib import Path


def read_json(path, default=None):
    """The JSON value a file holds; `default` when the file is missing, unreadable or not JSON."""
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default
