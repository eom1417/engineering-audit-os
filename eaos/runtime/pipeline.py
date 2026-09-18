"""Full discovery → reconstruction → scoped audit → diagnosis challenge → design → report."""
import json
import os
from pathlib import Path
from ..workspace import read,write,load_run,fresh,registry,DATA,now
from ..architecture import CORE_MODULES,validate_model
from ..discovery import classify,scan
from ..audit_records import check
from ..workflow import roadmap_check,render_report
from .context import Context
from .jobs import Jobs


def execute(path,provider,budget=96000,max_rounds=8):
    run,state=load_run(path)
    if budget<24000:raise ValueError('Engine budget must be at least 24000 characters; no token equivalence assumed')
    lock=run/'engine.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('Engine run is locked; verify no process is active before removing a stale engine.lock') from None
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        return _execute(run,state,provider,budget,max_rounds)
    except Exception as exc:
        write(run/'engine-state.json',{'status':'BLOCKED','revision':state['revision'],'error':str(exc),'at':now(),'resume':'Run eaos continue with the same provider config; valid completed jobs are reused. A changed source requires a fresh run.'})
        (run/'ENGINE-STATUS.md').write_text('# Audit blocked\n\n'+str(exc)+'\n\nExisting reports may be from a prior attempt. Inspect engine-state.json; do not claim completion.\n')
        raise
    finally:lock.unlink(missing_ok=True)


def _execute(run,state,provider,budget,max_rounds):
    inv=read(run/'inventory.json')
    if not fresh(state,inv)[0]:raise ValueError('Snapshot changed or inventory incomplete; start a fresh run')
    if not (run/'workflow.json').exists():raise ValueError('Start with eaos run or eaos audit to create workflow records')
    if not (run/'discovery.json').exists():scan(run)
    context=Context(run,state,budget);jobs=Jobs(run,context,provider,budget,max_rounds)
    def phase(name):
        if not fresh(state,inv)[0]:raise ValueError('Source changed during '+name+'; start a new run')
        write(run/'engine-state.json',{'status':'RUNNING','phase':name,'revision':state['revision'],'at':now()})
        print('EAOS: '+name,flush=True)
    def expose(name,value):write(run/name,value);jobs.catalog.add(name)
    phase('source inspection')
    batches,omissions=context.chunks()
    expose('source-index.json',[{'path':f['path'],'capture':f['capture'],'category':classify(f['path'])} for f in inv['files']])
    expose('source-omissions.json',omissions)
    briefs=[];surfaces={}
    for i,batch in enumerate(batches):
        ids={b['evidence_id'] for b in batch}
        def verify_brief(result):return [] if ids.issubset(set(result['evidence_ids'])) else ['Account for every supplied source block in evidence_ids']
        result=jobs.run_job(f'inspect-{i:05d}','inspect',{'source_blocks':batch,'task':'Read every supplied source range. Explain responsibility, rule ownership, coupling and behavior. Identify candidate root causes and counter-evidence, including larger structural problems. Do not invent confirmed findings from syntax alone.'},verify_brief)
        name=f'brief-{i:05d}.json';expose(name,result);briefs.append(result)
        for b in batch:surfaces.setdefault(b['path'],[]).append(b['evidence_id'])
    ledger=[]
    missing_paths={o['path'] for o in omissions}
    for f in inv['files']:
        rel=f['path'];ledger.append({'path':rel,'revision':state['revision'],'status':'blocked' if rel in missing_paths else 'reviewed','rationale':'One or more ranges not inspected; see source-omissions.json' if rel in missing_paths else 'Every captured text range was processed in source inspection; domain/flow checks follow separately.','evidence_ids':surfaces.get(rel,[])})
    write(run/'surface-review.json',ledger)
    expose('source-omissions.json',omissions)
    # Hierarchical synthesis keeps individual briefs available as addressable records.
    level=0;working=briefs
    while len(json.dumps(working,ensure_ascii=False))>budget//3:
        groups=[];group=[];size=0
        for brief in working:
            amount=len(json.dumps(brief,ensure_ascii=False))
            if amount>budget//3:raise ValueError('A source brief exceeds synthesis budget; reduce provider summary size')
            if group and size+amount>budget//3:groups.append(group);group=[];size=0
            group.append(brief);size+=amount
        if group:groups.append(group)
        reduced=[]
        for i,group in enumerate(groups):
            r=jobs.run_job(f'reduce-{level}-{i}','reduce',{'briefs':group,'task':'Synthesize cross-module responsibilities, ownership, dependencies, contradictory rules and failure modes. Preserve decisive evidence IDs and unknowns. Original brief records remain accessible; this is an index, not proof.'})
            expose(f'synthesis-{level}-{i}.json',r);reduced.append(r)
        if len(json.dumps(reduced))>=len(json.dumps(working)):raise ValueError('Synthesis did not reduce context; lower summary verbosity or raise explicit budget')
        working=reduced;level+=1
    if not working:raise ValueError('No eligible source content; inspect source-omissions.json')
    expose('system-briefs.json',working)
    state['scope']={'description':'Repository architecture and maintainability audit; deployment/runtime facts require separately supplied evidence. No live production access is implied.','environments':['repository'],'approved_exclusions':[]}
    state.update(scope_confirmed=True,inventory_reviewed=True,completion='INCOMPLETE')
    phase('architecture reconstruction')
    def verify_arch(result):
        model=result['architecture'];model['revision']=state['revision']
        errors,_=validate_model(model,context.evidence,state['revision'],set(context.files))
        if not result['flows']:errors.append('Trace actual product flows; for a library trace consumer calls')
        for flow in result['flows']:
            if not isinstance(flow,dict) or not all(flow.get(k) for k in ['id','name','steps','invariants','failure_recovery','evidence_ids']):errors.append('Flow requires steps, invariants, recovery and evidence')
        return errors
    architecture=jobs.run_job('architecture','architecture',{'briefs':working,'revision':state['revision'],'task':'Reconstruct the actual system, not an ideal folder template. Assign responsibility and business-rule ownership; distinguish domain, runtime and deployment boundaries. Include contracts, change scenarios and data/control flow. Read source and original briefs to resolve cross-boundary assumptions. Mark uncertainty, and do not label scenarios TESTED without real test evidence.'},verify_arch)
    model=architecture['architecture'];model['revision']=state['revision']
    expose('architecture.json',model);expose('flows.json',architecture['flows'])
    (run/'architecture.md').write_text('# Observed architecture\n\n```json\n'+json.dumps(model,ensure_ascii=False,indent=2)+'\n```\n')
    (run/'product-flows.md').write_text('# Product flows\n\n```json\n'+json.dumps(architecture['flows'],ensure_ascii=False,indent=2)+'\n```\n')
    state.update(architecture_reviewed=True,product_flows_reviewed=True)
    findings=[];coverage=[];decisions=[];unknowns=list(architecture['unknowns'])
    for module in registry()['modules']:
        mid=module['id']
        phase('scope and review module '+mid)
        controls={c['id'] for c in module['controls']}
        def verify_scope(r):
            errors=[]
            if r['applicability'] not in {'APPLICABLE','NOT_APPLICABLE'}:errors.append('Invalid applicability')
            if mid in CORE_MODULES and r['applicability']!='APPLICABLE':errors.append('Core module is mandatory')
            if not r['evidence_ids']:errors.append('Applicability needs source evidence')
            if r['applicability']=='APPLICABLE':
                seen=set()
                for c in r['instances']:
                    if not isinstance(c,dict) or not all(isinstance(c.get(k),str) and c[k].strip() for k in ['id','control_id','component','flow','environment','rationale']):errors.append('Invalid planned coverage instance');continue
                    if c['id'] in seen:errors.append('Duplicate coverage ID')
                    seen.add(c['id'])
                    if c['control_id'] not in controls:errors.append('Unknown control in module scope')
                if {c.get('control_id') for c in r['instances'] if isinstance(c,dict)}!=controls:errors.append('Every module control needs a declared instance')
            elif r['instances']:errors.append('Nonapplicable module cannot contain planned instances')
            return errors
        scoped=jobs.run_job('scope-'+mid,'review_plan',{'module':module,'system_briefs':working,'task':'Declare component × flow × environment instances BEFORE judging results. Inspect architecture.json and flows.json. Include every distinct critical boundary affected by each control; do not use one representative file for a whole system. Supporting domains apply when architecture/flows depend on them; otherwise justify nonapplicability from evidence.'},verify_scope)
        decisions.append({'module_id':mid,'applicability':scoped['applicability'],'reason':scoped['reason'],'evidence_ids':scoped['evidence_ids']})
        expose('scope-'+mid+'.json',scoped)
        if scoped['applicability']=='NOT_APPLICABLE':continue
        declared={c['id']:c for c in scoped['instances']}
        def verify_review(r):
            errors=[]
            if r['applicability']!='APPLICABLE':errors.append('Cannot silently change predeclared applicability')
            if {c['id'] for c in r['coverage']}!=set(declared):errors.append('Coverage differs from predeclared instances')
            for c in r['coverage']:
                if c['id'] in declared:
                    for key in ['control_id','component','flow','environment']:
                        if c[key]!=declared[c['id']][key]:errors.append('Coverage scope changed after declaration')
                c['revision']=state['revision']
            for f in r['findings']:
                f['revision']=state['revision']
                if not f['id'].startswith('F-'+mid+'-'):errors.append('Finding IDs must start F-'+mid+'-')
                if f['status']!='open' or f['verification_ids']:errors.append('New finding must remain open without fabricated verification')
                if not f['evidence_ids']:errors.append('Finding must cite source evidence')
                if any(p not in context.files for p in f['affected_files']):errors.append('Finding references absent file')
                if not set(f['control_ids']).issubset(controls):errors.append('Finding control outside module')
            return errors
        reviewed=jobs.run_job('review-'+mid,'review',{'module':module,'declared_scope':scoped,'system_briefs':working,'revision':state['revision'],'task':'Execute these checks against actual source. Search shared controls and counter-evidence. Detect structural root causes, not just style or file size. Trace critical reads/writes, lifecycle and failure paths. Emit full finding records and coverage for exactly the declared instances. Confirm only what source supports; runtime-only claims remain blocked. Findings IDs use F-'+mid+'-NNN.'},verify_review)
        findings+=reviewed['findings'];coverage+=reviewed['coverage'];unknowns+=reviewed['unknowns']
        expose('review-'+mid+'.json',reviewed)
        write(run/'findings.json',findings);write(run/'coverage.json',coverage)
        state.update(module_decisions=decisions+[d for d in state['module_decisions'] if d['module_id'] not in {x['module_id'] for x in decisions}],expected_instances=[c['id'] for c in coverage],unknowns=unknowns)
        write(run/'run.json',state)
    expose('findings.json',findings);expose('coverage.json',coverage)
    state.update(module_decisions=decisions,expected_instances=[c['id'] for c in coverage],unknowns=list(dict.fromkeys(unknowns+[o['path']+': '+o['reason'] for o in omissions])))
    write(run/'run.json',state)
    phase('root-cause challenge')
    index=[{'id':f['id'],'category':f['category'],'current_behavior':f['current_behavior'],'root_cause':f['root_cause'],'claim_status':f['claim_status'],'priority':f['priority']} for f in findings]
    expose('finding-index.json',index)
    challenge=jobs.run_job('diagnosis-challenge','challenge',{'system_briefs':working,'finding_index':index,'task':'Adversarially review the diagnosis. Read findings.json, architecture.json, coverage.json and cited source. Seek alternative causes, false positives, missed systemic ownership/boundary problems, duplicated root causes across modules, and claims based only on aesthetics. ACCEPT only if the diagnosis is adequately supported within the stated scope. This is a second pass of the same provider, not an independent human review.'})
    for repair_round in range(2):
        if challenge['assessment']=='ACCEPT':break
        old_finding_ids={f['id'] for f in findings};old_coverage={c['id']:c for c in coverage}
        def verify_reconciliation(r):
            errors=[]
            if not old_finding_ids.issubset({f['id'] for f in r['findings']}):errors.append('Retain existing IDs; mark disproven findings false_positive with explanation, do not erase history')
            if {c['id'] for c in r['coverage']}!=set(old_coverage):errors.append('Preserve declared coverage instances')
            for c in r['coverage']:
                c['revision']=state['revision']
                if c['id'] in old_coverage and any(c[k]!=old_coverage[c['id']][k] for k in ['control_id','component','flow','environment']):errors.append('Cannot shrink coverage during reconciliation')
            for f in r['findings']:
                f['revision']=state['revision']
                if f['status'] not in {'open','false_positive','duplicate'}:errors.append('Reconciliation cannot claim repairs')
                if not f['evidence_ids']:errors.append('Reconciled finding needs evidence')
                if any(p not in context.files for p in f['affected_files']):errors.append('Unknown affected file')
            return errors
        revised=jobs.run_job('reconcile-'+str(repair_round),'reconcile',{'challenge':challenge,'task':'Read current findings.json and coverage.json. Investigate every challenge against source. Return reconciled complete lists, preserving IDs and declared coverage. Explain disproven or duplicate diagnoses instead of silently deleting them. Add missed evidence-backed root causes and link failed coverage. Do not change code.'},verify_reconciliation)
        findings=revised['findings'];coverage=revised['coverage'];state['unknowns']+=revised['unknowns']
        expose('findings.json',findings);expose('coverage.json',coverage)
        index=[{'id':f['id'],'category':f['category'],'current_behavior':f['current_behavior'],'root_cause':f['root_cause'],'claim_status':f['claim_status'],'priority':f['priority']} for f in findings]
        expose('finding-index.json',index)
        challenge=jobs.run_job('diagnosis-recheck-'+str(repair_round),'challenge',{'finding_index':index,'previous_challenge':challenge,'task':'Re-read revised findings and source. Have the challenges been resolved with evidence? ACCEPT only with no remaining substantive diagnosis issues.'})
    expose('diagnosis-challenge.json',challenge)
    phase('target architecture and migration design')
    def verify_design(r):
        known_findings={f['id'] for f in findings}
        covered=set()
        for adr in r['target_architecture']['decisions']:
            if not isinstance(adr['finding_ids'],list) or any(not isinstance(fid,str) or fid not in known_findings for fid in adr['finding_ids']):return ['Target decision references unknown findings']
            covered.update(adr['finding_ids'])
        required={fid for task in r['tasks'] if task.get('kind')=='remediate' for fid in task['finding_ids']}
        if not required.issubset(covered):return ['Every remediation must connect to a target architecture decision']
        for component in r['target_architecture']['components']:
            if any(Path(p).is_absolute() or '..' in Path(p).parts for p in component['paths']):return ['Invalid target architecture path']
        for g in r['gates']:
            g['revision']=state['revision']
            if g['status']!='not_run' or g['evidence_ids'] or g.get('required_for_audit'):return ['Design gates must be unexecuted remediation gates']
        for t in r['tasks']:
            if t.get('status')!='planned':return ['Design tasks must start planned']
        # Validate using the existing task contracts, restore files if invalid.
        old_plan=read(run/'roadmap.json');old_gates=read(run/'gates.json')
        try:
            write(run/'roadmap.json',{'schema_version':1,'revision':state['revision'],'tasks':r['tasks'],'dispositions':r['dispositions']});write(run/'gates.json',r['gates'])
            result=roadmap_check(run,state)
            return result['errors']+result['gaps']
        finally:write(run/'roadmap.json',old_plan);write(run/'gates.json',old_gates)
    design=jobs.run_job('design','design',{'system_briefs':working,'finding_index':index,'diagnosis_challenge':challenge,'revision':state['revision'],'task':'Design an integrated target architecture and staged migration, not a list of cosmetic edits. Read full findings and architecture. Group symptoms under their actual causes; link all findings to justified tasks or dispositions. For confirmed architectural defects design proportionate root-cause repair, contracts, data migration, coexistence, cutover, regression tests and rollback. Compare real alternatives. Preserve sound structures. Make task dependencies explicit. Every task references existing node IDs and change_scenario IDs. If no defect is justified, retain structure and do not invent a rewrite. Do not invent costs; qualify estimates.'},verify_design)
    expose('target-architecture.json',design['target_architecture'])
    expose('roadmap.json',{'schema_version':1,'revision':state['revision'],'tasks':design['tasks'],'dispositions':design['dispositions']})
    expose('gates.json',design['gates'])
    state['unknowns']+=design['unknowns']
    phase('migration challenge and final verification')
    plan_challenge=jobs.run_job('plan-challenge','challenge',{'task':'Read target-architecture.json, roadmap.json, findings.json and source. Challenge migration safety, invariant preservation, compatibility, unnecessary abstraction, missing prerequisites and inadequate tests. Reject superficial plans that leave a confirmed root cause intact. Also reject gratuitous rewrites. ACCEPT means an assessed plan, not an implemented or runtime-verified system.'})
    for revision_round in range(2):
        if plan_challenge['assessment']=='ACCEPT':break
        design=jobs.run_job('design-revision-'+str(revision_round),'design',{'challenge':plan_challenge,'finding_index':index,'revision':state['revision'],'task':'Read the current target architecture and roadmap. Resolve each plan challenge through evidence-backed design, not reassurances. Return complete corrected tasks, dispositions, gates and target architecture. Preserve identity where possible and keep gates unexecuted.'},verify_design)
        expose('target-architecture.json',design['target_architecture'])
        expose('roadmap.json',{'schema_version':1,'revision':state['revision'],'tasks':design['tasks'],'dispositions':design['dispositions']})
        expose('gates.json',design['gates'])
        state['unknowns']+=design['unknowns']
        plan_challenge=jobs.run_job('plan-recheck-'+str(revision_round),'challenge',{'previous_challenge':plan_challenge,'task':'Re-read roadmap.json, target-architecture.json and affected source. ACCEPT only when the revised design resolves the substantive challenges without unsupported claims.'})
    expose('plan-challenge.json',plan_challenge)
    for name,result in [('diagnosis',challenge),('plan',plan_challenge)]:
        if result['assessment']=='REVISE':state['unknowns'].append(name+' challenge unresolved: '+result['rationale'])
    state['unknowns']=list(dict.fromkeys(state['unknowns']));write(run/'run.json',state)
    result=check(run);state['completion']=result['computed_audit_completion'];write(run/'run.json',state)
    result,progress,plan=render_report(run)
    with (run/'report.md').open('a') as file:
        for title,data in [('Target architecture and migration',design['target_architecture']),('Diagnosis challenge',challenge),('Plan challenge',plan_challenge)]:file.write('\n\n## '+title+'\n\n```json\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n```\n')
    final={'status':'COMPLETE' if progress['stage']=='AUDIT_AND_PLAN_READY' else 'PARTIALLY_COMPLETE','revision':state['revision'],'audit':result,'plan':plan,'workflow':progress['stage'],'report':str(run/'report.md'),'model_calls_this_run':len(jobs.metrics),'production_readiness':'NOT_ASSESSED','remediation':'NOT_REQUESTED','at':now()}
    from .reporting import render_deliverables
    render_deliverables(run,model,design,findings,plan,challenge,plan_challenge,final)
    write(run/'engine-state.json',final)
    (run/'ENGINE-STATUS.md').write_text('# Engine status\n\n'+json.dumps(final,ensure_ascii=False,indent=2)+'\n')
    return final
