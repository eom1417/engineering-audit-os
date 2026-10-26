"""The contract's events a headless assistant's run gives (eaos/ai/assistant/headless.py reads its stream): what each EAOS (or
read-only built-in) tool call shows as it starts, what its answer shows, and the assistant's own words."""
import difflib
import json
import re

READS = {'finding': 'id', 'fix_read': 'path', 'build_read': 'path', 'report_file': 'name', 'Read': 'file_path', 'Grep': 'pattern', 'Glob': 'pattern'}
EDITS = ('fix_edit', 'build_edit')


def _diff(edit):
    path = edit.get('path') or '?'
    if edit.get('delete'): return f'--- a/{path}\n+++ /dev/null\n(deleted)\n'
    if 'content' in edit:
        lines = str(edit['content']).splitlines(keepends=True)
        return ''.join(difflib.unified_diff([], lines, 'a/' + path, 'b/' + path))
    return ''.join(difflib.unified_diff(str(edit.get('find') or '').splitlines(keepends=True),
                                        str(edit.get('replace') or '').splitlines(keepends=True), 'a/' + path, 'b/' + path))


def tool_events(tool, arguments, labels):
    """The events of an EAOS (or read-only built-in) tool call, as it starts: (kind, text, data, detail)."""
    arguments = arguments or {}
    if tool in EDITS: return [_edit_event(arguments)]
    label = labels.get(tool) or {'en': tool, 'ar': tool}
    if tool in READS:
        what = str(arguments.get(READS[tool]) or '')
        return [('read', {'en': f"{label['en']}: {what}", 'ar': f"{label['ar']}: {what}"}, {'path': what, 'tool': tool}, None)]
    return [_step_event(tool, arguments, label)]


def _edit_event(arguments):
    """The event of a card's edit: the files it changes and their diff."""
    edits = [e for e in arguments.get('edits') or [] if isinstance(e, dict)]
    paths = sorted({str(e.get('path')) for e in edits if e.get('path')})
    card = arguments.get('card')
    return ('edit', {'en': f"Changing {', '.join(paths) or 'files'} for {card}", 'ar': f"يعدّل {', '.join(paths) or 'ملفات'} للبطاقة {card}"},
            {'card': card, 'paths': paths, 'diff': ''.join(_diff(e) for e in edits), 'kept': None, 'summary': arguments.get('summary')}, None)


def _step_event(tool, arguments, label):
    """The event of any other tool call: its label and card, its short arguments as the detail."""
    card = arguments.get('card') or arguments.get('id')
    shown = {k: v for k, v in arguments.items() if k not in ('project', 'edits', 'spec', 'proposal', 'text') and v not in (None, '', [], {})}
    return ('step', {'en': label['en'] + (f': {card}' if card else ''), 'ar': label['ar'] + (f': {card}' if card else '')},
            {'tool': tool, 'card': card}, json.dumps(shown, ensure_ascii=False)[:2000] if shown else None)


def result_events(tool, arguments, payload, labels=None):
    """The events an EAOS tool's answer gives: a check's verdict, a job's progress, an error the assistant will read.
    A tool's error is said plainly (which step could not answer, and that the assistant goes on); its technical words
    are the detail."""
    if not isinstance(payload, dict): return []
    if payload.get('error'): return [_error_event(tool, payload, labels)]
    result = payload.get('result') if isinstance(payload.get('result'), dict) else payload
    return [*_progress_events(tool, payload), *_kept_events(result, arguments), *_handed_events(tool, result)]


def _error_event(tool, payload, labels):
    """The event of a tool's error: said plainly, its technical words the detail."""
    label = (labels or {}).get(tool) or {'en': tool, 'ar': tool}
    return ('error', {'en': f"“{label['en']}” could not answer this time; the assistant reads why and goes on",
                      'ar': f"«{label['ar']}» ما قدر يجاوب هالمرة؛ المساعد يقرأ السبب ويكمل"},
            {'reason': str(payload['error'])[:2000], 'tool': tool, 'recoverable': True,
             'what_now': {'en': 'Nothing to do: the assistant goes on.', 'ar': 'ما عليك شي: المساعد يكمل.'}},
            str(payload['error'])[:2000] + (f"\n{payload['what_now']}" if payload.get('what_now') else ''))


def _progress_events(tool, payload):
    """A job's progress bar, when the answer is a job's progress."""
    progress = payload.get('progress')
    # only a job's progress is a progress bar: status's `progress` is the project's card count, not this run's
    if not (isinstance(progress, dict) and progress.get('total') and payload.get('job')): return []
    return [('progress', {'en': f"{progress.get('stage') or tool}: {progress.get('done')} of {progress.get('total')}",
                          'ar': f"{progress.get('stage') or tool}: {progress.get('done')} من {progress.get('total')}"},
             {'batch': payload.get('batch'), 'done': progress.get('done'), 'total': progress.get('total'), 'stage': progress.get('stage')}, None)]


def _kept_events(result, arguments):
    """A card's verdict, when the answer says whether its change was kept."""
    if not isinstance(result.get('kept'), bool): return []
    card = result.get('card') or (arguments or {}).get('card')
    why = str(result.get('why') or '')[:400]
    return [('check', {'en': f"{card}: {'the change passed its checks' if result['kept'] else 'the change was taken back: ' + why}",
                       'ar': f"{card}: {'التغيير نجح في الفحص' if result['kept'] else 'التغيير أُرجع: ' + why}"},
             {'name': 'card gates', 'card': card, 'passed': result['kept'], 'summary': why}, None)]


def _handed_events(tool, result):
    """The batch's hand-over, when a finishing (or waited) tool answers its branch."""
    if not (result.get('branch') and tool in ('fix_finish', 'build_finish', 'wait')): return []
    return [('check', {'en': f"Handed over on the branch {result['branch']}", 'ar': f"سُلّم على الفرع {result['branch']}"},
             {'name': 'batch gates', 'passed': True, 'summary': f"branch {result['branch']}", 'branch': result['branch']}, None)]


def said(text):
    """The assistant's words as a `say` event, without the question block (the question has its own event)."""
    from .prompts import QUESTION
    words = re.sub(r'<notification_summary>.*?</notification_summary>', '', QUESTION.sub('', str(text or '')), flags=re.S).strip()   # a host's own tag
    return [('say', {'en': words, 'ar': words}, {'words': words}, None)] if words else []


def json_text(content):
    """The JSON an MCP tool answered, from a tool_result's content (text, or a list of text parts; maybe wrapped in {"result"})."""
    if isinstance(content, list): content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
    if isinstance(content, dict): content = json.dumps(content)
    try: value = json.loads(content)
    except (TypeError, ValueError): return None
    if isinstance(value, dict) and set(value) == {'result'} and isinstance(value['result'], str):
        try: value = json.loads(value['result'])
        except ValueError: return None
    return value
