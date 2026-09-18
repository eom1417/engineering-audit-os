"""Regressions for defects found by applying EAOS to its own architecture/runtime."""
import ast
import contextlib
import io
from pathlib import Path
import sys
import unittest
from eaos import cli
from eaos.runtime.campaign import improve
from eaos.runtime.context import Context
from eaos.runtime.jobs import Jobs
from eaos.runtime.provider import Provider
from eaos.runtime.remediate import implement
from fixture_provider import FixtureProvider
from test_runtime import RuntimeTests

class SelfAuditRegressionTests(unittest.TestCase):
    setUp=RuntimeTests.setUp
    execute=RuntimeTests.execute

    def test_runtime_does_not_depend_on_cli_entrypoint(self):
        root=Path(__file__).resolve().parents[1]/'eaos/runtime'
        offenders=[]
        for p in root.glob('*.py'):
            for n in ast.walk(ast.parse(p.read_text())):
                if isinstance(n,ast.ImportFrom) and n.module in {'cli','eaos.cli'}:offenders.append(p.name)
        self.assertEqual(offenders,[], 'Session creation belongs below CLI and runtime, not inside CLI')

    def test_record_validation_does_not_depend_on_workflow_orchestration(self):
        p=Path(__file__).resolve().parents[1]/'eaos/audit_records.py'
        imports={n.module for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.ImportFrom)}
        self.assertNotIn('workflow',imports)

    def test_baseline_deletion_is_detected(self):
        self.execute();config=self.base/'checks.json'
        cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-c','from pathlib import Path; Path("export.py").unlink()']}]})
        with self.assertRaisesRegex(ValueError,'Baseline check modified source'):
            implement(self.run,'T-PRICE',self.base/'deleted',config,self.provider)

    def test_post_checks_cannot_modify_unplanned_source_and_claim_verified(self):
        self.execute();config=self.base/'checks.json'
        script='from pathlib import Path; p=Path("README.md"); p.write_text(p.read_text()+"\\nchanged by check") if Path("rules.py").exists() else None'
        cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-c',script]}]})
        result=implement(self.run,'T-PRICE',self.base/'mutated',config,self.provider)
        self.assertNotEqual(result['status'],'VERIFIED_IN_ISOLATED_COPY')

    def test_final_allowed_campaign_step_can_complete(self):
        self.execute();config=self.base/'checks.json'
        cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-m','unittest','discover','-s','tests']} ]})
        class AdaptiveFixture(FixtureProvider):
            def complete(self,messages):
                import json
                request=json.loads(messages[1]['content'])
                if request['stage']=='inspect':
                    text='\n'.join(b['source'] for b in request['instructions'].get('source_blocks',[]))
                    if 'from rules import price' in text:self.clean=True;self.ids=[]
                return super().complete(messages)
        provider=AdaptiveFixture();provider.ids=self.provider.ids
        with contextlib.redirect_stdout(io.StringIO()):result=improve(self.run,self.base/'campaign',config,provider,max_steps=1)
        self.assertEqual(result['status'],'COMPLETE',result)
        self.assertEqual(len(result['steps']),1)

    def test_increasing_call_budget_does_not_invalidate_model_identity(self):
        base={'kind':'command','argv':[sys.executable,'-c','pass']}
        self.assertEqual(Provider(dict(base,timeout_seconds=10,max_calls=400)).identity(),Provider(dict(base,timeout_seconds=20,max_calls=500)).identity())

    def test_call_budget_can_be_raised_for_saved_work(self):
        class BudgetProvider(FixtureProvider):config={'max_calls':401}
        provider=BudgetProvider();context=Context(self.run,cli.read(self.run/'run.json'),96000);jobs=Jobs(self.run,context,provider,96000)
        jobs.metrics=[{'fixture':'previous call'} for _ in range(400)]
        jobs.run_job('budget-resume','inspect',{'source_blocks':[]})
        self.assertEqual(provider.calls,1)

    def test_cli_mutation_respects_active_engine_lock(self):
        (self.run/'engine.lock').write_text('active-fixture')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            result=cli.main(['observe',str(self.run),'--file','app.py','--start','1','--end','2','--observation','Concurrent mutation'])
        self.assertEqual(result,2)
        self.assertEqual(cli.read(self.run/'evidence.json'),[])

    def test_remediation_respects_active_engine_lock(self):
        self.execute();(self.run/'engine.lock').write_text('active-fixture')
        config=self.base/'checks.json';cli.write(config,{'checks':[{'id':'G-PRICE','argv':[sys.executable,'-m','unittest','discover','-s','tests']}]})
        with self.assertRaisesRegex(ValueError,'locked'):
            implement(self.run,'T-PRICE',self.base/'concurrent',config,self.provider)
        self.assertFalse((self.base/'concurrent').exists())

    def test_unresolved_inspection_uncertainty_cannot_disappear(self):
        class UncertainFixture(FixtureProvider):
            def complete(self,messages):
                import json
                request=json.loads(messages[1]['content'])
                if request['stage']=='uncertainty':
                    questions=request['instructions']['questions']
                    return {'action':'final','result':{'resolutions':[{'question':q,'status':'unresolved','rationale':'No evidence resolves this question','evidence_ids':self.ids} for q in questions]}},{}
                response,usage=super().complete(messages)
                if request['stage']=='inspect':response['result']['unknowns']=['Ownership of an external policy is not established']
                return response,usage
        self.provider=UncertainFixture()
        result=self.execute()
        self.assertEqual(result['status'],'PARTIALLY_COMPLETE')
        self.assertIn('Ownership of an external policy is not established',cli.read(self.run/'run.json')['unknowns'])

    def test_json_credentials_and_connection_urls_are_redacted(self):
        from eaos.runtime.context import redact
        sample='{"api_key":"CREDENTIAL_SENTINEL", "database_url":"postgres://user:PASSWORD_SENTINEL@db/app"}\nAWS_SECRET_ACCESS_KEY=ENV_SENTINEL\n'
        cleaned=redact(sample)
        for secret in ['CREDENTIAL_SENTINEL','PASSWORD_SENTINEL','ENV_SENTINEL']:self.assertNotIn(secret,cleaned)
        self.assertEqual(cleaned.count('\n'),sample.count('\n'))

    def test_tampered_cache_is_not_reused(self):
        context=Context(self.run,cli.read(self.run/'run.json'),96000);jobs=Jobs(self.run,context,self.provider,96000)
        result=jobs.run_job('tamper','inspect',{'source_blocks':[]})
        path=next((self.run/'jobs').glob('tamper-*.json'));cached=cli.read(path);cached['result']['summary']='Tampered diagnosis';cli.write(path,cached)
        calls=self.provider.calls
        restored=jobs.run_job('tamper','inspect',{'source_blocks':[]})
        self.assertGreater(self.provider.calls,calls);self.assertEqual(restored['summary'],result['summary'])

del RuntimeTests
if __name__=='__main__':unittest.main()
