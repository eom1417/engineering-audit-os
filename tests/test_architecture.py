import ast
import copy
import json
from pathlib import Path
import unittest
from eaos import architecture as arch
from eaos import cli
from test_cli import AuditTests

class GraphTests(unittest.TestCase):
    def setUp(self):
        self.model=json.loads((Path(__file__).resolve().parents[1]/'examples/architecture/model.json').read_text())
    def test_architecture_module_has_no_io_or_cli_dependency(self):
        source=(Path(__file__).resolve().parents[1]/'eaos/architecture.py').read_text()
        imports={n.module for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)}
        self.assertEqual(imports,{'collections','pathlib'})
        self.assertFalse(any(isinstance(n,ast.Import) for n in ast.walk(ast.parse(source))))

    def test_direction_of_change_impact(self):
        result=arch.impact(self.model,'store')
        self.assertEqual(result['potential_dependents'],['entry','service'])
        self.assertEqual(result['distances'],{'store':0,'service':1,'entry':2})
    def test_depth_limit_is_explicit(self):
        result=arch.impact(self.model,'store',1)
        self.assertEqual(result['potential_dependents'],['service'])
        self.assertEqual(result['unexpanded_frontier'],['entry'])
    def test_hypothesis_excluded_from_proven_walk(self):
        self.model['edges'][0]['status']='HYPOTHESIS'
        result=arch.impact(self.model,'store')
        self.assertEqual(result['potential_dependents'],['service'])
        self.assertEqual(result['hypothesis_edges'],['EDGE-1'])
    def test_cycles_are_typed(self):
        self.model['edges'].append(dict(id='BACK',**{'from':'store','to':'entry'},relation='imports',status='CONFIRMED',reason='fixture',evidence_ids=['E-1']))
        self.assertEqual(arch.summary(self.model)['static_dependency_cycles'],[])
        self.model['edges'][1]['relation']='imports'
        self.assertEqual(arch.summary(self.model)['static_dependency_cycles'],[['entry','service','store']])
    def test_large_chain_no_recursion_failure(self):
        graph={str(i):{str(i+1)} for i in range(5000)};graph['5000']=set()
        self.assertEqual(arch.cycles(graph),[])
    def test_self_loop(self):
        self.assertEqual(arch.cycles({'a':{'a'}}),[['a']])
    def test_declared_policy_only(self):
        self.assertEqual(arch.summary(self.model)['declared_policy_violations'],[])
        self.model['dependency_policies']=[dict(id='P-1',**{'from':'entry','to':'service'},relation='uses_contract',rule='forbid',reason='fixture',evidence_ids=['E-1'])]
        self.assertEqual(arch.summary(self.model)['declared_policy_violations'][0]['edge_id'],'EDGE-1')
    def test_semantic_consumer_without_edge_in_context(self):
        self.model['edges']=[]
        context=arch.context_data(self.model,'service',1)
        self.assertIn('entry',[n['id'] for n in context['nodes']])
    def test_dangling_edge_rejected(self):
        self.model['edges'][0]['to']='missing'
        errors,gaps=arch.validate_model(self.model,{'E-1':{'revision':'SYNTHETIC_FIXTURE'}},'SYNTHETIC_FIXTURE',{'package.json','app.py','store.py'})
        self.assertTrue(any('unknown node' in e for e in errors))
    def test_tested_requires_test_evidence(self):
        self.model['change_scenarios'][0]['status']='TESTED'
        errors,gaps=arch.validate_model(self.model,{'E-1':{'revision':'SYNTHETIC_FIXTURE','kind':'source'}},'SYNTHETIC_FIXTURE',{'package.json','app.py','store.py'})
        self.assertTrue(any('requires test evidence' in e for e in errors))
    def test_model_schema(self):
        schema=cli.read(Path(__file__).resolve().parents[1]/'schemas/architecture.schema.json')
        self.assertEqual(cli.schema_errors(self.model,schema),[])

class ArchitectureCommands(AuditTests):
    # Reuse workspace setup only, not inherited test methods (filtered below).
    def test_architecture_profile_default(self):
        state=cli.read(self.run/'run.json')
        self.assertEqual(state['profile'],'architecture')
        self.assertEqual(next(d['applicability'] for d in state['module_decisions'] if d['module_id']=='16'),'OUT_OF_SCOPE')
    def test_model_gate_prevents_checkbox_completion(self):
        self.complete_fixture();cli.write(self.run/'architecture.json',arch.empty_model(cli.read(self.run/'run.json')['revision']))
        self.assertIn('False completion claim',cli.check(self.run)['errors'])
    def test_graph_impact_context_commands(self):
        self.complete_fixture()
        self.assertEqual(self.call('graph',str(self.run)),0)
        self.assertEqual(self.call('impact',str(self.run),'--node','store'),0)
        self.assertEqual(self.call('context',str(self.run),'--node','service','--budget-chars','30000'),0)
        packet=next((self.run/'packets').glob('architecture-*.md'))
        self.assertIn('CONTRACT-1',packet.read_text());self.assertIn('RULE-1',packet.read_text())
    def test_context_budget_and_no_silent_drop(self):
        self.complete_fixture()
        self.assertEqual(self.call('context',str(self.run),'--node','service','--budget-chars','1'),2)
        self.assertFalse((self.run/'packets').exists())
    def test_stale_model_rejected(self):
        self.complete_fixture();self.update('architecture.json',lambda m:m.update(revision='old'))
        self.assertEqual(self.call('graph',str(self.run)),2)
    def test_missing_change_scenarios_blocks_completion(self):
        self.complete_fixture();self.update('architecture.json',lambda m:m.update(change_scenarios=[]))
        self.assertIn('False completion claim',cli.check(self.run)['errors'])

# Avoid rerunning inherited base tests: preserve helpers via composition of methods.
for name in list(AuditTests.__dict__):
    if name.startswith('test_') and name not in ArchitectureCommands.__dict__:setattr(ArchitectureCommands,name,None)
# Prevent imported TestCase class from being collected again in this module.
del AuditTests
if __name__=='__main__':unittest.main()
