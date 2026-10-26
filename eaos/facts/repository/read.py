"""The fact set `repository` (eaos/facts/run.py): one fact per finding of the repository's craft (craft.py) and of its
assistants' context (context.py), each low severity, its sentence and fix in both languages."""
import subprocess
from pathlib import Path

from .. import digest, make
from ..defects.leftovers import _imported_modules
from . import context, craft
from .catalog import limits

NAME = 'repository'
VERSION = '1'
LIMITATIONS = ['Read from the files alone, never run; a folder a framework fills by its own convention is not judged.',
               'Tokens are counted as about four characters each.']


def published(target, paths):
    """The files of `paths` git tracks in `target` (what a push publishes; an ignored file is not), all of them outside git."""
    done = subprocess.run(['git', '-C', str(target), 'ls-files'], capture_output=True, text=True)
    return [p for p in paths if p in set(done.stdout.splitlines())] if done.returncode == 0 and done.stdout else paths


def findings(source, resolved, target=None):
    """Every finding of the snapshot `source`, with the resolver's facts `resolved` (what the project imports); the
    machine details only in the files `target`'s git publishes."""
    rules = limits()
    paths = [item['path'] for item in source.readable()]
    everything = {item['path'] for item in source.inventory['files']}
    read = context.texts(source, everything, rules)
    return (craft.crowded(paths, rules) + craft.families(paths, rules) + craft.vague(source, paths, rules)
            + craft.versions(paths, rules) + craft.traps(paths, _imported_modules(resolved or []), rules)
            + craft.stale_docs(source, everything, rules) + craft.tests_flat(paths, rules) + craft.dev_details(source, published(target or source.inventory['root'], paths), rules)
            + context.heavy(read, rules) + context.repeats(read, rules) + context.done(read, rules))


def run(target, source, resolved=None, **options):
    found = findings(source, resolved, Path(target) if target else None)
    facts = [make('repository_finding', NAME, VERSION, digest(f"{f['rule']}:{f['path']}".encode('utf-8')),
                  {'path': f['path'], 'start_line': f['params'].get('line') or 1}, f, limitations=LIMITATIONS) for f in found]
    by_rule = {}
    for f in found: by_rule[f['rule']] = by_rule.get(f['rule'], 0) + 1
    return {'facts': facts, 'summary': {'findings': len(facts), 'by_rule': by_rule}, 'available': True,
            'input_sha': source.content_fingerprint if hasattr(source, 'content_fingerprint') else digest(b'repository'), 'reason': None}
