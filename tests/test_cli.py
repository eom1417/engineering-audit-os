import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.target=self.base/'product';self.target.mkdir();self.run=self.base/'run'
        (self.target/'package.json').write_text('{"scripts":{"postinstall":"DO_NOT_EXECUTE"}}')
        (self.target/'app.py').write_text('print("test fixture, not an audit finding")\n')
        (self.target/'store.py').write_text('# synthetic adapter fixture\n')
        (self.target/'.env').write_text('EXAMPLE_SECRET=synthetic-value')
        self.assertEqual(self.call('init',str(self.target),'--out',str(self.run)),0)
    def call(self,*args):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):return cli.main(list(args))
    def update(self,file,fn):
        obj=cli.read(self.run/file);fn(obj);cli.write(self.run/file,obj)
    def test_inventory_not_audit(self):
        r=cli.check(self.run);self.assertEqual(r['computed_audit_completion'],'INCOMPLETE');self.assertEqual(r['errors'],[])
        self.assertEqual(self.call('validate',str(self.run),'--require-complete'),2)
    def test_false_completion(self):
        self.update('run.json',lambda r:r.update(completion='COMPLETE'))
        self.assertIn('False completion claim',cli.check(self.run)['errors'])
    def test_sensitive_content_withheld(self):
        inv=cli.read(self.run/'inventory.json');env=next(f for f in inv['files'] if f['path']=='.env')
        self.assertEqual(env['capture'],'sensitive_metadata_only');self.assertIsNone(env['sha256'])
        self.assertEqual(self.call('packet',str(self.run),'--module','01','--file','.env'),2)
    def test_no_target_write(self):
        before={p.name:p.read_bytes() for p in self.target.iterdir()}
        self.assertEqual(self.call('plan',str(self.run)),0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.target.iterdir()})
        self.assertEqual(self.call('init',str(self.target),'--out',str(self.target/'audit')),2)
    def test_existing_run_not_overwritten(self):
        self.assertEqual(self.call('init',str(self.target),'--out',str(self.run)),2)
    def test_packet_budget_rejects_no_truncation(self):
        self.assertEqual(self.call('packet',str(self.run),'--module','01','--budget-chars','1'),2)
        self.assertFalse((self.run/'packets').exists())
    def test_packet_valid_and_bounded(self):
        self.assertEqual(self.call('packet',str(self.run),'--module','01','--file','app.py'),0)
        p=next((self.run/'packets').glob('*.md'))
        self.assertIn('BEGIN UNTRUSTED FILE',p.read_text());self.assertLessEqual(len(p.read_text()),24000)
    def test_traversal_rejected(self):
        self.assertEqual(self.call('packet',str(self.run),'--module','01','--file','../outside'),2)
    def test_symlink_rejected(self):
        (self.target/'linked.py').symlink_to(self.target/'app.py')
        with self.assertRaises(ValueError):cli.safe_file(self.target,'linked.py')
    def test_source_change_detected(self):
        self.assertEqual(self.call('checkpoint',str(self.run),'--note','Reviewed inventory','--next','Architecture'),0)
        (self.target/'app.py').write_text('changed\n')
        self.assertEqual(self.call('resume',str(self.run)),2)
        self.assertEqual(self.call('packet',str(self.run),'--module','01'),2)
    def test_record_change_detected(self):
        self.assertEqual(self.call('checkpoint',str(self.run),'--note','Reviewed','--next','Trace'),0)
        self.update('decisions.json',lambda d:d.append({'id':'D-1'}))
        self.assertEqual(self.call('resume',str(self.run)),2)
    def test_clean_resume(self):
        self.assertEqual(self.call('checkpoint',str(self.run),'--note','Reviewed','--next','Trace'),0)
        self.assertEqual(self.call('resume',str(self.run)),0)
    def test_truncated_inventory(self):
        inv=cli.inventory(self.target,max_files=1)
        self.assertTrue(inv['truncated'])
    def finding(self):
        f=cli.read(Path(__file__).resolve().parents[1]/'templates/finding.json')
        f.update(revision=cli.read(self.run/'run.json')['revision'],control_ids=['EAOS-07-001'])
        return f
    def test_confirmed_needs_evidence(self):
        f=self.finding();f.update(claim_status='CONFIRMED',confidence='HIGH');cli.write(self.run/'findings.json',[f])
        self.assertTrue(any('requires evidence' in e for e in cli.check(self.run)['errors']))
    def test_closed_needs_passing_gates(self):
        f=self.finding();f.update(status='verified_closed',verification_ids=['G-1']);cli.write(self.run/'findings.json',[f])
        self.assertTrue(any('nonpassing gate' in e for e in cli.check(self.run)['errors']))
    def test_invalid_finding_schema(self):
        f=self.finding();f['affected_files']=5;cli.write(self.run/'findings.json',[f])
        self.assertTrue(any('invalid type' in e for e in cli.check(self.run)['errors']))
    def test_absence_search_requires_scope(self):
        rev=cli.read(self.run/'run.json')['revision']
        cli.write(self.run/'evidence.json',[{'id':'E-1','kind':'absence_search','location':'repo','revision':rev,'observed_at':cli.now(),'observation':'not found','method':'search','limitations':'gateway unknown'}])
        self.assertTrue(any('insufficient absence search' in e for e in cli.check(self.run)['errors']))
    def complete_fixture(self):
        # Synthetic record-contract exercise only; NOT substantive engineering verification.
        state=cli.read(self.run/'run.json');rev=state['revision']
        evidence=[{'id':'E-1','kind':'test','location':'synthetic-fixture','revision':rev,'observed_at':cli.now(),'observation':'Synthetic contract fixture','method':'unit test','limitations':'No real project assurance'}]
        coverage=[]
        for m in cli.registry()['modules']:
            for c in m['controls']:
                coverage.append({'id':'C-'+c['id'],'control_id':c['id'],'component':'synthetic','flow':'synthetic','environment':'fixture','revision':rev,'status':'pass','rationale':'Synthetic record validation only','evidence_ids':['E-1'],'finding_ids':[]})
        state.update(scope_confirmed=True,inventory_reviewed=True,architecture_reviewed=True,product_flows_reviewed=True,unknowns=[],expected_instances=[c['id'] for c in coverage],completion='COMPLETE')
        state['scope']['environments']=['fixture']
        for d in state['module_decisions']:d.update(applicability='APPLICABLE',reason='synthetic contract test',evidence_ids=['E-1'])
        model=cli.read(Path(__file__).resolve().parents[1]/'examples/architecture/model.json');model['revision']=rev
        cli.write(self.run/'architecture.json',model)
        cli.write(self.run/'run.json',state);cli.write(self.run/'evidence.json',evidence);cli.write(self.run/'coverage.json',coverage)
    def test_consistent_complete_contract(self):
        self.complete_fixture();r=cli.check(self.run);self.assertEqual(r['errors'],[]);self.assertEqual(r['computed_audit_completion'],'COMPLETE')
    def test_missing_control_prevents_completion(self):
        self.complete_fixture()
        self.update('coverage.json',lambda c:c.pop())
        self.assertEqual(cli.check(self.run)['record_integrity'],'INVALID')
    def test_gateway_unknown_blocks_completion(self):
        self.complete_fixture();self.update('run.json',lambda r:r['unknowns'].append('Gateway protections unverified'))
        self.assertIn('False completion claim',cli.check(self.run)['errors'])
    def test_na_mandatory_domain_rejected(self):
        self.complete_fixture();self.update('run.json',lambda r:r['module_decisions'][0].update(applicability='NOT_APPLICABLE'))
        self.assertTrue(any('Mandatory module' in e for e in cli.check(self.run)['errors']))
    def test_gate_cannot_pass_without_execution_evidence(self):
        rev=cli.read(self.run/'run.json')['revision']
        cli.write(self.run/'gates.json',[{'id':'G-1','status':'pass','revision':rev,'rationale':'claims passed','evidence_ids':[]}])
        self.assertTrue(any('requires execution evidence' in e for e in cli.check(self.run)['errors']))
if __name__=='__main__':unittest.main()
