"""A card stands on its own file and its own evidence (NS30.T1).

On EAOS itself, 129 of the 130 "two independent engines" cards rested on one project-wide finding: a literal
repeated across 17 files was counted as a second engine on each of them, and the card listed all 17 files. A group
finding spread over more than three files is evidence about the group, so it neither joins a file's cluster nor
lends it a second engine; and a claim about one kind cites only the evidence of that kind.
"""
import unittest

from eaos.analysis.claims import ledger as claims, correlate
from eaos.analysis.planning.ranking import claim_paths


def finding(fact_id, engine, kind, subject_kind, paths):
    return {'id': fact_id, 'kind': 'engine_finding', 'extractor': 'external',
            'location': {'path': paths[0], 'line': 1},
            'value': {'engine': engine, 'kind': kind, 'subject_kind': subject_kind, 'rule': kind, 'message': kind,
                      'measurements': [], 'sites': [{'path': path, 'line': 1} for path in paths]}}


def sets(*facts):
    observed = {'status': 'observed', 'granularity': 'file'}
    evaluated = {engine: {kind: observed for kind in ('complexity', 'literal_duplication')}
                 for engine in ('codegraph', 'reforge', 'jscpd')}
    return {'external': {'facts': list(facts), 'summary': {'evaluated_kinds': evaluated}}}


WIDE = [f'src/m{index}.py' for index in range(17)]


class WideGroupFindings(unittest.TestCase):
    def test_a_wide_group_finding_is_its_own_cluster_and_lends_no_second_engine_to_a_file(self):
        built = correlate.clusters(sets(
            finding('F-1', 'jscpd', 'literal_duplication', 'file', ['src/m0.py']),
            finding('F-2', 'reforge', 'literal_duplication', 'group', WIDE)))
        file_cluster = next(c for c in built if c['place'] == 'src/m0.py')
        self.assertEqual(file_cluster['engines'], ['jscpd'])
        self.assertEqual(file_cluster['corroboration']['literal_duplication']['verdict'], correlate.SINGLE)
        self.assertNotIn('F-2', file_cluster['fact_ids'])
        self.assertIn(('group:F-2', 'group', ['F-2']), [(c['place'], c['scope'], c['fact_ids']) for c in built])
        # A small group still corroborates the files it names.
        built = correlate.clusters(sets(
            finding('F-1', 'jscpd', 'literal_duplication', 'file', ['src/a.py', 'src/b.py']),
            finding('F-2', 'reforge', 'literal_duplication', 'group', ['src/a.py', 'src/b.py'])))
        cluster = next(c for c in built if c['place'] == 'src/a.py')
        self.assertEqual(cluster['corroboration']['literal_duplication']['verdict'], correlate.CORROBORATED)


class EvidenceOfItsKind(unittest.TestCase):
    def test_a_claim_cites_only_its_kind_and_its_own_file_leads_its_paths(self):
        over = finding('F-2', 'reforge', 'complexity', 'symbol', ['src/m0.py'])
        over['value']['measurements'] = [{'name': 'function.complexity', 'value': 31, 'threshold': 15}]
        made = claims.from_engines(sets(finding('F-1', 'codegraph', 'complexity', 'symbol', ['src/m0.py']), over,
                                        finding('F-3', 'jscpd', 'literal_duplication', 'file', ['src/m0.py', 'src/other.py'])))
        complexity = next(c for c in made if c['render']['params']['kind'] == 'complexity')
        # Self-audit: two engines measuring complexity 1 at store.py were "corroborated"; no value over a threshold, no card.
        under = dict(over, value={**over['value'], 'measurements': [{'name': 'function.complexity', 'value': 1, 'threshold': 15}]})
        self.assertEqual([c for c in claims.from_engines(sets(finding('F-1', 'codegraph', 'complexity', 'symbol', ['src/m0.py']), under))
                          if c['render']['params']['kind'] == 'complexity'], [])
        self.assertEqual(complexity['fact_ids'], ['F-1', 'F-2'])
        index = {'F-1': 'src/m0.py', 'F-3': 'src/a_first.py', 'F-3:paths': ['src/a_first.py', 'src/m0.py']}
        claim = {'fact_ids': ['F-1', 'F-3'], 'render': {'params': {'place': 'src/m0.py'}}}
        self.assertEqual(claim_paths(claim, index), ['src/m0.py', 'src/a_first.py'])
        # A cycle found at ChatMessage.tsx whose sites run through AIChatPage.tsx: the card on AIChatPage.tsx shows it.
        index = {'F-1': 'src/ChatMessage.tsx', 'F-2': 'src/MessageList.tsx'}
        claim = {'fact_ids': ['F-1', 'F-2'], 'render': {'params': {'place': 'src/AIChatPage.tsx'}}}
        self.assertEqual(claim_paths(claim, index)[0], 'src/AIChatPage.tsx')
        group = {'fact_ids': ['F-1'], 'render': {'params': {'place': 'group:F-1'}}}
        self.assertEqual(claim_paths(group, index), ['src/ChatMessage.tsx'])
