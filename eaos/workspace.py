"""Local, read-only target discovery and evidence orchestration. No LLM/network."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from . import __version__

DATA = Path(__file__).parent / 'data'
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'vendor', 'dist', 'build', '.next', '.nuxt', '.terraform'}
STACKS = {'package.json':'JavaScript/TypeScript', 'pyproject.toml':'Python', 'requirements.txt':'Python', 'go.mod':'Go', 'Cargo.toml':'Rust', 'pom.xml':'JVM', 'build.gradle':'JVM', 'composer.json':'PHP', 'Gemfile':'Ruby', 'mix.exs':'Elixir', 'pubspec.yaml':'Dart'}
INFRA = re.compile(r'(docker|compose|helm|kubernetes|k8s|terraform|serverless|pulumi|ansible|\.github/workflows|\.gitlab-ci|jenkins|cloudformation|\.tf$)', re.I)
SENSITIVE = re.compile(r'(^\.env($|\.)|\.pem$|\.key$|^id_(rsa|ed25519)$|credentials|secrets?\.|\.tfstate($|\.)|\.p12$|\.pfx$|^\.npmrc$|^\.netrc$)',re.I)

def now(): return datetime.now(timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,obj):
    p=Path(p); tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(p)
def registry(): return read(DATA/'controls.json')
def controls(): return {c['id']:c for m in registry()['modules'] for c in m['controls']}
def bounded_int(value):
    n=int(value)
    if n<1: raise argparse.ArgumentTypeError('must be positive')
    return n

def inventory(root, max_files=100000, max_bytes=2_000_000):
    root=Path(root).resolve()
    if not root.is_dir(): raise ValueError('Target must be a directory')
    files=[]; exclusions=[]; errors=[]; limited=False
    for base,dirs,names in os.walk(root,followlinks=False,onerror=lambda e:errors.append(str(e))):
        dirs.sort();names.sort()
        for name in list(dirs):
            p=Path(base)/name
            if name in SKIP_DIRS or p.is_symlink():
                exclusions.append({'path':p.relative_to(root).as_posix(),'reason':'symlink' if p.is_symlink() else 'generated/dependency/VCS directory; external verification may be required'})
                dirs.remove(name)
        for name in names:
            if len(files)>=max_files: limited=True;break
            p=Path(base)/name;rel=p.relative_to(root).as_posix()
            if p.is_symlink(): exclusions.append({'path':rel,'reason':'symlink'});continue
            if not p.is_file(): exclusions.append({'path':rel,'reason':'not regular file'});continue
            try:
                st=p.stat(); sensitive=bool(SENSITIVE.search(name))
                item={'path':rel,'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':None,'capture':'sensitive_metadata_only' if sensitive else 'oversize_metadata_only' if st.st_size>max_bytes else 'hashed'}
                if item['capture']=='hashed':
                    with p.open('rb') as f: b=f.read(max_bytes+1)
                    if len(b)>max_bytes: item['capture']='oversize_metadata_only'
                    else: item['sha256']=digest(b)
                files.append(item)
            except OSError as e: errors.append({'path':rel,'error':str(e)})
        if limited: break
    manifest_names=sorted({f['path'] for f in files if Path(f['path']).name in STACKS or f['path'].endswith(('.csproj','.fsproj','.sln'))})
    stack_hints=sorted({STACKS.get(Path(p).name,'.NET') for p in manifest_names})
    fingerprint=digest(json.dumps(files,sort_keys=True).encode())
    return {'root':str(root),'created_at':now(),'fingerprint':fingerprint,'limits':{'max_files':max_files,'max_bytes':max_bytes},'truncated':limited,'errors':errors,'exclusions':exclusions,'files':files,'manifest_candidates':manifest_names,'stack_hints':stack_hints,'infrastructure_candidates':[f['path'] for f in files if INFRA.search(f['path'])],'interpretation':'Filename hints only; confirm actual architecture, versions and deployed infrastructure with evidence.'}

def load_run(path):
    run=Path(path).resolve(); state=read(run/'run.json')
    if state.get('framework_version')!=__version__: raise ValueError('Unsupported framework version; migrate records explicitly')
    return run,state

def fresh(state, inv):
    current=inventory(state['target'],**inv['limits'])
    return current['fingerprint']==inv['fingerprint'] and not current['truncated'] and not current['errors'],current

def safe_file(root,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Only relative in-target paths accepted')
    raw=root/rel
    for p in [raw,*raw.parents]:
        if p==root: break
        if p.is_symlink(): raise ValueError('Symlink content capture prohibited')
    resolved=raw.resolve()
    if root not in resolved.parents or not resolved.is_file(): raise ValueError('Not a regular in-target file')
    if any(SENSITIVE.search(p) for p in rel.parts): raise ValueError('Sensitive path: metadata only; do not capture contents')
    return resolved



@contextmanager
def run_lock(run):
    """Single writer/read-consistent CLI session across cooperating processes."""
    lock=Path(run).resolve()/'engine.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('Run is locked; verify its process stopped before removing a stale engine.lock') from None
    try:
        with os.fdopen(fd,'w') as stream:stream.write(str(os.getpid()))
        yield
    finally:lock.unlink(missing_ok=True)
