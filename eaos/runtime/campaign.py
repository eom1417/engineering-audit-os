"""Iterative isolated remediation: implement → verify → fresh full audit → next task."""
from pathlib import Path
import shutil
from argparse import Namespace
from ..workspace import read,write,load_run
from .pipeline import execute
from .remediate import implement


def improve(path,out,checks,provider,budget=96000,max_rounds=8,max_steps=10):
    original,state=load_run(path);destination=Path(out).resolve();target=Path(state['target'])
    if destination.exists() or destination==target or target in destination.parents:raise ValueError('Campaign output must be new and outside the target')
    if not 1<=max_steps<=100:raise ValueError('Campaign max steps must be 1–100')
    destination.mkdir(parents=True);current=original;history=[]
    def finish(status,reason,project):
        result={'status':status,'reason':reason,'original_audit':str(original),'latest_audit':str(current),'project':str(project),'steps':history,'original_repository_modified':False}
        write(destination/'campaign.json',result)
        (destination/'CAMPAIGN.md').write_text('# Remediation campaign\n\nStatus: '+status+'\n\n'+reason+'\n\nLatest project: '+str(project)+'\nLatest audit: '+str(current)+'\n')
        return result
    for index in range(max_steps):
        tasks=read(current/'roadmap.json')['tasks'];byid={t['id']:t for t in tasks}
        candidates=[t for t in tasks if t['kind']=='remediate' and t['status']!='verified' and all(byid[d]['status']=='verified' for d in t['depends_on'])]
        findings=read(current/'findings.json')
        remaining=[f for f in findings if f['status'] not in {'verified_closed','false_positive','duplicate'}]
        current_state=read(current/'run.json')
        if not candidates:
            if not remaining and current_state['completion']=='COMPLETE':return finish('COMPLETE','No unresolved findings in the latest re-audited scope.',current_state['target'])
            return finish('PARTIALLY_COMPLETE','Remaining findings need investigation, an explicit disposition, or prerequisite work; no invented closure.',current_state['target'])
        candidates.sort(key=lambda t:(t['priority'],t['id']));task=candidates[0]
        result=implement(current,task['id'],destination/f'step-{index+1:03d}',checks,provider,budget,max_rounds)
        history.append({'task':task['id'],'input_audit':str(current),'result':result['status'],'project':result['project']})
        write(destination/'campaign-progress.json',history)
        if result['status']!='VERIFIED_IN_ISOLATED_COPY':return finish('PARTIALLY_COMPLETE','Verification or re-audit did not accept the candidate; inspect preserved changes and evidence.',result['project'])
        if not Path(result['patch']).read_text().strip():return finish('PARTIALLY_COMPLETE','Task produced no source changes; refusing an unproductive repair loop.',result['project'])
        next_run=destination/f'audit-{index+1:03d}'
        from ..cli import init
        from ..workflow import initialize
        limits=read(current/'inventory.json')['limits']
        init(Namespace(target=result['project'],out=str(next_run),profile=current_state['profile'],max_files=limits['max_files'],max_bytes=limits['max_bytes']))
        initialize(next_run)
        # Reuse only source-inspection jobs keyed by actual source content; semantic/global stages rerun.
        (next_run/'jobs').mkdir(exist_ok=True)
        for p in (current/'jobs').glob('inspect-*.json') if (current/'jobs').exists() else []:
            if not p.is_symlink() and not p.name.endswith('-invalid.json'):shutil.copy2(p,next_run/'jobs'/p.name)
        write(next_run/'decisions.json',[{'id':'PREDECESSOR','previous_audit':str(current),'remediation_task':task['id'],'verification':str(Path(result['patch']).parent/'verification/result.json'),'note':'Historical context only. Source evidence and global architecture are revalidated for this new snapshot.'}])
        execute(next_run,provider,budget,max_rounds);current=next_run
    return finish('PARTIALLY_COMPLETE','Configured campaign step limit reached; inspect current plan before increasing the bound.',read(current/'run.json')['target'])
