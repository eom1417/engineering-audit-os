"""A proposal to run the app (the assistant's, through run_try, or the setup's own): whether it is safe to run, and
how it is merged into the run profile, run.json (eaos/live_run.py reads it). Every proposal passes safe() before it
runs: no command that deploys or reaches a hosted environment, no program other than a package manager, node or
python, no address other than this computer's.
"""
import json
import re
from pathlib import Path

from .sandbox import PYTHON

# A script that deploys, publishes or reaches a hosted environment never runs, whatever it is called.
DANGER = re.compile(r'\b(deploy\w*|railway|vercel|netlify|flyctl|heroku|firebase|gh-pages|publish|wrangler|surge|'
                    r'kubectl|terraform|pulumi|gcloud|aws|azure|az\s|ssh|scp|rsync|docker\s+push|'
                    r'supabase\s+(db\s+push|link|functions\s+deploy)|release|staging|production|prod)\b', re.I)

# What a proposal's commands may start with: a JavaScript or Python package manager, node, python, or a Python web server
# (a project's own virtual environment's, `.venv/bin/python`, counts by its name).
RUNNERS = ('npm', 'npx', 'pnpm', 'yarn', 'bun', 'node', 'corepack', 'true') + PYTHON


def safe(proposal):
    """Reasons a proposal may not run; empty when it may."""
    return _addresses(proposal.get('env') or {}) + _commands(proposal) + _seed(proposal.get('seed_script') or '')


def _addresses(env):
    """An environment value pointing at another computer than this one."""
    return [f'{name} points at {host}, not at this computer' for name, value in env.items()
            for host in re.findall(r'[a-z][a-z0-9+.-]*://(?:[^@/\s]*@)?([^:/\s?#]+)', str(value), re.I)
            if host not in ('127.0.0.1', 'localhost', '{database_url}') and not str(value).startswith('{database_url}')]


def _commands(proposal):
    """A command that deploys, or that starts with no package manager, node or python."""
    problems = []
    for argv in [proposal.get('start')] + [c for key in ('install', 'prepare', 'build') for c in proposal.get(key) or []]:
        if not argv: continue
        text = ' '.join(map(str, argv))
        if DANGER.search(text): problems.append(f'refused: {text[:120]}')
        if Path(str(argv[0])).name not in RUNNERS: problems.append(f'refused, not a package manager, node or python: {text[:120]}')
    return problems


def _seed(script):
    """A seed script that mentions a hosted environment or reaches another computer."""
    problems = [f"the seed script mentions {DANGER.search(script)[0]!r}, which a run never reaches"] if DANGER.search(script) else []
    return problems + [f'the seed script reaches {host}' for host in re.findall(r'https?://([^:/\s\'"`]+)', script)
                       if host not in ('127.0.0.1', 'localhost')]


def apply(runtime, proposal, mode='lock'):
    """Merge a safe proposal into run.json (into its `baseline` for the production run); a seed script is
    written beside it, never into the project."""
    profile = json.loads((Path(runtime) / 'run.json').read_text(encoding='utf-8'))
    _merge(profile.setdefault('baseline', {}) if mode == 'baseline' else profile, proposal, mode)
    if proposal.get('database') == 'postgres' and 'database' not in profile: profile['database'] = {'kind': 'postgres', 'name': 'app'}
    if mode == 'lock': _lock_only(runtime, profile, proposal)
    write_profile(runtime, profile)
    return profile


def _merge(target, proposal, mode):
    """A proposal's environment and commands, into the lock run's profile or its baseline."""
    if proposal.get('env') is not None:          # the complete environment: what it leaves out is dropped
        target['env'] = {k: str(v) for k, v in proposal['env'].items()}
    target.setdefault('env', {}).update({k: str(v) for k, v in (proposal.get('fixtures') or {}).items()})
    for key in ('start', 'install', 'prepare') + (('build', 'app', 'headers') if mode == 'baseline' else ()):
        if proposal.get(key) is None: continue
        if proposal[key]: target[key] = proposal[key]
        elif key == 'prepare': target.pop('prepare', None)    # [] removes; start and install are never empty


def _lock_only(runtime, profile, proposal):
    """What only the lock run takes: no database, how the app keeps its language and theme, the seed script."""
    if proposal.get('database') == 'none':
        profile.pop('database', None)
        profile['env'] = {k: v for k, v in profile['env'].items() if '{database_url}' not in v}
    if isinstance(proposal.get('screens'), dict):
        from .screens.audit import variants
        known = variants.__code__.co_varnames[:variants.__code__.co_argcount]
        profile['screens'] = {k: v for k, v in proposal['screens'].items() if k in known}
    if proposal.get('seed_script'):
        seed = Path(runtime) / 'setup' / 'seed.cjs'
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_text(proposal['seed_script'], encoding='utf-8')
        profile['seed'] = [['node', str(seed)]]


def write_profile(runtime, profile):
    from .artifact_contracts import contracts, validate
    problems = validate(profile, contracts()['run-profile'])
    if problems: raise ValueError(f'run.json would break its contract: {problems[0]}')
    path = Path(runtime) / 'run.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    path.chmod(0o600)       # generated secrets live here: the run's own, but still nobody else's business
