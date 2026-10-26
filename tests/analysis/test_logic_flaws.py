"""The logic-flaw hunt (M9.2): only a flaw pointing at a real line of source and not refuted by the second reading is
kept; the kept ones are read by the claims like any fact set, only on the code they were found on, and a fixed line
closes their card."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from eaos.analysis.claims.ledger import from_facts
from eaos.analysis.claims.probe_queries import run_graph_query
from eaos.analysis.claims.recheck import recheck
from eaos.analysis.logic_flaws import hunt, record
from eaos.core.contracts.untrusted import CLAUSE, UNTRUSTED
from eaos.core.project.workspace import inventory
from eaos.core.system.process import check_cancelled
from eaos.facts import make
from eaos.facts.run import read_available
from eaos.facts.store import write_set
from eaos.interfaces import cli

ROUTE = "app.post('/orders/:id/refund', (req, res) => {\n  const order = find(req.params.id)\n  refund(order, req.body.amount)\n  res.json(order)\n})\n"


def flaw(**changes):
    return {'title': 'A refund takes any amount, even more than was paid', 'title_ar': 'الاسترداد يقبل أي مبلغ',
            'class': 'quantity', 'severity': 'high', 'principal': 'a signed-in buyer', 'invariant': 'a refund never exceeds the payment',
            'path': 'server.js', 'line': 3, 'steps': ['POST /orders/1/refund {"amount": 1000}'], 'impact': 'money paid out twice',
            'fix': 'Cap the amount at what was paid.', 'fix_ar': 'حدّ المبلغ بما دُفع.', 'test': 'a refund above the payment is refused',
            **changes}


class Assistant:
    """A fake assistant: the hunt's answer, then the critic's verdicts (an exception is raised); it records what it was asked."""

    def __init__(self, flaws, verdicts):
        self.answers, self.asked, self.config = [{'flaws': flaws, 'reviewed': ['POST /orders/:id/refund']}, {'verdicts': verdicts}], [], {}

    def complete(self, messages, small=False, stage=None, reads=None, deep=False):
        self.asked.append({'stage': stage, 'deep': deep, 'reads': reads, 'system': messages[0]['content'],
                           'brief': json.loads(messages[1]['content'])})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception): raise answer
        return {'result': answer}, {}


class LogicFlawsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project, self.out = Path(self.tmp.name, 'app'), Path(self.tmp.name, 'report')
        self.project.mkdir(); (self.out / 'facts').mkdir(parents=True)
        (self.project / 'server.js').write_text(ROUTE)
        (self.out / 'layers.json').write_text(json.dumps({'endpoints': [
            {'method': 'GET', 'route': '/health', 'authentication': None, 'writes': False},
            {'method': 'POST', 'route': '/orders/:id/refund', 'path': 'server.js', 'line': 1, 'authentication': 'req.user', 'writes': True, 'by_id': True},
            {'method': 'POST', 'route': '/notes', 'authentication': None, 'writes': True, 'data': 'x' * 5000}]}))

    def tearDown(self): self.tmp.cleanup()

    def _claims(self, target=None):
        return [c for c in from_facts(read_available(self.out), target=target or self.project) if (c.get('render') or {}).get('key') == 'logic_flaw']

    def test_a_grounded_flaw_the_critic_holds_is_kept_and_read_like_every_fact_set(self):
        assistant = Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'nothing caps the amount'}])
        summary = record.run(self.project, self.out, assistant)
        self.assertEqual((summary['flaws'], summary['holds']), (1, 1))
        kept = json.loads((self.out / record.RECORD).read_text())['flaws'][0]
        self.assertIn('refund(order, req.body.amount)', kept['excerpt'])
        self.assertEqual([a['stage'] for a in assistant.asked], ['logic_flaws', 'logic_flaws_critic'])
        self.assertTrue(all(a['deep'] and a['reads'] == str(self.project.resolve()) for a in assistant.asked))
        index = json.loads((self.out / 'facts/index.json').read_text())
        self.assertIn('logic_flaws', [row['set'] for row in index['sets']])
        sets = read_available(self.out)                     # how claims, cards and probes read a report's facts
        claim = self._claims()[0]
        self.assertEqual((claim['claim_type'], claim['confidence']), ('risk', 'LIKELY'))
        self.assertEqual({k: claim['render']['params'][k] for k in ('category', 'severity')}, {'category': 'security', 'severity': 'high'})
        self.assertEqual(run_graph_query(claim['probe_spec']['specification'], sets)[0], 'CONFIRMED')

    def test_an_unsure_flaw_is_medium_at_most(self):
        record.run(self.project, self.out, Assistant([flaw()], [{'number': 1, 'verdict': 'unsure', 'why': 'cannot tell'}]))
        claim = self._claims()[0]
        self.assertEqual((claim['confidence'], claim['render']['params']['severity']), ('HYPOTHESIS', 'medium'))
        self.assertEqual(claim['render']['params']['category'], 'reliability')

    def test_a_hunt_of_other_code_makes_no_card(self):
        record.run(self.project, self.out, Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'nothing caps it'}]))
        (self.project / 'server.js').write_text(ROUTE.replace('refund(order, req.body.amount)', 'refund(order, order.paid)'))
        self.assertEqual(self._claims(), [])

    def test_a_recheck_closes_the_card_once_the_cited_line_is_gone(self):
        record.run(self.project, self.out, Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'nothing caps it'}]))
        spec = self._claims()[0]['probe_spec']
        self.assertEqual(recheck(self.project, spec)[0], 'INCONCLUSIVE')     # unchanged code: only a new hunt can tell
        (self.project / 'server.js').write_text(ROUTE.replace('refund(order, req.body.amount)', 'refund(order, Math.min(req.body.amount, order.paid))'))
        self.assertEqual(recheck(self.project, spec)[0], 'REFUTED')

    def test_the_prompts_hold_the_project_text_as_untrusted_data(self):
        assistant = Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'x'}])
        record.run(self.project, self.out, assistant)
        self.assertTrue(all(CLAUSE in a['system'] for a in assistant.asked))
        self.assertEqual(assistant.asked[0]['brief']['trust'], UNTRUSTED)
        self.assertTrue(all(c['excerpt']['trust'] == UNTRUSTED for c in assistant.asked[1]['brief']['candidates']))

    def test_open_writes_are_read_first_and_each_row_is_bounded(self):
        endpoints = hunt.brief(self.out)['endpoints']
        self.assertEqual([row.get('route') for row in endpoints[1:]], ['/health', '/orders/:id/refund'])
        self.assertLessEqual(len(json.dumps(endpoints[0], ensure_ascii=False)), 2 * hunt.LIMIT['row'])

    def test_an_answer_that_is_no_object_is_a_plain_error(self):
        assistant = Assistant([], [])
        assistant.answers[0] = ['not', 'an', 'object']
        with self.assertRaisesRegex(ValueError, 'no JSON object'): record.run(self.project, self.out, assistant)

    def test_a_failing_critic_keeps_the_candidates_unsure(self):
        assistant = Assistant([flaw()], [])
        assistant.answers[1] = ValueError('Model adapter exited unsuccessfully')
        summary = record.run(self.project, self.out, assistant)
        self.assertEqual((summary['flaws'], summary['holds']), (1, 0))
        self.assertIn('did not finish', json.loads((self.out / record.RECORD).read_text())['critic'])

    def test_a_hunt_past_its_time_is_ended(self):
        class Slow(Assistant):
            def complete(self, *args, **kwargs):
                while True: check_cancelled()
        with self.assertRaises(hunt.Unfinished): record.run(self.project, self.out, Slow([], []), minutes=0.001)

    def test_a_flaw_without_a_real_place_or_refuted_is_set_aside_with_its_reason(self):
        (self.project / 'README.md').write_text('one\ntwo\nthree\n')
        (self.project / 'pay.js').write_text('a\nb\nc\n')
        layer = make('boundary_finding', 'boundaries', '1', 'x', {'path': 'pay.js', 'start_line': 2}, {'rule': 'unowned-row'})
        write_set(self.out, 'boundaries', 'boundaries', '1', [], {'facts': [layer], 'input_sha': 'x'})
        flaws = [flaw(path='../outside.js'), flaw(line=99), flaw(line=True), flaw(path='a\x00b.js'), flaw(path='README.md', line=1),
                 flaw(path='pay.js', line=2), flaw(severity='dire'), flaw(fix=''), flaw(), flaw(),
                 flaw(title='A second refund of the same order is paid', **{'class': 'skipped-step'})]
        assistant = Assistant(flaws, [{'number': 1, 'verdict': 'refuted', 'why': 'refund() caps it at line 9'}])
        record.run(self.project, self.out, assistant)
        result = json.loads((self.out / record.RECORD).read_text())
        self.assertEqual([f['title'] for f in result['flaws']], ['A second refund of the same order is paid'])
        self.assertEqual(result['flaws'][0]['verdict'], 'unsure')          # no verdict given: unsure, never held
        reasons = ' | '.join(d['why'] for d in result['dropped'])
        for said in ('no file ../outside.js', 'has no line 99', 'has no line True', 'cannot be read', 'README.md is not source',
                     'a layer finding already says pay.js:2', 'class or severity', 'no fix', 'the same flaw twice', 'refuted: refund() caps'):
            self.assertIn(said, reasons)
        self.assertEqual(len(assistant.asked[1]['brief']['candidates']), 2)   # the critic reads only grounded candidates


class LogicFlawsCommandTest(unittest.TestCase):
    """`eaos logic-flaws`: it asks before spending, counts its use with the check's, and runs the check again from its
    claims so the cards and their triage include what it found."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project, self.out = Path(self.tmp.name, 'app'), Path(self.tmp.name, 'report')
        self.project.mkdir(); (self.out / 'facts').mkdir(parents=True)
        (self.project / 'server.js').write_text(ROUTE)
        (self.out / 'layers.json').write_text(json.dumps({'endpoints': []}))
        (self.out / 'run-manifest.json').write_text(json.dumps({'options': {}, 'stages': {},
                                                                 'source_fingerprint': inventory(self.project)['fingerprint']}))
        self.assistant = Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'nothing caps it'}])

    def tearDown(self): self.tmp.cleanup()

    def _run(self, *words):
        with mock.patch('eaos.interfaces.deep_checks._assistant', return_value=self.assistant), \
                mock.patch('eaos.pipeline.run.again') as again, mock.patch('sys.stdin', io.StringIO('')), redirect_stdout(io.StringIO()) as said, redirect_stderr(io.StringIO()):
            code = cli.main(['logic-flaws', str(self.project), '--out', str(self.out), *words])
        return code, again, said.getvalue()

    def test_it_asks_before_spending(self):
        code, again, said = self._run()
        self.assertEqual((code, self.assistant.asked, again.called), (1, [], False))
        self.assertIn('--yes', said)

    def test_it_runs_the_check_again_from_the_claims(self):
        code, again, said = self._run('--yes')
        self.assertEqual(code, 0)
        again.assert_called_once_with(str(self.project), self.out, 'claims')
        self.assertEqual(self.assistant.config['usage'], str(self.out / 'usage.jsonl'))

    def test_it_refuses_a_report_of_other_code(self):
        (self.project / 'server.js').write_text('changed\n')
        code, again, _ = self._run('--yes')
        self.assertEqual((code, self.assistant.asked), (2, []))


if __name__ == '__main__':
    unittest.main()
