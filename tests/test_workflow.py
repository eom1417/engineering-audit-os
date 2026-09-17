"""Contract/integration tests; fixtures are not independent production audit calibration."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from eaos import cli, discovery, workflow
from test_cli import AuditTests as Helpers

class WorkflowTests(unittest.TestCase):
    setUp=Helpers.setUp
    call=Helpers.call
    update=Helpers.update
    complete_fixture=Helpers.complete_fixture
    finding=Helpers.finding

    def start(self):
        workflow.initialize(self.run);discovery.scan(self.run)

    def complete(self):
        self.complete_fixture();self.start()
        state=cli.read(self.run/'run.json');state['scope']['approved_exclusions']=['.env'];cli.write(self.run/'run.json',state)
        rows=[]
        for f in cli.read(self.run/'inventory.json')['files']:
            refs=[] if f['path']=='.env' else [discovery.capture(self.run,f['path'],1,1,'Synthetic source range fixture, not semantic audit')]
            rows.append({'path':f['path'],'revision':state['revision'],'status':'excluded' if f['path']=='.env' else 'reviewed','rationale':'Synthetic contract exercise, no substantive review','evidence_ids':refs})
        cli.write(self.run/'surface-review.json',rows)

    def add_finding(self):
        f=self.finding()
        for k,v in list(f.items()):
            if v=='REPLACE':f[k]='Synthetic fixture only'
        f.update(claim_status='CONFIRMED',confidence='HIGH',evidence_ids=['E-1'],affected_files=['app.py'],required_tests=['Test the relevant rule on invalid input'])
        cli.write(self.run/'findings.json',[f]);return f

    def task(self,tid='T-1'):
        t={k:'Synthetic acceptance fixture only' for k in workflow.TEXT_FIELDS}
        t.update({k:['fixture'] for k in workflow.LIST_FIELDS})
        model=cli.read(self.run/'architecture.json')
        t.update(id=tid,kind='remediate',status='planned',priority='P2',finding_ids=['F-001'],evidence_ids=['E-1'],node_ids=['service'],scenario_ids=[model['change_scenarios'][0]['id']],files=['app.py'],depends_on=[],required_gate_ids=['G-1'])
        return t

    def prepare_plan(self):
        self.complete();self.add_finding();state=cli.read(self.run/'run.json')
        cli.write(self.run/'gates.json',[{'id':'G-1','status':'not_run','revision':state['revision'],'rationale':'Predeclared remediation regression test','evidence_ids':[],'required_for_audit':False}])
        doc=cli.read(self.run/'roadmap.json');doc['tasks']=[self.task()];cli.write(self.run/'roadmap.json',doc)

    def test_single_entrypoint_read_only_and_no_script_execution(self):
        out=self.base/'single-entry'
        before={p.name:p.read_bytes() for p in self.target.iterdir()}
        self.assertEqual(self.call('audit',str(self.target),'--out',str(out)),0)
        self.assertEqual(workflow.status(out)['stage'],'SCOPE')
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.target.iterdir()})
        self.assertEqual(cli.read(out/'architecture.json')['nodes'],[])
        self.assertEqual(cli.read(out/'findings.json'),[])

    def test_inventory_cannot_advance_to_ready(self):
        self.start();self.assertEqual(workflow.status(self.run)['stage'],'SCOPE')
        self.update('run.json',lambda s:s.update(scope_confirmed=True,inventory_reviewed=True,scope={'environments':['local'],'approved_exclusions':[]}))
        self.assertEqual(workflow.status(self.run)['stage'],'RECONSTRUCT')

    def test_unaccounted_file_blocks_complete_audit(self):
        self.complete();self.update('surface-review.json',lambda rows:rows.pop())
        self.assertEqual(workflow.status(self.run)['stage'],'REVIEW_SURFACES')
        self.assertEqual(self.call('validate',str(self.run),'--require-complete'),2)

    def test_unrelated_evidence_cannot_mark_file_reviewed(self):
        self.complete();self.update('surface-review.json',lambda rows:[r.update(evidence_ids=['E-1']) for r in rows if r['status']=='reviewed'])
        self.assertTrue(any('lacks evidence at its path' in e for e in workflow.surface_check(self.run,cli.read(self.run/'run.json'))[0]))

    def test_exclusion_must_be_in_declared_scope(self):
        self.complete();self.update('run.json',lambda s:s['scope'].update(approved_exclusions=[]))
        self.assertTrue(any('exclusion' in g for g in workflow.surface_check(self.run,cli.read(self.run/'run.json'))[1]))

    def test_end_to_end_ready_is_not_remediation_or_production(self):
        self.prepare_plan()
        result=workflow.status(self.run)
        self.assertEqual(result['stage'],'AUDIT_AND_PLAN_READY')
        self.assertEqual(result['production_readiness'],'NOT_ASSESSED')
        self.assertEqual(result['remediation_completion'],'NOT_REQUESTED')
        self.assertEqual(result['task_order'],['T-1'])
        self.assertEqual(self.call('report',str(self.run)),0)
        report=(self.run/'report.md').read_text()
        for section in ['Architecture and change scenarios','Findings','Ordered development work','Control coverage','Verification gates','Evidence','Decisions']:self.assertIn(section,report)

    def test_missing_invariant_prevents_ready(self):
        self.prepare_plan();self.update('roadmap.json',lambda d:d['tasks'][0].update(invariant='TODO'))
        self.assertEqual(workflow.status(self.run)['stage'],'DESIGN_PLAN')
        self.assertEqual(self.call('roadmap',str(self.run)),2)

    def test_missing_finding_disposition_prevents_ready(self):
        self.complete();self.add_finding()
        self.assertEqual(workflow.status(self.run)['stage'],'DESIGN_PLAN')

    def test_seed_is_draft_and_preserves_existing_plan(self):
        self.complete();self.add_finding()
        self.assertEqual(self.call('roadmap',str(self.run),'--seed'),2)
        doc=(self.run/'roadmap.json').read_bytes()
        self.assertEqual(self.call('roadmap',str(self.run),'--seed'),2)
        self.assertEqual(doc,(self.run/'roadmap.json').read_bytes())

    def test_task_dependency_cycle_rejected(self):
        self.prepare_plan();doc=cli.read(self.run/'roadmap.json')
        t=self.task('T-2');t['depends_on']=['T-1'];doc['tasks'][0]['depends_on']=['T-2'];doc['tasks'].append(t);cli.write(self.run/'roadmap.json',doc)
        self.assertIn('Cyclic task dependencies',workflow.roadmap_check(self.run,cli.read(self.run/'run.json'))['errors'])

    def test_dependencies_precede_priority(self):
        self.prepare_plan();doc=cli.read(self.run/'roadmap.json')
        t=self.task('T-2');t.update(depends_on=['T-1'],priority='P0');doc['tasks'].append(t);cli.write(self.run/'roadmap.json',doc)
        self.assertEqual(workflow.roadmap_check(self.run,cli.read(self.run/'run.json'))['order'],['T-1','T-2'])

    def test_hypothesis_cannot_be_a_remediation_task(self):
        self.prepare_plan();self.update('findings.json',lambda f:f[0].update(claim_status='POSSIBLE'))
        self.assertTrue(any('requires confirmed' in e for e in workflow.roadmap_check(self.run,cli.read(self.run/'run.json'))['errors']))

    def test_verified_task_requires_executed_gates(self):
        self.prepare_plan();self.update('roadmap.json',lambda d:d['tasks'][0].update(status='verified'))
        errors=workflow.roadmap_check(self.run,cli.read(self.run/'run.json'))['errors']
        self.assertTrue(any('nonpassing' in e for e in errors));self.assertTrue(any('verified_closed' in e for e in errors))

    def test_source_mutation_invalidates_workflow_and_plan(self):
        self.prepare_plan();(self.target/'app.py').write_text('print("changed")\n')
        self.assertEqual(workflow.status(self.run)['stage'],'BLOCKED_SNAPSHOT')
        self.assertEqual(self.call('roadmap',str(self.run)),2)

    def test_capture_is_reproducible_and_deduplicated(self):
        eid=discovery.capture(self.run,'app.py',1,1,'Print fixture text')
        self.assertEqual(eid,discovery.capture(self.run,'app.py',1,1,'Print fixture text'))
        self.assertEqual(len(cli.read(self.run/'evidence.json')),1)
        self.assertEqual(cli.check(self.run)['errors'],[])
        self.update('evidence.json',lambda rows:rows[0]['source_ref'].update(range_sha256='fake'))
        self.assertTrue(any('Invalid captured' in e for e in cli.check(self.run)['errors']))

    def test_capture_rejects_sensitive_and_invalid_ranges(self):
        for rel,start,end in [('.env',1,1),('app.py',2,1),('../outside',1,1),('app.py',1,200)]:
            with self.assertRaises(ValueError):discovery.capture(self.run,rel,start,end,'observation')

    def test_report_partial_is_explicit(self):
        self.start();self.assertEqual(self.call('report',str(self.run)),2)
        self.assertIn('not evidence of a clean system',(self.run/'report.md').read_text())

class DiscoveryTests(unittest.TestCase):
    def test_python_ast_line_and_imports(self):
        r=discovery.observe_text('service.py','from .store import save\n\ndef create(x):\n    return save(x)\n')
        self.assertEqual(r['imports'][0],{'module':'store','names':['save'],'level':1,'line':1})
        self.assertEqual(r['symbols'][0]['line'],3)

    def test_typescript_hints_never_become_confirmed_edges(self):
        r=discovery.observe_text('route.ts',"// from './comment-not-real'\nimport { save } from './store';\n")
        self.assertEqual({i['status'] for i in r['imports']},{'HYPOTHESIS'})
        self.assertIn('false positives',r['limitations'][0])

    def test_manifest_does_not_copy_commands_or_credentials(self):
        r=discovery.observe_text('package.json','{"scripts":{"test":"echo PRIVATE_VALUE"},"dependencies":{"x":"https://user:password@private"}}')
        self.assertEqual(r['script_names'],['test']);self.assertNotIn('PRIVATE_VALUE',str(r));self.assertNotIn('password',str(r))

    def test_unsupported_language_remains_visible(self):
        r=discovery.observe_text('main.go','package main\n')
        self.assertEqual(r['parser'],'inventory_only')

    def test_mixed_project_parse_failure_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);target=base/'product';target.mkdir();run=base/'run'
            for name,content in {'bad.py':'def broken(', 'main.go':'package main', '.env':'SECRET=NEVER_COPY','package.json':'{}','route.ts':"import './x';"}.items():(target/name).write_text(content)
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(cli.main(['audit',str(target),'--out',str(run)]),0)
            rows={r['path']:r for r in cli.read(run/'discovery.json')['files']}
            self.assertEqual(rows['bad.py']['parse_status'],'BLOCKED')
            self.assertEqual(rows['main.go']['parse_status'],'UNSUPPORTED')
            self.assertEqual(rows['.env']['capture'],'sensitive_metadata_only')
            self.assertNotIn('NEVER_COPY',(run/'discovery.json').read_text())
            self.assertNotEqual(workflow.status(run)['stage'],'AUDIT_AND_PLAN_READY')

# Imported helper TestCase must not be collected twice.
del Helpers
if __name__=='__main__':unittest.main()
