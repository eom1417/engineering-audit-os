"""Surface/evidence record rules; independent of workflow orchestration."""
from .workspace import read

def meaningful(value):
    return isinstance(value,str) and bool(value.strip()) and value.strip().upper() not in {'REPLACE','TODO','TBD','UNKNOWN','NOT_ASSESSED'}

def surface_check(run,state):
    """A file-ledger complements, and never replaces, flow/control coverage."""
    inv=read(run/'inventory.json');rows=read(run/'surface-review.json');errors=[];gaps=[]
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):return ['surface-review must be an array of objects'],[]
    paths={f['path'] for f in inv['files']};ev={e['id']:e for e in read(run/'evidence.json')};seen=set()
    for r in rows:
        p=r.get('path')
        if not isinstance(p,str):errors.append('Surface requires string path');continue
        if p not in paths or p in seen:errors.append('Unknown or duplicate surface '+p)
        seen.add(p)
        if r.get('revision')!=state['revision']:errors.append('Stale surface '+p)
        if r.get('status') not in {'reviewed','excluded','blocked'}:errors.append('Invalid surface status '+p)
        if not meaningful(r.get('rationale')):errors.append('Missing surface rationale '+p)
        refs=r.get('evidence_ids')
        if not isinstance(refs,list) or not all(isinstance(e,str) for e in refs):errors.append('Invalid surface evidence '+p);continue
        if r.get('status')=='reviewed' and not refs:errors.append('Reviewed surface without evidence '+p)
        if any(e not in ev for e in refs):errors.append('Unknown surface evidence '+p)
        if r.get('status')=='reviewed' and not any(
            isinstance(ev.get(e,{}).get('source_ref'),dict) and ev[e]['source_ref'].get('path')==p
            or ev.get(e,{}).get('location')==p
            or str(ev.get(e,{}).get('location','')).startswith(p+':')
            for e in refs
        ):errors.append('Reviewed surface lacks evidence at its path '+p)
        if r.get('status')=='blocked':gaps.append('Blocked surface '+p)
        if r.get('status')=='excluded' and p not in state['scope'].get('approved_exclusions',[]):gaps.append('Surface exclusion not declared in scope '+p)
    gaps+=['Unreviewed surface '+p for p in sorted(paths-seen)]
    return errors,gaps


