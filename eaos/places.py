"""Where EAOS keeps a project's things: ~/.eaos (EAOS_HOME) and one workspace per project folder.

A leaf module, so the Studio's modules can find a project's records without importing guided (which imports the
pipeline, which exports the Studio: a cycle).
"""
import hashlib
import os
from pathlib import Path


def home():
    return Path(os.environ.get('EAOS_HOME') or Path.home() / '.eaos')


def workspace(project):
    """~/.eaos/projects/<name>-<id>: one per project folder, never inside it."""
    project = Path(project).resolve()
    ident = hashlib.sha256(str(project).encode('utf-8')).hexdigest()[:8]
    return home() / 'projects' / f'{project.name}-{ident}'
