"""The governance commands of the terminal (docs/GUIDE.md "Without the Studio"): what they print and ask, nothing
more. Each one calls eaos/interfaces/govern.py, which calls the Studio's own core; every line the person reads comes from
govern_words.WORDS, the contract (docs/studio-actions.json) or the core's own words, in Arabic and English.

    eaos check [--path …] [--mode …] [--assistant …] [--watch]     the estimate, then a new check in the background
    eaos watch [run]                                                a run live: stages, time left, cost so far, questions
    eaos stop|pause|resume|retry [run]   eaos runs [--all]           the queue
    eaos waiting   eaos answer <id> <option> [--text …]             what waits for the person
    eaos sign-in [--signed-out | --forget]                          sign in to the app while a check asks for it
    eaos problems [--kind …]   eaos problem <id>                    what the check found
    eaos fix|verify|explain|plan <ids…> | --group by=value           the verbs, previewed first
    eaos branch [name]   eaos branches [merge|delete|protect|unprotect|cleanup|restore] …   (eaos accept, undo and these: interfaces/terminal/branches.py)
    eaos history   eaos compare <a> <b>   eaos usage   eaos projects
"""
import functools
import shlex
import sys
import time
from pathlib import Path

from .. import govern
from ...journeys import guided
from ..mcp_server.server import refuse_in_studio_run
from ..govern_words import text_of, words
from ...core.project.runs import ACTIVE, TERMINAL, contract
from ...core.project import state as project_state


def say(line=''):
    print(line, flush=True)


def _reasons(problem, lang):
    """A refusal's reasons in the person's language: the core's own words when it gave them."""
    found = getattr(problem, 'reasons', None) or [getattr(problem, 'reason', None)]
    said = [text_of(r, lang) for r in found if isinstance(r, dict)]
    return said or [str(problem.args[0] if problem.args else problem)]


def command(function):
    """A governance command, `function(args, lang)`: a refusal is said in a box in plain words, never a traceback; a
    question nobody is at the terminal to answer is printed with the command that answers it."""
    @functools.wraps(function)
    def run(args):
        lang = guided.language(getattr(args, 'lang', None), _state(args))
        try: return function(args, lang) or 0
        except guided.NeedsAnswer as asked:
            again = 'eaos ' + shlex.join(getattr(args, 'words', None) or [args.command]) + ' --yes'
            guided.box(lang, asked.question['text'], status='ask', commands=[again], note=words('agree', lang))
            return 4
        except (guided.Declined, EOFError):     # "no", or the input ended without an answer
            guided.box(lang, words('not_done', lang, why=words('said_no', lang)), status='warn', commands=['eaos status'])
            return 5
        except (LookupError, ValueError, PermissionError) as problem:
            reasons = _reasons(problem, lang)
            guided.box(lang, reasons[0], status='warn', note=reasons[1:], commands=['eaos status'])
            return 3
    return run


def _state(args):
    try: return project_state.load(Path(getattr(args, 'project', None) or '.').resolve())
    except OSError: return None


def _project(args):
    return govern.core(args.project).project


def agreed(project, name, text, yes):
    """The person's yes to `text`, asked now (each time, never kept from before); refused inside a Studio run."""
    refuse_in_studio_run(name)
    state = project_state.load(project)
    state['questions'] = [q for q in state.get('questions') or [] if q['id'] != f'agree_{name}']
    return guided.ask(state, f'agree_{name}', text, yes)


def _said(actions, record):
    """What a run said last (its result, or why it did not happen)."""
    events = [e for e in actions.store.events(record['id']) if e['kind'] in ('result', 'error')]
    return events[-1]['text'] if events else record.get('label')


# ---------------------------------------------------------------- the check and the runs

@command
def check(args, lang):
    project = _project(args)
    inputs = govern.check_inputs(*(getattr(args, name, None) for name in ('path', 'mode', 'assistant', 'sign_in', 'published', 'run_app', 'again_from')))   # check, start
    shown = govern.estimate(project, inputs)['estimate']
    say(words('estimate', lang, low=shown['minutes_low'], high=shown['minutes_high'], basis=text_of(shown['basis'], lang)))
    record = govern.start_check(project, inputs, lang)
    if getattr(args, 'watch', True): return follow(project, record['id'], lang)
    guided.box(lang, words('started', lang, run=record['id']), commands=['eaos watch', f"eaos stop {record['id']}"])


@command
def watch(args, lang):
    project = _project(args)
    govern.wake(project)                    # a host that ended with the computer, or was never woken: started again
    record = govern.chosen_run(govern.core(project), args.run, ACTIVE, ('queued',), None)
    say(f"▶️  {text_of(record.get('label'), lang)} ({record['id']})")
    return follow(project, record['id'], lang)


def _status_line(actions, record, lang):
    from ...core.language import plain
    found = govern.progress(actions, record)
    clock = found['seconds'] and f"{found['seconds'] // 3600}:{found['seconds'] // 60 % 60:02d}:{found['seconds'] % 60:02d}"
    parts = [words('elapsed', lang, clock=clock) if clock and record.get('state') == 'running' else None,
             plain.stage(found['stage'], lang) + f" ({found['done']}/{found['total']})" if found['stage'] else None,
             words('left', lang, minutes=found['minutes_left']) if found['minutes_left'] is not None else None,
             words('cost', lang, cost=found['cost_usd']) if found['cost_usd'] else None]
    return '   ⏱  ' + ' · '.join(p for p in parts if p) if any(parts) else None


def _ask_inline(project, question, lang):
    """A run's question, its options and the command that answers it; asked here when a person is at the terminal."""
    say(f"❓ {text_of(question['text'], lang)}")
    for option in question.get('options') or []:
        say(f"   [{option['id']}] {text_of(option['label'], lang)}" + (' ✓' if option['id'] == question.get('recommendation') else ''))
    say('   ' + words('answer_with', lang, id=question['id']))
    if not sys.stdin.isatty(): return
    choice = input(words('ask', lang, options=', '.join(o['id'] for o in question.get('options') or []))).strip()
    if choice:
        refuse_in_studio_run('answer')
        say('   ' + words('answered' if govern.answer(project, question['id'], choice)['status'] == 'answered' else 'handed', lang, id=question['id']))


def follow(project, run, lang):
    """A run, live: its events as they come; every half minute the time since it began, its stage, the time left and
    the cost so far; its questions. Back when it ends, or on Ctrl-C while it goes on."""
    actions, after, asked, shown, beat = govern.core(project), 0, None, None, 0.0
    try:
        while True:
            record = actions.store.load(run)
            if asked != govern.SIGN_IN and govern.signing_in(project):
                asked = govern.SIGN_IN
                say(f"🔑 {words('sign_in_waits', lang)}\n   eaos sign-in")
            after = _said_since(actions, run, after, lang)
            if record.get('state') in TERMINAL: return _ended(record, lang)
            asked = _asked_once(project, record, asked, lang)
            line = _status_line(actions, record, lang) if time.monotonic() - beat > 30 else None
            if line and line != shown: say(line); shown, beat = line, time.monotonic()
            time.sleep(1)
    except KeyboardInterrupt:
        say(words('still', lang))
        return 0


def _said_since(actions, run, after, lang):
    """The run's events after `after` printed (its questions aside); the last one's number."""
    for event in actions.store.events(run, after):
        after = event['seq']
        if event['kind'] != 'question': say(f"   · {text_of(event.get('text'), lang)}")
    return after


def _asked_once(project, record, asked, lang):
    """The run's question asked here when it is a new one; the question asked last."""
    question = record.get('question') if record.get('state') == 'waiting_for_person' else None
    if question and question['id'] != asked:
        _ask_inline(project, question, lang)
        return question['id']
    return asked


def _ended(record, lang):
    state = text_of(contract()['lifecycle']['states'][record['state']], lang)
    ok = record['state'] == 'done'
    after = ['eaos problems', 'eaos waiting'] if ok else [f"eaos retry {record['id']}", 'eaos runs']
    counts = ((record.get('result') or {}).get('answer') or {}).get('counts') if isinstance((record.get('result') or {}).get('answer'), dict) else None
    guided.box(lang, words('ended', lang, state=state), status='ok' if ok else 'warn', commands=after,
               note=words('checked', lang, problems=counts.get('problems'), ready=counts.get('ready')) if counts else None)
    return 0 if ok else 2


@command
def runs(args, lang):
    actions = govern.core(args.project)
    rows = actions.runs({'all': '1'} if args.all else {})['runs']
    states = contract()['lifecycle']['states']
    for row in rows[:30]:
        say(f"{row['id']}  {text_of(states[row['state']], lang):<14} {text_of(row.get('label'), lang)}  {(row.get('created') or '')[:16]}")
    guided.box(lang, words('runs', lang, count=len(rows)) if rows else words('no_runs', lang), commands=['eaos watch', 'eaos check'])


@command
def control(args, lang):
    done = govern.control(args.project, args.command, args.run)
    state = text_of(contract()['lifecycle']['states'][done['state']], lang)
    guided.box(lang, f"{text_of(done.get('label'), lang)}: {state}", commands=['eaos runs', f"eaos watch {done['id']}"])


# ---------------------------------------------------------------- what waits for the person

@command
def waiting(args, lang):
    rows = govern.waiting(args.project)
    for row in rows:
        say(f"❓ {row['id']}: {text_of(row['text'], lang)}")
        for option in row['options']:
            say(f"   [{option['id']}] {text_of(option['label'], lang)}" + (' ✓' if option['id'] == row.get('recommendation') else ''))
    first = rows[0] if rows else None
    later = ['eaos accept', 'eaos undo'] if first and first['kind'] == 'branch' else [f"eaos answer {first['id']} <option>"] if first else ['eaos status']
    guided.box(lang, words('waiting', lang, count=len(rows)) if rows else words('none_waiting', lang), commands=later)


@command
def answer(args, lang):
    refuse_in_studio_run('answer')
    done = govern.answer(args.project, args.id, args.option, args.text, args.assistant)
    guided.box(lang, words('answered' if done['status'] == 'answered' else 'handed', lang, id=args.id), commands=['eaos watch', 'eaos waiting'])


@command
def signing_in(args, lang):
    """`eaos sign-in`: the person signs in to their app while a check asks: in a window where this computer shows one,
    else on the sign-in page served on a port of its own; or goes on signed out; or forgets the sessions kept."""
    from ..studio_server import sign_in as page
    project = _project(args)
    if args.forget:
        page.forget(project)
        return guided.box(lang, words('sign_in_forgot', lang), commands=['eaos status'])
    if not govern.signing_in(project): return guided.box(lang, words('sign_in_none', lang), commands=['eaos watch'])
    if args.signed_out:
        page.skip(project)
        return guided.box(lang, words('sign_in_skipped', lang), commands=['eaos watch'])
    if not page.display():
        say(words('sign_in_open', lang))
        from ..studio_server.server import serve_sign_in
        serve_sign_in(project, lambda address: say(f'   {address}'))
        return guided.box(lang, words('sign_in_done' if page.status(project)['kept'] else 'sign_in_skipped', lang), commands=['eaos watch'])
    page.open_browser(project, headed=True)
    _codes(page.status(project)['codes'], lang)
    input(words('sign_in_window', lang))
    page.done(project)
    guided.box(lang, words('sign_in_done', lang), commands=['eaos watch'])


def _codes(codes, lang):
    """What the app sent while the person signs in: its last lines, and its mail."""
    say(words('app_said', lang))
    for line in (codes or {}).get('output', [])[-8:]: say(f'   {line}')
    for mail in (codes or {}).get('mail', []): say(f"   ✉️  {mail['subject']}: {' '.join(mail['text'].split())[:300]}")


# ---------------------------------------------------------------- what the check found, and the verbs

@command
def problems(args, lang):
    from ...journeys.agent_tools import findings
    found = findings(args.project, args.kind, args.where, args.text, args.fixable, args.limit, args.offset, args.area, args.severity)
    for row in found['findings']:
        say(f"{row['id']}  {'🔧' if row['fixable_automatically'] else '  '} {row.get('title') or ''}  ({', '.join(row.get('paths') or [])})")
    first = found['findings'][0]['id'] if found['findings'] else '<id>'
    guided.box(lang, words('problems', lang, shown=len(found['findings']), total=found['total']),
               commands=[f'eaos problem {first}', f'eaos fix {first}'])


@command
def problem(args, lang):
    from ...journeys.agent_tools import finding
    found = finding(args.id, args.project)
    for key in ('title', 'kind', 'paths', 'impact', 'rule_broken', 'suggested_change', 'how_it_is_proven_gone'):
        if found.get(key): say(f"{key}: {', '.join(found[key]) if isinstance(found[key], list) else text_of(found[key], lang)}")
    _evidence([item for item in found.get('evidence') or [] if isinstance(item, dict)])
    guided.box(lang, f"{found.get('id')}: {found.get('title') or ''}", commands=[f'eaos fix {args.id}', f'eaos explain {args.id}'])


def _evidence(evidence):
    """A problem's evidence: who found what, and the code of the first fact that carries it."""
    for item in evidence[:5]:
        value = item.get('value') or {}
        say(f"   · {value.get('engine') or item.get('kind')}: {value.get('message') or ''}")
    code = next(((item.get('code') or {}).get('code') for item in evidence if item.get('code')), None)
    if code: say(code)


def _show_preview(shown, lang):
    for card in shown['cards'][:20]:
        say(f"   {card['id']}  {card.get('title') or ''}")
    for left in shown['left_out'][:10]:
        say('   ' + words('left_out', lang, id=left['id'], why=left.get('why_ar') if lang == 'ar' and left.get('why_ar') else left.get('why')))
    _show_where(shown.get('where'), lang)
    if shown.get('auto_accept'): say(words('auto', lang))
    if shown['handoff']['available'] and not shown.get('assistant'): say(words('handoff', lang))


def _show_where(where, lang):
    """Where a Fix builds and delivers, as its preview set it; its problem refuses the run."""
    if where and where.get('base'):
        say(words('where', lang, base=where['base']['branch'], deliver=where.get('deliver_as'), target=where.get('merge_into')))
    if where and where.get('problem'): raise LookupError(text_of(where['problem'], lang))


@command
def act(args, lang):
    """fix, verify, explain or plan: the preview printed, the person's yes for a Fix (it changes code), then the run."""
    project, verb, auto = _project(args), args.command, bool(getattr(args, 'auto_accept', False))
    if auto: refuse_in_studio_run('auto_accept')
    shown = govern.verb_preview(project, verb, govern.selection_of(args.ids, args.group), auto, args.assistant)
    _show_preview(shown, lang)
    label = text_of(contract_verb(verb)['label'], lang)
    question = words('verb_what', lang, label=label, count=len(shown['cards']), files=len(shown['files']), low=shown['estimate']['minutes_low'],
                     high=shown['estimate']['minutes_high'], risk=shown['risk']['level'])
    if shown['confirm']: agreed(project, 'auto_accept' if auto else verb, f"{question} {words('go_ahead', lang)}", args.yes)
    else: say(question)
    record = govern.verb_start(project, shown, (shown['confirm'] or {}).get('token'), args.assistant)
    guided.box(lang, words('queued_run', lang, label=text_of(record['label'], lang), run=record['id']), commands=['eaos watch', 'eaos runs'])


def contract_verb(verb):
    return next(v for v in contract()['verbs'] if v['id'] == verb)


@command
def projects(args, lang):
    """`eaos projects`: the Studio's project switcher in a terminal."""
    from ..studio_server.projects import listing
    rows = listing(args.project)['projects']
    for row in rows:
        say(f"{'✓' if row['current'] else ' '} {row['name']:<28} {row['score'] if row['score'] is not None else '-':<6} {(row['checked'] or '-')[:16]:<16} "
            f"{'🟢' if row['studio'] else '  '} {row['path']}")
    guided.box(lang, words('projects', lang, count=len(rows)), commands=['eaos studio <folder>'])


# ---------------------------------------------------------------- history, comparison, use

@command
def history(args, lang):
    scans = govern.history(args.project)['scans']
    for scan in scans:
        score = f"{round(scan['score'] * 100)}" if isinstance(scan.get('score'), (int, float)) else '-'
        say(f"{scan['id']}  {scan['at'][:16]}  {scan.get('branch') or '':<14} {score:>4}  {scan.get('open_total') if scan.get('open_total') is not None else '-':>5}  "
            f"{scan.get('closed') if scan.get('closed') is not None else '-'}/{scan.get('total') if scan.get('total') is not None else '-'}")
    later = [f"eaos compare {scans[-2]['id']} {scans[-1]['id']}"] if len(scans) > 1 else ['eaos check']
    guided.box(lang, words('history', lang, count=len(scans)) if scans else words('no_history', lang), commands=later)


@command
def compare(args, lang):
    found = govern.compare(args.project, args.first, args.second)
    say(f"score {found['score']:+}" if found['score'] is not None else 'score -')
    say(f"open {found['open']:+}" if found['open'] is not None else 'open -')
    for name, change in found['severity'].items():
        if change: say(f"   {name} {change:+}")
    for card in found['closed_between'][:20]: say(f"   ✅ {card.get('id') or card['key']} {card['title']}")
    guided.box(lang, words('compared', lang, a=args.first, b=args.second, closed=len(found['closed_between'])), commands=['eaos history'])


def _use(found):
    if not found: return '-'
    cost = f"${found['cost_usd']:.2f}" if found.get('cost_usd') is not None else '$?'
    return f"{cost}  {sum(found.get(k) or 0 for k in ('input', 'cache_write', 'cache_read', 'output', 'thinking')):,} tokens  {found.get('calls', 0)} call(s)"


@command
def usage(args, lang):
    found = govern.usage(args.project)
    check_use = found.get('check') or {}
    for name, use in (check_use.get('stages') or {}).items(): say(f"   {name:<24} {_use(use)}")
    for row in [r for r in found['runs'] if r.get('usage')][:15]: say(f"   {row['id']}  {text_of(row.get('label'), lang)[:40]:<40} {_use(row['usage'])}")
    guided.box(lang, words('usage', lang, check=_use(check_use.get('total')), chat=_use(found.get('chat'))), commands=['eaos runs'])


def govern_host(args):
    """`eaos govern`: the headless host the commands wake (eaos/interfaces/govern.py host)."""
    return govern.host(args.project, (args.answer, args.option, args.text) if args.answer else None)



guided.TERMINAL['check'] = check                # eaos start --path/--mode: the check, followed (registered here: see guided)
