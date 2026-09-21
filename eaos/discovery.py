"""Bounded static observations, not semantic findings or a reconstructed architecture."""
from __future__ import annotations
import ast
from collections import Counter
import json
from pathlib import Path
import re
from .workspace import read, write, load_run, fresh, safe_file, digest, now, INFRA, STACKS
from .vocabulary import CONFIG, SOURCE, classify



def python_observations(text):
    tree=ast.parse(text);symbols=[];imports=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            symbols.append({'name':n.name,'kind':type(n).__name__,'line':n.lineno,'end_line':n.end_lineno})
        elif isinstance(n,ast.Import):
            imports.extend({'module':a.name,'names':[],'level':0,'line':n.lineno} for a in n.names)
        elif isinstance(n,ast.ImportFrom):
            imports.append({'module':n.module or '', 'names':[a.name for a in n.names], 'level':n.level,'line':n.lineno})
    return {'parser':'python_ast','symbols':symbols,'imports':imports,'limitations':['Syntax only; imports inside conditions are not proof of runtime execution. Dynamic imports and runtime wiring require agent review.']}

def observe_text(path,text):
    if Path(path).suffix=='.py':return python_observations(text)
    if Path(path).name=='package.json':
        obj=json.loads(text)
        if not isinstance(obj,dict):raise ValueError('Manifest must be an object')
        # Retain names only: scripts, URLs and package configuration may contain credentials.
        names=lambda key:sorted(obj.get(key,{})) if isinstance(obj.get(key),dict) else []
        return {'parser':'package_json','dependency_names':names('dependencies'),'dev_dependency_names':names('devDependencies'),'script_names':names('scripts'),'limitations':['Scripts not executed or copied. Workspace membership, versions and build behavior require review.']}
    if Path(path).suffix in {'.js','.jsx','.ts','.tsx','.mjs','.cjs'}:
        # Lexical hints deliberately never promoted to confirmed graph edges.
        patterns=r'''(?:\bfrom\s*|\bimport\s*|\brequire\s*\(\s*|\bimport\s*\(\s*)["']([^"'\r\n]+)["']'''
        return {'parser':'js_ts_lexical_hints','imports':[{'module':m.group(1),'line':text.count('\n',0,m.start())+1,'status':'HYPOTHESIS'} for m in re.finditer(patterns,text)],'limitations':['Not an AST parser. Comments, strings, aliases, exports and framework routing can produce false positives or omissions.']}
    return {'parser':'inventory_only','limitations':['No language parser available. Agent must read this surface; no automatic pass.']}

def scan(path):
    run,state=load_run(path);inv=read(run/'inventory.json')
    if not fresh(state,inv)[0]:raise ValueError('Snapshot changed or incomplete; create a new run before discovery')
    records=[]
    for item in inv['files']:
        rel=item['path'];row={'path':rel,'category':classify(rel),'sha256':item['sha256'],'capture':item['capture'],'parse_status':'NOT_PARSED','observations':{}}
        if item['capture']=='hashed' and row['category'] in {'source','test','manifest'}:
            try:
                raw=safe_file(Path(state['target']),rel).read_bytes()
                if digest(raw)!=item['sha256']:raise ValueError('File changed during scan')
                text=raw.decode('utf-8')
                if '\x00' in text:raise ValueError('Binary content')
                row['observations']=observe_text(rel,text)
                row['parse_status']='OBSERVED' if row['observations']['parser']!='inventory_only' else 'UNSUPPORTED'
            except (ValueError,SyntaxError,UnicodeError,OSError,RecursionError) as exc:
                row['parse_status']='BLOCKED';row['reason']=type(exc).__name__+'; inspect source locally (raw error withheld)'
        records.append(row)
    if not fresh(state,inv)[0]:raise ValueError('Snapshot changed during scan; observations discarded')
    result={'schema_version':1,'revision':state['revision'],'created_at':now(),'files':records,'counts':dict(Counter(r['parse_status'] for r in records)), 'limitations':['Static observations only. No architecture, responsibility or finding is inferred automatically.','Unsupported and blocked files remain in the review denominator.','Filename-based secret exclusion is not a comprehensive secret scanner. Do not upload unreviewed source packets.']}
    write(run/'discovery.json',result)
    return result


def capture(path,relative,start,end,observation):
    """Register an agent observation against a reproducible source range, without copying code."""
    run,state=load_run(path);inv=read(run/'inventory.json')
    if not fresh(state,inv)[0]:raise ValueError('Snapshot changed or incomplete; cannot capture evidence')
    item=next((x for x in inv['files'] if x['path']==relative),None)
    if not item or item['capture']!='hashed':raise ValueError('File not eligible for source evidence')
    raw=safe_file(Path(state['target']),relative).read_bytes()
    if digest(raw)!=item['sha256']:raise ValueError('Source changed during capture')
    text=raw.decode('utf-8')
    if '\x00' in text:raise ValueError('Binary content is not source evidence')
    lines=text.splitlines(keepends=True)
    if not 1<=start<=end<=len(lines):raise ValueError('Invalid source line range')
    if not observation.strip():raise ValueError('Observation is required')
    ref={'path':relative,'start_line':start,'end_line':end,'sha256':item['sha256'],'range_sha256':digest(''.join(lines[start-1:end]).encode('utf-8'))}
    eid='SRC-'+digest(json.dumps([state['revision'],ref,observation],sort_keys=True).encode())[:20]
    rows=read(run/'evidence.json')
    if not any(e.get('id')==eid for e in rows):
        rows.append({'id':eid,'kind':'source','location':f'{relative}:{start}-{end}','revision':state['revision'],'observed_at':now(),'observation':observation,'method':'source_range_capture','limitations':'Source range and hashes verified; meaning is an agent assertion, not independently proven.','source_ref':ref})
        write(run/'evidence.json',rows)
    return eid
