"""EXECUTIVE.pdf: the one page a decision maker reads, typeset by Typst from the report's own records.

The page holds the decision asked for (EXECUTION-PLAN.md's), the three numbers that matter with their
sources (reports.json), the three largest risks (debt-register.json) and the milestones (plan.json). The
template adds layout only: every word and number on the page is a value of the JSON built here, and every
number in that JSON is read from a record, never computed for the page.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..engines.process import which
from .four_reports import clip

TEMPLATE = Path(__file__).resolve().parent.parent / 'templates/typst/executive.typ'
FONTS = {'ar': 'Noto Naskh Arabic', 'en': 'Noto Sans'}
LABELS = {
    'ar': {'title': 'الملخص التنفيذي', 'decision': 'القرار المطلوب', 'numbers': 'أهم الأرقام', 'risks': 'أكبر المخاطر',
           'milestones': 'المعالم', 'number_columns': ['القيمة', 'المقياس', 'المصدر'],
           'risk_columns': ['المعرّف', 'الخطورة', 'الخطر'], 'milestone_columns': ['المعلم', 'الاسم', 'الهدف', 'البطاقات'],
           'footer': 'كل رقم في هذه الصفحة مأخوذ من سجلات التقرير (reports.json و debt-register.json و plan.json). التفصيل في التقارير الأربعة.',
           'features': 'وظائف يقدّمها البرنامج', 'high': 'بنود دَين عالية أو حرجة', 'ready': 'بطاقات جاهزة من أصل كل البطاقات',
           'decide': 'تخصيص فريق للمعلم الأول ({name}): {goal}', 'of': 'من'},
    'en': {'title': 'Executive summary', 'decision': 'Decision asked for', 'numbers': 'The numbers that matter',
           'risks': 'The largest risks', 'milestones': 'Milestones', 'number_columns': ['Value', 'Measure', 'Source'],
           'risk_columns': ['Id', 'Severity', 'Risk'], 'milestone_columns': ['Milestone', 'Name', 'Goal', 'Cards'],
           'footer': 'Every number on this page is read from the report\'s records (reports.json, debt-register.json, plan.json). The four reports hold the detail.',
           'features': 'features the program delivers', 'high': 'high or critical debt items', 'ready': 'ready cards of all cards',
           'decide': 'Staff the first milestone ({name}): {goal}', 'of': 'of'},
}


def plain(text):
    """Markdown code marks mean nothing on a typeset page."""
    return str(text).replace('`', '')


def _load(out, name):
    try: return json.loads((Path(out) / name).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def content(out, language='ar'):
    """The page as data. Numbers are copied from records; the page computes none."""
    labels = LABELS[language]
    reports = (_load(out, 'reports.json').get('reports') or {})
    current, plan_numbers = reports.get('CURRENT-STATE.md') or {}, reports.get('EXECUTION-PLAN.md') or {}
    plan = _load(out, 'plan.json')
    milestones = plan.get('milestones') or []
    first = milestones[0] if milestones else {}
    goal_key = 'goal_ar' if language == 'ar' else 'goal'
    numbers = [
        {'value': str(current.get('features', {}).get('value', '—')), 'label': labels['features'],
         'source': 'reports.json → CURRENT-STATE.md.features'},
        {'value': str(current.get('high_or_critical', {}).get('value', '—')), 'label': labels['high'],
         'source': 'reports.json → CURRENT-STATE.md.high_or_critical'},
        # "32 of 60" in words: a slash reads backwards in right-to-left text
        {'value': f"{plan_numbers.get('ready', {}).get('value', '—')} {labels['of']} {plan_numbers.get('cards', {}).get('value', '—')}",
         'label': labels['ready'], 'source': 'reports.json → EXECUTION-PLAN.md.ready, cards'},
    ]
    register = _load(out, 'debt-register.json').get('items') or []
    dossier = _load(out, 'dossier.json')
    provenance = dossier.get('provenance') or {}
    target = Path(str(provenance.get('target') or dossier.get('target') or out)).name
    return {
        'language': language, 'title': f"{labels['title']} · {target}",
        'subtitle': f"eaos {provenance.get('tool_version', '')} · {provenance.get('generated_at', '')}".strip(' ·'),
        'decision': plain(labels['decide'].format(name=plain(first.get('name', '—')), goal=first.get(goal_key) or first.get('goal', '—'))),
        'numbers': numbers,
        'risks': [{'id': item['id'], 'severity': item.get('severity', '—'), 'title': plain(clip(item.get('title', ''), 150))}
                  for item in register[:3]],
        'milestones': [{'id': m['id'], 'name': plain(m['name']), 'goal': plain(clip(m.get(goal_key) or m.get('goal', ''), 120)),
                        'cards': str(len(m.get('tasks') or []))} for m in milestones[:8]],
        'labels': labels, 'footer': labels['footer'],
    }


def available(language='ar'):
    """None when Typst and a font for the language are installed, else the reason the PDF cannot be made."""
    binary = which('typst')
    if not binary: return 'Typst is not installed: python -m eaos tools install --only typst'
    fonts = subprocess.run([binary, 'fonts'], capture_output=True, text=True, timeout=60).stdout.splitlines()
    if FONTS[language] not in fonts: return f"no font covers the report language: install {FONTS[language]} (fonts-noto-core)"
    return None


def write(out, language='ar'):
    """Typeset EXECUTIVE.pdf into out; returns its page count. Raises RuntimeError with Typst's own message."""
    out = Path(out)
    with tempfile.TemporaryDirectory() as folder:
        shutil.copy(TEMPLATE, Path(folder) / 'executive.typ')
        (Path(folder) / 'executive.json').write_text(json.dumps(content(out, language), ensure_ascii=False), encoding='utf-8')
        done = subprocess.run([which('typst'), 'compile', '--root', folder, str(Path(folder) / 'executive.typ'),
                               str(out / 'EXECUTIVE.pdf')], capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError('typst: ' + (done.stderr or done.stdout).strip()[-1500:])
    return pages(out / 'EXECUTIVE.pdf')


def pages(path):
    """The page count a PDF declares for itself."""
    import re
    return len(re.findall(rb'/Type\s*/Page(?![s\w])', Path(path).read_bytes()))
