"""Explicit remediation in a separate copy, baseline/post checks and source re-audit."""
import difflib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from ..workspace import read,write,load_run,inventory,fresh,digest,SENSITIVE,run_lock
from ..workflow import roadmap_check
from .context import Context,redact
from .jobs import Jobs


def check_commands(config,required):
    if not isinstance(config,dict) or not isinstance(config.get('checks'),list):raise ValueError('Checks config requires checks array')
    ids=[]
    for check in config['checks']:
        if not isinstance(check,dict) or not isinstance(check.get('id'),str):raise ValueError('Check requires string ID')
        argv=check.get('argv')
        if not isinstance(argv,list) or not argv or any(not isinstance(a,str) or not a for a in argv):raise ValueError('Check argv must be a nonempty string array')
        seconds=check.get('timeout_seconds',120)
        if type(seconds) is not int or not 1<=seconds<=600:raise ValueError('Check timeout must be 1–600 seconds')
        cwd=Path(check.get('cwd','.'))
        if cwd.is_absolute() or '..' in cwd.parts:raise ValueError('Check cwd must remain in the isolated copy')
        ids.append(check['id'])
    if len(set(ids))!=len(ids) or not set(required).issubset(ids):raise ValueError('Every predeclared task gate needs a unique configured command')
    inherited=config.get('inherit_env',[])
    if not isinstance(inherited,list) or not all(isinstance(x,str) for x in inherited):raise ValueError('inherit_env must be an array of names')
    for rel in ephemeral_paths(config):
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise ValueError('ephemeral_paths must be relative paths inside the isolated copy')
    return config['checks']


# Generated artifacts a verification command may legitimately create. The policy is declared,
# never inferred: anything outside it counts as a real change to the candidate.
EPHEMERAL_DIRS={'__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.tox','.nox','.cache','htmlcov','.coverage_cache','node_modules','.git','.venv','venv','.eggs'}
EPHEMERAL_SUFFIXES=('.pyc','.pyo','.pyd')
EPHEMERAL_NAMES={'.coverage'}


def ephemeral_paths(config):
    declared=config.get('ephemeral_paths',[]) if isinstance(config,dict) else []
    if not isinstance(declared,list) or not all(isinstance(x,str) and x.strip() for x in declared):raise ValueError('ephemeral_paths must be an array of relative path strings')
    return [x.strip('/') for x in declared]


def ignored(rel,declared):
    parts=rel.split('/')
    if set(parts)&EPHEMERAL_DIRS or parts[-1] in EPHEMERAL_NAMES or rel.endswith(EPHEMERAL_SUFFIXES):return True
    if any(part.endswith('.egg-info') for part in parts):return True
    return any(rel==x or rel.startswith(x+'/') for x in declared)


def tree_state(root,declared=()):
    """Complete path→content state of the isolated copy; unknown new paths are visible, not only known ones."""
    state={}
    for path in sorted(Path(root).rglob('*')):
        rel=path.relative_to(root).as_posix()
        if ignored(rel,declared):continue
        if path.is_symlink():state[rel]='symlink:'+digest(str(path.readlink()).encode())
        elif path.is_file():state[rel]=digest(path.read_bytes())
    return state


def tree_diff(before,after):
    added=sorted(set(after)-set(before));removed=sorted(set(before)-set(after))
    modified=sorted(rel for rel in set(before)&set(after) if before[rel]!=after[rel])
    return {'added':added,'removed':removed,'modified':modified}


def diff_paths(diff):return sorted(set(diff['added'])|set(diff['removed'])|set(diff['modified']))


def describe_diff(diff):
    return '; '.join(f'{label}: '+', '.join(diff[label]) for label in ['added','removed','modified'] if diff[label])


def run_checks(root,config,phase):
    results=[]
    env={k:v for k,v in os.environ.items() if k in {'PATH','SystemRoot','WINDIR','TMPDIR','TEMP','TMP','LANG'} or k in config.get('inherit_env',[])}
    for check in config['checks']:
        cwd=(root/check.get('cwd','.')).resolve()
        if cwd!=root and root not in cwd.parents:raise ValueError('Check cwd escaped isolated copy')
        start=time.monotonic();timed_out=False;raw=b''
        with tempfile.TemporaryFile() as output:
            try:
                proc=subprocess.Popen(check['argv'],cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,shell=False,start_new_session=(os.name=='posix'))
                try:code=proc.wait(timeout=check.get('timeout_seconds',120))
                except subprocess.TimeoutExpired:
                    timed_out=True
                    if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
                    else:proc.kill()
                    proc.wait();code=None
                output.seek(0);raw=output.read(200_001)
                text=redact(raw[:200_000].decode('utf-8',errors='replace'))
            except OSError:
                code=None;text='Configured check could not start; inspect argv and local tools.'
        results.append({'id':check['id'],'argv':check['argv'],'cwd':check.get('cwd','.'),'phase':phase,'exit_code':code,'timed_out':timed_out,'duration_seconds':round(time.monotonic()-start,3),'status':'pass' if code==0 and not timed_out else 'fail','output':text,'output_truncated':len(raw)>200_000 if 'raw' in locals() else False})
    return results


def validated_edits(edits,allowed,root):
    seen=set();validated=[]
    for edit in edits:
        rel=edit['path'];p=Path(rel)
        if rel not in allowed or p.is_absolute() or '..' in p.parts or rel in seen:raise ValueError('Edit outside planned task paths or duplicate edit')
        if any(SENSITIVE.search(part) for part in p.parts):raise ValueError('Sensitive path edits prohibited')
        target=root/p
        if any(parent.is_symlink() for parent in [target,*target.parents] if parent!=root and root in parent.parents):raise ValueError('Symlink edit prohibited')
        resolved=target.resolve()
        if root not in resolved.parents:raise ValueError('Edit escaped isolated copy')
        if edit['content'] is not None and len(edit['content'].encode())>2_000_000:raise ValueError('Generated file too large')
        if target.exists() and not target.is_file():raise ValueError('Edit target is not a file')
        seen.add(rel);validated.append((target,edit['content']))
    return validated


def implement(path,task_id,out,checks_path,provider,budget=96000,max_rounds=8):
    with run_lock(path):
        return _implement(path,task_id,out,checks_path,provider,budget,max_rounds)


def _implement(path,task_id,out,checks_path,provider,budget=96000,max_rounds=8):
    run,state=load_run(path);inv=read(run/'inventory.json')
    if not fresh(state,inv)[0]:raise ValueError('Audit source changed; review current source first')
    readiness=roadmap_check(run,state)
    if not readiness['ready']:raise ValueError('Plan has unresolved contract errors or gaps')
    tasks=read(run/'roadmap.json')['tasks'];task=next((t for t in tasks if t['id']==task_id),None)
    if not task or task['kind']!='remediate':raise ValueError('Choose a confirmed remediation task')
    # One contract for both planners: an investigation, a blocked repair, or a record too old to
    # interpret is refused here rather than executed on trust.
    from ..decision_bridge import executable
    allowed,verdict=executable(task,read(run/'findings.json'),read(run/'gates.json'))
    if not allowed:raise ValueError('The decision contract refuses this task: '+'; '.join(verdict['refusals']))
    byid={t['id']:t for t in tasks}
    if any(byid[dep]['status']!='verified' for dep in task['depends_on']):raise ValueError('Task prerequisites are not verified')
    config=read(checks_path);check_commands(config,task['required_gate_ids'])
    destination=Path(out).resolve();source=Path(state['target'])
    if destination.exists() or destination==source or source in destination.parents:raise ValueError('Use a new output directory outside the original repository')
    destination.mkdir(parents=True);project=destination/'project';project.mkdir();records=destination/'verification';records.mkdir()
    for item in inv['files']:
        if item['capture']!='hashed':continue
        from ..workspace import safe_file
        try:original=safe_file(source,item['path'])
        except ValueError:continue
        if digest(original.read_bytes())!=item['sha256']:raise ValueError('Source changed while copying')
        target=project/item['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target)
    manifest={f['path']:f['sha256'] for f in inv['files'] if f['capture']=='hashed' and (project/f['path']).is_file()}
    declared=ephemeral_paths(config);copied=tree_state(project,declared)
    baseline=run_checks(project,config,'baseline');write(records/'baseline.json',baseline)
    if any(r['status']!='pass' for r in baseline):
        result={'status':'BASELINE_FAILED','project':str(project),'checks':baseline,'original_target_unchanged':fresh(state,inv)[0]};write(records/'result.json',result);return result
    baseline_drift=tree_diff(copied,tree_state(project,declared))
    if diff_paths(baseline_drift):raise ValueError('Baseline check modified source; inspect isolated copy before proceeding — '+describe_diff(baseline_drift))
    context=Context(run,state,budget);jobs=Jobs(records,context,provider,budget,max_rounds)
    # Records and retrieval are from the original audit; source edits are only written into project.
    for name in ['architecture.json','findings.json','roadmap.json','target-architecture.json','flows.json']:
        if (run/name).exists():write(records/name,read(run/name));jobs.catalog.add(name)
    initial=[]
    for rel in task['files']:
        if rel in context.files:
            lines=context.lines(rel)
            if lines:initial.append(context.source(rel,1,min(len(lines),80)))
    before={rel:(project/rel).read_text() if (project/rel).is_file() else None for rel in task['files']}
    feedback={};checks=[];accepted=False
    for attempt in range(3):
        def verify_repair(r):
            errors=[]
            if not r['edits']:return ['At least one concrete edit is required']
            try:validated_edits(r['edits'],set(task['files']),project)
            except ValueError as exc:errors.append(str(exc))
            for edit in r['edits']:
                rel=edit['path']
                if rel not in context.files:continue
                count=len(context.lines(rel));ranges=[]
                for eid in context.seen:
                    ref=context.evidence[eid]['source_ref']
                    if ref['path']==rel:ranges.append((ref['start_line'],ref['end_line']))
                last=0
                for start,end in sorted(ranges):
                    if start>last+1:break
                    last=max(last,end)
                if last<count:errors.append('Read all existing source before replacing '+rel+'; uncovered lines after '+str(last))
            return errors
        result=jobs.run_job('repair-'+str(attempt),'repair',{'task':task,'source_blocks':initial,'feedback':feedback,'task_instructions':'Implement the actual root-cause correction, preserving the invariant and compatibility. Return full file contents only for task.files, including tests where planned. Read full files before replacing them. Never change a check to conceal failure; never return placeholders. Source tools reference the original audit. Current candidate contents are in feedback on retries.'},verify_repair)
        edits=validated_edits(result['edits'],set(task['files']),project)
        for p,content in edits:
            if content is None:p.unlink(missing_ok=True)
            else:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf-8')
        prepared=tree_state(project,declared)
        planned=tree_diff(copied,prepared)
        unplanned=sorted(set(diff_paths(planned))-set(task['files']))
        checks=run_checks(project,config,'post-change-'+str(attempt))
        drift=tree_diff(prepared,tree_state(project,declared))
        if diff_paths(drift):checks.append({'id':'SOURCE-INTEGRITY','phase':'post-change-'+str(attempt),'status':'fail','exit_code':None,'output':'Verification commands changed the isolated copy after the candidate was prepared — '+describe_diff(drift)})
        if unplanned:checks.append({'id':'PLAN-CONFORMANCE','phase':'post-change-'+str(attempt),'status':'fail','exit_code':None,'output':'Isolated copy differs from the original outside the planned task files: '+', '.join(unplanned)})
        write(records/('checks-'+str(attempt)+'.json'),checks)
        if all(c['status']=='pass' for c in checks):accepted=True;break
        feedback={'failed_checks':[c for c in checks if c['status']!='pass'],'candidate_files':{rel:(project/rel).read_text() if (project/rel).is_file() else None for rel in task['files']}}
    # The patch is derived from the real difference between the original copy and the delivered
    # candidate, so a change the plan did not anticipate cannot stay invisible in the delivery.
    from ..workspace import safe_file
    changed=tree_diff(copied,tree_state(project,declared));patch='';unrepresented=[]
    for rel in diff_paths(changed):
        previous=before.get(rel)
        if previous is None and rel in manifest:
            try:previous=safe_file(source,rel).read_text(encoding='utf-8')
            except (ValueError,OSError,UnicodeError):unrepresented.append(rel);continue
        current=None
        if (project/rel).is_file():
            try:current=(project/rel).read_text(encoding='utf-8')
            except UnicodeError:unrepresented.append(rel);continue
        if previous==current:unrepresented.append(rel);continue
        patch+=''.join(difflib.unified_diff((previous or '').splitlines(keepends=True),(current or '').splitlines(keepends=True),fromfile='a/'+rel if previous is not None else '/dev/null',tofile='b/'+rel if current is not None else '/dev/null'))
    (destination/'changes.patch').write_text(patch)
    patch_complete=not unrepresented
    if not patch_complete:checks.append({'id':'PATCH-COMPLETENESS','phase':'delivery','status':'fail','exit_code':None,'output':'changes.patch does not represent every difference in the isolated copy: '+', '.join(unrepresented)})
    assessment=None
    if accepted:
        changed_inventory=inventory(project,**inv['limits']);newstate=dict(state,target=str(project),revision=changed_inventory['fingerprint'])
        write(records/'inventory.json',changed_inventory);write(records/'evidence.json',[])
        newcontext=Context(records,newstate,budget);newjobs=Jobs(records,newcontext,provider,budget,max_rounds)
        newjobs.catalog={'architecture.json','findings.json','roadmap.json'}
        blocks=[]
        for rel in task['files']:
            if rel in newcontext.files:
                lines=newcontext.lines(rel)
                if lines:blocks.append(newcontext.source(rel,1,min(len(lines),80)))
        assessment=newjobs.run_job('re-audit','reaudit',{'task':task,'changed_source':blocks,'actual_checks':checks,'task_instructions':'Re-audit the changed invariant and adjacent contracts. Read full affected source when needed. Test success alone does not prove root-cause repair. ACCEPT only if source supports resolution without a new boundary or behavior defect. Old architecture/findings are historical context; source reads reference the changed copy.'})
    original_unchanged=fresh(state,inv)[0]
    verified=accepted and patch_complete and assessment is not None and assessment['assessment']=='ACCEPT' and original_unchanged
    result={'status':'VERIFIED_IN_ISOLATED_COPY' if verified else 'NEEDS_REVIEW','task_id':task_id,'project':str(project),'patch':str(destination/'changes.patch'),'changed_paths':changed,'patch_complete':patch_complete,'baseline':baseline,'post_checks':checks,'re_audit':assessment,'original_target_unchanged':original_unchanged,'limits':'Checks were actually executed in a separate copy, not an OS sandbox. No deployment performed; original audit records remain historical and are not relabeled as repaired.'}
    write(records/'result.json',result)
    (destination/'RESULT.md').write_text('# Remediation result\n\n```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```\n')
    return result
