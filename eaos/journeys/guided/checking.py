"""Step 1, the check: the assistant the check asks and whether it is ready, the tools it waits for, then
eaos/journeys/check.py runs it.
"""
from datetime import datetime, timezone

from ...core.project_state import runtime_of, waiting_batch
from .. import check_choices
from ...report.start_here import summary_counts
from .person import AI_QUESTION, Declined, WITHOUT_AI_QUESTION, WITHOUT_QUESTION, answered, ask, box, progress_printer, say
from .project import chosen_assistant, report_of, save, source


def choose_assistant(state, use, name=None, via='person'):
    """Keeps the person's choice for the check's AI on this project: whether to use an assistant (`use_assistant`) and
    which one (`assistant`: claude or codex). Asked again only when they change it."""
    from ...ai import ADAPTERS
    if name is not None and name not in ADAPTERS: raise ValueError(f'no assistant named {name}: claude or codex')
    state['questions'] = [q for q in state.get('questions') or [] if q['id'] != 'use_assistant'] + [
        {'id': 'use_assistant', 'kind': 'yes_no', 'answer': bool(use), 'via': via, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}]
    if name: state['assistant'] = name
    save(state)
    return state


def check_provider(state):
    """The provider of the person's assistant for the check's AI stages (docs/AI-IN-THE-PIPELINE.md): on unless they
    said no to `use_assistant`, as long as the assistant they chose answers (eaos/ai/readiness.py). Otherwise a
    falsy NoAssistant that says why (they said no, it is not signed in, not answering), or None when no assistant is
    installed: the rules stand alone and the live map and the report name the reason."""
    from ...ai import provider, readiness
    # The assistant is on by default (owner, 2026-10-11): only the person's explicit no turns it off.
    said = answered(state, 'use_assistant')
    if said is False: return readiness.NoAssistant('ai_declined', 'the person chose to check without AI, so the rules stand alone')
    if said is None and not chosen_assistant(state): return None
    name = chosen_assistant(state) or state.get('assistant') or 'claude'
    found = readiness.probe(name)
    if not found['ready']:
        return readiness.NoAssistant(found['code'], f"{found['name']} was not ready ({found['code']}), so the rules stand alone")
    return provider(name=name)[1]


def check_runtime(state):
    """The folder the check runs the app in, an isolated copy, once the person agreed to run it
    (check_choices.agreed_to_run); None otherwise, and the check reads the code alone."""
    return runtime_of(state) if check_choices.agreed_to_run(state) else None


def agree_to_assistant(state, yes):
    """Asks once, when an assistant is installed, whether the check may use it; a no is kept and the check goes on. Then
    the assistant chosen is asked for one word (eaos/ai/readiness.py): when it is not ready, the reason and its fix
    are said and the person decides whether this check starts without AI. False: they said no, the check does not start."""
    from ...ai import readiness
    lang = 'ar' if state['lang'] == 'ar' else 'en'
    name = chosen_assistant(state)
    if not name: return True
    try: ask(state, 'use_assistant', AI_QUESTION[lang].format(name=readiness.NAMES[name]), yes)
    except Declined: return True
    if not answered(state, 'use_assistant'): return True
    found = readiness.probe(name)
    if found['ready']: return True
    say(f"❌ {(found.get('reason') or {}).get(lang) or found['code']}")
    state['questions'] = [q for q in state.get('questions') or [] if q['id'] != 'start_without_ai']
    try: return ask(state, 'start_without_ai', WITHOUT_AI_QUESTION[lang].format(name=found['name']), yes)
    except Declined:
        box(lang, f"لم يبدأ الفحص: {found['name']} غير جاهز" if lang == 'ar' else f"The check did not start: {found['name']} is not ready",
            commands=['eaos start .'], status='fail',
            note=('أصلحه كما في السطر أعلاه ثم أعد الأمر، أو أعده واختر البدء بدون ذكاء' if lang == 'ar'
                  else 'Fix it as the line above says and run the command again, or run it again and start without AI'))
        return False


def tools_for_check(state, echo=lambda done, total: None, install=True):
    """Waits until none of the tools the check needs on this project is still being installed (eaos/core/toolchain.py);
    {name: reason} of those that could not be. `install=False` once the person chose to start without them."""
    from ...core import toolchain
    return toolchain.wait_for_check(source(state), echo, install)['failed']


def start_without(state, failed, yes):
    """Whether the person starts the check without the tools that failed (asked each time, never kept)."""
    names = ', '.join(sorted(failed))
    for name, reason in sorted(failed.items()): say(f"❌ {name}: {reason}")
    state['questions'] = [q for q in state.get('questions') or [] if q['id'] != 'start_without_tools']
    try: return ask(state, 'start_without_tools', WITHOUT_QUESTION['ar' if state['lang'] == 'ar' else 'en'].format(names=names), yes)
    except Declined: return False


def check_tools(state, args):
    """{name: reason} of the tools that failed and the check starts without (the person said so), or None when the
    check does not start."""
    lang = state['lang']
    failed = tools_for_check(state, lambda done, total: say(f"   {'أدوات الفحص الجاهزة' if lang == 'ar' else 'Checking tools ready'}: {done}/{total}"))
    if not failed or start_without(state, failed, args.yes): return failed
    box(lang, 'لم يبدأ الفحص: تنقصه أدوات' if lang == 'ar' else 'The check did not start: tools are missing',
        commands=['eaos tools install', 'eaos start .'], status='fail')
    return None


def scan(state, args):
    """Step 1: the whole audit, with progress, then START-HERE.md in plain words. It starts once the tools it needs
    here are installed, or without those that failed when the person says so."""
    lang = state['lang']
    from ..check import run
    failed = check_tools(state, args)
    if failed is None: return 1
    if not agree_to_assistant(state, args.yes): return 1
    say(('أفحص مشروعك الآن. يأخذ هذا عادة من 5 إلى 30 دقيقة حسب حجمه، ولن يتغير فيه شيء.' if lang == 'ar' else
         'Checking your project now. This usually takes 5 to 30 minutes depending on its size; nothing in it changes.'))
    check_choices.keep(state, getattr(args, 'mode', None))
    save(state)                                                 # the check reads the state as it stands
    manifest, state, page = run(state, check_choices.options(state, progress_printer(lang), failed, check_provider(state),
                                                             check_runtime(state), getattr(args, 'path', None)))
    counts = summary_counts(report_of(state))
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
    waiting = waiting_batch(state)
    if waiting:
        box(lang, (f"الدفعة {waiting['number']} تنتظر قرارك في الفرع {waiting['branch']}" if lang == 'ar'
                   else f"Batch {waiting['number']} is waiting for you on the branch {waiting['branch']}"),
            commands=['eaos accept', 'eaos undo'])
    else:
        box(lang, ('لا توجد إصلاحات آلية أخرى لهذا المشروع الآن؛ ما تبقى يحتاج قرارك، وهو في صفحة «ابدأ هنا»' if lang == 'ar'
                   else 'No more automatic fixes for this project now; what is left needs your decision, and it is on the "Start here" page'),
            where=report_of(state) / 'START-HERE.md', commands=['eaos status'])
    return 0
