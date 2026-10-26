"""What the assistant used, read from what every call already leaves: tokens, the cost at API prices, time and models.

Nothing is estimated. Claude Code's stream ends with a `result` event carrying its usage, its cost and its models (while
it runs, each message carries its tokens so far, not yet a cost); Codex's `turn.completed` events carry its tokens (it
gives no cost). A check's calls are of two kinds: the AI stages that ask
through the Studio's adapters keep their stream under nodes/<node>/runs/ (eaos/ai/assistant/headless.py ask), and
the ones that go through a provider (the semantic reading, the translation) append a row to <report>/usage.jsonl
(eaos/ai/assistant/claude_adapter.py record). A run of the Studio (a fix batch, a verify) keeps its stream in its folder.

`cache_read` is the conversation read again on every turn: on EAOS's batch 5, 138 million of 140 million tokens. The
person's plan is a subscription, so the cost is the API's price for the same tokens: a measure to compare, not a bill.
"""
import json
from datetime import datetime
from pathlib import Path

TOKENS = ('input', 'cache_write', 'cache_read', 'output', 'thinking')
CLAUDE = {'input_tokens': 'input', 'cache_creation_input_tokens': 'cache_write', 'cache_read_input_tokens': 'cache_read',
          'output_tokens': 'output'}
CODEX = {'input_tokens': 'input', 'cached_input_tokens': 'cache_read', 'output_tokens': 'output', 'reasoning_output_tokens': 'thinking'}
FILE = 'usage.jsonl'


def row(usage, cost=None, models=(), duration_ms=None, turns=None, **labels):
    """One call's use from a Claude `usage` object (or the fields of a Codex one)."""
    usage = usage or {}
    names = CLAUDE if 'cache_read_input_tokens' in usage or 'cache_creation_input_tokens' in usage else CODEX
    out = {field: 0 for field in TOKENS}
    for name, field in names.items(): out[field] += int(usage.get(name) or 0)
    out['thinking'] += int((usage.get('output_tokens_details') or {}).get('thinking_tokens') or 0)
    return {**out, 'cost_usd': cost, 'models': sorted(models), 'duration_ms': duration_ms, 'turns': turns, 'calls': 1, **labels}


def from_stream(lines):
    """One call's use from the stream it left (Claude Code's result event, Codex's completed turns, or a Claude run still
    going); None without any."""
    events = [event for event in map(_json, lines) if isinstance(event, dict)]
    return _result(events) or total([row(u) for u in _turns(events)]) or total(_messages(events))


def _result(events):
    """Every turn's result event, summed: a run resumed with the person's answer, or tried again, is one process per
    turn, each ending with its own use and cost."""
    return total([row(e['usage'], e.get('total_cost_usd'), e.get('modelUsage') or (), e.get('duration_ms'), e.get('num_turns'))
                  for e in events if e.get('type') == 'result' and isinstance(e.get('usage'), dict)])


def _turns(events):
    return [e['usage'] for e in events if e.get('type') == 'turn.completed' and isinstance(e.get('usage'), dict)]


def _messages(events):
    """Each message's last usage so far (a run still going): its cost is known only from the result event."""
    messages = {(e.get('message') or {}).get('id'): e['message'] for e in events
                if e.get('type') == 'assistant' and isinstance((e.get('message') or {}).get('usage'), dict)}
    return [row(m['usage'], models=[m['model']] if m.get('model') else ()) for m in messages.values()]


def total(rows):
    """The sum of several calls' use: tokens, cost (None when no call gave one), time, turns, calls and models."""
    rows = [r for r in rows if r]
    if not rows: return None
    return {**{field: sum(r.get(field) or 0 for r in rows) for field in TOKENS + ('duration_ms', 'turns')},
            'cost_usd': _cost(rows), 'calls': sum(r.get('calls', 1) for r in rows), 'models': _models(rows)}


def _cost(rows):
    """The calls' summed cost, or None when no call gave one."""
    costs = [r['cost_usd'] for r in rows if isinstance(r.get('cost_usd'), (int, float))]
    return round(sum(costs), 4) if costs else None


def _models(rows):
    """Every model the calls used, sorted."""
    return sorted({m for r in rows for m in r.get('models') or ()})


def of_check(report):
    """{'stages': {stage: use}, 'total': use} of the check that wrote `report`: the calls since it started."""
    report = Path(report)
    began = _started(report)
    stages = {}
    for stream in sorted((report / 'nodes').glob('*/runs/**/stream.jsonl')):
        if began and stream.stat().st_mtime < began: continue            # an older check's call, kept beside
        stages.setdefault(stream.relative_to(report / 'nodes').parts[0], []).append(from_stream(_lines(stream)))
    for line in _lines(report / FILE):
        found = _json(line)
        if isinstance(found, dict): stages.setdefault(found.get('stage') or 'other', []).append(found)
    stages = {name: use for name, rows in sorted(stages.items()) if (use := total(rows))}
    return {'stages': stages, 'total': total(list(stages.values()))}


def of_run(folder):
    """The use of one Studio run (its stream.jsonl), or None before its first answer."""
    return from_stream(_lines(Path(folder) / 'stream.jsonl'))


def _started(report):
    try: return datetime.fromisoformat(json.loads((report / 'run-manifest.json').read_text(encoding='utf-8'))['started_at']).timestamp()
    except (OSError, ValueError, KeyError, TypeError): return None


def _lines(path):
    try: return Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError: return []


def _json(line):
    try: return json.loads(line)
    except ValueError: return None
