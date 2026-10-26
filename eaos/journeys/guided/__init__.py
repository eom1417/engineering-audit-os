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
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ...core.project import branches
from ...core.project.state import current, load, looks_like_project
from ...core.project.places import home, outputs_root, workspace
from .batches import reconcile
from .checking import choose_assistant, later_steps, scan
from .doctor import doctor, doctor_rows
from .person import Declined, NeedsAnswer, box, explain, say, show_error
from .project import RESUME, language, log_failure, outputs, report_of, save, scan_done
from .running import fix, fix_done, ready, ready_done, safety, safety_done

# The names other modules call through the package (guided.publish, guided.report_of ...), each kept in one module here.
from ...core.project.state import runtime_of  # noqa: F401
from ...core.project.places import second_name  # noqa: F401
from .batches import choose, close_batch, merge, retire_stale_batch  # noqa: F401
from .checking import (agree_to_assistant, check_provider, check_runtime,  # noqa: F401
                       tools_for_check)
from .doctor import assistant_row  # noqa: F401
from .person import LINE, ToolsMissing, answered, ask, catalog, progress_printer  # noqa: F401
from .project import (PUBLISHERS, REPORT_PARTS, _branch_exists, _git, _saved_note, chosen_assistant, publish,  # noqa: F401
                      publish_fixes, report_stamp, safety_holds, same_code, set_up, source, tip)
from .running import safety_run  # noqa: F401


# The commands a user types, each ending with the next-step box (X4 in docs/north-star.json).
USER_COMMANDS = ('start', 'next', 'status', 'doctor', 'clean', 'accept', 'undo', 'show', 'do', 'assistant', 'handover')


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
    """A request in plain words (`eaos do "افحص مشروعي"`), understood (eaos/core/language/intents.py) and done."""
    from ...core.language.intents import understand
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
    from ...ai.assistant.setup import install
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


# (id, Arabic title, English title, done(state), run(state, args)): check and fix, its words in eaos/data/journeys.json
STEPS = [(step['id'], step['title']['ar'], step['title']['en'], done, run) for step, (done, run) in zip(
    json.loads((Path(__file__).resolve().parents[2] / 'data/journeys.json').read_text(encoding='utf-8'))['journeys']['check']['steps'],
    ((scan_done, scan), (ready_done, ready), (safety_done, safety), (fix_done, fix)))]


def next_step(state):
    return next((step for step in STEPS if not step[3](state)), None)


# ---------------------------------------------------------------- the user commands

# What a project folder holds at its top; the home folder, the disk's root, or Downloads never is one.
def start(args):
    project = Path(args.project).resolve()
    if not project.is_dir(): raise ValueError(f'project folder not found: {project}')
    if not looks_like_project(project): raise ValueError(f'not a project folder: {project}')
    state = load(project) or {'schema_version': 1, 'project': str(project), 'workspace': str(workspace(project)),
                              'started': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'questions': []}
    state['lang'] = language(args.lang, state if not args.lang else None)
    save(state)
    _keep_assistant(state, getattr(args, 'assistant', None))
    lang = state['lang']
    say((f"مرحبًا. سأفحص مشروع «{project.name}» وأكتب لك تقريرًا بكلام بسيط. لن أغيّر شيئًا في مشروعك." if lang == 'ar' else
         f"Hello. I will check «{project.name}» and write you a report in plain words. I will not change anything in your project."))
    if _missing_first(project, lang): return 1
    watch(state, args)
    if not (getattr(args, 'path', None) or getattr(args, 'mode', None)): return advance(state, args)
    return TERMINAL['check'](args)              # asked: a check now, the one `eaos check` starts, followed here


def _keep_assistant(state, named):
    """The assistant `eaos start --assistant` named kept for the check's AI ('none': the check goes without one)."""
    if named: choose_assistant(state, named != 'none', None if named == 'none' else named, via='command')


def _missing_first(project, lang):
    """Whether the computer misses something the check needs now that `eaos doctor --fix` cannot install; said, with its fix."""
    blocking = [row for row in doctor_rows(project) if not row['ok'] and row['when'] == 'now']
    if not blocking or all(row['fix'] == 'eaos doctor --fix' for row in blocking): return False
    for row in blocking: say(f"❌ {row[lang]}\n     → {row['fix']}")
    box(lang, 'ينقص جهازك شيء قبل الفحص' if lang == 'ar' else 'Your computer is missing something first',
        commands=[blocking[0]['fix'], 'eaos start .'], status='fail')
    return True


def watch(state, args):
    """Interface first: the install of the tools starts in the background (eaos/core/toolchain/runs.py), and the project's Studio,
    started when it is not running, is printed and opened in the browser, unless `eaos start --no-watch`: on
    "Preparing the tools" while a tool the check needs here is not ready, else on the live map."""
    if getattr(args, 'no_watch', False): return
    from ...core.system import launch
    from ...core import toolchain
    toolchain.prepare(state['project'])
    record, _ = launch.start(state)
    if not record: return
    url = launch.url_of(record, '/scan' if toolchain.ready(state['project']) else '/tools')
    say(f"تابع العمل حيًّا: {url}" if state['lang'] == 'ar' else f"Watch the work live: {url}")
    launch._open(url, True)


def next_command(args):
    state = current(args.project)
    reconcile(state)
    if args.lang: state['lang'] = args.lang; save(state)
    return advance(state, args)


def advance(state, args):
    step = next_step(state)
    if step is None: return later_steps(state, args)
    return step[4](state, args)


def status(args):
    state = current(args.project)
    reconcile(state)
    lang = language(args.lang, state)
    say(('مشروع' if lang == 'ar' else 'Project') + f": {state['project']}\n{branches.fresh_line(state, lang)}")
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
    """Remove the isolated copies, caches and app sessions EAOS made; reports and state stay. With --pictures, the screen
    pictures, the crawl and the assistant's raw runs of every report (eaos/pipeline/run.py PICTURES): a new check
    takes them again."""
    lang = language(args.lang)
    freed = 0
    if (pictures := getattr(args, 'pictures', False)): freed += _pictures_cleared()
    from ...live.isolation.sandbox import sweep                     # a live run's folder (held) stays: another project's check runs on
    from ...live.access.sign_in import forget                    # the sessions of the apps: a check asks to sign in again
    freed += sum(sweep(folder) for folder in (home() / 'projects').glob('*/runtime*/sandbox'))
    for folder in (home() / 'projects').glob('*'): forget(folder)
    freed += _copies_removed()
    box(lang, (f"حذفت النسخ المؤقتة{' وصور الشاشات القديمة' if pictures else ''} ووفّرت {freed / 2 ** 30:.1f} GB. التقارير باقية" if lang == 'ar'
               else f"Removed the temporary copies{' and the old screen pictures' if pictures else ''} and freed {freed / 2 ** 30:.1f} GB. Reports are kept"),
        where=home(), commands=['eaos next'])
    return 0


def _pictures_cleared():
    """The screen pictures, crawl and raw assistant runs of every report removed (PICTURES); the bytes freed."""
    from ...pipeline.run import PICTURES, clear
    freed = 0
    for report in (*outputs_root().glob('*/technical'), *outputs_root().glob('*/branches/*/technical')):
        freed += clear(report, PICTURES)
    return freed


def _copies_removed():
    """The isolated copies of every project's batches removed; the bytes freed."""
    freed = 0
    for folder in (home() / 'projects').glob('*/runtime/candidates'):
        for copy in [p for p in folder.iterdir() if p.is_dir()]:
            freed += sum(f.stat().st_size for f in copy.rglob('*') if f.is_file() and not f.is_symlink())
            shutil.rmtree(copy, ignore_errors=True)
    return freed


def resume(args):
    """Where the work stopped, for the person moving to another assistant (a usage limit ran out), and what to tell it.
    The words come from eaos/journeys/handover.resume, registered in RESUME."""
    state = current(args.project)
    lang = language(args.lang, state)
    found = RESUME[0](state['project'], lang) if RESUME else None
    if not found or not found['rows']:
        box(lang, 'لم يبدأ عمل EAOS في هذا المشروع بعد' if lang == 'ar' else 'No EAOS work has started in this project yet',
            commands=['eaos start .'], status='warn')
        return 0
    for label, value in found['rows']: say(f'   {label}: {value}')
    ar = lang == 'ar'
    box(lang, ('هذا ما وصل إليه العمل. افتح أي مساعد (Claude Code أو Codex) في مجلد مشروعك واكتب له الجملة أدناه' if ar else
               'This is where the work is. Open any assistant (Claude Code or Codex) in your project folder and write it the line below'),
        where=found['handover'], commands=[found['say']], note=(None if found['open'] else ('لا يوجد عمل مفتوح الآن' if ar else 'Nothing is open now')))
    return 0


# accept, undo and the check `start` asks for are the terminal's (eaos/interfaces/terminal/commands.py: what will happen, the person's yes),
# registered by that module itself (TERMINAL['check'] and COMMANDS), so that this one does not import it.
TERMINAL = {}
COMMANDS = {'start': start, 'next': next_command, 'status': status, 'doctor': doctor, 'clean': clean,
            'show': show, 'do': do, 'assistant': assistant, 'handover': resume}


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
        _ask_to_agree(lang, waiting.question, args)
        return 4
    except Declined:
        show_error(lang, 'declined')
        return 5
    except LookupError as problem:
        if 'no EAOS project here' not in str(problem): raise
        show_error(lang, 'not_started')
        return 6
    except (Exception, KeyboardInterrupt) as problem:
        _failed(lang, problem, state)
        return 1


def _ask_to_agree(lang, question, args):
    """The question a command stopped on, with the command that answers yes."""
    box(lang, question['text'], status='ask',
        note=('للموافقة اكتب الأمر أدناه، ولن يحدث شيء حتى توافق' if lang == 'ar'
              else 'To agree, type the command below; nothing happens until you do'),
        commands=[f"eaos {args.command} --yes" + (f" {args.project}" if args.command == 'start' and args.project not in (None, '.') else '')])


def _failed(lang, problem, state):
    """A failure in plain words with its fix; logged, unless it is the person's slip."""
    if explain(problem)['id'] in ('not_a_folder', 'not_a_project'):   # the person's slip, nothing to log
        show_error(lang, problem=problem)
        return
    where = outputs(state) if state else home()
    show_error(lang, problem=problem, log=log_failure(where, problem))
