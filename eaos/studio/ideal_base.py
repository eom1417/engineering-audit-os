"""What the ideal planner (eaos/studio/ideal.py), its rules' baseline (ideal_rules.py) and its prompts
(ideal_prompts.py) share: the views and operations of a plan, what counts as evidence, and how they read a report."""
import json
import re
from pathlib import Path

VIEWS = ('system', 'change', 'journeys', 'paths', 'data_paths', 'infra', 'pipeline', 'plan_order')
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
EVIDENCE = re.compile(r'^(FACT|CLM|TASK|RULE)-[A-Za-z0-9_.:-]+$')
LIMIT = {'elements': 160, 'cards': 140, 'facts': 50, 'doc_chars': 4000, 'docs_chars': 24000}


def _load(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(report, name):
    data = _load(Path(report) / 'facts' / f'{name}.json', {}) or {}
    return [f for f in data.get('facts') or [] if isinstance(f, dict) and f.get('id')]


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_.:-]+', '-', str(text)).strip('-') or 'root'
