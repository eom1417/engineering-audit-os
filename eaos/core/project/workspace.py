"""Local, read-only target discovery and evidence orchestration. No LLM/network."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from ... import __version__

DATA = Path(__file__).resolve().parents[2] / 'data'
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'vendor', 'dist', 'build', '.next', '.nuxt', '.terraform'}
STACKS = {'package.json':'JavaScript/TypeScript', 'pyproject.toml':'Python', 'requirements.txt':'Python', 'go.mod':'Go', 'Cargo.toml':'Rust', 'pom.xml':'JVM', 'build.gradle':'JVM', 'composer.json':'PHP', 'Gemfile':'Ruby', 'mix.exs':'Elixir', 'pubspec.yaml':'Dart'}
INFRA = re.compile(r'(docker|compose|helm|kubernetes|k8s|terraform|serverless|pulumi|ansible|\.github/workflows|\.gitlab-ci|jenkins|cloudformation|\.tf$)', re.I)
# A secrets or credentials file is data (secrets.json, app-credentials.yaml, a folder named secrets), never code:
# adminSecrets.ts or credentialsForm.tsx are source the audit must read, or it calls their imports missing.
SENSITIVE = re.compile(r'(^\.env($|\.)|\.pem$|\.key$|^id_(rsa|ed25519)$|(^|[._-])(credentials?|secrets?)(\.(json|ya?ml|toml|ini|txt|env|conf|cfg|properties|xml|csv)$|$)|\.tfstate($|\.)|\.p12$|\.pfx$|^\.npmrc$|^\.netrc$)',re.I)

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

def _prune_dirs(root, base, dirs, exclusions):
    for name in list(dirs):
        p=Path(base)/name
        if name in SKIP_DIRS or p.is_symlink():
            exclusions.append({'path':p.relative_to(root).as_posix(),'reason':'symlink' if p.is_symlink() else 'generated/dependency/VCS directory; external verification may be required'})
            dirs.remove(name)

def _capture(p, name, size, max_bytes):
    if SENSITIVE.search(name): return 'sensitive_metadata_only',None
    if size>max_bytes: return 'oversize_metadata_only',None
    with p.open('rb') as f: b=f.read(max_bytes+1)
    if len(b)>max_bytes: return 'oversize_metadata_only',None
    return 'hashed',digest(b)

def _scan_file(root, base, name, max_bytes, found):
    p=Path(base)/name;rel=p.relative_to(root).as_posix()
    if p.is_symlink(): found['exclusions'].append({'path':rel,'reason':'symlink'});return
    if not p.is_file(): found['exclusions'].append({'path':rel,'reason':'not regular file'});return
    try:
        st=p.stat()
        capture,sha=_capture(p,name,st.st_size,max_bytes)
        found['files'].append({'path':rel,'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha,'capture':capture})
    except OSError as e: found['errors'].append({'path':rel,'error':str(e)})

def _scan_names(root, base, names, limits, found):
    """False when the file limit stopped the scan."""
    for name in names:
        if len(found['files'])>=limits['max_files']: return False
        _scan_file(root,base,name,limits['max_bytes'],found)
    return True

def inventory(root, max_files=100000, max_bytes=2_000_000):
    root=Path(root).resolve()
    if not root.is_dir(): raise ValueError('Target must be a directory')
    found={'files':[],'exclusions':[],'errors':[]}; limited=False
    limits={'max_files':max_files,'max_bytes':max_bytes}
    for base,dirs,names in os.walk(root,followlinks=False,onerror=lambda e:found['errors'].append(str(e))):
        dirs.sort();names.sort()
        _prune_dirs(root,base,dirs,found['exclusions'])
        if not _scan_names(root,base,names,limits,found): limited=True;break
    files,exclusions,errors=found['files'],found['exclusions'],found['errors']
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

def _refuse_symlinks(root, raw):
    for p in [raw,*raw.parents]:
        if p==root: return
        if p.is_symlink(): raise ValueError('Symlink content capture prohibited')

def safe_file(root,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Only relative in-target paths accepted')
    raw=root/rel
    _refuse_symlinks(root,raw)
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
