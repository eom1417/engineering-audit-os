"""Steps 2-4: the app run in its isolated copy, the safety net recorded on it, and where the fixes are made."""
import json

from ...core.project.state import runtime_of
from .person import ask, box, explain, say
from .project import _commit, _saved_note, log_failure, outputs, report_of, safety_holds, save, set_up, source


def ready_done(state):
    return set_up(state)


def ready(state, args):
    """Step 2: consent, then a run profile nobody writes (eaos/live/app/setup.py)."""
    from ...live.app import setup as live_setup
    from ...ai import available, provider
    lang, commit = state['lang'], _commit(state)
    ask(state, 'run_app', _run_question(lang, (available() or [None])[0]), args.yes)
    runtime = runtime_of(state)
    live_setup.authorize(source(state), runtime, live_setup.owner(state['project']))
    say(('أجهّز تشغيل برنامجك. قد يأخذ هذا من 5 إلى 20 دقيقة.' if lang == 'ar'
         else 'Setting up your app to run. This can take 5 to 20 minutes.'))
    _, model = provider()
    result = live_setup.setup(source(state), runtime, report=report_of(state), provider=model,
                              say=lambda n: _setup_progress(lang, n, live_setup.ATTEMPTS))
    state['setup'] = {'commit': commit, 'ok': result['ok'], 'attempts': result['attempts'], 'limitations': result['limitations']}
    state.pop('safety', None)
    save(state)
    _setup_box(state, lang, result, runtime)
    return 0


def _run_question(lang, assistant):
    if lang == 'ar':
        return ("لأصلح بأمان، أحتاج أن أشغّل برنامجك في نسخة منفصلة على جهازك، بقاعدة بيانات مؤقتة وبلا أسرارك"
                + (f"، وقد أستعين بمساعدك الذكي ({assistant}) لأفهم طريقة تشغيله" if assistant else '') + '. أوافق؟')
    return ("To fix safely I need to run your app in a separate copy on this computer, with a temporary database and none of your secrets"
            + (f"; I may ask your AI assistant ({assistant}) how it runs" if assistant else '') + '. OK?')


def _setup_progress(lang, n, attempts):
    if str(n).startswith('baseline'):
        say('   ' + ('أجهّز نسخة الإنتاج من برنامجك لقياس سرعته…' if lang == 'ar' else 'Preparing the production build of your app, to measure its speed…'))
    else:
        say(f"   [{n}/{attempts}] " + ('أشغّل برنامجك وأفتح بعض شاشاته…' if lang == 'ar' else 'Starting your app and opening some of its screens…'))


def _setup_box(state, lang, result, runtime):
    """How the setup ended, with the unsaved edits and the limitations noted."""
    notes = [n for n in [_saved_note(state)] if n]
    if result['limitations']:
        notes.append((f"{len(result['limitations'])} ملاحظة عمّا لم يكتمل، مكتوبة في الملف أدناه (limitations)" if lang == 'ar'
                      else f"{len(result['limitations'])} notes on what is incomplete, written in the file below (limitations)"))
    if result['ok']:
        box(lang, 'برنامجك يعمل في النسخة المنفصلة' if lang == 'ar' else 'Your app runs in the separate copy',
            where=runtime / 'run.json', commands=['eaos next'], note=notes or None)
        return
    box(lang, ('لم أستطع تشغيل برنامجك كاملًا؛ سأكمل بما أمكن، والقيود مكتوبة' if lang == 'ar'
               else 'I could not get your app fully running; I will go on with what works, and the limits are written down'),
        where=runtime / 'run.json', commands=['eaos next'], status='warn', note=notes)


def safety_done(state):
    return safety_holds(state)


def safety_run(state, step=lambda n: None):
    """The safety net's work, without words: every screen recorded on the original, then its speed under load
    when a production run works. {'screens', 'passed', 'skipped': [...], 'p95_ms', 'speed', 'speed_error'}; the
    skipped are kept with the state, so "recorded nothing" says why (a real batch was refused with no reason).
    Written as it happens as the flow `safety` of the live map (eaos/live/behavior/lock.py:FLOW)."""
    from ...core import progress
    from ...live.behavior.lock import FLOW
    with progress.Flow(runtime_of(state), 'safety', FLOW):
        return _safety_run(state, step)


def _safety_run(state, step):
    from ...live.behavior import specs as lock_specs
    from ...core import progress
    from ...live.behavior.lock import refused, run_lock
    from ...live.trials.load_baseline import run_baseline
    runtime = runtime_of(state)
    step(1)
    # The specs written again by this EAOS, so a change in how they are written reaches the safety net with no new check.
    lock_specs.build(report_of(state), source(state))
    results = (lock := run_lock(report_of(state), source(state), runtime))['results']
    skipped = refused(lock)
    outcome = {'screens': len(results), 'passed': (passed := sum(r['status'] == 'passed' for r in results)), 'p95_ms': None, 'speed_error': None, 'skipped': skipped}
    baseline = json.loads((runtime / 'run.json').read_text(encoding='utf-8')).get('baseline') or {}
    if baseline.get('build') and baseline.get('verified') and list((report_of(state) / 'nfr/k6').glob('*.js')):
        step(2)
        progress.begin('speed')
        try:
            performance = run_baseline(report_of(state), source(state), runtime)
            outcome['p95_ms'] = max((s['before']['p95_ms'] for s in performance['scenarios']), default=None)
            outcome['speed'] = 'measured'
            progress.end('speed', detail={'p95_ms': outcome['p95_ms']})
        except Exception as problem:            # speed is measured when it can be; the screens are the safety net
            outcome.update(speed='failed', speed_error=f'{type(problem).__name__}: {problem}'[:600],
                           speed_log=str(log_failure(outputs(state), problem)))
            progress.end('speed', 'failed', outcome['speed_error'][:300], 'speed_failed')
    else:
        outcome['speed'] = 'no_production_run' if baseline.get('build') else 'no_build'
        progress.skip('speed', 'the production build of the app did not run during the setup' if baseline.get('build')
                      else 'the app has no production build', outcome['speed'])
    state['safety'] = {'commit': state['setup']['commit'], 'screens': len(results), 'passed': passed, 'p95_ms': outcome['p95_ms'], 'skipped': skipped[:5]}
    save(state)
    return outcome


def safety(state, args):
    """Step 3: the safety net: every screen recorded on the original, and its speed under load."""
    lang, runtime = state['lang'], runtime_of(state)
    say(('أصوّر كل شاشات برنامجك كما هي الآن، ثم أقيس سرعته. هذا ما سأقارن به بعد كل إصلاح (15 إلى 30 دقيقة).' if lang == 'ar'
         else 'Recording every screen of your app as it is now, then measuring its speed. Every fix is compared with this (15 to 30 minutes).'))
    def step(n):
        say(f'   [{n}/2] ' + (('أصوّر الشاشات…' if lang == 'ar' else 'Recording the screens…') if n == 1 else
                              ('أقيس السرعة تحت ضغط مستخدمين كثيرين…' if lang == 'ar' else 'Measuring speed under many users…')))
    outcome = safety_run(state, step)
    passed, total, speed, ar = outcome['passed'], outcome['screens'], outcome['p95_ms'], lang == 'ar'
    happened = (f"صوّرت {passed} من {total} شاشة" + (f"، وأبطأ الطلبات تأخذ {speed:.0f} ملي ثانية" if speed else '')
                if ar else f"Recorded {passed} of {total} screens" + (f"; the slowest requests take {speed:.0f} ms" if speed else ''))
    box(lang, happened, where=runtime / 'behavior-lock/results.json', commands=['eaos next'],
        status='ok' if passed else 'warn', note=_safety_notes(outcome, lang) or None)
    return 0


def _safety_notes(outcome, lang):
    """What the safety net could not do: the speed not measured and why, the screens not recorded."""
    ar = lang == 'ar'
    unmeasured = {'no_production_run': ('لم تعمل نسخة الإنتاج من برنامجك هنا، فلم أقس السرعة؛ السبب في run.json', 'The production build of your app did not run here, so speed was not measured; the reason is in run.json'),
                  'no_build': ('لا يوجد أمر بناء للإنتاج، فلم أقس السرعة', 'No production build, so speed was not measured')}.get(outcome['speed'])
    notes = [unmeasured[0 if ar else 1]] if unmeasured else []
    if outcome['speed'] == 'failed':
        notes.append(('لم أستطع قياس السرعة: ' if ar else 'Could not measure speed: ')
                     + explain(RuntimeError(outcome['speed_error']))[lang]['message'] + f" ({outcome['speed_log']})")
    if outcome['skipped']: notes.append((f"{len(outcome['skipped'])} شاشة لم تُصوَّر، وأسبابها في السجل" if ar
                                         else f"{len(outcome['skipped'])} screens were not recorded; the reasons are in the record"))
    return notes


def _waves(state):
    return [w for w in state.get('waves') or [] if w.get('base') == (state.get('setup') or {}).get('commit')]


def fix_done(state):
    """A wave of this commit is in the person's project as a branch, or no ready card is left to try."""
    from ..fix.waves import next_batch
    if any(w.get('status') == 'applied' for w in _waves(state)): return True
    return not next_batch(report_of(state), state)


def fix(state, args):
    """Step 4: the fixes are made by the person's AI assistant through EAOS's tools (fix_start, fix_edit, fix_finish),
    from the assistant or the Studio; this command never calls a model itself. It says where to go."""
    from ..fix.waves import next_batch
    lang = state['lang']
    batch = next_batch(report_of(state), state)
    box(lang, (f'{len(batch)} إصلاحات جاهزة. يصلحها مساعدك الذكي: افتح Claude Code أو Codex في هذا المجلد واكتب /eaos ثم '
               '"أصلح"، أو اضغط "أصلح" في الاستوديو' if lang == 'ar' else
               f'{len(batch)} fixes are ready. Your AI assistant makes them: open Claude Code or Codex in this folder and type '
               '/eaos then "fix", or press "Fix" in the Studio'),
        commands=['eaos studio'], note=None)
    return 0
