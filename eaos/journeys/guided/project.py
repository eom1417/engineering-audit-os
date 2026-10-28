"""A project as the journeys keep it: its outputs folder, its state saved, its report and the page people read, the
code of the branch EAOS works on, and whether a check, a run and a safety net still hold for it.
"""
import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from ...core.project import branches, state as project_state
from ...core.project.state import runtime_of
from ..fix import waves
from ...core.project.places import outputs_root, second_name
from ...core.system.files import read_json


OUTPUTS_README = {
    'ar': """# مخرجات EAOS لمشروع «{name}»

افتح **REPORT.html**: تقرير واحد بكلام بسيط (ملخص المشروع، والفجوات والمخاطر، وخريطة البنية، والخطة والتقدم).

| المجلد | ما فيه |
| --- | --- |
| `REPORT.html` | التقرير للقراءة: افتحه في المتصفح |
| `technical/` | التقرير الفني الكامل، لمساعدك الذكي وللمطوّرين. لا تحتاج أن تفتحه |
| `fixes/` | كل دفعة إصلاحات: ما تغيّر وما لم ينجح، والفرع الذي وُضعت فيه |
| `logs/` | سجلات تقنية، لمن يساعدك إذا ظهرت مشكلة |

مشروعك نفسه ({project}) لا يُكتب فيه شيء إلا فرع الإصلاحات حين يُسلَّم.
""",
    'en': """# EAOS outputs for «{name}»

Open **REPORT.html**: one report in plain words (project summary, gaps and risks, structure map, plan and progress).

| Folder | What is in it |
| --- | --- |
| `REPORT.html` | The report to read: open it in your browser |
| `technical/` | The full technical report, for your AI assistant and developers. You do not need to open it |
| `fixes/` | Every batch of fixes: what changed, what did not pass, and the branch it is on |
| `logs/` | Technical logs, for whoever helps you if something goes wrong |

Nothing is written into your project itself ({project}) except the branch of fixes when it is handed over.
"""}


def outputs(state):
    """The project's folder in ~/EAOS: named after the project (with -2, -3 when another project has the name),
    made once and kept in the state, with a README that says what each part is."""
    if state.get('outputs'):
        folder = Path(state['outputs'])
    else:
        name = Path(state['project']).name
        folder, number = outputs_root() / name, 1
        while (folder / '.eaos-project').is_file() and (folder / '.eaos-project').read_text(encoding='utf-8').strip() != state['project']:
            number += 1
            folder = outputs_root() / f'{name}-{number}'
        state['outputs'] = str(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / '.eaos-project').write_text(state['project'] + '\n', encoding='utf-8')
    readme = folder / 'README.md'
    if not readme.is_file():
        lang = state.get('lang') if state.get('lang') in OUTPUTS_README else 'en'
        readme.write_text(OUTPUTS_README[lang].format(name=Path(state['project']).name, project=state['project']), encoding='utf-8')
    return folder


def save(state):
    """The state written (eaos/core/project/state.py), the open batch drawn and the closed ones' copies removed first."""
    waves.saved(state, runtime_of(state))
    project_state.write(state)


def language(requested=None, state=None):
    if requested: return requested
    if state and state.get('lang'): return state['lang']
    return 'ar' if (os.environ.get('LANG') or os.environ.get('LC_ALL') or '').lower().startswith('ar') else 'en'


def log_failure(where, problem):
    logs = Path(where) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    path.write_text(''.join(traceback.format_exception(type(problem), problem, problem.__traceback__)), encoding='utf-8')
    return path


# ---------------------------------------------------------------- the steps `next` walks through

def report_of(state):
    """The technical report, in the branch's part of the outputs folder (eaos/core/project/branches.home); one an older EAOS left
    in the workspace is moved there once."""
    outputs(state)
    report = branches.home(state) / 'technical'
    old = Path(state['workspace']) / 'report'
    if old.is_dir() and not report.exists(): shutil.move(str(old), str(report))
    return report


def branch_links(state):
    """The branch this report is for, and every other branch with a report, as paths from this one's REPORT.html."""
    if not state.get('branch'): return None
    here = branches.home(state)
    others = []
    for name in sorted({state.get('home_branch'), *(state.get('by_branch') or {})} - {state['branch'], None}):
        page = branches.home({**state, 'branch': name}) / 'REPORT.html'
        if page.is_file(): others.append({'name': name, 'href': os.path.relpath(page, here)})
    return {'name': state['branch'], 'main': branches.default_branch(state['project']), 'others': others}


# The parts of the page other modules give, registered by those modules so that this one does not import them:
# {'handover': eaos.journeys.handover.brief}. Each takes the state and returns what the page shows.
REPORT_PARTS = {}
# What `eaos handover` tells the person, registered by eaos/journeys/handover.py the same way.
RESUME = []


def report_stamp(state):
    """What the last REPORT.html of the branch was made from: {version, commit, digest, built, scanned_commit (the project
    commit the check read), errors}; {} when none."""
    return read_json(branches.home(state) / '.report.json', {})


def publish(state, lang=None, event=None):
    """REPORT.html in the branch's outputs folder, rebuilt from the ledger (eaos/core/project/ledger.py) so that it shows what is in
    the person's branch now, stamped with the EAOS that made it. Nothing here fails in silence: a part that cannot be
    built is named on the page, in .report.json beside it and in logs/, and the rest of the page is still made. It is
    never a reason for a step to fail: without it, the technical report is still there."""
    from ...core.system.version_info import stamp
    report, home_folder = report_of(state), branches.home(state)
    target, made = home_folder / 'REPORT.html', datetime.now(timezone.utc).isoformat(timespec='seconds')
    errors, progress = [], {'waves': state.get('waves') or []}

    def part(name, build):
        try: progress[name] = build()
        except Exception as problem:
            errors.append(f'{name}: {type(problem).__name__}: {problem}'[:300])
            log_failure(outputs(state), problem)

    from ...core.project.ledger import for_report, sync
    part('ledger', lambda: for_report(sync(state, event, report)))
    part('branch', lambda: branch_links(state))
    for name, build in REPORT_PARTS.items(): part(name, lambda build=build: build(state))
    progress.update(eaos=stamp(made), report_errors=errors)
    _studio_data(state, report, lang, progress, errors)
    _human_page(state, report, lang, progress, errors)
    page = report / 'human' / 'index.html'
    home_folder.mkdir(parents=True, exist_ok=True)
    if page.is_file(): second_name(page, target)
    (home_folder / '.report.json').write_text(json.dumps({**stamp(made), 'scanned_commit': state.get('scanned_commit'),
                                                         'errors': errors}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return target if target.is_file() else report / 'START-HERE.md'


def _studio_data(state, report, lang, progress, errors):
    """The Studio's data, from the same ledger as the page (eaos/report/studio/export.py); what failed added to `errors`."""
    try:
        from ...report.studio.export import export as studio
        errors += [f"studio {e['section']}: {e['error']}"[:300]
                   for e in studio(report, lang or state.get('lang') or 'en', Path(state['project']).name, state['project'],
                                   progress, state)['errors']]
    except Exception as problem:
        errors.append(f'studio: {type(problem).__name__}: {problem}'[:300])
        log_failure(outputs(state), problem)


def _human_page(state, report, lang, progress, errors):
    """The page for people (human/index.html); what failed added to `errors`, and when the page itself could not be
    made, a page that says so in its place."""
    try:
        from ...report.human_report import write
        write(report, lang or state.get('lang') or 'en', Path(state['project']).name, progress=progress)
        errors += [f"{e.get('section')}: {e.get('error')}"[:300] for e in read_json(report / 'human/errors.json', [])]
    except Exception as problem:            # the page itself could not be made: say so on it, never leave the old one
        errors.append(f'page: {type(problem).__name__}: {problem}'[:300])
        log_failure(outputs(state), problem)
        _failed_page(state, report, errors)


def _failed_page(state, report, errors):
    """human/index.html when the page could not be built: the errors, and where the logs are."""
    page = report / 'human' / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    import html
    page.write_text('<!doctype html><meta charset="utf-8"><title>EAOS</title><body style="font:16px system-ui;padding:32px">'
                    '<h1>تعذّر بناء التقرير · The report could not be built</h1><ul>'
                    + ''.join(f'<li>{html.escape(e)}</li>' for e in errors)
                    + f'</ul><p>{html.escape(str(outputs(state) / "logs"))}</p></body>', encoding='utf-8')


def publish_fixes(state, wave):
    """outputs/fixes/wave-N: the batch's patches, wave.json, and a summary a person can read."""
    target = waves.publish(state, runtime_of(state), branches.home(state) / 'fixes', wave['number'])
    words = SUMMARY_WORDS['ar' if state.get('lang') == 'ar' else 'en']
    lines = [f"# {words['batch']} {wave['number']}", '',
             words['branch'].format(branch=wave.get('branch')) if wave.get('kept') else words['nothing'], '']
    if wave.get('stat'): lines += [words['changes'].format(stat=wave['stat']), '']
    if wave.get('kept'):
        lines += ['## ' + words['fixed'], ''] + [f'- {card}' for card in wave['kept']] + ['']
    if wave.get('failed'):
        lines += ['## ' + words['failed'], ''] + [f'- {card}: {why}' for card, why in wave['failed'].items()] + ['']
    lines += [words['patches'], '']
    (target / 'SUMMARY.md').write_text('\n'.join(lines), encoding='utf-8')
    publish(state)
    return target


# The words of a batch's SUMMARY.md, in the person's language.
SUMMARY_WORDS = {'ar': {'batch': 'الدفعة', 'branch': 'الفرع في مشروعك: `{branch}`',
                        'nothing': 'لم ينجح أي إصلاح، فلم يتغير شيء في مشروعك.', 'changes': 'التغييرات: {stat}',
                        'fixed': 'ما أُصلح', 'failed': 'ما لم ينجح، ولماذا',
                        'patches': 'ملفات .patch هنا هي التغييرات نفسها، واحدًا لكل إصلاح.'},
                 'en': {'batch': 'Batch', 'branch': 'The branch in your project: `{branch}`',
                        'nothing': 'No fix passed, so nothing changed in your project.', 'changes': 'The changes: {stat}',
                        'fixed': 'Fixed', 'failed': 'Not fixed, and why',
                        'patches': 'The .patch files here are the changes themselves, one per fix.'}}


def scan_done(state):
    manifest = report_of(state) / 'run-manifest.json'
    return manifest.is_file() and json.loads(manifest.read_text(encoding='utf-8')).get('status') in ('COMPLETE', 'PARTIAL', 'INCOMPLETE') \
        and (report_of(state) / 'START-HERE.md').is_file()


# How a way of working other than fixing rebuilds its page for people: {'build': eaos.journeys.build_from_plan.blueprint.publish}, registered
# by that module itself, so that this one does not import it.
PUBLISHERS = {}


def same_code(state, commit, head=None):
    """`head` holds the code of `commit` plus EAOS's own fixes only (every commit between them made by EAOS, and merges):
    a check, a run and a safety net made at `commit` still hold, and a merged batch costs no new check."""
    if not commit: return False                 # before reading the head: a folder without git has no commit to compare
    head = head or _commit(state)
    if commit == head: return True
    if _git(state['project'], 'merge-base', '--is-ancestor', commit, head).returncode: return False
    authors = _git(state['project'], 'log', '--no-merges', '--format=%ae', f'{commit}..{head}')
    return authors.returncode == 0 and set(authors.stdout.split()) <= {'eaos@localhost'}


def _branch_exists(state, branch):
    return not _git(state['project'], 'rev-parse', '--verify', '--quiet', f'refs/heads/{branch}').returncode


def tip(state):
    """The commit of the branch EAOS works on (the one checked out, when none was chosen); '' without it."""
    done = _git(state['project'], 'rev-parse', '--verify', '--quiet', branches.ref(state) + '^{commit}')
    return done.stdout.strip() if done.returncode == 0 else ''


def source(state, commit=None):
    """A folder whose checkout is the branch EAOS works on, for everything that reads or runs the original: the project
    itself when that branch is checked out there, else EAOS's own copy beside state.json at the branch's last commit, or
    at `commit` (the checked one, a check going on: eaos/pipeline/run.py again); the project's checkout is never switched."""
    branch = state.get('branch')
    if not branch or (branches.checked_out(state['project']) == branch and commit in (None, tip(state))): return Path(state['project'])
    copy = Path(state['workspace']) / ('checkout' + branches.suffix(state))
    if not (copy / '.git').is_dir():
        shutil.rmtree(copy, ignore_errors=True)
        done = _git(state['project'], 'clone', '--quiet', '--no-checkout', '--no-hardlinks', '.', str(copy))
        if done.returncode: raise RuntimeError(f'could not copy the branch {branch}: {done.stderr[-300:]}')
    commit = commit or tip(state)
    if not commit: raise RuntimeError(f'the branch {branch} is not in the project any more: choose another one')
    if _git(copy, 'rev-parse', 'HEAD').stdout.strip() != commit:
        _git(copy, 'fetch', '--quiet', str(state['project']), f'+{branches.ref(state)}:refs/remotes/source/{branch}')
        if _git(copy, 'checkout', '--quiet', '--force', '--detach', commit).returncode:
            raise RuntimeError(f'could not bring the copy of {branch} to {commit[:12]}')
        _git(copy, 'clean', '-fdqx')
    return copy


def _git(project, *args):
    import subprocess
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def _commit(state):
    if _git(state['project'], 'rev-parse', '--git-dir').returncode: raise RuntimeError(f"{state['project']}: fatal: not a git repository")
    commit = tip(state)
    if not commit: raise RuntimeError(f"{state['project']}: the branch {state.get('branch') or 'checked out'} has no commit")
    return commit


def _saved_note(state):
    """Unsaved edits are not part of the run: said once, plainly, never a stop."""
    if not _git(state['project'], 'status', '--porcelain').stdout.strip(): return None
    return ('عندك تعديلات لم تُحفظ في git: أعمل على آخر نسخة محفوظة فقط' if state['lang'] == 'ar'
            else 'You have edits not saved in git: I work on the last saved version only')


def set_up(state, head=None):
    """The app's run is set up for the code at `head` (the branch's last commit): that commit, or it plus EAOS's own merged
    fixes. One judgement for the CLI's steps and MCP's status (M3.3)."""
    return same_code(state, (state.get('setup') or {}).get('commit'), _commit(state) if head is None else head)


def safety_holds(state, head=None):
    """The safety net was recorded on the code at `head`, so a batch may change it: one judgement for both (M3.3)."""
    return same_code(state, (state.get('safety') or {}).get('commit'), _commit(state) if head is None else head)


def chosen_assistant(state):
    """The assistant the check asks: the person's own choice for this project (`assistant` in state.json), else
    $EAOS_ASSISTANT, else the first installed (eaos/ai/__init__.py); None when none is installed."""
    from ...ai import ADAPTERS, available
    if state.get('assistant') in ADAPTERS: return state['assistant']
    found = available()
    return found[0] if found else None
