"""Audit-record consistency and completion gates, separate from CLI dispatch."""
from pathlib import Path
import re
from .workspace import read, load_run, registry, controls, DATA, fresh, safe_file, digest
from . import architecture as arch

GATE_STATES = {'pass','fail','blocked','not_run','not_applicable'}
COVER_STATES = {'pass','fail','blocked','not_run','not_applicable'}

SUPPORTED_KEYWORDS={'type','enum','const','properties','required','additionalProperties','items',
                    'minLength','maxLength','pattern','minItems','maxItems','minimum','maximum','description',
                    '$schema','$id','title','format','anyOf'}

# Contract checks deliberately limited to record consistency, never proof of real-world behavior.
# Keywords outside SUPPORTED_KEYWORDS are reported rather than ignored: a constraint nobody enforces
# is worse than no constraint, because the schema reads as a guarantee.
def schema_errors(value, spec, path='$'):
    errors=[]
    types={'object':dict,'array':list,'string':str,'null':type(None),'boolean':bool,'integer':int,'number':(int,float)}
    unsupported=sorted(set(spec)-SUPPORTED_KEYWORDS)
    if unsupported:errors.append(path+' schema uses unenforced keywords: '+', '.join(unsupported))
    expected=spec.get('type')
    allowed=expected if isinstance(expected,list) else [expected] if expected else []
    if allowed:
        if any(t=='integer' for t in allowed) and isinstance(value,bool):return [path+' invalid type']
        if not any(isinstance(value,types[t]) for t in allowed if t in types):return [path+' invalid type']
    if 'enum' in spec and value not in spec['enum']:errors.append(path+' invalid enum')
    if 'const' in spec and value!=spec['const']:errors.append(path+' must equal '+repr(spec['const']))
    if isinstance(value,str):
        if len(value)<spec.get('minLength',0):errors.append(path+' empty text')
        if 'maxLength' in spec and len(value)>spec['maxLength']:errors.append(path+' longer than '+str(spec['maxLength']))
        if 'pattern' in spec and not re.search(spec['pattern'],value):errors.append(path+' does not match '+spec['pattern'])
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if 'minimum' in spec and value<spec['minimum']:errors.append(path+' below minimum')
        if 'maximum' in spec and value>spec['maximum']:errors.append(path+' above maximum')
    if isinstance(value,list):
        if len(value)<spec.get('minItems',0):errors.append(path+' needs at least '+str(spec['minItems'])+' items')
        if 'maxItems' in spec and len(value)>spec['maxItems']:errors.append(path+' has more than '+str(spec['maxItems'])+' items')
    if isinstance(value,dict):
        for key in spec.get('required',[]):
            if key not in value:errors.append(path+' missing '+key)
        props=spec.get('properties',{})
        for key,v in value.items():
            if key in props:errors+=schema_errors(v,props[key],path+'.'+key)
            elif spec.get('additionalProperties') is False:errors.append(path+' unexpected '+key)
    if isinstance(value,list) and 'items' in spec:
        for i,v in enumerate(value):errors+=schema_errors(v,spec['items'],path+f'[{i}]')
    return errors

def check(run,check_target=True):
    run,state=load_run(run); errors=[]; gaps=[]
    def need(test,msg):
        if not test:errors.append(msg)
    cs=controls();modules={m['id']:m for m in registry()['modules']}
    findings=read(run/'findings.json');coverage=read(run/'coverage.json');evidence=read(run/'evidence.json');gates=read(run/'gates.json')
    for name,rows in [('findings',findings),('coverage',coverage),('evidence',evidence),('gates',gates),('module_decisions',state.get('module_decisions'))]:
        if not isinstance(rows,list) or not all(isinstance(r,dict) for r in rows):
            raise ValueError(name+' must be an array of objects')
    for rows in [findings,coverage,evidence,gates,state['module_decisions']]:
        for row in rows:
            for key in ['evidence_ids','verification_ids','required_gate_ids','control_ids','finding_ids']:
                if key in row and (not isinstance(row[key],list) or not all(isinstance(x,str) for x in row[key])):raise ValueError(key+' must be an array of strings')
    if not isinstance(state.get('expected_instances'),list) or not all(isinstance(x,str) for x in state['expected_instances']):raise ValueError('Invalid expected_instances')
    def indexed(rows,label):
        need(isinstance(rows,list),label+' must be array')
        result={}
        for row in rows:
            need(isinstance(row,dict) and bool(row.get('id')),label+' missing id')
            if not isinstance(row,dict) or not row.get('id'):continue
            need(row['id'] not in result,label+' duplicate id '+row['id']);result[row['id']]=row
        return result
    ev=indexed(evidence,'evidence');gs=indexed(gates,'gates');fs=indexed(findings,'findings');cov=indexed(coverage,'coverage')
    for e in evidence:
        for key in ['id','kind','location','revision','observed_at','observation','method','limitations']:
            need(bool(e.get(key)),f"Evidence {e.get('id')} missing {key}")
        need(e.get('revision')==state['revision'],f"Evidence {e.get('id')} stale revision")
        need(e.get('kind') in ['source','runtime','test','configuration','requirement','external','absence_search'],f"Evidence {e.get('id')} invalid kind")
        if e.get('kind')=='absence_search':
            need(all(e.get(k) for k in ['search_scope','queries','shared_controls_checked','remaining_unknowns']),f"Evidence {e.get('id')} insufficient absence search")
        if e.get('method')=='source_range_capture' or 'source_ref' in e:
            ref=e.get('source_ref',{})
            try:
                if not isinstance(ref,dict):raise ValueError('Invalid source reference')
                start,end=ref['start_line'],ref['end_line']
                if type(start) is not int or type(end) is not int:raise ValueError('Invalid line range')
                item=next((f for f in read(run/'inventory.json')['files'] if f['path']==ref['path']),None)
                if not item or item['capture']!='hashed' or item['sha256']!=ref['sha256']:raise ValueError('Source hash not in inventory')
                if check_target:
                    raw=safe_file(Path(state['target']),ref['path']).read_bytes()
                    lines=raw.decode('utf-8').splitlines(keepends=True)
                    if digest(raw)!=ref['sha256'] or not 1<=start<=end<=len(lines):raise ValueError('Source changed or invalid range')
                    if digest(''.join(lines[start-1:end]).encode('utf-8'))!=ref['range_sha256']:raise ValueError('Range hash mismatch')
            except (KeyError,TypeError,ValueError,OSError,UnicodeError):
                errors.append('Invalid captured source evidence '+str(e.get('id')))
    for g in gates:
        if g.get('required_for_audit') and g.get('status') in ['blocked','not_run']:
            gaps.append(f"Required audit gate {g.get('id')} unresolved")
        need(g.get('status') in GATE_STATES,f"Gate {g.get('id')} invalid status")
        need(g.get('revision')==state['revision'],f"Gate {g.get('id')} stale revision")
        need(bool(g.get('rationale')),f"Gate {g.get('id')} missing rationale")
        if g.get('status') in ['pass','fail']:
            need(bool(g.get('evidence_ids')),f"Gate {g.get('id')} requires execution evidence")
        for eid in g.get('evidence_ids',[]):need(eid in ev,f'Unknown gate evidence {eid}')
    schema=read(DATA/'schemas/finding.schema.json')
    for f in findings:
        name=f.get('id','?')
        structural=schema_errors(f,schema,'finding.'+str(name))
        if structural:
            errors.extend(structural);continue
        for key in schema['required']:need(key in f,f'Finding {name} missing {key}')
        for key,spec in schema['properties'].items():
            if key not in f:continue
            value=f[key]
            if 'enum' in spec:need(value in spec['enum'],f'Finding {name} invalid {key}')
            if spec.get('type')=='string':need(isinstance(value,str) and len(value)>=spec.get('minLength',0),f'Finding {name} invalid text {key}')
            if spec.get('type')=='array':need(isinstance(value,list) and all(isinstance(v,str) for v in value),f'Finding {name} invalid array {key}')
        need(f.get('revision')==state['revision'],f'Finding {name} stale revision')
        need(isinstance(f.get('impacts'),dict) and all(k in f['impacts'] for k in schema['properties']['impacts']['required']),f'Finding {name} missing impacts')
        need(bool(f.get('control_ids')),f'Finding {name} requires control mapping')
        for cid in f.get('control_ids',[]):need(cid in cs,f'Unknown control {cid}')
        for eid in f.get('evidence_ids',[]):need(eid in ev,f'Unknown finding evidence {eid}')
        if f.get('claim_status') in ['CONFIRMED','HIGHLY_LIKELY']:need(bool(f.get('evidence_ids')),f'Finding {name} requires evidence')
        if f.get('claim_status')=='CONFIRMED':need(f.get('confidence') in ['HIGH','MEDIUM'],f'Confirmed finding {name} cannot have LOW confidence')
        if f.get('status')=='verified_closed':
            ids=f.get('verification_ids',[])
            need(bool(f.get('required_gate_ids')),f'Closed finding {name} requires predeclared gates')
            need(set(f.get('required_gate_ids',[])).issubset(set(ids)),f'Closed finding {name} omitted required gates')
            need(bool(ids),f'Closed finding {name} requires verification gates')
            for gid in ids:need(gid in gs and gs[gid].get('status')=='pass',f'Closed finding {name} has nonpassing gate {gid}')
            need(bool(f.get('required_tests')),f'Closed finding {name} requires regression test specification')
        if f.get('claim_status') in ['POSSIBLE','NOT_VERIFIED','HIGHLY_LIKELY'] and f.get('status') not in ['false_positive','duplicate']:
            gaps.append(f'Finding {name} unresolved hypothesis')
        if f.get('status')=='accepted_risk':need(bool(f.get('owner')) and bool(f.get('risk_expiry')),f'Accepted risk {name} requires owner and expiry')
        if f.get('status')=='duplicate':need(f.get('duplicate_of') in fs and f['duplicate_of']!=name,f'Invalid duplicate {name}')
    decisions=state.get('module_decisions',[]);ds={d.get('module_id'):d for d in decisions}
    need(len(ds)==len(decisions),'Duplicate module decisions')
    need(set(ds)==set(modules),'Every module needs an applicability decision')
    for mid,d in ds.items():
        need(d.get('applicability') in ['APPLICABLE','NOT_APPLICABLE','UNDECIDED','OUT_OF_SCOPE'],f'Module {mid} invalid applicability')
        if mid in arch.CORE_MODULES and d.get('applicability') in ['NOT_APPLICABLE','OUT_OF_SCOPE']:need(False,f'Mandatory module {mid} cannot be excluded')
        if d.get('applicability')=='UNDECIDED':gaps.append(f'Module {mid} undecided')
        elif d.get('applicability')!='OUT_OF_SCOPE' and (not d.get('reason') or not d.get('evidence_ids')):gaps.append(f'Module {mid} lacks applicability justification')
        if d.get('applicability')=='OUT_OF_SCOPE' and (state.get('profile')!='architecture' or not d.get('reason')):need(False,'Invalid profile exclusion '+str(mid))
        for eid in d.get('evidence_ids',[]):need(eid in ev,f'Unknown module evidence {eid}')
    expected=state.get('expected_instances',[])
    need(len(expected)==len(set(expected)),'Duplicate expected instances')
    need(set(expected)==set(cov),'Coverage instances differ from declared inventory')
    covered_controls=set()
    for c in coverage:
        cid=c.get('control_id');covered_controls.add(cid)
        need(cid in cs,f'Unknown coverage control {cid}')
        for key in ['component','flow','environment','revision','rationale']:need(bool(c.get(key)),f"Coverage {c.get('id')} missing {key}")
        need(c.get('revision')==state['revision'],f"Coverage {c.get('id')} stale revision")
        need(c.get('status') in COVER_STATES,f"Coverage {c.get('id')} invalid status")
        if c.get('status') in ['blocked','not_run']:gaps.append(f"Coverage {c.get('id')} unresolved")
        if c.get('status') in ['pass','fail','not_applicable']:
            need(bool(c.get('evidence_ids')),f"Coverage {c.get('id')} requires evidence")
        for eid in c.get('evidence_ids',[]):need(eid in ev,f'Unknown coverage evidence {eid}')
        if c.get('status')=='fail':
            need(bool(c.get('finding_ids')),f"Failed coverage {c.get('id')} needs finding")
        for fid in c.get('finding_ids',[]):need(fid in fs,f'Unknown coverage finding {fid}')
    for mid,d in ds.items():
        if d.get('applicability')=='APPLICABLE' and mid in modules:
            for c in modules[mid]['controls']:
                if c['id'] not in covered_controls:gaps.append('Uncovered applicable control '+c['id'])
    for flag in ['scope_confirmed','inventory_reviewed','architecture_reviewed','product_flows_reviewed']:
        if state.get(flag) is not True:gaps.append(flag+' is not confirmed')
    if not state.get('scope',{}).get('environments'):gaps.append('No environment scope')
    if state.get('unknowns'):gaps.append('Unresolved unknowns')
    inv=read(run/'inventory.json')
    model=read(run/'architecture.json')
    model_errors,model_gaps=arch.validate_model(model,ev,state['revision'],{f['path'] for f in inv['files']})
    errors.extend(model_errors);gaps.extend(model_gaps)
    need(state['revision']==inv['fingerprint'],'Run revision differs from inventory fingerprint')
    if inv['errors'] or inv['truncated']:gaps.append('Discovery incomplete')
    if check_target:
        ok,_=fresh(state,inv)
        if not ok:gaps.append('Target changed or unavailable snapshot; new run/revalidation required')
    if (run/'workflow.json').exists():
        from .surface_records import surface_check, meaningful
        surface_errors,surface_gaps=surface_check(run,state)
        errors.extend(surface_errors);gaps.extend(surface_gaps)
        for finding in findings:
            for field in ['current_behavior','expected_behavior','root_cause','why_this_matters','recommended_remediation','implementation_strategy']:
                if not meaningful(finding.get(field)):errors.append('Finding '+str(finding.get('id'))+' contains unfinished '+field)
    activity=bool(evidence or findings or coverage)
    computed='INCOMPLETE' if errors or not activity else 'PARTIALLY_COMPLETE' if gaps else 'COMPLETE'
    need(state.get('completion') in ['INCOMPLETE','PARTIALLY_COMPLETE','COMPLETE'],'Invalid claimed completion')
    if state.get('completion')=='COMPLETE' and computed!='COMPLETE':errors.append('False completion claim')
    return {'record_integrity':'INVALID' if errors else 'VALID','computed_audit_completion':computed,'claimed_completion':state.get('completion'),'errors':errors,'gaps':gaps,'limits':'Checks record consistency only. Evidence authenticity, exhaustive scope and engineering judgments require review; COMPLETE does not mean secure or ready for production.'}
