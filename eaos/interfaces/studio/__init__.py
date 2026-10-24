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
import fcntl
import functools
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ...ai import headless as adapters_module, prompts
from ...journeys import batch_branch, build_tools, check_choices, guided, selection as selecting
from . import chat, handoff, helpers, plan
from .branches import BranchControl, Blocked
from .runs import PLANNERS, Manager
from ...core.security import Locks
from ...core.store import BRIEF_ONLY, TERMINAL, Scrubber, Store, contract, now, _read_json, _write_json
from ...core import project_state

VERBS = ('fix', 'verify', 'explain', 'plan')
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


def _where_of(where):
    """The part of a Fix preview's place that is confirmed and handed to fix_start: {base, base_commit, deliver_as,
    merge_into}; None without one."""
    if not where or not where.get('base'): return None
    return {'base': where['base']['branch'], 'base_commit': where['base']['commit'], 'deliver_as': where.get('deliver_as'),
            'merge_into': where.get('merge_into')}


def _group_name(selection):
    """The name of the group a Fix was chosen as (an area, a component, ...): its new branch is named after it."""
    group = (selection or {}).get('group') if isinstance(selection, dict) and selection.get('kind') == 'group' else None
    return str((group or {}).get('value') or '') or None


def _auto_accept(verb, inputs):
    """Whether the person chose, in a Fix preview, to accept the batch automatically when its checks pass."""
    return verb == 'fix' and (inputs or {}).get('auto_accept') is True


def _bound(selection, where, auto):
    """What a confirm token is bound to: the selection, a Fix's place, and the person's auto-accept choice, so a token
    of a preview without it never starts a run that accepts by itself."""
    bound = {'selection': selection, 'where': where} if where else selection
    return {'bound': bound, 'auto_accept': True} if auto else bound


class Refused(Exception):
    def __init__(self, status, reason, **extra):
        super().__init__(reason)
        self.status, self.reason, self.extra = status, reason, extra


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


def _chosen_answer(question, option, text):
    """The option the owner chose, or None for a custom answer; refused when the answer is neither, or both."""
    chosen = next((o for o in question.get('options', []) if o['id'] == option), None)
    if option is not None and text is not None:
        raise ValueError('send either an option or a custom answer, not both')
    if text is not None and (not isinstance(text, str) or not text.strip() or len(text) > 4000):
        raise ValueError('text must contain 1 to 4000 characters')
    if not chosen and not (option is None and text):
        raise ValueError('choose an authoritative option or a custom answer')
    return chosen


def _owner_response(saved, row, answer, path):
    """The owner's saved answer to a report question, saved now when it is the first; `answer`: (decision, option,
    text, the chosen option). A different answer to a question already answered is refused."""
    decision, option, text, chosen = answer
    response = saved.get(row['scope'])
    if response and (response['option'] != option or response.get('text') != text):
        raise LookupError('this question already has an owner answer')
    if response: return response
    response = {'decision': decision, 'scope': row['scope'], 'option': option, 'text': text,
                'label': chosen['label'] if chosen else text, 'at': now(), 'provenance': 'owner:studio',
                'status': 'saved', 'run': 'd' + row['scope'][:40],
                'history': [{'at': now(), 'event': 'saved', 'by': 'owner:studio'}]}
    saved[row['scope']] = response
    _write_json(path, saved)
    return response


def _run_label(verb, label, cards):
    if not verb: return label
    return {lang: f"{label[lang]}: {', '.join(c['id'] for c in cards[:3])}{' …' if len(cards) > 3 else ''}" for lang in ('en', 'ar')}


def _mode(action, needed, assistant):
    if action in PLANNERS: return 'planner'
    if not needed: return 'direct'
    return 'handoff' if assistant == 'handoff' else 'assistant'


def _decision_words(operation, branch, ok, result):
    """What happened to the waiting branch, in both languages."""
    if ok:
        return {'en': f"{'Taken in' if operation == 'accept' else 'Thrown away'}: {branch}",
                'ar': f"{'اعتُمد' if operation == 'accept' else 'رُمي'}: {branch}"}
    return {'en': f"{operation} did not happen: {result.get('status') or result.get('error')}",
            'ar': f"ما تم: {result.get('status') or result.get('error')}"}


class Actions:
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
        except Blocked as problem:
            return (403 if problem.needs in ('confirm', 'confirm_unmerged') else 409), {'error': str(problem), 'reasons': problem.reasons, 'needs': problem.needs}
        except Refused as problem:
            return problem.status, {'error': problem.reason, **problem.extra}
        except selecting.SelectionError as problem:
            return 400, {'error': str(problem), 'reasons': [problem.reason]}
        except KeyError as problem:
            return 404, {'error': f'not found: {problem}'}
        except LookupError as problem:
            return 409, {'error': str(problem)}
        except ValueError as problem:
            return 400, {'error': str(problem)}

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
        from ...core.usage import of_check, of_run, total
        folder = self._studio()
        runs = []
        for record in self.store.all():
            found = record.get('usage') or of_run(self.store.path(record['id']))
            if found and record.get('state') in TERMINAL and not record.get('usage'): self.store.update(record['id'], usage=found)
            runs.append({'id': record['id'], 'verb': record.get('verb'), 'action': record.get('action'), 'label': record.get('label'),
                         'state': record.get('state'), 'assistant': record.get('assistant'), 'created': record.get('created'),
                         'cards': len((record.get('result') or {}).get('cards_closed') or []), 'usage': found})
        talked = [json.loads(line).get('usage') for path in (self.store.folder / 'chat').glob('*/turns.jsonl')
                  for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        return {'check': of_check(folder.parent) if folder else None, 'runs': runs, 'chat': total(talked)}

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
        rows = [row for row in self.store.all() if query.get('all') or not row.get('read')]
        if query.get('state'): rows = [row for row in rows if row.get('state') == query['state']]
        if query.get('q'):
            needle = query['q'].lower()
            rows = [row for row in rows if needle in json.dumps([row.get('label'), row.get('cards'), row.get('result'), row.get('action'), row.get('verb')],
                                                                ensure_ascii=False).lower()]
        queue = self.store.queue()  # read once: the queue reads every run, and a list of runs is not n^2 reads
        return {'runs': [{k: v for k, v in self.public(row, queue).items() if k not in BRIEF_ONLY} for row in rows], 'queue': queue}

    def questions(self):
        """The questions waiting, each `binding` when only an option answers it (prompts.binding)."""
        return [{**row['question'], 'binding': prompts.binding(row, row['question'])} for row in self.store.all() if row.get('state') == 'waiting_for_person' and row.get('question')]

    def report_decisions(self):
        folder = self._studio()
        rows = (selecting._load(folder, 'decisions') or {}).get('decisions', []) if folder else []
        saved = _read_json(self.store.folder / 'decisions.json', {}) or {}
        result = []
        for question in rows:
            scope = selecting.decision_scope(folder, question)
            response = saved.get(scope)
            run = None
            if response and response.get('run'):
                try: run = self.public(self.store.load(response['run']))
                except KeyError: pass
            result.append({'id': question['id'], 'scope': scope, 'question': question,
                           'response': response, 'execution': run})
        return result

    def answer_decision(self, decision, body):
        with (self.store.folder / 'decisions.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            row = next((r for r in self.report_decisions() if r['id'] == decision), None)
            if not row: raise KeyError(decision)
            if body.get('scope') != row['scope']: raise LookupError('the report question changed; reload before answering')
            question = row['question']
            option, text = body.get('option'), body.get('text')
            chosen = _chosen_answer(question, option, text)
            path = self.store.folder / 'decisions.json'
            saved = _read_json(path, {}) or {}
            response = _owner_response(saved, row, (decision, option, text, chosen), path)
            if question.get('tool') == 'blueprint': return build_tools.answered(self.project, row, response)
            run = response['run']
            try: self.store.load(run)
            except KeyError: self._queue_review(run, question, response, body.get('assistant'))
            response['status'] = 'queued'
            if not any(e['event'] == 'queued' for e in response['history']):
                response['history'].append({'at': now(), 'event': 'queued', 'run': run})
            saved[row['scope']] = response
            _write_json(path, saved)
            self.store.set_queue(self.store.queue())
            return next(r for r in self.report_decisions() if r['id'] == decision)

    def _queue_review(self, run, question, response, wanted):
        """A run for the assistant to review the owner's answer, with the cards it blocks and their evidence."""
        assistant = self._assistant(wanted, True)
        blocked = [c for c in (selecting._load(self._studio(), 'cards') or {}).get('cards', []) if c['id'] in question.get('blocks', [])]
        evidence_ids = {e for c in blocked for e in c.get('evidence', []) if isinstance(e, str)}
        facts = (selecting._load(self._studio(), 'evidence') or {}).get('facts', [])
        context = {'question': question, 'answer': response,
                   'evidence': [f for f in facts if f.get('id') in evidence_ids][:40],
                   'project': self.project.name, 'report': Path(self._studio()).parent.name,
                   'blocked_cards': [{'id': c['id'], 'title': c.get('title'), 'paths': c.get('paths'), 'evidence': c.get('evidence')} for c in blocked]}
        record = {'id': run, 'action': 'report_decision', 'verb': None,
                  'label': {'en': 'Review owner answer', 'ar': 'مراجعة إجابة المالك'},
                  'inputs': {}, 'owner_decision': context, 'cards': question.get('blocks', []),
                  'assistant': None if assistant == 'handoff' else assistant,
                  'mode': 'handoff' if assistant == 'handoff' else 'assistant', 'state': 'queued',
                  'attempt': 1, 'created': now(), 'queued_at': now(), 'read': False}
        self.store.save(record, new=True)
        self.store.append(run, 'action', record['label'], {'action': 'report_decision', 'by': 'person'})

    # what a run would be
    def _kind(self, name, body):
        """(verb or None, action id) of a preview or a run: a verb when the body selects cards."""
        verb = body.get('verb') or (name if name in VERBS and name not in self.actions else None)
        if verb is None and name in VERBS and body.get('selection'): verb = name
        if verb:
            if verb not in self.verbs: raise ValueError(f'no verb named {verb}')
            return verb, verb
        if name not in self.actions: raise KeyError(name)
        return None, name

    def _inputs(self, action, inputs, verb=None, project=None):
        """The inputs of an action, or of a verb that declares any (a Fix's auto_accept), checked against the contract;
        the project is the server's own (create), never the page's."""
        from ...core.artifact_contracts import validate
        inputs = {key: value for key, value in (inputs or {}).items() if key != 'project'}
        schema = self.verbs[verb].get('inputs') if verb else self.actions[action]['inputs']
        if verb and not schema: return {}
        problems = validate(inputs, schema)
        if problems: raise ValueError('; '.join(problems[:5]))
        return {**inputs, 'project': project} if project else inputs

    def _assistant(self, wanted, needed):
        if not needed: return None
        if wanted == 'handoff': return 'handoff'
        if wanted:
            if wanted not in self.adapters: raise ValueError(f'no assistant named {wanted}')
            return wanted
        return next((key for key, adapter in self.adapters.items() if adapter.available()), 'handoff')

    def _needs_confirm(self, verb, action, inputs):
        if verb: return self.verbs[verb]['changes_code']
        spec = self.actions[action]
        return spec['irreversible'] or spec['changes_code'] or (spec['needs_consent'] and bool(inputs.get('person_agreed')))

    def _past(self, verb):
        rows = []
        for row in self.store.all():
            if row.get('verb') == verb and row.get('state') == 'done' and row.get('started') and row.get('ended') and row.get('cards'):
                minutes = (datetime.fromisoformat(row['ended']) - datetime.fromisoformat(row['started'])).total_seconds() / 60
                rows.append((minutes, len(row['cards'])))
        return rows

    def preview(self, name, body):
        verb, action = self._kind(name, body)
        inputs = self._inputs(action, body.get('inputs'), verb)
        needed = self.verbs[verb]['needs_assistant'] if verb else self.actions[action]['needs_assistant']
        assistant = self._assistant(body.get('assistant'), needed)
        chosen = self.adapters.get(assistant).detect() if assistant and assistant != 'handoff' else None
        out = {'action': action, 'verb': verb, 'selection': body.get('selection') if verb else None,
               'cards': [], 'left_out': [], 'files': [], 'batches': [],
               'assistant': chosen, 'assistants': self.assistants() if needed else [],
               'irreversible': bool(not verb and self.actions[action]['irreversible']),
               'needs_consent': bool(not verb and self.actions[action]['needs_consent']) or verb == 'fix'}
        if verb: self._verb_preview(out, verb, body)
        else: self._action_preview(out, action, inputs)
        self._handoff(out, (verb, action, needed), inputs)
        # a Fix confirms where it builds too: the token pins the base commit the person saw, and nothing is confirmed
        # while the preview says the place is wrong (a protected target, a branch name git refuses)
        where = out.get('where')
        out['auto_accept'] = _auto_accept(verb, inputs)
        bound = _bound(out['selection'], _where_of(where), out['auto_accept'])
        out['confirm'] = (self.locks.confirm(action, bound, self.project)
                          if self._needs_confirm(verb, action, inputs) and not (where and where.get('problem')) else None)
        return out

    def _verb_preview(self, out, verb, body):
        """The cards a verb would take and leave out, and where a Fix would build."""
        cards, left = selecting.resolve(body.get('selection'), self._studio())
        out.update(selecting.preview_of(verb, cards, left, self._past(verb)))
        if verb == 'fix' and self._has_commits(): out.update(where=self.branches.fix_where(body.get('where'), _group_name(body.get('selection'))), speed=helpers.speed(self.project, cards))

    def _action_preview(self, out, action, inputs):
        """An action's time (a check's from this project's last one, eaos/journeys/check_choices.py), risk and what happens when it
        fails; where Accept would merge."""
        spec = self.actions[action]
        low, high = (5, 30) if action == 'audit' else (10, 40) if action in ('run_setup', 'run_try', 'safety_net', 'fix_finish', 'build_finish') else (0, 1)
        measured = action == 'audit' and self._studio() and check_choices.estimate(self._studio().parent, inputs.get('paths'), inputs.get('mode'), inputs.get('again_from'))
        if action == 'audit':
            out['check'] = check_choices.offered(project_state.load(str(self.project)), self._studio() and self._studio().parent)
        out.update(estimate=measured or {'minutes_low': low, 'minutes_high': high, 'basis': {'en': 'a rough rule for this step', 'ar': 'تقدير تقريبي لهذه الخطوة'}},
                   risk={'level': 'high' if spec['irreversible'] else 'medium' if spec['changes_code'] else 'low',
                         'why': spec['description'] if spec['description']['en'] else spec['label']},
                   on_failure=selecting.ON_FAILURE['fix' if spec['changes_code'] else 'read'])
        if action == 'accept' and self._has_commits(): out['merge'] = self.branches.accept_where()

    def _handoff(self, out, kind, inputs):
        """The request a chat assistant could take over; `kind`: (verb, action, needs an assistant)."""
        verb, action, needed = kind
        prompt = prompts.build(verb, out['cards'], self.project, self.lang, action=action, inputs={} if verb else inputs,
                               labels={k: v['label'] for k, v in self.actions.items()}, where=_where_of(out.get('where')))
        # The planner asks the assistant itself: there is no request a chat assistant could take over.
        handed = bool(needed) and action not in PLANNERS
        out['handoff'] = {'available': handed, 'request': handoff.request_text(prompt, '<run>') if handed else None}

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
        where = self._checked_where(body, selection) if verb == 'fix' and self._has_commits() else None
        bound = _bound(selection, where, auto)
        if self._needs_confirm(verb, action, inputs) and not self.locks.spend(body.get('confirm'), action, bound, self.project):
            raise Refused(403, 'this needs your explicit confirmation: open its preview and confirm', needs='confirm')
        record = self._run_record((verb, action), body, (inputs, selection, where, auto))
        run, label, reading = record['id'], record['label'], record['read']
        self.store.save(record, new=True)
        shown = {k: v for k, v in inputs.items() if k not in ('edits', 'spec', 'proposal', 'text')}
        self.store.append(run, 'action', {'en': f"You asked: {label['en']}", 'ar': f"طلبت: {label['ar']}"},
                          {'action': action, 'by': 'person', 'arguments': {**shown, **({'cards': record['cards']} if verb else {})}})
        if reading:
            if 'seconds' in inputs: self.store.update(run, inputs={**inputs, 'seconds': 0})
            self.manager._direct(run, follow=False)                 # never queued: it answers now, in this call
            return self.store.load(run)
        self.store.set_queue(self.store.queue())
        return self.store.load(run)

    def _checked_where(self, body, selection):
        """Where a Fix builds now: refused when its base moved since the preview, or the place is wrong."""
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
                'cards': [c['id'] for c in cards], 'cards_detail': [{'id': c['id'], 'title': c.get('title'), 'paths': selecting._paths(c)} for c in cards],
                'left_out': left, 'assistant': assistant if assistant != 'handoff' else None,
                'mode': _mode(action, needed, assistant),
                'owner_answers': [{'question': r['question'], 'response': r['response']} for r in self.report_decisions() if r['response']],
                'context': self.branches.run_context(), **({'where': {**where, **helpers.speed_of(self.project, body)}} if where else {}), **({'auto_accept': True} if auto else {}),
                'state': 'running' if reading else 'queued', 'attempt': 1, 'created': now(), 'queued_at': now(), 'read': reading,
                **({'started': now()} if reading else {})}

    def _merge_choice(self, body):
        """Where Accept merges, as the person chose in its sheet (one of their branches, never a protected one), and
        whether the branch is kept after merging."""
        chosen = {}
        target = str(body.get('merge_into') or '').strip()
        if target:
            from .branches import valid_name
            valid_name(self.project, target)
            if not self.branches.tip(f'refs/heads/{target}'): raise LookupError(f'no branch named {target} to merge into')
            reason = self.branches.blocked_target(target)
            if reason: raise Refused(409, f"{target} is protected ({reason['en']}): choose another branch to merge into", reasons=[reason])
            chosen['merge_into'] = target
        if body.get('delete_after') is False: chosen['delete_after'] = False
        return chosen

    def decide(self, run, operation, body):
        """Accept or undo the branch a run handed over: only with the confirm token of that preview."""
        if not self.locks.spend(body.get('confirm'), operation, None, self.project):
            raise Refused(403, f'{operation} needs your explicit confirmation: open its preview and confirm', needs='confirm')
        record = self.store.load(run)
        branch = (record.get('result') or {}).get('branch')
        if not branch: raise LookupError('this run handed no branch over')
        if record.get('outcome'): raise LookupError(f"this run's branch was already {record['outcome']}")
        # accept and undo act on the newest waiting branch: refuse when that is not this run's, so a decision on one
        # run never takes in or throws away another run's work
        newest = self.manager.newest_waiting()
        if newest != branch:
            raise LookupError(f'another branch ({newest}) waits after {branch}: decide that one first' if newest else f'{branch} is not waiting for a decision any more')
        # Accept merges where the person chose in its sheet (one of their branches, never a protected one) and deletes the
        # branch after merging unless they unticked it
        chosen = self._merge_choice(body) if operation == 'accept' else {}
        self.store.append(run, 'action', {'en': f'You chose to {operation} {branch}', 'ar': f"اخترت {'اعتماد' if operation == 'accept' else 'رمي'} {branch}"},
                          {'action': operation, 'by': 'person', 'arguments': {'branch': branch, **chosen}})
        result = self.manager.call(operation, {'person_agreed': True, **chosen})
        ok = isinstance(result, dict) and not result.get('error') and result.get('status') == {'accept': 'accepted', 'undo': 'undone'}[operation]
        self.store.append(run, 'result' if ok else 'error', _decision_words(operation, branch, ok, result),
                          {'branch': branch, 'outcome': operation if ok else None, 'answer': result} if ok else
                          {'reason': str(result.get('status') or result.get('error')), 'recoverable': True,
                           'what_now': {'en': str(result.get('what_now') or ''), 'ar': str(result.get('what_now') or '')}})
        if ok: self.store.update(run, outcome={'accept': 'accepted', 'undo': 'undone'}[operation], decided=now())
        return {'run': self.public(self.store.load(run)), 'result': result}

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
