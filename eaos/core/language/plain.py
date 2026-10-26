"""Plain words for a person who did not write the code: what each kind of problem is, and what each stage does, read
from the one words catalog (eaos/data/words.json, M3.5) the Studio is built with too.

The report's own files keep their precise, technical wording; these are for the first page a user reads (START-HERE.md),
REPORT.html and the guided commands.
"""
from .words import catalog

# The kinds of problem, most urgent first (their order in eaos/data/words.json): something broken or unsafe before
# something untidy.
ORDER = list(catalog()['kinds'])


def kind(task):
    """The plain kind of a card: its pattern, except module-level state its own module keeps private (the fact's
    `encapsulated`, carried in the claim's render), which is not "changed by several parts"."""
    pattern = task.get('pattern') or 'generic'
    params = (task.get('render') or {}).get('params') or {}
    return 'mutable_state_private' if pattern == 'mutable_state' and params.get('encapsulated') else pattern


def problem(pattern, language):
    """(name of a group of them, one sentence) of a problem kind in plain words (eaos/data/words.json)."""
    kinds = catalog()['kinds']
    found = kinds.get(pattern) or kinds['generic']
    at = 0 if language == 'ar' else 1
    return found['group'][at], found['why'][at]


# What each audit stage is doing, as the user sees it while waiting.
def stage(name, language):
    """What EAOS says while a stage runs (eaos/data/words.json `doing`); a stage it does not know by its own name."""
    found = catalog()['stages'].get(name)
    return found['doing'][0 if language == 'ar' else 1] if found else name
