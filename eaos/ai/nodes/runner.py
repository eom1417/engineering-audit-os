"""One run of an AI node (eaos/ai/nodes/core.py run_node starts it): what it says as it goes, its batches asked at
the permitted width, the critique pass, the answer in the person's language, the subjects judged before kept, the rules
fallback and the record it ends with."""
import contextvars
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext

from ...core.language import foreign_texts, restate
from ...core.process import Stuck, check_cancelled
from .core import (WORDS, answer_schema, cached, check, check_shape, critique_prompt, critique_schema, digest, fallback, folder_of,
                   keep, launcher_of, now, record, rules_decisions, short, spent)


def _joined(answers):
    """The answers of a list asked in batches, as one answer."""
    if len(answers) == 1: return answers[0]
    return {'summary': ' '.join(short(a.get('summary'), 300) for a in answers if a.get('summary')),
            'decisions': [d for a in answers for d in a.get('decisions') or []]}


class Run:
    """One run of a node on its inputs: what it says as it goes, and the record it ends with."""

    def __init__(self, node, spec, report, data, settings):
        self.node, self.spec, self.report, self.data, self.settings = node, spec, report, data, settings
        self.tell = settings['say'] or (lambda en, ar: None)
        self.subjects, self.known = list(spec.subjects(data)), set(spec.known(report, data))
        self.at, self.began = now(), time.monotonic()
        self.base = {'at': self.at, 'inputs': digest(data), 'passes': list(node.passes), 'summary': ''}
        self.unanswered = None      # {asked, failed, why}: some batches failed, the rules decided their subjects

    def done(self, row, key=None):
        row = keep(self.report, self.node, row, key, self.settings['logged'])
        if hasattr(self.spec, 'finish'): self.spec.finish(self.report, row, self.data)
        return row

    def rules_only(self, state, why, **ran):
        """The rules decide alone; `ran`: assistant, model, prompt, schema, seconds and cost of an ask that failed."""
        node, ran = self.node, {'assistant': None, 'model': None, 'prompt': None, 'schema': None, 'seconds': None, 'cost': None, **ran}
        self.tell(f'{node.title}: {why}', f'{node.title}: تقرّر بالقواعد فقط')
        return self.done(record(node, {**self.base, 'state': state, 'method': 'rules', 'assistant': ran['assistant'], 'model': ran['model'],
                                       'prompt': ran['prompt'], 'schema': ran['schema'], 'cached': False,
                                       'seconds': ran['seconds'], 'cost_usd': ran['cost'], 'why': why},
                                rules_decisions(node, self.spec, self.data, why), []))

    def go(self):
        node, spec = self.node, self.spec
        if not self.subjects:
            return self.rules_only('rules_only', 'There was nothing for the node to decide.')
        detail = getattr(spec, 'DETAIL', None)
        before, left = self._judged()
        asks = self._asks(left, detail)
        key = self._key(asks, before)
        hit = None if self.settings['fresh'] else cached(self.report, node, key)
        if hit:
            self.tell(f'{node.title}: the same inputs as before, the cached decision stands', f'{node.title}: المدخلات نفسها، فيبقى القرار المحفوظ')
            return self.done({**hit, 'at': self.at, 'cached': True})
        if not asks: return self._decided(None, ({'decisions': before}, None), asks, [], key)
        launcher = self._launcher()
        if launcher is None: return self.rules_only('rules_only', WORDS['no_assistant'])
        asked = [p for _, _, p in asks]
        try: answer, critique = self._ask(launcher, asks, asked, detail)
        except Exception as problem:   # noqa: BLE001 - every failure falls back to the rules, with its reason
            return self._failed(problem, launcher, asks, asked)
        self._remember(answer)
        return self._decided(launcher, ({**answer, 'decisions': before + (answer.get('decisions') or [])}, critique), asks, asked, key)

    def _asks(self, left, detail):
        """(data, schema, prompt) of each question about the data left to ask (none when nothing is)."""
        node, spec = self.node, self.spec
        # A long list is asked in batches (spec.batches), one question each; a planning node, whose critique reviews the
        # whole draft, is asked at once.
        parts = [] if left is None else spec.batches(left) if hasattr(spec, 'batches') and 'critique' not in node.passes else [left]
        return [(part, answer_schema(node, spec.subjects(part), detail), spec.prompt(part)) for part in parts]

    def _key(self, asks, before):
        """The cache key of a run: the node, its version, what is asked and the decisions kept from before."""
        node = self.node
        return digest([node.name, node.version, getattr(self.spec, 'VERSION', '1'), [digest(p) for _, _, p in asks],
                       [digest(s) for _, s, _ in asks], before])

    def _judged(self):
        """(the decisions kept, the data left to ask, None when nothing is): a subject of the node's list (spec.LIST)
        judged before on the very same input keeps its decision, so a check gone on from a stage asks only what is new
        or changed. A fresh check clears them with the other caches (eaos/pipeline/run.py BULKY)."""
        field = getattr(self.spec, 'LIST', None)
        if not field or self.settings['fresh']: return [], self.data
        self.frame = digest(self.spec.prompt({**self.data, field: []}))     # the task itself: new words ask every subject again
        before, left = [], []
        for item in self.data[field]:
            hit = cached(self.report, self.node, self._item_key(item))
            if hit: before.append(hit)
            else: left.append(item)
        if before: self.tell(f'{self.node.title}: {len(before)} judged before on the same evidence, kept',
                             f'{self.node.title}: {len(before)} حُكم عليها قبل على نفس الدليل، فيبقى حكمها')
        return before, ({**self.data, field: left} if left else None)

    def _item_key(self, item):
        return 'one-' + digest([self.node.name, self.node.version, getattr(self.spec, 'VERSION', '1'), self.frame, item])

    def _remember(self, answer):
        """Each decision on a subject of the node's list, kept under its own input (_judged)."""
        field = getattr(self.spec, 'LIST', None)
        if not field or self.settings['fresh']: return
        items = {item['id']: item for item in self.data[field]}
        folder = folder_of(self.report, self.node) / 'cache'
        folder.mkdir(parents=True, exist_ok=True)
        for row in answer.get('decisions') or []:
            item = items.get(row.get('subject')) if isinstance(row, dict) else None
            if item: (folder / f'{self._item_key(item)}.json').write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')

    def _launcher(self):
        s = self.settings
        stamp = self.at.replace(':', '').replace('+0000', 'Z')
        images = self.spec.images(self.data) if hasattr(self.spec, 'images') else ()
        return s['launcher'] or launcher_of(s['adapters'], folder_of(self.report, self.node) / 'runs' / stamp, s['cancel'], s['started'], images)

    def _ask(self, launcher, asks, asked, detail):
        """(answer, critique): one ask per batch, several at once when the check allows several assistants, joined in
        the batches' order; a batch that fails leaves its subjects to the rules (_decided), unless every batch failed or
        the assistant is stuck or stopped. Then a planning node's critique pass."""
        outcomes = self._batches(launcher, asks)
        failed = [problem for problem in outcomes if isinstance(problem, Exception)]
        if failed: self._some_failed(failed, len(outcomes))
        answer = _joined([one for one in outcomes if not isinstance(one, Exception)])
        if 'critique' not in self.node.passes: return answer, None
        return self._critique(launcher, answer, asks[0][2], asked, detail)

    def _some_failed(self, failed, asked):
        """Raise the failure when every batch failed or the assistant is stuck or stopped; else the record says how many
        failed, and the check is partial (eaos/pipeline/ai_runners.py _partly)."""
        stuck = next((p for p in failed if isinstance(p, Stuck)), None)
        if len(failed) == asked or stuck or self._stopped(): raise stuck or failed[0]
        self.unanswered = {'asked': asked, 'failed': len(failed), 'why': short(f'{type(failed[0]).__name__}: {failed[0]}', 300)}

    def _batches(self, launcher, asks):
        """Ask at the permitted width, with the stage's stop and progress context; always join in input order."""
        slots = self.settings['assistants']
        at_once = min(len(asks), slots.count if slots else 1)
        if at_once <= 1: return [self._batch(launcher, asks, index) for index in range(len(asks))]
        with ThreadPoolExecutor(at_once, thread_name_prefix=f'eaos-{self.node.name}') as pool:
            futures = [pool.submit(contextvars.copy_context().run, self._batch, launcher, asks, index) for index in range(len(asks))]
            return [future.result() for future in futures]

    def _batch(self, launcher, asks, index):
        """One batch's answer in the person's language, in its asked shape; the error instead when it failed."""
        node, who, (_, schema, prompt) = self.node, getattr(launcher, 'assistant', None), asks[index]
        batch = f' ({index + 1}/{len(asks)})' if len(asks) > 1 else ''
        self.tell(f'{node.title}: {who or "the assistant"} decides{batch}', f'{node.title}: {who or "المساعد"} يقرّر{batch}')
        name = node.passes[0] if len(asks) == 1 else f'{node.passes[0]}-{index + 1}'
        try:
            one = self._answer(launcher, name, prompt, schema)
            check_shape(one, schema, 'answer')
            return one
        except Exception as problem:   # noqa: BLE001 - _ask decides what a failed batch means
            return problem

    def _stopped(self):
        return self.settings['cancel'] is not None and self.settings['cancel'].is_set()

    def _answer(self, launcher, name, prompt, schema):
        with self.settings['assistants'] or nullcontext():
            check_cancelled()
            return self._in_language(launcher, launcher(name, prompt, schema), schema, name)

    def _critique(self, launcher, answer, prompt, asked, detail):
        node = self.node
        self.tell(f'{node.title}: a second pass reviews the decisions', f'{node.title}: تمرير ثانٍ يراجع القرارات')
        second = critique_prompt(prompt, self.data, answer, self.settings['lang'])
        asked.append(second)
        schema = critique_schema(node, self.subjects, detail)
        reviewed = self._answer(launcher, 'critique', second, schema)
        check_shape(reviewed, schema, 'review')
        return reviewed, reviewed.get('critique')

    def _in_language(self, launcher, answer, schema, name):
        """The answer, its texts for the person in their language: sent back once when some are not (eaos/core/language.py)."""
        lang = self.settings['lang']
        texts = foreign_texts(answer, lang)
        if not texts: return answer
        self.tell(f'{self.node.title}: {len(texts)} texts are not in your language; the assistant writes them again',
                  f'{self.node.title}: {len(texts)} نصوص مو بلغتك؛ المساعد يكتبها من جديد')
        again = launcher(f'{name}-language', restate(answer, texts, lang), schema)
        return again if isinstance(again, dict) and len(foreign_texts(again, lang)) < len(texts) else answer

    def _failed(self, problem, launcher, asks, asked):
        why, state = fallback('stuck' if isinstance(problem, Stuck) else 'stopped' if self._stopped() else f'{type(problem).__name__}: {problem}')
        return self.rules_only(state, why, assistant=getattr(launcher, 'assistant', None), model=getattr(launcher, 'model', None),
                               prompt=digest(asked), schema=digest([s for _, s, _ in asks]),
                               seconds=round(time.monotonic() - self.began, 1), cost=spent(launcher))

    def _decided(self, launcher, answered, asks, asked, key):
        """The record of the decisions that stand; no launcher: every one was judged before (_judged), none asked."""
        node, spec, data = self.node, self.spec, self.data
        answer, critique = answered
        self.tell(f'{node.title}: checking that every decision stands on evidence', f'{node.title}: يتحقق أن كل قرار قائم على دليل')
        kept, dropped = check(node, spec, data, answer, self.known)
        decided = {d['subject'] for d in kept}
        left = rules_decisions(node, spec, data, 'The assistant left this subject undecided, so the rules decided it.', decided)
        row = record(node, {**self.base, 'state': 'decided', 'method': 'model', 'assistant': getattr(launcher, 'assistant', None),
                            'model': getattr(launcher, 'model', None),
                            'prompt': digest(asked), 'schema': digest([s for _, s, _ in asks]), 'cached': launcher is None, 'calls': len(asked),
                            'seconds': round(time.monotonic() - self.began, 1),
                            'cost_usd': spent(launcher), 'why': None, 'summary': short((answer or {}).get('summary'), 800)},
                     kept + left, dropped, critique=critique if isinstance(critique, dict) else None,
                     **({'batches': self.unanswered} if self.unanswered else {}))
        self.tell(f'{node.title}: {len(kept)} decisions with their evidence, {len(dropped)} dropped without it',
                  f'{node.title}: {len(kept)} قرارًا بدليله، وحُذف {len(dropped)} بلا دليل')
        return self.done(row, None if self.unanswered else key)     # a partial answer is never the cached whole
