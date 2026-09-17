"""Validate framework references and consistency; not an engineering scanner."""
from pathlib import Path
import json
import sys
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from eaos.cli import check

def main():
    if len(sys.argv)>1:
        result=check(sys.argv[1]);print(json.dumps(result,ensure_ascii=False,indent=2));return bool(result['errors'])
    data=json.loads((R/'controls.json').read_text());src=json.loads((R/'sources.json').read_text())
    source_rows=src if isinstance(src,list) else src['sources']
    sources={s['id'] for s in source_rows};ids=set();errors=[]
    for m in data['modules']:
        if not (R/'modules'/f"{m['id']}.md").exists():errors.append('Missing module '+m['id'])
        for c in m['controls']:
            if c['id'] in ids:errors.append('Duplicate '+c['id'])
            ids.add(c['id'])
            for key in ['invariant','procedure','verification','counter_evidence','evidence_required']:
                if not c.get(key):errors.append('Missing '+key+' '+c['id'])
            for sid in c['source_ids']+c['seed_refs']:
                if sid not in sources:errors.append('Unknown source '+sid)
    for p in (R/'eaos/data').rglob('*'):
        if p.is_file():
            original=R/p.relative_to(R/'eaos/data')
            if not original.exists() or original.read_bytes()!=p.read_bytes():errors.append('Stale packaged copy '+str(p.relative_to(R)))
    print(json.dumps({'modules':len(data['modules']),'controls':len(ids),'sources':len(sources),'errors':errors},ensure_ascii=False,indent=2))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
