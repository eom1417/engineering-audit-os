"""The guided way in: `eaos start`, `eaos next`, `eaos status`, `eaos doctor`, `eaos clean`.

For a person who built their app with an AI assistant and does not read code. Four rules hold everywhere:

  1. Nothing to write by hand. Everything EAOS keeps for a project lives outside it, in
     ~/.eaos/projects/<name>-<id>/ (or $EAOS_HOME): the report, the run's records, the logs, and state.json,
     which remembers where the person is. The project folder is never written.
  2. Questions are yes/no or a choice, asked only when nothing can be detected. Without a terminal to ask in
     (an AI assistant runs the command), the question is printed with the command that answers it
     (`eaos next --yes`), and nothing happens until then. Every question asked is kept in state.json.
  3. Every command ends with the same box: what happened, where the results are, and the next command to copy.
  4. A failure is shown in plain words with its fix (eaos/data/errors.json); the technical detail goes to a
     log file whose path is shown, never to the screen.

`next` picks the next step by itself from STEPS: each step says when it is done and how to do it.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import plain
from .start_here import start_here, summary_counts  # noqa: F401  (one home: eaos/start_here.py)

ERRORS = Path(__file__).resolve().parent / 'data/errors.json'
# The commands a user types, each ending with the next-step box (X4 in docs/north-star.json).
USER_COMMANDS = ('start', 'next', 'status', 'doctor', 'clean', 'accept', 'undo', 'show', 'do', 'assistant')
LINE = '─' * 60


class NeedsAnswer(Exception):
    """A yes/no question with nobody at a terminal to answer it."""

    def __init__(self, question):
        super().__init__(question['id'])
        self.question = question


class Declined(Exception):
    """The person said no; nothing was changed."""


# ---------------------------------------------------------------- the place EAOS keeps a project's things

def home():
    return Path(os.environ.get('EAOS_HOME') or Path.home() / '.eaos')


def workspace(project):
    """~/.eaos/projects/<name>-<id>: one per project folder, never inside it."""
    project = Path(project).resolve()
    ident = hashlib.sha256(str(project).encode('utf-8')).hexdigest()[:8]
    return home() / 'projects' / f'{project.name}-{ident}'


def load(project):
    path = workspace(project) / 'state.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def save(state):
    where = Path(state['workspace'])
    where.mkdir(parents=True, exist_ok=True)
    state['updated'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    (where / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def language(requested=None, state=None):
    if requested: return requested
    if state and state.get('lang'): return state['lang']
    return 'ar' if (os.environ.get('LANG') or os.environ.get('LC_ALL') or '').lower().startswith('ar') else 'en'


def current(project='.'):
    """The state of the project in this folder, or of the nearest folder above it that was started."""
    here = Path(project).resolve()
    for folder in (here, *here.parents):
        state = load(folder)
        if state: return state
    raise LookupError('no EAOS project here: run eaos start first')


# ---------------------------------------------------------------- what the person sees

def say(text, stream=None):
    print(text, file=stream or sys.stdout, flush=True)


def box(lang, happened, where=None, commands=(), status='ok', note=None, stream=None, log=None):
    """The fixed ending of every user command: what happened, where, and what to copy next."""
    icon = {'ok': '✅', 'warn': '⚠️', 'fail': '❌', 'ask': '❓'}[status]
    ar = lang == 'ar'
    lines = [LINE, f"{icon} {'ما حدث' if ar else 'What happened'}: {happened}"]
    for line in ([note] if isinstance(note, str) else note or []): lines.append(f'   {line}')
    if where: lines.append(f"📁 {'النتائج' if ar else 'Results'}: {where}")
    if log: lines.append(f"🧾 {'السجل التقني' if ar else 'Technical log'}: {log}")
    if commands:
        lines.append(f"⏭️  {'الخطوة التالية، انسخ والصق' if ar else 'Next step, copy and paste'}:")
        lines += [f'   {command}' for command in commands]
    lines.append(LINE)
    say('\n'.join(lines), stream)


def progress_printer(lang):
    def show(done, total, stage):
        say(f"   [{done + 1}/{total}] {plain.stage(stage, lang)}…")
    return show


def ask(state, qid, text, yes=False, kind='yes_no'):
    """A yes/no question: answered by --yes, by a person at a terminal, or returned to whoever runs us."""
    question = {'id': qid, 'kind': kind, 'text': text}
    asked = state.setdefault('questions', [])
    earlier = next((q for q in asked if q['id'] == qid and q.get('answer') is not None), None)
    if earlier: return earlier['answer']
    if yes: answer = True
    elif sys.stdin.isatty():
        reply = input(f"❓ {text} [{'نعم/لا' if state.get('lang') == 'ar' else 'yes/no'}] ").strip().lower()
        answer = reply in ('y', 'yes', 'نعم', 'ن', 'ايوه', 'ايوة', 'اي', 'اه', 'أيوه')
    else:
        raise NeedsAnswer(question)
    asked.append({**question, 'answer': answer, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    save(state)
    if not answer: raise Declined(qid)
    return answer


# ---------------------------------------------------------------- errors in plain words

def catalog():
    return json.loads(ERRORS.read_text(encoding='utf-8'))['errors']


def explain(problem):
    """The catalog entry for an error: the first whose pattern matches its type and text."""
    text = f'{type(problem).__name__}: {problem}' if isinstance(problem, BaseException) else str(problem)
    for entry in catalog():
        if any(re.search(pattern, text) for pattern in entry['match']): return entry
    return next(entry for entry in catalog() if entry['id'] == 'unknown')


def complete_entries():
    """(complete, total): catalog entries with a plain message, a fix and a command to copy, in both languages (X5)."""
    rows = catalog()
    ok = sum(all(str((row.get(lang) or {}).get(key) or '').strip() and (row.get(lang) or {}).get('commands')
                 for lang in ('ar', 'en') for key in ('message', 'fix')) for row in rows)
    return ok, len(rows)


def show_error(lang, entry_id=None, problem=None, log=None):
    entry = next(e for e in catalog() if e['id'] == entry_id) if entry_id else explain(problem)
    text = entry[lang]
    box(lang, text['message'], status='warn' if entry['id'] in ('not_started', 'declined', 'interrupted') else 'fail',
        note=[text['fix']] + ([text['after']] if text.get('after') else []), commands=text['commands'], log=log)


def log_failure(where, problem):
    logs = Path(where) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    path.write_text(''.join(traceback.format_exception(type(problem), problem, problem.__traceback__)), encoding='utf-8')
    return path


# ---------------------------------------------------------------- the readiness check

def doctor_rows(project=None):
    """What each part of the journey needs, and whether it is here: [{id, ok, when, ar, en, fix}]."""
    from .toolchain import doctor as tools
    js = bool(project) and any((Path(project) / folder / 'package.json').is_file() for folder in ('.', 'app', 'web', 'client', 'frontend'))
    rows = [
        {'id': 'python', 'ok': sys.version_info >= (3, 10), 'when': 'now', 'ar': 'Python 3.10 أو أحدث', 'en': 'Python 3.10 or newer',
         'fix': 'https://www.python.org/downloads/'},
        {'id': 'git', 'ok': bool(shutil.which('git')), 'when': 'now', 'ar': 'git', 'en': 'git', 'fix': 'https://git-scm.com/downloads'},
        {'id': 'node', 'ok': bool(shutil.which('node') and shutil.which('npm')), 'when': 'now' if js else 'later',
         'ar': 'Node.js (لمشاريع JavaScript)', 'en': 'Node.js (for JavaScript projects)', 'fix': 'https://nodejs.org'},
    ]
    if project:
        rows.append({'id': 'project_git', 'ok': (Path(project) / '.git').exists(), 'when': 'later',
                     'ar': 'المشروع محفوظ في git (للإصلاح فقط)', 'en': 'The project is saved in git (only for fixing)',
                     'fix': 'git init && git add -A && git commit -m "first save"'})
    scan = [t for t in tools(stage='assessment')['tools'] if t['role'] in ('read', 'validate')]
    missing = [t['name'] for t in scan if not t['ok']]
    rows.append({'id': 'scan_tools', 'ok': not missing, 'when': 'now',
                 'ar': 'أدوات الفحص' + (f" (ناقص: {', '.join(missing)})" if missing else ''),
                 'en': 'Checking tools' + (f" (missing: {', '.join(missing)})" if missing else ''), 'fix': 'eaos doctor --fix'})
    run = [t for t in tools(stage='execution')['tools'] if t['name'] in ('playwright', 'k6', 'jscodeshift')]
    missing = [t['name'] for t in run if not t['ok']]
    rows.append({'id': 'fix_tools', 'ok': not missing, 'when': 'later',
                 'ar': 'أدوات تشغيل برنامجك وإصلاحه' + (f" (ناقص: {', '.join(missing)})" if missing else ''),
                 'en': 'Tools to run and fix your app' + (f" (missing: {', '.join(missing)})" if missing else ''),
                 'fix': 'eaos doctor --fix'})
    from .local_db import binaries
    rows.append({'id': 'database', 'ok': binaries() is not None, 'when': 'later',
                 'ar': 'قاعدة بيانات مؤقتة لتشغيل برنامجك (PostgreSQL)', 'en': 'A temporary database to run your app (PostgreSQL)',
                 'fix': 'eaos doctor --fix'})
    assistant = next((name for name in ('claude', 'codex') if shutil.which(name)), None)
    rows.append({'id': 'assistant', 'ok': bool(assistant), 'when': 'later',
                 'ar': 'مساعد ذكي للإصلاح' + (f' ({assistant})' if assistant else ' (Claude Code أو Codex)'),
                 'en': 'An AI assistant for fixes' + (f' ({assistant})' if assistant else ' (Claude Code or Codex)'),
                 'fix': 'https://claude.com/claude-code  ·  https://github.com/openai/codex'})
    free = shutil.disk_usage(str(home().parent if not home().exists() else home())).free / 2 ** 30
    rows.append({'id': 'disk', 'ok': free >= 5, 'when': 'now', 'ar': f'مساحة فارغة 5 GB على الأقل (المتاح {free:.0f} GB)',
                 'en': f'At least 5 GB free (you have {free:.0f} GB)', 'fix': 'eaos clean'})
    return rows


def doctor(args):
    lang = language(args.lang)
    project = Path(args.project).resolve() if args.project else None
    rows = doctor_rows(project)
    for row in rows:
        mark = '✅' if row['ok'] else ('❌' if row['when'] == 'now' else '⬜')
        later = '' if row['ok'] or row['when'] == 'now' else (' (لاحقًا)' if lang == 'ar' else ' (later)')
        say(f"{mark} {row[lang]}{later}" + ('' if row['ok'] else f"\n     → {row['fix']}"))
    tools_missing = [row for row in rows if not row['ok'] and row['fix'] == 'eaos doctor --fix']
    if args.fix and tools_missing:
        from .toolchain import install
        if any(row['id'] == 'database' for row in tools_missing):
            import subprocess
            say('…' + ('أثبّت PostgreSQL المؤقت' if lang == 'ar' else 'Installing the temporary PostgreSQL'))
            subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'pgserver>=0.1.4'], check=True)
        stages = ['assessment'] + (['execution'] if any(row['id'] == 'fix_tools' for row in tools_missing) else [])
        say('…' + ('أثبّت الأدوات الناقصة' if lang == 'ar' else 'Installing the missing tools'))
        for stage in stages: install(stage=stage, echo=lambda line: say('   ' + str(line)))
        return doctor(type(args)(project=args.project, lang=lang, fix=False))
    blocking = [row for row in rows if not row['ok'] and row['when'] == 'now']
    if blocking:
        fixable = all(row['fix'] == 'eaos doctor --fix' for row in blocking)
        box(lang, ('ينقصك شيء قبل البدء' if lang == 'ar' else 'Something is missing before you start'),
            commands=['eaos doctor --fix'] if fixable else [blocking[0]['fix'], 'eaos doctor'], status='fail')
        return 1
    box(lang, ('جهازك جاهز للفحص' if lang == 'ar' else 'Your computer is ready to check a project'),
        commands=[_start_command(args.project)], status='ok',
        note=None if all(row['ok'] for row in rows) else ('⬜ = تحتاجه لاحقًا عند الإصلاح، لا الآن' if lang == 'ar'
                                                          else '⬜ = needed later, when fixing, not now'))
    return 0


def _start_command(project):
    return f"eaos start {project}" if project and project != '.' else 'eaos start .'


# ---------------------------------------------------------------- the steps `next` walks through

def report_of(state):
    return Path(state['workspace']) / 'report'


def scan_done(state):
    manifest = report_of(state) / 'run-manifest.json'
    return manifest.is_file() and json.loads(manifest.read_text(encoding='utf-8')).get('status') in ('COMPLETE', 'PARTIAL', 'INCOMPLETE') \
        and (report_of(state) / 'START-HERE.md').is_file()


def scan(state, args):
    """Step 1: the whole audit, with progress, then START-HERE.md in plain words."""
    lang = state['lang']
    from .pipeline import execute, resume
    out = report_of(state)
    partial = (out / 'run-manifest.json').is_file()
    say(('أفحص مشروعك الآن. يأخذ هذا عادة من 5 إلى 30 دقيقة حسب حجمه، ولن يتغير فيه شيء.' if lang == 'ar' else
         'Checking your project now. This usually takes 5 to 30 minutes depending on its size; nothing in it changes.'))
    options = dict(language=lang, engines=[], site=True, progress=progress_printer(lang))
    try:
        manifest = (resume if partial else execute)(state['project'], out, **options)
    except ValueError:                                  # the source changed since the partial run: start afresh
        shutil.rmtree(out, ignore_errors=True)
        manifest = execute(state['project'], out, **options)
    page = out / 'START-HERE.md'
    if not page.is_file(): start_here(out, lang, Path(state['project']).name)   # compose did not run: still one page
    state['scanned'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    save(state)
    counts = summary_counts(out)
    happened = (f"فحصت مشروعك: {counts['problems']} مشكلة، منها {counts['ready']} يمكن إصلاحها آليًا" if lang == 'ar' else
                f"Checked your project: {counts['problems']} problems, {counts['ready']} of them can be fixed automatically")
    note = None
    if manifest.get('status') != 'COMPLETE':
        note = ('بعض أجزاء الفحص لم تكتمل، ومذكورة في أسفل الصفحة' if lang == 'ar'
                else 'Some parts of the check did not complete; they are listed at the bottom of the page')
    box(lang, happened, where=page, commands=['eaos next'], status='ok' if not note else 'warn', note=note)
    return 0


def later_steps(state, args):
    lang = state['lang']
    waiting = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if waiting:
        box(lang, (f"الدفعة {waiting['number']} تنتظر قرارك في الفرع {waiting['branch']}" if lang == 'ar'
                   else f"Batch {waiting['number']} is waiting for you on the branch {waiting['branch']}"),
            commands=['eaos accept', 'eaos undo'])
    else:
        box(lang, ('لا توجد إصلاحات آلية أخرى لهذا المشروع الآن؛ ما تبقى يحتاج قرارك، وهو في صفحة «ابدأ هنا»' if lang == 'ar'
                   else 'No more automatic fixes for this project now; what is left needs your decision, and it is on the "Start here" page'),
            where=report_of(state) / 'START-HERE.md', commands=['eaos status'])
    return 0


def runtime_of(state):
    return Path(state['workspace']) / 'runtime'


def _git(project, *args):
    import subprocess
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def _commit(state):
    done = _git(state['project'], 'rev-parse', 'HEAD')
    if done.returncode: raise RuntimeError(f"{state['project']}: fatal: not a git repository")
    return done.stdout.strip()


def _saved_note(state):
    """Unsaved edits are not part of the run: said once, plainly, never a stop."""
    if not _git(state['project'], 'status', '--porcelain').stdout.strip(): return None
    return ('عندك تعديلات لم تُحفظ في git: أعمل على آخر نسخة محفوظة فقط' if state['lang'] == 'ar'
            else 'You have edits not saved in git: I work on the last saved version only')


def ready_done(state):
    """The run is set up, for the commit the project is at now."""
    setup = state.get('setup') or {}
    return bool(setup.get('commit')) and setup['commit'] == _commit(state) and (runtime_of(state) / 'run.json').is_file()


def ready(state, args):
    """Step 2: consent, then a run profile nobody writes (eaos/live_setup.py)."""
    from . import live_setup
    from .runtime.assistants import available, provider
    lang, commit = state['lang'], _commit(state)
    assistant = (available() or [None])[0]
    ask(state, 'run_app',
        (f"لأصلح بأمان، أحتاج أن أشغّل برنامجك في نسخة منفصلة على جهازك، بقاعدة بيانات مؤقتة وبلا أسرارك"
         + (f"، وقد أستعين بمساعدك الذكي ({assistant}) لأفهم طريقة تشغيله" if assistant else '') + '. أوافق؟')
        if lang == 'ar' else
        ("To fix safely I need to run your app in a separate copy on this computer, with a temporary database and none of your secrets"
         + (f"; I may ask your AI assistant ({assistant}) how it runs" if assistant else '') + '. OK?'), args.yes)
    runtime = runtime_of(state)
    who = _git(state['project'], 'config', 'user.name').stdout.strip() or os.environ.get('USER') or 'the owner'
    live_setup.authorize(state['project'], runtime, who)
    say(('أجهّز تشغيل برنامجك. قد يأخذ هذا من 5 إلى 20 دقيقة.' if lang == 'ar'
         else 'Setting up your app to run. This can take 5 to 20 minutes.'))
    _, model = provider()
    def progress(n):
        if str(n).startswith('baseline'):
            say('   ' + ('أجهّز نسخة الإنتاج من برنامجك لقياس سرعته…' if lang == 'ar' else 'Preparing the production build of your app, to measure its speed…'))
        else:
            say(f"   [{n}/{live_setup.ATTEMPTS}] " + ('أشغّل برنامجك وأفتح بعض شاشاته…' if lang == 'ar' else 'Starting your app and opening some of its screens…'))
    result = live_setup.setup(state['project'], runtime, report=report_of(state), provider=model, say=progress)
    state['setup'] = {'commit': commit, 'ok': result['ok'], 'attempts': result['attempts'], 'limitations': result['limitations']}
    state.pop('safety', None)
    save(state)
    notes = [n for n in [_saved_note(state)] if n]
    if result['limitations']:
        notes.append((f"{len(result['limitations'])} ملاحظة عمّا لم يكتمل، مكتوبة في الملف أدناه (limitations)" if lang == 'ar'
                      else f"{len(result['limitations'])} notes on what is incomplete, written in the file below (limitations)"))
    if result['ok']:
        box(lang, 'برنامجك يعمل في النسخة المنفصلة' if lang == 'ar' else 'Your app runs in the separate copy',
            where=runtime / 'run.json', commands=['eaos next'], note=notes or None)
    else:
        box(lang, ('لم أستطع تشغيل برنامجك كاملًا؛ سأكمل بما أمكن، والقيود مكتوبة' if lang == 'ar'
                   else 'I could not get your app fully running; I will go on with what works, and the limits are written down'),
            where=runtime / 'run.json', commands=['eaos next'], status='warn', note=notes)
    return 0


def safety_done(state):
    safety = state.get('safety') or {}
    return bool(safety.get('commit')) and safety['commit'] == (state.get('setup') or {}).get('commit')


def safety(state, args):
    """Step 3: the safety net: every screen recorded on the original, and its speed under load."""
    from .behavior_lock import run_lock
    from .runtime_baseline import run_baseline
    lang, runtime = state['lang'], runtime_of(state)
    say(('أصوّر كل شاشات برنامجك كما هي الآن، ثم أقيس سرعته. هذا ما سأقارن به بعد كل إصلاح (15 إلى 30 دقيقة).' if lang == 'ar'
         else 'Recording every screen of your app as it is now, then measuring its speed. Every fix is compared with this (15 to 30 minutes).'))
    say('   [1/2] ' + ('أصوّر الشاشات…' if lang == 'ar' else 'Recording the screens…'))
    record = run_lock(report_of(state), state['project'], runtime)
    results = record['results']
    passed = sum(r['status'] == 'passed' for r in results)
    speed, notes = None, []
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    baseline = profile.get('baseline') or {}
    if baseline.get('build') and baseline.get('verified') and list((report_of(state) / 'nfr/k6').glob('*.js')):
        say('   [2/2] ' + ('أقيس السرعة تحت ضغط مستخدمين كثيرين…' if lang == 'ar' else 'Measuring speed under many users…'))
        try:
            performance = run_baseline(report_of(state), state['project'], runtime)
            speed = max((s['before']['p95_ms'] for s in performance['scenarios']), default=None)
        except Exception as problem:            # speed is measured when it can be; the screens are the safety net
            log = log_failure(state['workspace'], problem)
            notes.append(('لم أستطع قياس السرعة: ' if lang == 'ar' else 'Could not measure speed: ')
                         + explain(problem)[lang]['message'] + f' ({log})')
    elif baseline.get('build'):
        notes.append('لم تعمل نسخة الإنتاج من برنامجك هنا، فلم أقس السرعة؛ السبب في run.json' if lang == 'ar'
                     else 'The production build of your app did not run here, so speed was not measured; the reason is in run.json')
    else:
        notes.append('لا يوجد أمر بناء للإنتاج، فلم أقس السرعة' if lang == 'ar' else 'No production build, so speed was not measured')
    state['safety'] = {'commit': state['setup']['commit'], 'screens': len(results), 'passed': passed, 'p95_ms': speed}
    save(state)
    happened = (f"صوّرت {passed} من {len(results)} شاشة" + (f"، وأبطأ الطلبات تأخذ {speed:.0f} ملي ثانية" if speed else '')
                if lang == 'ar' else f"Recorded {passed} of {len(results)} screens" + (f"; the slowest requests take {speed:.0f} ms" if speed else ''))
    skipped = [r for r in results if r['status'] != 'passed']
    if skipped: notes.append((f"{len(skipped)} شاشة لم تُصوَّر، وأسبابها في السجل" if lang == 'ar'
                              else f"{len(skipped)} screens were not recorded; the reasons are in the record"))
    box(lang, happened, where=runtime / 'behavior-lock/results.json', commands=['eaos next'],
        status='ok' if passed else 'warn', note=notes or None)
    return 0


def _waves(state):
    return [w for w in state.get('waves') or [] if w.get('base') == (state.get('setup') or {}).get('commit')]


def fix_done(state):
    """A wave of this commit is in the person's project as a branch, or no ready card is left to try."""
    from .waves import next_batch
    if any(w.get('status') == 'applied' for w in _waves(state)): return True
    return not next_batch(report_of(state), state.get('tried') or [])


def fix(state, args):
    """Step 4: a wave of fixes, made by the codemods and the person's assistant, checked, then handed over as a
    branch (eaos/waves.py). One question, the first time: may I fix, and put the result on a branch?"""
    from . import waves
    from .runtime.assistants import provider
    lang = state['lang']
    batch = waves.next_batch(report_of(state), state.get('tried') or [])
    number = len(state.get('waves') or []) + 1
    ask(state, 'fix_code',
        (f'أصلح الآن دفعات من الإصلاحات الجاهزة (هذه الدفعة {len(batch)})، وأجرّب كلًّا منها في النسخة المنفصلة، '
         f'ثم أضع ما ينجح في فرع جديد في مشروعك (eaos/wave-{number}) دون أن ألمس فرعك الحالي أو ملفاتك. أوافق؟')
        if lang == 'ar' else
        (f'Fix batches of the ready fixes now (this one: {len(batch)}), try each in the separate copy, and put what '
         f'passes on a new branch in your project (eaos/wave-{number}) without touching your current branch or files. OK?'), args.yes)
    say((f'أصلح الدفعة {number}: {len(batch)} إصلاحات. قد يأخذ هذا من 20 إلى 60 دقيقة.' if lang == 'ar'
         else f'Fixing batch {number}: {len(batch)} fixes. This can take 20 to 60 minutes.'))

    def progress(kind, *rest):
        if kind == 'card':
            index, total, card = rest
            title, _ = plain.problem(card.get('pattern'), lang)
            say(f"   [{index}/{total}] {title}: {(card.get('paths') or [''])[0]}")
        elif kind == 'acceptance': say('   ' + ('أتحقق أن كل مشكلة اختفت…' if lang == 'ar' else 'Checking every problem is gone…'))
        elif kind == 'gates': say('   ' + ('أشغّل فحوص مشروعك وأقارن الشاشات…' if lang == 'ar' else "Running your project's checks and comparing the screens…"))
        elif kind == 'bisect': say('   ' + ('أبحث عن الإصلاح الذي سبّب مشكلة…' if lang == 'ar' else 'Looking for the fix that caused a problem…'))
    _, model = provider()
    summary = waves.run_batch(report_of(state), state['project'], runtime_of(state), number, batch, provider=model, say=progress)
    wave = {'number': number, 'base': state['setup']['commit'], 'cards': batch, 'kept': summary['kept'],
            'failed': summary['failed'], 'branch': summary['branch'], 'stat': summary['stat'], 'status': 'empty'}
    state['tried'] = sorted(set(state.get('tried') or []) | set(batch))
    if summary['kept']:
        waves.apply(state['project'], summary)
        wave['status'] = 'applied'
        state['applied'] = True
    state.setdefault('waves', []).append(wave)
    save(state)
    notes = []
    if summary['failed']:
        notes.append((f"{len(summary['failed'])} لم تنجح فتركتها، وأسبابها في {runtime_of(state) / 'runtime/execution.json'}" if lang == 'ar'
                      else f"{len(summary['failed'])} did not pass and were left out; the reasons are in {runtime_of(state) / 'runtime/execution.json'}"))
    if not summary['kept']:
        box(lang, ('لم ينجح أي إصلاح في هذه الدفعة، فلم يتغير شيء في مشروعك' if lang == 'ar'
                   else 'No fix in this batch passed, so nothing changed in your project'), commands=['eaos next'], status='warn', note=notes)
        return 0
    notes.insert(0, (f"التغييرات: {summary['stat']}. فرعك الحالي كما هو." if lang == 'ar'
                     else f"The changes: {summary['stat']}. Your current branch is as it was."))
    box(lang, (f"نجح {len(summary['kept'])} من {len(batch)} إصلاحًا، وهي الآن في الفرع {summary['branch']} في مشروعك" if lang == 'ar'
               else f"{len(summary['kept'])} of {len(batch)} fixes passed; they are on the branch {summary['branch']} in your project"),
        where=runtime_of(state) / 'waves' / f'wave-{number}', note=notes,
        commands=['eaos accept   ' + ('# لاعتمادها في مشروعك' if lang == 'ar' else '# to take them into your project'),
                  'eaos undo     ' + ('# للتخلي عنها' if lang == 'ar' else '# to throw them away')])
    return 0


def accept(args):
    """Take the latest wave into the current branch: a fast-forward only, and only with no unsaved edits."""
    state = current(args.project)
    lang = state['lang']
    wave = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if wave is None:
        box(lang, 'لا توجد دفعة إصلاحات تنتظر الاعتماد' if lang == 'ar' else 'No batch of fixes is waiting', commands=['eaos next'], status='warn')
        return 0
    if _git(state['project'], 'status', '--porcelain').stdout.strip():
        raise RuntimeError('uncommitted changes: working tree is not clean')
    done = _git(state['project'], 'merge', '--ff-only', wave['branch'])
    if done.returncode:
        box(lang, ('فرعك تغيّر منذ الإصلاح، فلا أدمج تلقائيًا' if lang == 'ar' else 'Your branch changed since the fixes, so I do not merge automatically'),
            commands=[f"git merge {wave['branch']}"], status='warn',
            note=('ادمجها بنفسك أو اطلب من مساعدك الذكي ذلك' if lang == 'ar' else 'Merge it yourself, or ask your AI assistant to'))
        return 0
    wave['status'] = 'accepted'
    save(state)
    box(lang, (f"اعتمدت الدفعة {wave['number']} في مشروعك" if lang == 'ar' else f"Batch {wave['number']} is now in your project"),
        commands=['eaos next   ' + ('# للدفعة التالية' if lang == 'ar' else '# for the next batch')],
        note=('إن أردت التراجع لاحقًا: git revert، أو اطلب من مساعدك الذكي' if lang == 'ar' else 'To go back later: git revert, or ask your AI assistant'))
    return 0


def undo(args):
    """Throw the latest wave away: its branch goes, while it is not merged."""
    from .waves import undo as drop
    state = current(args.project)
    lang = state['lang']
    wave = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if wave is None:
        box(lang, 'لا يوجد ما أتراجع عنه' if lang == 'ar' else 'There is nothing to undo', commands=['eaos next'], status='warn')
        return 0
    outcome = drop(state['project'], wave['branch'])
    if outcome == 'merged':
        box(lang, ('هذه الدفعة مدموجة في فرعك، فلا أحذفها؛ التراجع عنها قرارك' if lang == 'ar'
                   else 'This batch is merged into your branch, so I do not remove it; undoing it is your decision'),
            commands=['git log --oneline -5'], status='warn', note=('اطلب من مساعدك الذكي: «تراجع عن دمج eaos/wave»' if lang == 'ar'
                                                                      else 'Ask your AI assistant: "revert the eaos/wave merge"'))
        return 0
    wave['status'] = 'undone'
    save(state)
    box(lang, (f"حذفت الفرع {wave['branch']}؛ مشروعك كما كان" if lang == 'ar' else f"Removed the branch {wave['branch']}; your project is as it was"),
        commands=['eaos next'])
    return 0


def show(args):
    """The "Start here" page, printed: what was found, in plain words."""
    state = current(args.project)
    lang = language(args.lang, state)
    page = report_of(state) / 'START-HERE.md'
    if not page.is_file():
        box(lang, 'لم أفحص المشروع بعد' if lang == 'ar' else 'I have not checked the project yet', commands=['eaos next'], status='warn')
        return 0
    say(page.read_text(encoding='utf-8'))
    box(lang, 'هذه نتيجة الفحص' if lang == 'ar' else 'This is what the check found', where=page, commands=['eaos next'])
    return 0


def do(args):
    """A request in plain words (`eaos do "افحص مشروعي"`), understood (eaos/intents.py) and done."""
    from .intents import understand
    lang = language(args.lang)
    request = ' '.join(args.request or [])
    intent, _ = understand(request)
    if intent is None:
        box(lang, ('لم أفهم الطلب. جرّب مثلًا: «افحص مشروعي»، «كمّل»، «وش المشاكل»، «وين وصلنا»' if lang == 'ar'
                   else 'I did not understand. Try, for example: "check my project", "continue", "what is wrong", "where are we"'),
            commands=['eaos do "افحص مشروعي"' if lang == 'ar' else 'eaos do "check my project"'], status='warn')
        return 0
    command = intent['command'][0]
    say(('سأنفّذ: ' if lang == 'ar' else 'Doing: ') + 'eaos ' + ' '.join(intent['command']))
    from argparse import Namespace
    target = intent['command'][1] if len(intent['command']) > 1 else args.project
    inner = Namespace(command=command, project=target if command != 'doctor' else None, lang=args.lang, yes=args.yes, fix=False)
    return COMMANDS[command](inner)


def assistant(args):
    """Teach the person's AI assistant to use EAOS: the Claude Code skill and the Codex instructions, installed."""
    from .assistant_setup import install
    lang = language(args.lang)
    done = install()
    if not done:
        box(lang, ('لم أجد Claude Code ولا Codex على جهازك' if lang == 'ar' else 'I found neither Claude Code nor Codex on this computer'),
            commands=['eaos start .'], status='warn',
            note=('ثبّت أحدهما لتكلّمه بكلامك، أو استخدم أوامر eaos مباشرة' if lang == 'ar'
                  else 'Install one to talk to it in your own words, or use the eaos commands directly'))
        return 0
    box(lang, ('صار مساعدك يعرف EAOS: ' if lang == 'ar' else 'Your assistant now knows EAOS: ') + ', '.join(done),
        commands=['«افحص مشروعي»' if lang == 'ar' else '"check my project"'],
        note=('افتح مساعدك في مجلد مشروعك واكتب له بكلامك' if lang == 'ar' else 'Open your assistant in your project folder and ask in your own words'))
    return 0


# (id, Arabic title, English title, done(state), run(state, args)).
STEPS = [
    ('scan', 'فحص المشروع وكتابة التقرير', 'Check the project and write the report', scan_done, scan),
    ('ready', 'تجهيز تشغيل برنامجك في نسخة منفصلة', 'Set up your app to run in a separate copy', ready_done, ready),
    ('safety', 'تصوير برنامجك وقياس سرعته قبل أي تغيير', 'Record your app and measure its speed before any change', safety_done, safety),
    ('fix', 'إصلاح دفعة وتسليمها فرعًا في مشروعك', 'Fix a batch and hand it over as a branch in your project', fix_done, fix),
]


def next_step(state):
    return next((step for step in STEPS if not step[3](state)), None)


# ---------------------------------------------------------------- the user commands

def start(args):
    project = Path(args.project).resolve()
    if not project.is_dir(): raise FileNotFoundError(f'No such file or directory: {project}')
    state = load(project) or {'schema_version': 1, 'project': str(project), 'workspace': str(workspace(project)),
                              'started': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'questions': []}
    state['lang'] = language(args.lang, state if not args.lang else None)
    save(state)
    lang = state['lang']
    say((f"مرحبًا. سأفحص مشروع «{project.name}» وأكتب لك تقريرًا بكلام بسيط. لن أغيّر شيئًا في مشروعك." if lang == 'ar' else
         f"Hello. I will check «{project.name}» and write you a report in plain words. I will not change anything in your project."))
    blocking = [row for row in doctor_rows(project) if not row['ok'] and row['when'] == 'now']
    if blocking:
        tools_only = all(row['fix'] == 'eaos doctor --fix' for row in blocking)
        if not tools_only:
            for row in blocking: say(f"❌ {row[lang]}\n     → {row['fix']}")
            box(lang, 'ينقص جهازك شيء قبل الفحص' if lang == 'ar' else 'Your computer is missing something first',
                commands=[blocking[0]['fix'], 'eaos start .'], status='fail')
            return 1
        ask(state, 'install_tools', 'أدوات الفحص غير مثبّتة. أثبّتها الآن؟ (تحتاج إنترنت، بضع دقائق)' if lang == 'ar'
            else 'The checking tools are not installed. Install them now? (needs internet, a few minutes)', args.yes)
        from .toolchain import install
        install(stage='assessment', echo=lambda line: say('   ' + str(line)))
    return advance(state, args)


def next_command(args):
    state = current(args.project)
    if args.lang: state['lang'] = args.lang; save(state)
    return advance(state, args)


def advance(state, args):
    step = next_step(state)
    if step is None: return later_steps(state, args)
    return step[4](state, args)


def status(args):
    state = current(args.project)
    lang = language(args.lang, state)
    say(('مشروع' if lang == 'ar' else 'Project') + f": {state['project']}")
    upcoming = next_step(state)
    for step in STEPS:
        mark = '✅' if step[3](state) else ('▶️' if step is upcoming else '⬜')
        say(f"{mark} {step[1] if lang == 'ar' else step[2]}")
    if upcoming:
        box(lang, ('التالي: ' if lang == 'ar' else 'Next: ') + (upcoming[1] if lang == 'ar' else upcoming[2]),
            where=state['workspace'], commands=['eaos next'])
    else:
        box(lang, 'كل الخطوات المتاحة الآن اكتملت' if lang == 'ar' else 'Every step available now is done',
            where=report_of(state) / 'START-HERE.md', commands=['eaos next'])
    return 0


def clean(args):
    """Remove the isolated copies and caches EAOS made; reports and state stay."""
    lang = language(args.lang)
    freed = 0
    for folder in (home() / 'projects').glob('*/runtime/sandbox'):
        freed += sum(f.stat().st_size for f in folder.rglob('*') if f.is_file() and not f.is_symlink())
        shutil.rmtree(folder, ignore_errors=True)
    for folder in (home() / 'projects').glob('*/runtime/candidates'):
        for copy in [p for p in folder.iterdir() if p.is_dir()]:
            freed += sum(f.stat().st_size for f in copy.rglob('*') if f.is_file() and not f.is_symlink())
            shutil.rmtree(copy, ignore_errors=True)
    gb = freed / 2 ** 30
    box(lang, (f'حذفت النسخ المؤقتة ووفّرت {gb:.1f} GB. التقارير باقية' if lang == 'ar'
               else f'Removed the temporary copies and freed {gb:.1f} GB. Reports are kept'),
        where=home(), commands=['eaos next'])
    return 0


COMMANDS = {'start': start, 'next': next_command, 'status': status, 'doctor': doctor, 'clean': clean, 'accept': accept, 'undo': undo,
            'show': show, 'do': do, 'assistant': assistant}


def main(args):
    """Run one user command; any failure ends in plain words, a fix, and the log's path."""
    lang = language(getattr(args, 'lang', None))
    try:
        state = current(getattr(args, 'project', '.') or '.')
        lang = language(getattr(args, 'lang', None), state)
    except LookupError:
        state = None
    try:
        return COMMANDS[args.command](args) or 0
    except NeedsAnswer as waiting:
        box(lang, waiting.question['text'], status='ask',
            note=('للموافقة اكتب الأمر أدناه، ولن يحدث شيء حتى توافق' if lang == 'ar'
                  else 'To agree, type the command below; nothing happens until you do'),
            commands=[f"eaos {args.command} --yes" + (f" {args.project}" if args.command == 'start' and args.project not in (None, '.') else '')])
        return 4
    except Declined:
        show_error(lang, 'declined')
        return 5
    except LookupError as problem:
        if 'no EAOS project here' not in str(problem): raise
        show_error(lang, 'not_started')
        return 6
    except (Exception, KeyboardInterrupt) as problem:
        where = Path(state['workspace']) if state else home()
        show_error(lang, problem=problem, log=log_failure(where, problem))
        return 1
