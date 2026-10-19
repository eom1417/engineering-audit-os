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


# The guards' reasons (eaos/target_architecture.py _decide_current, _decide_targets), in Arabic: the beginning of each.
GUARD_WORDS = (('it would delete files the owner protects (a critical feature or the architecture policy)', 'ممكن يحذف ملفات أنت حاميها (ميزة مهمة أو سياسة البنية)'),
               ('it stands only on cards the triage set aside', 'رأيه قائم على مشاكل اعتبرها الفرز إنذارًا كاذبًا'),
               ("today's components still move into it, so it stays", 'أجزاء اليوم لسا تنتقل له، فيبقى'),
               ('is not an operation on a component that exists today', 'هذي العملية ما تنطبق على جزء موجود اليوم'))


def guard_words(why, ar):
    """A guard's reason in the person's language: the Arabic of its known beginning, else as it was written."""
    if not ar: return why
    return next((words + why[why.index(en) + len(en):] for en, words in GUARD_WORDS if en in (why or '')), why)
