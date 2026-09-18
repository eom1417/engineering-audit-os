"""Readable architecture/decision/implementation artifacts from canonical records."""
import json
from pathlib import Path


def render_deliverables(run,model,design,findings,plan,diagnosis,challenge,status):
    run=Path(run)
    def bullet(values):return '\n'.join('- '+str(v) for v in values)
    def save(name,parts):(run/name).write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
    def value(obj,key):return str(obj.get(key,''))
    nodes=model['nodes'];ids={n['id']:'n'+str(i) for i,n in enumerate(nodes)}
    graph=['flowchart TD']
    for n in nodes:
        label=(n['name']+' / '+n['responsibility'])[:180].replace('"',"'").replace('\n',' ').replace('<','(').replace('>',')')
        graph.append(f'  {ids[n["id"]]}["{label}"]')
    for edge in model['edges']:
        connector='-.->' if edge['status']=='HYPOTHESIS' else '-->'
        graph.append(f'  {ids[edge["from"]]} {connector}|{edge["relation"]}| {ids[edge["to"]]}')
    (run/'architecture.mmd').write_text('\n'.join(graph)+'\n')
    parts=['# Observed architecture','Source-derived assessment. Hypothesis edges use dotted arrows. Runtime and deployment facts require their own evidence.','```mermaid\n'+'\n'.join(graph)+'\n```']
    for n in nodes:parts+=['## '+n['name'],n['responsibility'],bullet([k+': '+value(n,k) for k in ['domain','boundary','owner','paths','evidence_ids']])]
    parts+=['## Contracts','```json\n'+json.dumps(model['contracts'],ensure_ascii=False,indent=2)+'\n```','## Business rules','```json\n'+json.dumps(model['business_rules'],ensure_ascii=False,indent=2)+'\n```','## Change scenarios','```json\n'+json.dumps(model['change_scenarios'],ensure_ascii=False,indent=2)+'\n```']
    save('ARCHITECTURE.md',parts)
    target=design['target_architecture'];parts=['# Target architecture and migration',target['retained_structure']]
    components=target['components'];target_ids={c['id']:'t'+str(i) for i,c in enumerate(components)};target_graph=['flowchart TD']
    for c in components:
        label=(c['name']+' / '+c['change']).replace('"',"'").replace('<','(').replace('>',')').replace('\n',' ')
        target_graph.append(f'  {target_ids[c["id"]]}["{label}"]')
    for c in components:
        for dep in c['depends_on']:target_graph.append(f'  {target_ids[c["id"]]} --> {target_ids[dep]}')
    (run/'target-architecture.mmd').write_text('\n'.join(target_graph)+'\n')
    parts+=['```mermaid\n'+'\n'.join(target_graph)+'\n```','## Target components and contracts','```json\n'+json.dumps(components,ensure_ascii=False,indent=2)+'\n```']
    for adr in target['decisions']:
        parts+=['## '+value(adr,'id'),value(adr,'problem')]
        for key in ['finding_ids','evidence_ids','options','chosen','tradeoffs','target_boundaries','migration_steps','compatibility','rollback','success_measures']:
            parts+=['### '+key,bullet(adr[key]) if isinstance(adr.get(key),list) else value(adr,key)]
    save('TARGET-ARCHITECTURE.md',parts)
    tasks={t['id']:t for t in design['tasks']};parts=['# Ordered implementation plan','No task is executed by this report. Use the explicit implement command with configured verification checks.','Order: '+', '.join(plan['order'])]
    for tid in plan['order']:
        t=tasks[tid];parts+=['## '+tid+' — '+t['title']]
        for key,val in t.items():
            if key not in {'id','title'}:parts+=['### '+key,bullet(val) if isinstance(val,list) else str(val)]
    parts+=['## Deferred/no-change decisions','```json\n'+json.dumps(design['dispositions'],ensure_ascii=False,indent=2)+'\n```']
    save('IMPLEMENTATION-PLAN.md',parts)
    parts=['# Executive assessment','Status: '+status['status'],'Findings: '+str(len(findings))+'; planned tasks: '+str(len(tasks)), '## Structural findings']
    for f in sorted(findings,key=lambda f:(f['priority'],f['id'])):
        parts+=['### '+f['id']+' — '+f['subcategory'],f['current_behavior'],'Root cause: '+f['root_cause'],'Impact: '+f['why_this_matters'],'Proposed response: '+f['recommended_remediation'],'Evidence: '+', '.join(f['evidence_ids'])]
    parts+=['## Diagnosis challenge',diagnosis['assessment']+': '+diagnosis['rationale'],'## Migration challenge',challenge['assessment']+': '+challenge['rationale'],'## Readiness','A completed audit/plan does not mean remediation completed or production certified. Consult report.md for coverage, exclusions, evidence and unresolved facts.']
    save('EXECUTIVE.md',parts)
