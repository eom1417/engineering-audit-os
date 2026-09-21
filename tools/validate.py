"""Validate framework references and consistency; not an engineering scanner."""
from fnmatch import fnmatch
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R))
from eaos.cli import check

PACKAGED_ROOTS=['core','modules','schemas']
PACKAGED_TOP=['controls.json','sources.json','START-HERE.md']


def expected_package_files(root):
    """The set that MUST be packaged, derived from canonical sources — not from what happens to exist."""
    root=Path(root);expected=set(PACKAGED_TOP)
    for module in json.loads((root/'controls.json').read_text())['modules']:expected.add('modules/'+module['id']+'.md')
    for folder in PACKAGED_ROOTS:
        for path in sorted((root/folder).iterdir()):
            if path.is_file():expected.add(folder+'/'+path.name)
    return expected


def package_data_patterns(root):
    try:import tomllib
    except ImportError:return None
    config=tomllib.loads((Path(root)/'pyproject.toml').read_text())
    return config.get('tool',{}).get('setuptools',{}).get('package-data',{}).get('eaos')


def packaged_errors(root,data=None):
    root=Path(root);data=Path(data) if data else root/'eaos/data'
    errors=[]
    if not data.is_dir():return ['Packaged data directory is absent: '+str(data)]
    expected=expected_package_files(root)
    present={path.relative_to(data).as_posix() for path in data.rglob('*') if path.is_file()}
    errors+=['Missing packaged file '+rel for rel in sorted(expected-present)]
    errors+=['Unexpected packaged file '+rel for rel in sorted(present-expected)]
    errors+=['Stale packaged copy '+rel for rel in sorted(expected&present) if (root/rel).read_bytes()!=(data/rel).read_bytes()]
    patterns=package_data_patterns(root)
    if patterns is not None:
        for rel in sorted(expected):
            if not any(fnmatch(rel,pattern.split('data/',1)[-1] if pattern.startswith('data/') else pattern) for pattern in patterns):
                errors.append('Packaging pattern does not include '+rel)
    return errors


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
    errors+=packaged_errors(R)
    # An invariant a docstring asserts and no test enforces is an intention, not a guarantee.
    from invariants import check as invariant_check, extract, load_register, merge
    register=merge(extract(),load_register())
    unenforced=invariant_check(register)
    errors+=unenforced
    print(json.dumps({'modules':len(data['modules']),'controls':len(ids),'sources':len(sources),
                      'invariants':len(register['invariants']),'unenforced_invariants':len(unenforced),
                      'errors':errors},ensure_ascii=False,indent=2))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
