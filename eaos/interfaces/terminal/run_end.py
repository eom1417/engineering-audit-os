"""The box that ends a run followed in the terminal (commands.follow), apart from commands.py, which imports it."""
from ...journeys import guided
from ..govern_words import text_of, words
from ...core.project import state as project_state
from ...core.project.runs import contract


def ended(record, lang, project):
    """The box that ends a run followed in the terminal (commands.follow): its state, and what to copy next."""
    state = text_of(contract()['lifecycle']['states'][record['state']], lang)
    ok = record['state'] == 'done'
    counts = ((record.get('result') or {}).get('answer') or {}).get('counts') if isinstance((record.get('result') or {}).get('answer'), dict) else None
    guided.box(lang, words('ended', lang, state=state), status='ok' if ok else 'warn', commands=_after(record, ok, project),
               note=words('checked', lang, problems=counts.get('problems'), ready=counts.get('ready')) if counts else None)
    return 0 if ok else 2


def _after(record, ok, project):
    """What to copy after a run: a fix that handed a batch over names the diff to read, accept and undo."""
    wave = project_state.waiting_batch(project_state.load(project) or {}) if ok and record.get('verb') == 'fix' else None
    if wave: return [f"git diff {wave.get('merge_into') or wave['base'][:12]}...{wave['branch']}", 'eaos accept', 'eaos undo']
    return ['eaos problems', 'eaos waiting'] if ok else [f"eaos retry {record['id']}", 'eaos runs']
