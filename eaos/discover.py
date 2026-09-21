"""Discovery documents derived from facts.

Each document is a one-file artifact that answers a real question a reader
might have, and is grounded entirely in the persisted fact sets. Nothing is
invented: a missing fact is reported as a gap, not guessed.
"""
from collections import defaultdict
from pathlib import Path
from .facts.store import read_set


NAME = 'discovery'
VERSION = '1'
LIMITATIONS = [
    'A discovery document is a rendering of the facts already collected; rerunning it produces '
    'byte-identical output, not new observations.',
    'A reader should treat every claim in the document as a citation: the value is the fact, the '
    'path is the location, and the limitation section lists what the static walk could not see.',
]



def _read_sets(out):
    out = Path(out); sets = {}
    for name in ['graph', 'flows', 'runtime', 'domain']:
        path = out / 'facts' / f'{name}.json'
        if path.is_file(): sets[name] = read_set(out, name)
    return sets




def data_model(out, language='ar'):
    out = Path(out); sets = _read_sets(out); ar = language == 'ar'
    title = 'نموذج البيانات' if ar else 'Data model'
    lines = ['# ' + title, '']
    models = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'data_model']
    if not models:
        lines += ['*' + ('لا نماذج مكتشفة' if ar else 'No models detected') + '*']
    by_framework = defaultdict(list)
    for model in models:
        by_framework[model['value']['framework']].append(model)
    for framework in sorted(by_framework):
        rows = by_framework[framework]
        lines += ['', '## ' + framework + f' ({len(rows)})', '']
        for model in rows[:SHOWN_PER_FRAMEWORK]:
            lines += ['- `' + model['value']['name'] + '` @ `' + model['location']['path'] + '`']
        if len(rows) > SHOWN_PER_FRAMEWORK:
            lines += ['- ' + (f'… و{len(rows) - SHOWN_PER_FRAMEWORK} أخرى في `facts/runtime.json`' if ar
                              else f'… and {len(rows) - SHOWN_PER_FRAMEWORK} more in `facts/runtime.json`')]
    migrations = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'migration_step']
    if migrations:
        lines += ['', '## ' + ('الهجرات' if ar else 'Migrations') + f' ({len(migrations)})', '']
        for migration in migrations[:SHOWN_PER_FRAMEWORK]:
            lines += ['- `' + migration['value']['name'] + '` @ `' + migration['location']['path'] + '`']
    return '\n'.join(lines) + '\n'



def deployment(out, language='ar'):
    out = Path(out); sets = _read_sets(out); ar = language == 'ar'
    facts = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'deployment_target']
    title = 'النشر' if ar else 'Deployment'
    if not facts:
        return '# ' + title + '\n\n*' + ('لا أهداف نشر' if ar else 'No deployment targets') + '*\n'
    lines = ['# ' + title, '']
    note = ('> الميناء من Dockerfile/compose. لا يثبت أن النشر يشتغل فعلًا.' if ar else
             '> From Dockerfile/compose. Does not prove the deployment actually runs.')
    lines += [note, '']
    for fact in facts:
        v = fact['value']
        if v.get('kind') == 'dockerfile':
            lines += ['- `' + fact['location']['path'] + '` exposes port ' + str(v['port'])]
        elif v.get('kind') == 'compose':
            lines += ['- `' + fact['location']['path'] + '` declares service `' + str(v['service']) + '`']
    return '\n'.join(lines) + '\n'


def observability(out, language='ar'):
    out = Path(out); sets = _read_sets(out); ar = language == 'ar'
    facts = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'observability_signal']
    title = 'المراقبة' if ar else 'Observability'
    if not facts:
        return '# ' + title + '\n\n*' + ('لا إشارات مراقبة' if ar else 'No observability signals') + '*\n'
    lines = ['# ' + title, '']
    by_kind = defaultdict(list)
    for fact in facts:
        by_kind[fact['value']['kind']].append(fact['location']['path'])
    for kind in sorted(by_kind):
        paths = sorted(set(by_kind[kind]))
        lines += ['- **' + kind + '**: ' + ', '.join('`' + p + '`' for p in paths[:20])]
    return '\n'.join(lines) + '\n'


def security_surface(out, language='ar'):
    out = Path(out); sets = _read_sets(out); ar = language == 'ar'
    facts = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'security_surface']
    title = 'سطح الأمن' if ar else 'Security surface'
    if not facts:
        return '# ' + title + '\n\n*' + ('لا تلميحات أمان' if ar else 'No security hints') + '*\n'
    lines = ['# ' + title, '']
    note = ('> تلميحات تحليل ثابت فقط.' if ar else '> Static analysis hints only.')
    lines += [note, '']
    by_hint = defaultdict(list)
    for fact in facts:
        by_hint[fact['value']['hint']].append(fact['location']['path'])
    site_label = 'موضع' if ar else 'site(s)'
    for hint in sorted(by_hint):
        paths = sorted(set(by_hint[hint]))
        lines += ['- **' + hint + '**: ' + str(len(paths)) + ' ' + site_label]
    return '\n'.join(lines) + '\n'


def integrations(out, language='ar'):
    out = Path(out); sets = _read_sets(out); ar = language == 'ar'
    facts = [f for f in sets.get('runtime', {}).get('facts', []) if f['kind'] == 'integration_target']
    title = 'التكاملات الصادرة' if ar else 'Outbound integrations'
    if not facts:
        return '# ' + title + '\n\n*' + ('لا تكاملات صادرة' if ar else 'No outbound integrations') + '*\n'
    lines = ['# ' + title, '']
    note = ('> المضيفون من عناوين URL في الكود.' if ar else
             '> Hosts extracted from URLs in code.')
    lines += [note, '']
    by_host = defaultdict(list)
    for fact in facts:
        by_host[fact['value']['host']].append(fact['location']['path'])
    site_label = 'موضع' if ar else 'site(s)'
    for host in sorted(by_host):
        lines += ['- **' + host + '**: ' + str(len(by_host[host])) + ' ' + site_label]
    return '\n'.join(lines) + '\n'


# SYSTEM-MAP.md, FLOWS.md, CONTRACTS.md and EVOLUTION.md belong to the claims stage, which
# renders them from the ledger with claim cross-references and declared budgets. Writing them
# here too meant the last writer won: 574 lines of measured content were replaced by four empty
# headings in every full run. This module writes only what it alone derives.
# A document that grows with the project outgrows its budget on a real one.
SHOWN_PER_FRAMEWORK = 25

OWNED = ('DATA-MODEL.md', 'DEPLOYMENT.md', 'OBSERVABILITY.md', 'SECURITY-SURFACE.md', 'INTEGRATIONS.md')


def write_all(out, language='ar'):
    out = Path(out)
    files = {
        'DATA-MODEL.md': data_model(out, language=language),
        'DEPLOYMENT.md': deployment(out, language=language),
        'OBSERVABILITY.md': observability(out, language=language),
        'SECURITY-SURFACE.md': security_surface(out, language=language),
        'INTEGRATIONS.md': integrations(out, language=language),
    }
    written = []
    for name, content in files.items():
        path = out / name
        path.write_text(content, encoding='utf-8')
        written.append(str(path))
    return written
