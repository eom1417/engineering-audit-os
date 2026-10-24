"""The readiness check (`eaos doctor`): what this computer has and misses for a check, with the fix of each."""
import re
import shutil
import sys
from pathlib import Path

from ...core.places import home
from .person import box, say
from .project import language


# ---------------------------------------------------------------- the readiness check

def node_major():
    """The major version of the Node.js on PATH, or 0 when there is none."""
    import subprocess
    if not (shutil.which('node') and shutil.which('npm')): return 0
    try: out = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError): return 0
    found = re.match(r'v?(\d+)', out.strip())
    return int(found.group(1)) if found else 0


def _node_row(js):
    major = node_major()
    return {'id': 'node', 'ok': major >= 22, 'when': 'now' if js and major == 0 else 'optional' if js else 'later',
            'ar': 'Node.js 22 أو أحدث' + (f' (عندك {major}، وبعض الأدوات والمشاريع تحتاج 22)' if 0 < major < 22 else ''),
            'en': 'Node.js 22 or newer' + (f' (you have {major}; some tools and projects need 22)' if 0 < major < 22 else ''), 'fix': 'https://nodejs.org  (LTS)'}


def _tools_row(row_id, when, ar, en, tools):
    missing = ', '.join(t['name'] for t in tools if not t['ok'])
    return {'id': row_id, 'ok': not missing, 'when': when, 'ar': ar + (f' (ناقص: {missing})' if missing else ''),
            'en': en + (f' (missing: {missing})' if missing else ''), 'fix': 'eaos doctor --fix'}


def doctor_rows(project=None, probe=False):
    """What each part of the journey needs, and whether it is here: [{id, ok, when, ar, en, fix}]. `probe`: ask each AI
    assistant for one word (eaos/ai/readiness.py) instead of only looking for its command."""
    from ...core.toolchain import doctor as tools
    js = bool(project) and any((Path(project) / folder / 'package.json').is_file() for folder in ('.', 'app', 'web', 'client', 'frontend'))
    rows = [{'id': 'python', 'ok': sys.version_info >= (3, 10), 'when': 'now', 'ar': 'Python 3.10 أو أحدث', 'en': 'Python 3.10 or newer',
             'fix': 'https://www.python.org/downloads/'},
            {'id': 'git', 'ok': bool(shutil.which('git')), 'when': 'now', 'ar': 'git', 'en': 'git', 'fix': 'https://git-scm.com/downloads'},
            _node_row(js)]
    if project:
        rows.append({'id': 'project_git', 'ok': (Path(project) / '.git').exists(), 'when': 'later',
                     'ar': 'المشروع محفوظ في git (للإصلاح فقط)', 'en': 'The project is saved in git (only for fixing)',
                     'fix': 'git init && git add -A && git commit -m "first save"'})
    # The check runs without any of them, and the report names what it could not look at: missing ones warn.
    rows.append(_tools_row('scan_tools', 'optional', 'أدوات الفحص', 'Checking tools',
                           [t for t in tools(stage='assessment')['tools'] if t['role'] in ('read', 'validate') and not t.get('unavailable')]))
    rows.append(_tools_row('fix_tools', 'later', 'أدوات تشغيل برنامجك وإصلاحه', 'Tools to run and fix your app',
                           [t for t in tools(stage='execution')['tools'] if t['name'] in ('playwright', 'k6', 'jscodeshift') and not t.get('unavailable')]))
    from ...core.local_db import binaries
    free = shutil.disk_usage(str(home().parent if not home().exists() else home())).free / 2 ** 30
    return rows + [{'id': 'database', 'ok': binaries() is not None, 'when': 'later',
                    'ar': 'قاعدة بيانات مؤقتة لتشغيل برنامجك (PostgreSQL)', 'en': 'A temporary database to run your app (PostgreSQL)',
                    'fix': 'eaos doctor --fix'}, assistant_row(probe),
                   {'id': 'disk', 'ok': free >= 5, 'when': 'now', 'ar': f'مساحة فارغة 5 GB على الأقل (المتاح {free:.0f} GB)',
                    'en': f'At least 5 GB free (you have {free:.0f} GB)', 'fix': 'eaos clean'}]


def assistant_row(probe=False):
    """The doctor's row for the AI assistants: with `probe`, each one's readiness in a word and, when none is ready, the
    first one's reason and fix; without, whether one is installed."""
    from ...ai import readiness
    return _probed_assistants(readiness) if probe else _installed_assistant(readiness)


def _installed_assistant(readiness):
    found = next((name for name in readiness.NAMES if shutil.which(name)), None)
    named = f' ({readiness.NAMES[found]})' if found else None
    return {'id': 'assistant', 'ok': bool(found), 'when': 'later',
            'ar': 'مساعد ذكي للإصلاح' + (named or ' (Claude Code أو Codex)'),
            'en': 'An AI assistant for fixes' + (named or ' (Claude Code or Codex)'),
            'fix': 'https://claude.com/claude-code  ·  https://github.com/openai/codex'}


def _probed_assistants(readiness):
    rows = readiness.probe_all()
    shown = {lang: ' · '.join(f"{row['name']}: {READY_WORD[lang][row['code'].split('_', 1)[1]]}" for row in rows) for lang in ('ar', 'en')}
    blocked = next((row for row in rows if row['installed']), rows[0])
    return {'id': 'assistant', 'ok': any(row['ready'] for row in rows), 'when': 'later', 'assistants': rows,
            'ar': f"مساعد ذكي للفحص والإصلاح ({shown['ar']})", 'en': f"An AI assistant for the check and fixes ({shown['en']})",
            'fix': (blocked.get('reason') or {}).get('en') or blocked['code']}


# One word for each readiness problem (eaos/ai/readiness.py), for a line that lists every assistant.
READY_WORD = {'ar': {'ready': 'جاهز', 'not_installed': 'غير مثبّت', 'not_working': 'لا يعمل', 'not_signed_in': 'غير مسجّل الدخول',
                     'sign_in_expired': 'دخوله انتهى', 'limit': 'وصل حدّه', 'no_answer': 'ما جاوب', 'failed': 'توقف بخطأ'},
              'en': {'ready': 'ready', 'not_installed': 'not installed', 'not_working': 'does not run', 'not_signed_in': 'not signed in',
                     'sign_in_expired': 'sign-in expired', 'limit': 'usage limit reached', 'no_answer': 'no answer', 'failed': 'stopped with an error'}}


def _pip_install(*packages):
    """Install into EAOS's own environment: with pip, or with uv (the installer's environments have no pip)."""
    import subprocess
    uv = shutil.which('uv') or next((str(p) for p in [home() / 'app/uv/uv'] if p.exists()), None)
    has_pip = subprocess.run([sys.executable, '-m', 'pip', '--version'], capture_output=True).returncode == 0
    argv = ([sys.executable, '-m', 'pip', 'install', '--quiet'] if has_pip or not uv else [uv, 'pip', 'install', '--quiet', '--python', sys.executable])
    subprocess.run(argv + list(packages), check=True)


def doctor(args):
    lang = language(args.lang)
    rows = doctor_rows(Path(args.project).resolve() if args.project else None, probe=True)
    from ... import __version__
    from ...core.build_info import commit
    say(f"ℹ️ EAOS {__version__} · {commit() or ('commit غير معروف' if lang == 'ar' else 'commit unknown')}")
    for row in rows: say(_doctor_line(row, lang))
    tools_missing = [row for row in rows if not row['ok'] and row['fix'] == 'eaos doctor --fix']
    if args.fix and tools_missing:
        from ...core.toolchain import install
        if any(row['id'] == 'database' for row in tools_missing):
            say('…' + ('أثبّت PostgreSQL المؤقت' if lang == 'ar' else 'Installing the temporary PostgreSQL'))
            _pip_install('pgserver>=0.1.4')
        say('…' + ('أثبّت الأدوات الناقصة' if lang == 'ar' else 'Installing the missing tools'))
        install(echo=lambda line: say('   ' + str(line)))
        return doctor(type(args)(project=args.project, lang=lang, fix=False))
    return _doctor_verdict(rows, lang, args.project)


def _doctor_line(row, lang):
    mark = '✅' if row['ok'] else {'now': '❌', 'optional': '⚠️'}.get(row['when'], '⬜')
    later = ('' if row['ok'] or row['when'] == 'now' else (' (الفحص يعمل بدونها، والتقرير يذكر ما لم يُفحص)' if lang == 'ar' else ' (the check runs without them; the report names what was not checked)')
             if row['when'] == 'optional' else (' (لاحقًا)' if lang == 'ar' else ' (later)'))
    return f"{mark} {row[lang]}{later}" + ('' if row['ok'] else f"\n     → {row['fix']}")


def _doctor_verdict(rows, lang, project):
    blocking = [row for row in rows if not row['ok'] and row['when'] == 'now']
    if blocking:
        fixable = all(row['fix'] == 'eaos doctor --fix' for row in blocking)
        box(lang, ('ينقصك شيء قبل البدء' if lang == 'ar' else 'Something is missing before you start'),
            commands=['eaos doctor --fix'] if fixable else [blocking[0]['fix'], 'eaos doctor'], status='fail')
        return 1
    box(lang, ('جهازك جاهز للفحص' if lang == 'ar' else 'Your computer is ready to check a project'),
        commands=[f"eaos start {project}" if project and project != '.' else 'eaos start .'], status='ok',
        note=None if all(row['ok'] for row in rows) else ('ما تبقى لا يمنع الفحص. لتثبيته: eaos doctor --fix' if lang == 'ar'
                                                          else 'What is left does not stop the check. To install it: eaos doctor --fix'))
    return 0
