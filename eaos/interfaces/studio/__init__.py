"""The command centre's action API (docs/studio-actions.json, docs/STUDIO.md D8): run EAOS from the Studio.

Framework-agnostic: `Actions.handle(method, path, headers, body)` answers every endpoint of the contract with
`(status, dict)`, and `Actions.sse(run, last_event_id, follow)` yields a run's events as Server-Sent Events frames. The
local server (NS37.T2) mounts them with `mount(...)` (eaos/interfaces/studio/serve.py); the tests call them directly.

    actions = Actions(project, port=8765)            # the launch token and the CSRF token are made here
    status, payload = actions.handle('POST', '/api/runs', headers, {'action': 'audit'})
    for frame in actions.sse(run_id, last_event_id=12, follow=True): ...

Every call passes the locks of eaos/core/security.py first; every accepted action becomes an `action` event
before it runs; reading actions answer at once, the others queue as runs (eaos/interfaces/studio/runs.py).
"""
import functools
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ...ai import headless as adapters_module, prompts
from ...journeys import batch_branch, guided, selection as selecting
from . import chat, helpers, plan
from .branches import BranchControl, Blocked
from .decisions import Decisions
from .previews import Previews, _auto_accept, _bound, _group_name, _where_of
from .runs import PLANNERS, Manager
from ...core.security import Locks
from ...core.store import BRIEF_ONLY, TERMINAL, Scrubber, Store, contract, now
from ...core import project_state

HEARTBEAT = 15


@functools.lru_cache(maxsize=1)
def _server_tools():
    from .. import mcp_server
    return mcp_server.functions()


@functools.lru_cache(maxsize=1)
def reading_tools():
    """The tools the MCP server marks read-only: they answer at once and are not queued."""
    from .. import mcp_server
    return mcp_server.reading()


class Refused(Exception):
    def __init__(self, status, reason, **extra):
        super().__init__(reason)
        self.status, self.reason, self.extra = status, reason, extra


def _refusal(problem):
    """(status, answer) of a refused call: a blocked change, a refusal, a selection that cannot run, a thing not found,
    a conflict, a wrong input."""
    if isinstance(problem, Blocked):
        return (403 if problem.needs in ('confirm', 'confirm_unmerged') else 409), {'error': str(problem), 'reasons': problem.reasons, 'needs': problem.needs}
    if isinstance(problem, Refused): return problem.status, {'error': problem.reason, **problem.extra}
    if isinstance(problem, selecting.SelectionError): return 400, {'error': str(problem), 'reasons': [problem.reason]}
    if isinstance(problem, KeyError): return 404, {'error': f'not found: {problem}'}
    if isinstance(problem, LookupError): return 409, {'error': str(problem)}
    return 400, {'error': str(problem)}


def _cards_of_run(cards, left):
    """A run record's cards: their ids, each with its title and paths, and those left out."""
    return {'cards': [c['id'] for c in cards], 'cards_detail': [{'id': c['id'], 'title': c.get('title'), 'paths': selecting._paths(c)} for c in cards],
            'left_out': left}


def _run_id():
    return 'r' + datetime.now().strftime('%Y%m%d-%H%M%S-') + os.urandom(3).hex()


# The GET routes that take nothing from the path: /api/<route> -> (actions, query) -> answer.
GET_ROUTES = {
    ('session',): lambda a, q: a.session(),
    ('actions',): lambda a, q: a.contract,
    ('assistants',): lambda a, q: {'assistants': a.assistants()},
    ('usage',): lambda a, q: a.usage(),
    ('chat', 'control'): lambda a, q: chat.control(a),
    ('runs',): lambda a, q: a.runs(q),
    ('questions',): lambda a, q: {'questions': a.questions()},
    ('decisions',): lambda a, q: {'decisions': a.report_decisions()},
    ('freshness',): lambda a, q: {'freshness': a.branches.freshness()},
    ('context',): lambda a, q: {'context': a.branches.context() if a.branches.is_repo() else None},
    ('branches',): lambda a, q: a.branches.inventory(q.get('base') or None),
    ('branches', 'detail'): lambda a, q: a.branches.detail(q.get('name'), q.get('kind') or 'local', q.get('remote'), q.get('base') or None,
                                                           q.get('path') or None),
}


def _run_label(verb, label, cards):
    if not verb: return label
    return {lang: f"{label[lang]}: {', '.join(c['id'] for c in cards[:3])}{' …' if len(cards) > 3 else ''}" for lang in ('en', 'ar')}


def _mode(action, needed, assistant):
    if action in PLANNERS: return 'planner'
    if not needed: return 'direct'
    return 'handoff' if assistant == 'handoff' else 'assistant'


class Actions(Previews, Decisions):
    def __init__(self, project, **options):
        """`options`, by name: home, port (8765), adapters (this computer's), studio, lang ('ar'), token, remote_origin,
        dispatch (True: this object's thread starts the queued runs; eaos/interfaces/govern.py builds it without)."""
        home, adapters, studio = options.get('home'), options.get('adapters'), options.get('studio')
        if home: os.environ['EAOS_HOME'] = str(home)
        self.project = Path(project).expanduser().resolve()
        self.locks = Locks(options.get('port', 8765), options.get('token'), options.get('remote_origin'))
        self.token, self.csrf = self.locks.token, self.locks.csrf
        self.studio = Path(studio) if studio else None
        self.lang = lang = options.get('lang', 'ar')
        self.adapters = adapters_module.installed() if adapters is None else dict(adapters)
        self.contract = contract()
        self.actions = {action['id']: action for action in self.contract['actions']}
        self.verbs = {verb['id']: verb for verb in self.contract['verbs']}
        self.store = Store(guided.workspace(self.project) / 'runs', Scrubber(self.project, [self.token, self.csrf]))
        self.manager = Manager(self.project, self.store, self.adapters, self.contract, _server_tools, lang, options.get('dispatch', True))
        self.branches = BranchControl(self)
        self.manager.branch_control = self.branches

    def close(self):
        self.manager.close()

    # the one entry
    def handle(self, method, path, headers, body=None):
        method = str(method).upper()
        refused = self.locks.check(method, path, headers or {})
        if refused:
            self.store.refused(method, urlsplit(path).path, refused[1])
            return refused[0], {'error': refused[1]}
        route = urlsplit(path).path.rstrip('/')
        query = {key: values[-1] for key, values in parse_qs(urlsplit(path).query).items()}
        body = body if isinstance(body, dict) else {}
        try:
            return 200, self._route(method, route, query, body)
        except (Blocked, Refused, LookupError, ValueError) as problem:
            return _refusal(problem)

    def _route(self, method, route, query, body):
        parts = route.strip('/').split('/')
        if parts[:1] != ['api']: raise KeyError(route)
        if method == 'GET': return self._get(parts[1:], query, route)
        return self._post(parts[1:], body, route)

    def _get(self, rest, query, route):
        answer = GET_ROUTES.get(tuple(rest))
        if answer: return answer(self, query)
        if len(rest) == 2 and rest[0] == 'runs': return {'run': self.public(self.store.load(rest[1]))}
        if len(rest) == 2 and rest[0] == 'chat': return chat.progress(self, rest[1])
        if len(rest) == 3 and rest[0] == 'runs' and rest[2] == 'events':
            self.store.load(rest[1])
            return {'events': self.store.events(rest[1], int(query.get('after') or 0))}
        raise KeyError(route)

    def _post(self, rest, body, route):
        if rest[:1] == ['branches']: return self._branch_change(rest, body, route)
        if rest == ['runs']: return {'run': self.public(self.create(body))}
        if rest == ['runs', 'reorder']: return {'queue': self.manager.reorder(body.get('order'))}
        if rest == ['chat']: return chat.start(self, body)
        if rest == ['chat', 'control']: return chat.control(self, body)
        if rest == ['plan']: return plan.start(self, body)
        if len(rest) == 3: return self._post_on(rest, body, route)
        raise KeyError(route)

    def _branch_change(self, rest, body, route):
        change = {('analysis',): self.branches.select, ('merge', 'preview'): self.branches.preview_merge, ('merge',): self.branches.merge,
                  ('conflict',): self.branches.propose_resolution, ('delete', 'preview'): self.branches.preview_delete,
                  ('delete',): self.branches.delete, ('restore',): self.branches.restore, ('fetch',): self.branches.fetch,
                  ('protect', 'preview'): self.branches.preview_protect, ('protect',): self.branches.protect,
                  ('cleanup', 'preview'): self.branches.preview_cleanup, ('cleanup',): self.branches.cleanup}.get(tuple(rest[1:]))
        if change is None: raise KeyError(route)
        if not self.branches.is_repo(): raise LookupError('this project folder is not a git repository')
        return change(body)

    def _post_on(self, rest, body, route):
        """POST /api/<things>/<id>/<operation>."""
        kind, name, operation = rest
        if kind == 'actions' and operation == 'preview': return self.preview(name, body)
        if kind == 'decisions' and operation == 'answer': return {'decision': self.answer_decision(name, body)}
        if kind == 'questions' and operation == 'answer':
            return {'run': self.public(self.manager.answer(name, body.get('option'), body.get('text')))}
        if kind == 'runs': return self.run_operation(name, operation, body, route)
        raise KeyError(route)

    def run_operation(self, run, operation, body, route):
        self.store.load(run)
        if operation in ('pause', 'resume', 'stop', 'retry'):
            self.store.append(run, 'action', chat.pressed(operation), {'action': operation, 'by': 'person', 'arguments': {}})
            return {'run': self.public(getattr(self.manager, operation)(run))}
        if operation in ('accept', 'undo'): return self.decide(run, operation, body)
        raise KeyError(route)

    # reading
    def session(self):
        return {'csrf': self.csrf, 'mode': 'live', 'project': self.project.name, 'contract': self.contract['revision'],
                'assistants': self.assistants(), 'lang': self.lang, 'branch_control': True}

    def assistants(self):
        return [{**adapter.detect(), 'model': adapter.model()} for adapter in self.adapters.values()]

    def usage(self):
        """What the assistant used (eaos/core/usage.py): the last check, stage by stage, and every run, newest first; a run that
        ended keeps its use in its record, counted once."""
        from ...core.usage import of_check, total
        folder = self._studio()
        runs = [self._run_use(record) for record in self.store.all()]
        talked = [json.loads(line).get('usage') for path in (self.store.folder / 'chat').glob('*/turns.jsonl')
                  for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        return {'check': of_check(folder.parent) if folder else None, 'runs': runs, 'chat': total(talked)}

    def _run_use(self, record):
        """One run's row of usage: what it is, and what its assistant used (kept in its record once it ended)."""
        from ...core.usage import of_run
        found = record.get('usage') or of_run(self.store.path(record['id']))
        if found and record.get('state') in TERMINAL and not record.get('usage'): self.store.update(record['id'], usage=found)
        return {'id': record['id'], 'verb': record.get('verb'), 'action': record.get('action'), 'label': record.get('label'),
                'state': record.get('state'), 'assistant': record.get('assistant'), 'created': record.get('created'),
                'cards': len((record.get('result') or {}).get('cards_closed') or []), 'usage': found}

    def public(self, record, queue=None):
        hidden = ('offset', 'pid', 'paused_pid', 'inputs_secret', 'branches_before', 'waves_before')
        out = {key: value for key, value in record.items() if key not in hidden}
        try: out['work_branch'] = self.branches.work_branch(record)
        except Exception: out['work_branch'] = None
        if record['id'] in (queue := self.store.queue() if queue is None else queue): out['position'] = queue.index(record['id']) + 1
        if (branch := (record.get('result') or {}).get('branch')) and not record.get('outcome'):
            out['outcome'] = batch_branch.decided(project_state.load(self.project) or {}, branch)   # decided anywhere, it waits no more
        return out

    def runs(self, query):
        rows = self._runs_asked(query)
        queue = self.store.queue()  # read once: the queue reads every run, and a list of runs is not n^2 reads
        return {'runs': [{k: v for k, v in self.public(row, queue).items() if k not in BRIEF_ONLY} for row in rows], 'queue': queue}

    def _runs_asked(self, query):
        """The runs the query asks for: the unread ones (all with `all`), in a `state`, matching the words `q`."""
        rows = [row for row in self.store.all() if query.get('all') or not row.get('read')]
        if query.get('state'): rows = [row for row in rows if row.get('state') == query['state']]
        if query.get('q'):
            needle = query['q'].lower()
            rows = [row for row in rows if needle in json.dumps([row.get('label'), row.get('cards'), row.get('result'), row.get('action'), row.get('verb')],
                                                                ensure_ascii=False).lower()]
        return rows

    def questions(self):
        """The questions waiting, each `binding` when only an option answers it (prompts.binding)."""
        return [{**row['question'], 'binding': prompts.binding(row, row['question'])} for row in self.store.all() if row.get('state') == 'waiting_for_person' and row.get('question')]

    # what a run would be
    def _speak(self, lang):
        """The language the person reads the Studio in becomes the project's: the check and the fixes it starts write in it."""
        state = project_state.load(self.project) if lang in ('ar', 'en') else None
        if state and state.get('lang') != lang:
            state['lang'] = lang
            guided.save(state)

    def _has_commits(self):
        return self.branches.is_repo() and not self.branches.head()['unborn']

    def _studio(self):
        return self.studio if self.studio else selecting.studio_folder(self.project)

    # running
    def create(self, body, project=None):
        """A run; `project`: another folder, chosen by the server itself (a new project from its plan, plan.py), never by the page."""
        if not (body.get('action') or body.get('verb')): raise ValueError('say which action to run (action) or which verb (verb)')
        verb, action = self._kind(str(body.get('action') or body.get('verb')), body)
        self._speak(body.get('lang'))
        inputs = self._inputs(action, body.get('inputs'), verb, project)
        auto = _auto_accept(verb, inputs)
        if verb: inputs = {}
        selection = body.get('selection') if verb else None
        where = self._checked_where(body, selection) if verb == 'fix' else None
        bound = _bound(selection, where, auto)
        if self._needs_confirm(verb, action, inputs) and not self.locks.spend(body.get('confirm'), action, bound, self.project):
            raise Refused(403, 'this needs your explicit confirmation: open its preview and confirm', needs='confirm')
        record = self._run_record((verb, action), body, (inputs, selection, where, auto))
        run = record['id']
        self.store.save(record, new=True)
        self._asked(record, inputs)
        if record['read']: return self._answered_now(run, inputs)
        self.store.set_queue(self.store.queue())
        return self.store.load(run)

    def _answered_now(self, run, inputs):
        """A reading run, never queued: it answers now, in this call (without waiting, when it is a wait)."""
        if 'seconds' in inputs: self.store.update(run, inputs={**inputs, 'seconds': 0})
        self.manager._direct(run, follow=False)
        return self.store.load(run)

    def _asked(self, record, inputs):
        """The person's ask, the run's first event: its label and its arguments (no edits, spec, proposal or text)."""
        label = record['label']
        shown = {k: v for k, v in inputs.items() if k not in ('edits', 'spec', 'proposal', 'text')}
        self.store.append(record['id'], 'action', {'en': f"You asked: {label['en']}", 'ar': f"طلبت: {label['ar']}"},
                          {'action': record['action'], 'by': 'person', 'arguments': {**shown, **({'cards': record['cards']} if record['verb'] else {})}})

    def _checked_where(self, body, selection):
        """Where a Fix builds now (None in a folder with no commit yet): refused when its base moved since the preview, or
        the place is wrong."""
        if not self._has_commits(): return None
        asked = body.get('where') if isinstance(body.get('where'), dict) else {}
        now_at = self.branches.fix_where(asked, _group_name(selection))
        where = _where_of(now_at)
        if asked.get('base_commit') and where['base_commit'] != asked['base_commit']:
            raise Refused(409, f"the branch {where['base']} moved since the preview: preview again", needs='preview')
        if now_at.get('problem'): raise Refused(409, now_at['problem']['en'], needs='preview', reasons=[now_at['problem']])
        return where

    def _run_record(self, kind, body, given):
        """A new run's record; `kind`: (verb, action); `given`: (inputs, selection, where, auto accept)."""
        verb, action = kind
        inputs, selection, where, auto = given
        needed = self.verbs[verb]['needs_assistant'] if verb else self.actions[action]['needs_assistant']
        cards, left = selecting.resolve(selection, self._studio()) if verb else ([], [])
        label = _run_label(verb, self.verbs[verb]['label'] if verb else self.actions[action]['label'], cards)
        assistant = self._assistant(body.get('assistant'), needed)
        run = _run_id()
        reading = not verb and action in reading_tools()
        return {'id': run, 'action': action, 'verb': verb, 'label': label, 'selection': selection, 'inputs': inputs,
                **_cards_of_run(cards, left), 'assistant': assistant if assistant != 'handoff' else None,
                'mode': _mode(action, needed, assistant),
                'owner_answers': self._owner_answers(),
                'context': self.branches.run_context(), **({'where': {**where, **helpers.speed_of(self.project, body)}} if where else {}), **({'auto_accept': True} if auto else {}),
                'state': 'running' if reading else 'queued', 'attempt': 1, 'created': now(), 'queued_at': now(), 'read': reading,
                **({'started': now()} if reading else {})}

    def _owner_answers(self):
        """The owner's answers to the report's questions, which every run is given."""
        return [{'question': r['question'], 'response': r['response']} for r in self.report_decisions() if r['response']]

    # following
    def sse(self, run, last_event_id=None, follow=False, heartbeat=HEARTBEAT):
        """The run's events after `last_event_id` as SSE frames; with `follow`, then live until the run ends."""
        self.store.load(run)
        after = int(last_event_id or 0)
        beat = time.monotonic()
        while True:
            for event in self.store.events(run, after):
                after = event['seq']
                yield f"id: {event['seq']}\nevent: {event['kind']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if not follow: return
            if self.store.load(run).get('state') in TERMINAL and not self.store.events(run, after): return
            if time.monotonic() - beat >= heartbeat:
                beat = time.monotonic()
                yield ': ping\n\n'
            self.store.wait_change(1.0)

    def wait(self, run, states, timeout=60):
        """The run once its state is one of `states` (or as it is when the time runs out)."""
        end = time.monotonic() + timeout
        while True:
            record = self.store.load(run)
            if record.get('state') in states or time.monotonic() > end: return record
            time.sleep(0.1)


def mount(router, actions, prefix=''):
    """The action API on an existing Starlette app or router (NS37.T2's read server): see eaos/interfaces/studio/serve.py."""
    from .serve import starlette_routes
    for route in starlette_routes(actions, prefix):
        router.routes.append(route)
    return router
