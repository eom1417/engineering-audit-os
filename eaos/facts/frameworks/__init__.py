"""Framework detectors. Adding one module here is how a new detector joins the pipeline.

Each module exposes LANGUAGES / FILENAMES and detect(context). What the detector emits is one of
the canonical fact kinds declared in this package (``entry_point``, ``data_access``); the core
loop reads the kind out of the helper and routes each fact into the right summary bucket. A
detector must never emit a fact it has not actually matched in the text: a missed entry point
is a declared gap, an invented one is a defect.
"""
from . import go_cli, go_command, go_web, js_routes, js_web, jvm_web, library_api, manifests, python_cli, python_jobs, python_web, streamlit, supabase_access, http_access

# Order matters for matching: data-access detectors sit alongside invocation detectors so a
# single read of the file text produces both fact kinds. A detector that has no
# ``FACT_KIND`` attribute is treated as an ``entry_point`` detector to keep the original list
# self-describing without changing every existing module.
MODULES = [python_web, python_cli, python_jobs, streamlit, js_web, js_routes,
           go_cli, go_command, go_web, jvm_web, library_api, manifests, supabase_access, http_access]


def applicable(module, rel, language):
    if getattr(module, 'FILENAMES', None) and rel.split('/')[-1] in module.FILENAMES: return True
    return language in getattr(module, 'LANGUAGES', ())


def fact_kind(module):
    """The kind this detector's ``detect`` results become when the loop persists them as facts."""
    return getattr(module, 'FACT_KIND', 'entry_point')
