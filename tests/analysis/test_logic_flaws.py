"""The logic-flaw hunt (M9.2): only a flaw pointing at a real line and not refuted by the second reading is kept, and
the kept ones become claims of the business rules' boundary."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.claims.ledger import from_facts
from eaos.analysis.claims.probe_queries import run_graph_query
from eaos.analysis.logic_flaws import hunt, record
from eaos.facts.run import read_available

ROUTE = "app.post('/orders/:id/refund', (req, res) => {\n  const order = find(req.params.id)\n  refund(order, req.body.amount)\n  res.json(order)\n})\n"


def flaw(**changes):
    return {'title': 'A refund takes any amount, even more than was paid', 'title_ar': 'الاسترداد يقبل أي مبلغ',
            'class': 'quantity', 'severity': 'high', 'principal': 'a signed-in buyer', 'invariant': 'a refund never exceeds the payment',
            'path': 'server.js', 'line': 3, 'steps': ['POST /orders/1/refund {"amount": 1000}'], 'impact': 'money paid out twice',
            'fix': 'Cap the amount at what was paid.', 'fix_ar': 'حدّ المبلغ بما دُفع.', 'test': 'a refund above the payment is refused',
            **changes}


class Assistant:
    """A fake assistant: the hunt's answer, then the critic's verdicts; it records what it was asked."""

    def __init__(self, flaws, verdicts):
        self.answers, self.asked = [{'flaws': flaws, 'reviewed': ['POST /orders/:id/refund']}, {'verdicts': verdicts}], []

    def complete(self, messages, small=False, stage=None, reads=None, deep=False):
        self.asked.append({'stage': stage, 'deep': deep, 'reads': reads, 'brief': json.loads(messages[1]['content'])})
        return {'result': self.answers.pop(0)}, {}


class LogicFlawsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project, self.out = Path(self.tmp.name, 'app'), Path(self.tmp.name, 'report')
        self.project.mkdir(); (self.out / 'facts').mkdir(parents=True)
        (self.project / 'server.js').write_text(ROUTE)
        (self.out / 'layers.json').write_text(json.dumps({'endpoints': [
            {'method': 'GET', 'route': '/health', 'authentication': None, 'writes': False},
            {'method': 'POST', 'route': '/orders/:id/refund', 'path': 'server.js', 'line': 1, 'authentication': 'req.user', 'writes': True, 'by_id': True},
            {'method': 'POST', 'route': '/notes', 'authentication': None, 'writes': True}]}))

    def tearDown(self): self.tmp.cleanup()

    def test_a_grounded_flaw_the_critic_holds_is_kept_with_its_place_and_becomes_a_claim(self):
        assistant = Assistant([flaw()], [{'number': 1, 'verdict': 'holds', 'why': 'nothing caps the amount'}])
        summary = record.run(self.project, self.out, assistant)
        self.assertEqual((summary['flaws'], summary['holds']), (1, 1))
        kept = json.loads((self.out / record.RECORD).read_text())['flaws'][0]
        self.assertIn('refund(order, req.body.amount)', kept['excerpt'])
        self.assertEqual([a['stage'] for a in assistant.asked], ['logic_flaws', 'logic_flaws_critic'])
        self.assertTrue(all(a['deep'] and a['reads'] == str(self.project.resolve()) for a in assistant.asked))
        sets = read_available(self.out)                     # how claims, cards and probes read a report's facts
        self.assertIn('logic_flaws', sets)
        claim = [c for c in from_facts(sets, target=self.project) if c['statement'] == flaw()['title']][0]
        self.assertEqual((claim['claim_type'], claim['confidence']), ('risk', 'LIKELY'))
        self.assertEqual(run_graph_query(claim['probe_spec']['specification'], sets)[0], 'CONFIRMED')

    def test_open_writes_are_read_first(self):
        routes = [row['route'] for row in hunt.brief(self.out)['endpoints']]
        self.assertEqual(routes, ['/notes', '/health', '/orders/:id/refund'])

    def test_a_flaw_without_a_real_place_or_refuted_is_set_aside_with_its_reason(self):
        flaws = [flaw(path='../outside.js'), flaw(line=99), flaw(severity='dire'), flaw(fix=''), flaw(), flaw(),
                 flaw(title='A second refund of the same order is paid', **{'class': 'skipped-step'})]
        assistant = Assistant(flaws, [{'number': 1, 'verdict': 'refuted', 'why': 'refund() caps it at line 9'}])
        result = record.check(self.project, self.out, assistant)
        self.assertEqual([f['title'] for f in result['flaws']], ['A second refund of the same order is paid'])
        self.assertEqual(result['flaws'][0]['verdict'], 'unsure')          # no verdict given: unsure, never held
        reasons = ' | '.join(d['why'] for d in result['dropped'])
        for said in ('no file ../outside.js', 'has no line 99', 'class or severity', 'no fix', 'the same flaw twice', 'refuted: refund() caps'):
            self.assertIn(said, reasons)
        self.assertEqual(len(assistant.asked[1]['brief']['candidates']), 2)   # the critic reads only grounded candidates


if __name__ == '__main__':
    unittest.main()
