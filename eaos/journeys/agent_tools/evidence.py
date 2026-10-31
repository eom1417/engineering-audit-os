"""The evidence behind the check: the findings and one finding with its code, the structure, the plan, the impact of a
change, a question about the project, the tools, the report's files.
"""
import os
from pathlib import Path

from .. import guided
from ...core import toolchain
from ...analysis.repair.finish_line import proof
from ...analysis.planning.cards import title_of
from ...core.project import state as project_state
from .project import EVIDENCE, PAGE, _head, _read, _report, state_of


def _ready(task):
    from ...core.contracts.decisions import ready
    return ready(task)


def _claims(report):
    path = report / 'dossier.json'
    return {c['id']: c for c in _read(path).get('claims') or []} if path.is_file() else {}


def findings(project=None, kind=None, path=None, text=None, fixable_only=False, limit=PAGE, offset=0, area=None, severity=None):  # limits: parameters -- the findings tool's arguments, one for one (MCP server and CLI)
    state = state_of(project)
    report, lang = _report(state), state.get('lang') or 'en'
    claims, rows = _claims(report), []
    from ..fix.selection import cards_in      # area and severity as the Studio's filter reads them
    only = [cards_in(report / 'studio', by, value) for by, value in (('area', area), ('severity', severity)) if value]
    for task in _read(report / 'plan.json').get('tasks') or []:
        if not _wanted(task, kind, path, text, fixable_only) or any(task['id'] not in ids for ids in only): continue
        rows.append(_finding_row(task, claims.get(task.get('claim_id')) or {}, lang))
    rows.sort(key=lambda r: -(r['priority'] or 0))
    offset, limit = max(int(offset), 0), min(max(int(limit), 1), 200)
    return {'total': len(rows), 'offset': offset, 'findings': rows[offset:offset + limit], 'more': offset + limit < len(rows)}


def _finding_row(task, claim, lang):
    """One card as findings lists it, its title in the person's language (an engine's card was said in Arabic only)."""
    return {'id': task['id'], 'title': title_of(task, lang), 'kind': task.get('pattern'), 'paths': (task.get('paths') or [])[:5],
            'fixable_automatically': _ready(task), 'decision': (task.get('decision') or {}).get('kind'),
            'confidence': claim.get('confidence'), 'priority': task.get('priority')}


def _wanted(task, kind, path, text, fixable_only):
    """Whether a card passes the filters, each only when given."""
    filters = ((kind, lambda: task.get('pattern') == kind),
               (path, lambda: any(path in p for p in task.get('paths') or [])),
               (text, lambda: text.lower() in (task.get('title') or '').lower()),
               (fixable_only, lambda: _ready(task)))
    return all(passes() for given, passes in filters if given)


def _excerpt(root, location, around=8, limit=60):
    path = Path(root) / (location.get('path') or '')
    if not location.get('path') or not path.is_file(): return None
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    line = int(location.get('line') or location.get('start_line') or 1)
    end = int(location.get('end_line') or line)
    start, stop = max(1, line - around), min(len(lines), max(end, line) + around, line + limit)
    return {'path': location['path'], 'from_line': start, 'to_line': stop,
            'code': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, stop + 1))}


def _card_and_claim(report, id):
    """(card or None, claim or {}) of a TASK-… or CLM-… id; ValueError when it is neither."""
    claims = _claims(report)
    task = _card_of(report, id)
    claim = claims.get(id) or claims.get((task or {}).get('claim_id')) or {}
    if not task and not claim: raise ValueError(f'{id} is neither a card nor a claim of this report')
    return task, claim


def _card_of(report, id):
    """The card of a TASK-… id, else the card of a CLM-… claim; None when neither."""
    tasks = {t['id']: t for t in _read(report / 'plan.json').get('tasks') or []}
    return tasks.get(id) or next((t for t in tasks.values() if t.get('claim_id') == id), None)


def _evidence(state, report, card, claim):
    """The facts behind a card and its claim (up to EVIDENCE; shown six, an assistant missed the rest), with their code."""
    from ...facts.store import by_id
    fact_ids = list(dict.fromkeys((claim.get('fact_ids') or []) + ((card.get('evidence') or {}).get('fact_ids') or [])))
    facts = by_id(report, fact_ids[:EVIDENCE])
    return [{'fact': fact_id, 'kind': facts[fact_id].get('kind'), 'value': facts[fact_id].get('value'),
             'code': _excerpt(guided.source(state), facts[fact_id].get('location') or {})}
            for fact_id in fact_ids[:EVIDENCE] if facts.get(fact_id)]


def _what_and_why(card, claim):
    """What a finding is, why it matters, and how it is proven gone."""
    return {'id': card.get('id') or claim.get('id'), 'claim': claim.get('id'), 'title': card.get('title') or claim.get('statement'),
            'kind': card.get('pattern'), 'confidence': claim.get('confidence'), 'paths': card.get('paths'),
            'impact': card.get('impact') or (claim.get('impact') or {}).get('scenario'), **_change(card, claim)}


def _change(card, claim):
    """The rule a finding breaks, the code before and after its change, and how it is proven gone."""
    assessment = claim.get('assessment') or {}
    return {'rule_broken': assessment.get('violated_invariant'), 'before': card.get('before') or assessment.get('before'),
            'after': card.get('after') or assessment.get('after'), 'suggested_change': assessment.get('proposed_change'),
            'how_it_is_proven_gone': proof(claim) or claim.get('falsifier') or ((card.get('evidence') or {}).get('falsifier'))}


def _card_work(card):
    """How a card can be worked on: fixable, by a codemod, its decision, what it waits on and what uses it."""
    decision = card.get('decision') or {}
    return {'fixable_automatically': _ready(card) if card else False,
            'has_codemod': ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0,
            'decision': card.get('decision', {}).get('kind') if card else None,
            'blockers': decision.get('blockers'),
            'depends_on': card.get('prerequisites'), 'used_by': ((card.get('blast_radius') or {}).get('direct_dependents') or [])[:15]}


def finding(id, project=None):
    """One card (TASK-…) or claim (CLM-…), whole: what, why, the evidence with its code, the change, the check."""
    state = state_of(project)
    report = _report(state)
    task, claim = _card_and_claim(report, id)
    card = task or {}
    return {**_what_and_why(card, claim), **_card_work(card), 'evidence': _evidence(state, report, card, claim)}


def structure(project=None):
    state = state_of(project)
    report = _report(state)
    target = _read(report / 'target-architecture.json') if (report / 'target-architecture.json').is_file() else {}
    trim = lambda rows, n=40: (rows or [])[:n] if isinstance(rows, list) else rows
    cycles = [t['title'] for t in _read(report / 'plan.json').get('tasks') or [] if t.get('pattern') == 'import_cycle']
    return {'current_components': trim(target.get('current_components')), 'target_components': trim(target.get('target_components')),
            'forbidden_edges': trim(target.get('forbidden_edges')), 'target_edges': trim(target.get('target_edges')),
            'decisions': trim(target.get('decisions'), 20), 'gaps': trim(target.get('gap_matrix'), 40),
            'import_cycles': cycles[:30], 'import_cycle_count': len(cycles), 'limits': target.get('limits'),
            'documents': [str(report / name) for name in ('TARGET-ARCHITECTURE.md', 'CURRENT-STATE.md')
                          if (report / name).is_file()]}


def design(project=None):
    """What the project's screens are made of (design/inventory.json), pictures aside: how many looks per part, values per kind."""
    state = state_of(project)
    drawn = _read(_report(state) / 'design' / 'inventory.json') if (_report(state) / 'design' / 'inventory.json').is_file() else None
    if not drawn: return {'status': 'not_read', 'what_now': 'The screens were not read: the app must run in a check (run_setup, then audit).'}
    return {'pages': drawn['pages'], 'components': {role: {'count': part['count'], 'looks': len(part['looks'])} for role, part in drawn['components'].items()},
            'values': {kind: part['distinct'] for kind, part in drawn['values'].items()}, 'near_colours': drawn['near_colours'][:10],
            'formats': drawn['formats'], 'libraries': drawn['libraries'], 'motion': drawn['motion']}


def _milestone_row(m, tasks, whole, tried_card, where):
    """One milestone with its cards (of `tasks`, by id): all of them when `whole`, else the first 25 and how many more."""
    cards = [tasks[i] for i in m['tasks'] if i in tasks]
    shown = cards if whole else cards[:25]
    return {'id': m['id'], 'name': m.get('name'), 'goal': m.get('goal'), 'exit': m.get('exit'),
            'cards': [{'id': c['id'], 'title': c.get('title'), 'kind': c.get('pattern'), 'fixable_automatically': _ready(c),
                       'tried': tried_card(c), 'state': where.get(c['id'], 'open')} for c in shown],
            'more_cards': 0 if whole else max(0, len(cards) - 25)}


def plan(project=None, milestone=None):
    from ...core.project.ledger import keys, sync
    state = state_of(project)
    guided.reconcile(state)
    report = _report(state)
    data = _read(report / 'plan.json')
    rows = data.get('tasks') or []
    tasks = {t['id']: t for t in rows}
    tried, ids = set(state.get('tried') or []), keys(rows)
    record = sync(state, report=report) or {}
    where = _card_states(record)
    out = [_milestone_row(m, tasks, bool(milestone), lambda c: ids.get(c['id']) in tried, where)
           for m in data.get('milestones') or [] if not milestone or m['id'] == milestone]
    return {'milestones': out, 'progress': record.get('totals'),
            'order': 'Fix in this order: milestone by milestone, the fixable cards first. Only these cards count as progress: '
                     'work outside the plan is not recorded anywhere.'}


def _card_states(record):
    """{card id: its state} in the progress record."""
    return {c['id']: c['state'] for c in (record.get('cards') or {}).values() if c.get('id')}


def impact(target, project=None, depth=3):
    """What changing a file or a symbol touches, from the check's facts: who imports it, the flows and entry points through
    it, the tests that cover it, and the files that change with it in the history."""
    from ...analysis.maps.impact import LIMITS, assess
    result = assess(_report(state_of(project)), target, depth)
    return {**result, 'limits': LIMITS}


def ask(question, project=None):
    """The check's records that answer a question, each with its place; NOT_IN_RECORDS when none does."""
    from ...ai.ask import answer
    return answer(_report(state_of(project)), question)


def tools_check(project=None, retry=False):
    """This EAOS (version, commit) and every external tool it runs: installed or not, at which version, and whether this
    project needs it (its files decide: a JavaScript linter is not needed by a Go project); what the check waits for
    here (`for_the_check`: ready, still coming, failed with why). `retry`: start the install again (the tools that
    failed are tried again; an install already running goes on)."""
    from ...core.system import version_info as build_info
    folder = Path(project or os.getcwd()).expanduser().resolve()
    files = toolchain.project_files(folder) if project_state.looks_like_project(folder) else None
    if retry: toolchain.prepare(folder if files is not None else None)
    rows = _tool_rows(files)
    wanted, later = _missing(rows)
    gate = toolchain.readiness(files or ())
    return {'eaos': {'version': build_info.__version__, 'commit': build_info.commit()}, 'tools_folder': str(toolchain.home()),
            'installed': sum(r['ok'] for r in rows), 'total': len(rows), 'tools': rows, 'installing': toolchain.installing(),
            'for_the_check': gate, 'missing_for_later_steps': later,
            'install': 'eaos tools install' if wanted or gate['failed'] else None}


def _tool_rows(files):
    """Every external tool as the doctor sees it, with whether the project's `files` need it and the check waits for it:
    the needed and missing first."""
    rows = toolchain.doctor()['tools']
    rules = {t['name']: t for t in toolchain.registry()['tools']}
    for row in rows:
        row['needed_here'] = None if files is None else toolchain.rule_applies(rules[row['name']].get('applies', 'all'), files)
        row['for_the_check'] = bool(rules[row['name']].get('check'))
    rows.sort(key=lambda r: (r['needed_here'] is False, not r['for_the_check'], r['ok'], r['name']))
    return rows


def _missing(rows):
    """(the tools not installed that could be and the project may need, the names of those the check does not wait for)."""
    wanted = [r for r in rows if not r['ok'] and not r['unavailable'] and r['needed_here'] is not False]
    return wanted, [r['name'] for r in wanted if not r['for_the_check']]


def report_file(name='', project=None, offset=0, limit=20000):
    state = state_of(project)
    report = _report(state).resolve()
    if not name:
        return {'files': sorted(str(p.relative_to(report)) for p in report.rglob('*') if p.is_file() and p.suffix in ('.md', '.json', '.txt'))[:400]}
    path = (report / name).resolve()
    if report not in path.parents or not path.is_file(): raise ValueError(f'{name} is not a file of this report')
    text = path.read_text(encoding='utf-8', errors='replace')
    offset, limit = max(int(offset), 0), min(max(int(limit), 1000), 100000)
    return {'file': str(path), 'size': len(text), 'offset': offset, 'text': text[offset:offset + limit], 'more': offset + limit < len(text)}


def open_report(project=None, show=True):
    """REPORT.html, the four reports for people, rebuilt with the fixes so far and opened in the person's browser."""
    state = state_of(project)
    _report(state)
    guided.reconcile(state)
    page = guided.publish(state)
    guided.save(state)
    opened = False
    if show and page.suffix == '.html':
        import webbrowser
        try: opened = webbrowser.open(page.resolve().as_uri())
        except Exception: opened = False
    made = guided.report_stamp(state)
    stale = _stale(state, made)
    return {'report_for_people': str(page), 'opened_in_browser': opened, 'outputs_folder': str(guided.outputs(state)),
            'built': made.get('built'), 'version': made.get('version'), 'report_errors': made.get('errors') or [],
            'checked_commit': made.get('scanned_commit'), 'stale': stale,
            'what_now': 'Tell the person where it is' + ('' if opened else ' and how to open it (double-click the file)') + '.'
                        + (' Some parts could not be built: tell the person which, plainly (report_errors).' if made.get('errors') else '')
                        + (' The branch has moved on with new work since this check: say the report shows the code as it was '
                           'then; a new check (audit with fresh=true) runs only when the person asks for it.' if stale else '')}


def _stale(state, made):
    """{checked, now} once the branch went past the checked commit with code of its own (not only EAOS's merged fixes);
    else None."""
    checked, now = made.get('scanned_commit') or state.get('scanned_commit'), _head(state)
    if not checked or not now or guided.same_code(state, checked, now): return None
    return {'checked': checked, 'now': now}
