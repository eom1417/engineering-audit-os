"""Framework detectors. Adding a framework means adding one module here, never touching the core.

Each module exposes LANGUAGES / FILENAMES and detect(context) -> list of entry-point dicts:
{surface, route, http_method, handler, framework, line}. A detector must never emit an entry point
it has not actually matched in the text; a missed entry point is a declared gap, an invented one is a defect.
"""
from . import go_cli, go_command, go_web, js_web, jvm_web, library_api, manifests, python_cli, python_jobs, python_web

MODULES = [python_web, python_cli, python_jobs, js_web, go_cli, go_command, go_web, jvm_web, library_api, manifests]


def applicable(module, rel, language):
    if getattr(module, 'FILENAMES', None) and rel.split('/')[-1] in module.FILENAMES: return True
    return language in getattr(module, 'LANGUAGES', ())
