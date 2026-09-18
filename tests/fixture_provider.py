"""Scripted protocol fixture, NOT a live model or independent architecture evaluator."""
import copy
import json
from pathlib import Path
from eaos.architecture import CORE_MODULES

class FixtureProvider:
    def __init__(self,clean=False):self.ids=[];self.calls=0;self.clean=clean
    def identity(self):return {'kind':'SCRIPTED_TEST_FIXTURE','clean':self.clean}
    def complete(self,messages):
        self.calls+=1
        request=json.loads(messages[1]['content']);stage=request['stage'];data=request['instructions']
        if stage in {'inspect','reduce'}:
            blocks=data.get('source_blocks',[])
            ids=[b['evidence_id'] for b in blocks] if blocks else list(self.ids)
            self.ids=list(dict.fromkeys(self.ids+ids))
            result={'summary':'Controlled pricing fixture: quote and export are entry contracts; premium discount is duplicated and inconsistent. No production evaluation.','responsibilities':['quote: interactive total','exported_total: exported total'],'business_rules':['Premium discount is 10 percent per README requirement'],'flows':['quote/export → inline discount → amount'],'risks':[] if self.clean else ['Rule ownership is duplicated; outputs diverge for premium customers'],'unknowns':[],'evidence_ids':ids}
        elif stage=='architecture':
            nodes=[{'id':nid,'name':nid,'kind':'module','responsibility':role,'domain':'billing','boundary':'in-process function','owner':'fixture','paths':[path],'evidence_ids':self.ids} for nid,path,role in [('api','app.py','Quote entry and inline pricing rule'),('export','export.py','Export entry and inline pricing rule')]]
            result={'architecture':{'schema_version':1,'revision':data['revision'],'coverage':{'status':'REVIEWED','scope':'Controlled fixture repository only','limitations':[]},'nodes':nodes,'edges':[],'contracts':[{'id':'PRICE-CONTRACT','owner':'api','consumers':['export'],'description':'Both entry points return a rounded total','invariant':'Same pricing policy across entry paths','failure_semantics':'Numeric caller inputs in this fixture','compatibility':'Preserve argument names and numeric return','evidence_ids':self.ids}],'business_rules':[{'id':'PREMIUM','owner':'api','consumers':['export'],'description':'Premium pricing rule currently copied between two entry modules','invariant':'10 percent discount in both paths','evidence_ids':self.ids}],'change_scenarios':[{'id':'CHANGE-PRICE','stimulus':'Change premium discount','environment':'repository','artifact':'quote and export','response':'Both paths use one policy','measure':'One rule owner and equal outputs for premium/standard cases','method':'Trace ownership and run regression tests','affected_nodes':['api','export'],'status':'TRACED','evidence_ids':self.ids}],'dependency_policies':[]},'flows':[{'id':'PRICE-FLOW','name':'Quote and export','steps':['input amount and premium state','calculate price','return total'],'invariants':['same discount policy'],'failure_recovery':['caller retries a pure calculation'],'evidence_ids':self.ids}],'unknowns':[]}
        elif stage=='review_plan':
            module=data['module'];applies=module['id'] in CORE_MODULES
            result={'applicability':'APPLICABLE' if applies else 'NOT_APPLICABLE','reason':'Controlled pure-function fixture; this contract test is not substantive production audit','evidence_ids':self.ids,'instances':[{'id':'C-'+c['id'],'control_id':c['id'],'component':'api/export','flow':'PRICE-FLOW','environment':'repository','rationale':'Controlled fixture check'} for c in module['controls']] if applies else []}
        elif stage=='review':
            mid=data['module']['id'];findings=[]
            if mid=='02' and not self.clean:
                f=json.loads((Path(__file__).resolve().parents[1]/'templates/finding.json').read_text())
                for key,value in list(f.items()):
                    if value=='REPLACE':f[key]='Controlled fixture observation'
                f.update(id='F-02-001',category='Architecture',subcategory='Duplicated business-rule ownership',location='app.py:1-2; export.py:1-2',current_behavior='Quote discounts premium by 5 percent; export discounts by 10 percent.',expected_behavior='Both paths apply the documented 10 percent premium rule.',root_cause='Entry modules independently own and execute the same policy.',why_this_matters='A policy change can drift across product flows.',recommended_remediation='Give pricing one owner and preserve both entry contracts.',implementation_strategy='Introduce rules.price and delegate from both entries; add cross-flow regression tests.',regression_risks='Changed totals for premium quote callers; verify the documented policy.',verification_method='Run before/after tests and inspect ownership.',affected_files=['app.py','export.py'],affected_components=['api','export'],affected_flows=['PRICE-FLOW'],required_tests=['Premium and standard totals agree across both entries'],control_ids=[data['module']['controls'][0]['id']],evidence_ids=self.ids,claim_status='CONFIRMED',confidence='HIGH',root_cause_status='CONFIRMED',revision=data['revision'],priority_rationale='User-visible inconsistency in a documented business rule',owner='fixture owner')
                findings=[f]
            coverage=[]
            for i,c in enumerate(data['declared_scope']['instances']):
                row=dict(c,revision=data['revision'],status='fail' if findings and i==0 else 'pass',evidence_ids=self.ids,finding_ids=['F-02-001'] if findings and i==0 else [])
                coverage.append(row)
            result={'applicability':'APPLICABLE','reason':'Controlled fixture','evidence_ids':self.ids,'findings':findings,'coverage':coverage,'unknowns':[]}
        elif stage=='design':
            if self.clean:result={'tasks':[],'dispositions':[],'gates':[],'target_architecture':{'decisions':[],'retained_structure':'Controlled clean fixture: preserve existing structure; no unnecessary rewrite.'},'unknowns':[]}
            else:
                from eaos.workflow import TEXT_FIELDS,LIST_FIELDS
                task={k:'Controlled fixture design' for k in TEXT_FIELDS};task.update({k:[] for k in LIST_FIELDS})
                task.update(id='T-PRICE',title='Unify pricing policy ownership',objective='Same documented premium price across entry paths',invariant='Premium discount is 10 percent; standard totals remain unchanged',root_cause='Entry-owned duplicate policy drift',approach='A shared pure pricing module used by both entry contracts',cost='Small change; estimate to be confirmed by implementation',risk='Premium quote totals change to documented behavior',rollback='Revert both delegates and new pricing module together; existing behavior then returns',acceptance_criteria='Regression tests pass and entries delegate to one pricing owner',priority_rationale='Inconsistent customer-visible totals',finding_ids=['F-02-001'],evidence_ids=self.ids,node_ids=['api','export'],scenario_ids=['CHANGE-PRICE'],files=['app.py','export.py','rules.py','tests/test_pricing.py'],steps=['Add pure pricing policy','Delegate quote and export','Protect both entry contracts with tests'],alternatives=['Change one constant: smaller but leaves policy drift risk','Shared pure function: central owner without a service boundary'],tests=['Premium/standard totals equal through both entries'],depends_on=[],required_gate_ids=['G-PRICE'],kind='remediate',status='planned',priority='P1')
                adr={'id':'ADR-PRICE','problem':'Duplicated ownership of one pricing rule','finding_ids':['F-02-001'],'evidence_ids':self.ids,'options':['Fix only the constant','Introduce one pure policy function'],'chosen':'One pure policy function','tradeoffs':'Small dependency shared by two entries; no new service or framework','target_boundaries':['Entry orchestration delegates pricing to rules module'],'migration_steps':['Add pure rule','Switch entry functions together','Run contract tests'],'compatibility':'Function signatures and rounding retained; premium quote corrected','rollback':'Revert one cohesive change','success_measures':['One policy implementation','Both entry outputs match expected pricing']}
                result={'tasks':[task],'dispositions':[],'gates':[{'id':'G-PRICE','name':'Pricing regression','revision':data['revision'],'rationale':'Protect pricing invariant across both entry paths','status':'not_run','evidence_ids':[],'required_for_audit':False}],'target_architecture':{'decisions':[adr],'retained_structure':'Keep the existing small in-process design and public entry functions.'},'unknowns':[]}
            result['target_architecture']['components']=[
                {'id':'api','name':'Quote entry','responsibility':'Preserve quote contract and delegate policy','owner':'billing','paths':['app.py'],'contracts':['quote(amount, premium=False) returns rounded total'],'depends_on':[] if self.clean else ['policy'],'change':'retain' if self.clean else 'modify','evidence_ids':self.ids},
                {'id':'export','name':'Export entry','responsibility':'Preserve export contract and delegate policy','owner':'billing','paths':['export.py'],'contracts':['exported_total(amount, premium=False) returns same total'],'depends_on':['api'] if self.clean else ['policy'],'change':'retain' if self.clean else 'modify','evidence_ids':self.ids}]
            if not self.clean:result['target_architecture']['components'].append({'id':'policy','name':'Pricing policy','responsibility':'Own the single premium discount rule','owner':'billing','paths':['rules.py'],'contracts':['Pure price(amount, premium) applies the documented rate'],'depends_on':[],'change':'introduce','evidence_ids':self.ids})
        elif stage in {'challenge','reaudit'}:
            ids=[b['evidence_id'] for b in data.get('changed_source',[])] or self.ids
            result={'assessment':'ACCEPT','issues':[],'rationale':'Scripted fixture acceptance exercises the protocol. It is not an independent model review. Actual behavior is tested separately.','evidence_ids':ids}
        elif stage=='repair':
            contents={'rules.py':'def price(amount, premium=False):\n    return round(amount * (0.90 if premium else 1.0), 2)\n','app.py':'from rules import price\n\ndef quote(amount, premium=False):\n    return price(amount, premium)\n','export.py':'from rules import price\n\ndef exported_total(amount, premium=False):\n    return price(amount, premium)\n','tests/test_pricing.py':'import unittest\nfrom app import quote\nfrom export import exported_total\n\nclass PricingTests(unittest.TestCase):\n    def test_prices(self):\n        for premium, expected in [(False, 100), (True, 90)]:\n            self.assertEqual(quote(100, premium), expected)\n            self.assertEqual(exported_total(100, premium), expected)\n'}
            result={'edits':[{'path':path,'content':content} for path,content in contents.items()],'rationale':'Centralize the duplicated policy while preserving public entry functions; fixture patch','evidence_ids':self.ids}
        else:raise AssertionError('Unsupported test stage '+stage)
        return {'action':'final','result':copy.deepcopy(result)},{'fixture':True}
