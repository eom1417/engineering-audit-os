"""An engine's function measure longer than the function is a misreading, set aside.

Lizard measured excalidraw's `drawElementOnCanvas` at 729 code lines and a complexity of 110 (2026-11-04); the function
runs 263 lines (EAOS's own metrics, the syntax tree's span). Lizard had read the functions after it as part of it, and
the figure reached a card as evidence, where a judge of M17.3 found it false. An engine names a function by its first
line only; EAOS's span of the function holding that line says how long it can be.
"""
SLACK = 1.1     # a signature or decorator line counted on one side only

def _spans(metrics):
    """{path: [(start, end)]} of every function and method EAOS measured."""
    spans = {}
    for fact in metrics:
        location, scope = fact.get('location') or {}, (fact.get('value') or {}).get('scope')
        if scope in ('function', 'method') and location.get('start_line') and location.get('end_line'):
            spans.setdefault(location['path'], []).append((location['start_line'], location['end_line']))
    return spans


def _length(fact):
    return next((m.get('value') for m in (fact.get('value') or {}).get('measurements') or [] if m.get('name') == 'nloc'), None)


def _too_long(fact, spans):
    location, length = fact.get('location') or {}, _length(fact)
    line = location.get('line')
    if not isinstance(length, (int, float)) or not isinstance(line, int): return False
    holding = [end - start + 1 for start, end in spans.get(location.get('path'), ()) if start <= line <= end]
    return bool(holding) and length > min(holding) * SLACK


def set_aside(facts, metrics):
    """(the facts kept, how many complexity measures were set aside as longer than their function)."""
    spans = _spans(metrics)
    kept = [fact for fact in facts if not ((fact.get('value') or {}).get('kind') == 'complexity' and _too_long(fact, spans))]
    return kept, len(facts) - len(kept)
