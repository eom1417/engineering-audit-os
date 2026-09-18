import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from eaos import cli,workflow
from eaos.runtime.pipeline import execute
from eaos.runtime.remediate import implement,validated_edits,check_commands,run_checks
from eaos.runtime.context import Context,redact
from eaos.runtime.jobs import Jobs
from eaos.runtime.provider import Provider
from fixture_provider import FixtureProvider

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.target=self.base/'product';self.run=self.base/'run'
        fixture=Path(__file__).resolve().parents[1]/'examples/benchmark/coupled-billing'
        shutil.copytree(fixture,self.target)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(cli.main(['init',str(self.target),'--out',str(self.run)]),0)
        workflow.initialize(self.run);self.provider=FixtureProvider()

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()):return execute(self.run,self.provider)

    def test_complete_engine_from_source_to_report(self):
        before={p.relative_to(self.target).as_posix():p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        result=self.execute()
        self.assertEqual(result['status'],'COMPLETE',result)
        self.assertEqual(cli.read(self.run/'findings.json')[0]['root_cause'],'Entry modules independently own and execute the same policy.')
        self.assertEqual(cli.read(self.run/'roadmap.json')['tasks'][0]['invariant'],'Premium discount is 10 percent; standard totals remain unchanged')
        for name in ['ARCHITECTURE.md','architecture.mmd','TARGET-ARCHITECTURE.md','IMPLEMENTATION-PLAN.md','EXECUTIVE.md','report.md','engine-state.json']:self.assertTrue((self.run/name).is_file(),name)
        self.assertEqual(before,{p.relative_to(self.target).as_posix():p.read_bytes() for p in self.target.rglob('*') if p.is_file()})

    def test_resume_reuses_valid_jobs_without_model_calls(self):
        self.execute();calls=self.provider.calls;result=self.execute()
        self.assertEqual(result['status'],'COMPLETE');self.assertEqual(self.provider.calls,calls)

    def test_changed_source_blocks_resume(self):
        self.execute();(self.target/'app.py').write_text('changed\n')
        with self.assertRaises(ValueError):self.execute()
        self.assertEqual(cli.read(self.run/'engine-state.json')['status'],'BLOCKED')
        self.assertFalse((self.run/'engine.lock').exists())

    def test_actual_repair_baseline_regression_and_root_owner(self):
        self.execute();config=self.base/'checks.json'
        cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-m','unittest','discover','-s','tests'],'timeout_seconds':30}]})
        original=(self.target/'app.py').read_bytes()
        result=implement(self.run,'T-PRICE',self.base/'repair',config,self.provider)
        self.assertEqual(result['status'],'VERIFIED_IN_ISOLATED_COPY',result)
        project=self.base/'repair/project'
        self.assertIn('from rules import price',(project/'app.py').read_text())
        self.assertIn('from rules import price',(project/'export.py').read_text())
        self.assertTrue(all(r['exit_code']==0 for r in result['baseline']+result['post_checks']))
        self.assertEqual(original,(self.target/'app.py').read_bytes())
        self.assertIn('rules.py',(self.base/'repair/changes.patch').read_text())
        self.assertEqual(cli.read(self.run/'findings.json')[0]['status'],'open')

    def test_no_rewrite_when_validated_findings_are_empty(self):
        # Protocol check only: scripted clean judgment is supplied, not independently discovered.
        (self.target/'export.py').write_text('from app import quote\n\ndef exported_total(amount, premium=False):\n    return quote(amount, premium)\n')
        (self.target/'app.py').write_text('def quote(amount, premium=False):\n    return round(amount * (0.90 if premium else 1.0), 2)\n')
        shutil.rmtree(self.run)
        with contextlib.redirect_stdout(io.StringIO()):cli.main(['init',str(self.target),'--out',str(self.run)])
        workflow.initialize(self.run);self.provider=FixtureProvider(clean=True)
        self.assertEqual(self.execute()['status'],'COMPLETE')
        self.assertEqual(cli.read(self.run/'roadmap.json')['tasks'],[])

    def test_missing_provider_data_never_marks_complete(self):
        class Broken(FixtureProvider):
            def complete(self,messages):return {'action':'final','result':{}},{}
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):execute(self.run,Broken(),max_rounds=2)
        self.assertEqual(cli.read(self.run/'engine-state.json')['status'],'BLOCKED')
        self.assertEqual(cli.read(self.run/'run.json')['completion'],'INCOMPLETE')

    def test_source_budget_splits_all_lines(self):
        # A stream of chunks, not a complete-repository context dump.
        context=Context(self.run,cli.read(self.run/'run.json'),24000)
        chunks,omissions=context.chunks();blocks=[b for batch in chunks for b in batch]
        for path in context.files:
            refs=[b for b in blocks if b['path']==path]
            lines=context.lines(path)
            self.assertEqual(sum(b['end_line']-b['start_line']+1 for b in refs),len(lines))
        self.assertEqual(omissions,[])

    def test_read_requests_and_unknown_evidence_rejected(self):
        state=cli.read(self.run/'run.json');context=Context(self.run,state,96000)
        class Reader:
            def __init__(self):self.count=0
            def identity(self):return {'kind':'reader-fixture'}
            def complete(self,messages):
                self.count+=1
                if self.count==1:return {'action':'read','reads':[{'path':'app.py','start':1,'end':2}],'notes':'Need actual pricing source'},{}
                block=json.loads(messages[-1]['content'])['requested_data'][0]
                return {'action':'final','result':{'summary':'Observed quote source','responsibilities':[],'business_rules':[],'flows':[],'risks':[],'unknowns':[],'evidence_ids':[block['evidence_id']]}},{}
        jobs=Jobs(self.run,context,Reader(),96000)
        result=jobs.run_job('source-read','inspect',{'task':'Read quote'})
        self.assertTrue(result['evidence_ids'][0].startswith('SRC-'))
        self.assertTrue(context.verify_refs({'evidence_ids':['fabricated']}))

    def test_arbitrary_record_reads_and_traversal_denied(self):
        context=Context(self.run,cli.read(self.run/'run.json'),96000);jobs=Jobs(self.run,context,self.provider,96000)
        with self.assertRaises(ValueError):jobs.record('../private.json')
        with self.assertRaises(ValueError):context.source('../outside',1,1)
        with self.assertRaises(ValueError):validated_edits([{'path':'../outside','content':'bad'}],{'../outside'},self.target)

    def test_secret_redaction_retains_line_count(self):
        text='api_key = "sk-abcdefghijklmnopqrstuvwxyz"\nnormal = 5\n'
        result=redact(text)
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz',result)
        self.assertEqual(text.count('\n'),result.count('\n'))

    def test_http_provider_wire_contract_and_truncated_output_rejection(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        received=[];finish=['stop']
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body=json.dumps({'choices':[{'finish_reason':finish[0],'message':{'content':json.dumps({'action':'final','result':{'ok':True}})}}],'usage':{'total_tokens':12}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            provider=Provider({'kind':'chat_completions','endpoint':'http://127.0.0.1:'+str(server.server_port)+'/v1/chat/completions','model':'protocol-fixture','api_key_env':''})
            response,usage=provider.complete([{'role':'user','content':'JSON fixture'}])
            self.assertTrue(response['result']['ok']);self.assertEqual(usage['total_tokens'],12)
            self.assertEqual(received[0]['response_format'],{'type':'json_object'})
            finish[0]='length'
            with self.assertRaises(ValueError):provider.complete([])
        finally:server.shutdown();server.server_close();thread.join()

    def test_challenged_design_is_revised_automatically(self):
        class ChallengeFixture(FixtureProvider):
            def __init__(self):super().__init__();self.challenged=False
            def complete(self,messages):
                req=json.loads(messages[1]['content']);response,usage=super().complete(messages)
                if req['stage']=='challenge' and req['instructions']['task'].startswith('Read target-architecture') and not self.challenged:
                    self.challenged=True;response['result'].update(assessment='REVISE',issues=[{'finding_id':'F-02-001','reason':'Recheck cutover compatibility','evidence_ids':self.ids}])
                return response,usage
        self.provider=ChallengeFixture();self.assertEqual(self.execute()['status'],'COMPLETE')
        self.assertTrue(list((self.run/'jobs').glob('design-revision-*.json')))
        self.assertEqual(cli.read(self.run/'plan-challenge.json')['assessment'],'ACCEPT')

    def test_model_provider_explicit_and_no_redirect_credentials(self):
        with self.assertRaises(ValueError):Provider({'kind':'chat_completions','model':'chosen','endpoint':'http://remote.example/chat','api_key_env':''})
        with self.assertRaises(ValueError):Provider({'kind':'chat_completions','model':'chosen','endpoint':'https://user:pass@example.test/chat','api_key_env':''})
        with self.assertRaises(ValueError):Provider({'kind':'command','argv':'echo unsafe-shell'})

    def test_command_provider_real_subprocess_json_protocol(self):
        provider=Provider({'kind':'command','argv':[sys.executable,'-c','import sys,json; data=json.load(sys.stdin); print(json.dumps({"action":"final","result":{"received":len(data["messages"])}}))']})
        response,usage=provider.complete([{'role':'user','content':'fixture'}])
        self.assertEqual(response['result']['received'],1)

    def test_command_provider_failure_withholds_stderr(self):
        provider=Provider({'kind':'command','argv':[sys.executable,'-c','import sys; print("SECRET_SENTINEL",file=sys.stderr); sys.exit(1)']})
        with self.assertRaises(ValueError) as ctx:provider.complete([])
        self.assertNotIn('SECRET_SENTINEL',str(ctx.exception))

    def test_verification_commands_are_explicit_and_cover_gates(self):
        with self.assertRaises(ValueError):check_commands({'checks':[]},['G'])
        with self.assertRaises(ValueError):check_commands({'checks':[{'id':'G','argv':'echo unsafe'}]},['G'])
        with self.assertRaises(ValueError):check_commands({'checks':[{'id':'G','argv':['true'],'cwd':'../outside'}]},['G'])

    def test_failed_baseline_prevents_edits(self):
        self.execute();config=self.base/'checks.json';cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-c','raise SystemExit(3)']}]})
        result=implement(self.run,'T-PRICE',self.base/'failed',config,self.provider)
        self.assertEqual(result['status'],'BASELINE_FAILED')
        self.assertFalse((self.base/'failed/project/rules.py').exists())

    def test_gate_executes_and_records_timeout(self):
        result=run_checks(self.target,{'checks':[{'id':'G','argv':[sys.executable,'-c','import time; time.sleep(10)'],'timeout_seconds':1}]},'fixture')
        self.assertTrue(result[0]['timed_out']);self.assertEqual(result[0]['status'],'fail')

if __name__=='__main__':unittest.main()
