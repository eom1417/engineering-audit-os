"""Side channels of a declared pipeline: the keys of one shared context (a stage's `context`, `ctx` or `state`
parameter) a stage writes and another reads, or nobody reads (eaos/facts/pipeline_code.py)."""
import ast
from collections import defaultdict

from .pipeline_read import slug, site, _str, _method_call, CONTEXT_PARAMS, DICT_METHODS


def context_channels(py, found, functions):
    """Keys of one shared context a stage writes and another reads: side channels beside the declared edges."""
    writes, reads, lines = defaultdict(set), defaultdict(set), {}
    for (rel, name), key in _stage_functions(found, functions).items():
        node = py.defs[rel].get(name)
        param = next((a.arg for a in node.args.args if a.arg in CONTEXT_PARAMS), None)
        if not param: continue
        for sub in ast.walk(node):
            used, written, noted = _context_use(sub, param)
            if used is None: continue
            (writes if written else reads)[used].add(key)
            if noted: lines.setdefault((used, key), (rel, sub.lineno))
    for name in sorted(writes): _context_channel(py, found, name, writes[name], reads.get(name, set()), lines)


def _stage_functions(found, functions):
    """{(rel, function name): stage key} of the functions the stages start at."""
    return {(rel, node.name): key for key in found.order for rel, node in functions
            if found.stages[key]['entry']['path'] == rel and found.stages[key]['entry']['line'] == node.lineno}


def _context_use(sub, param):
    """(key, written, its line noted) when `sub` writes or reads a key of the context parameter; (None, ...) otherwise."""
    return next((use for read in _USES if (use := read(sub, param))), (None, False, False))


def _subscript_use(sub, param):
    """context['key'], read or written."""
    if isinstance(sub, ast.Subscript) and _is_name(sub.value, param) and _str(sub.slice):
        return _str(sub.slice), isinstance(sub.ctx, ast.Store), True
    return None


def _get_use(sub, param):
    """context.get('key')."""
    return (_str(sub.args[0]), False, True) if _method_call(sub, param, 'get') and sub.args and _str(sub.args[0]) else None


def _membership_use(sub, param):
    """'key' in context: a read whose line is not noted."""
    if isinstance(sub, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops) and _str(sub.left) \
            and any(_is_name(c, param) for c in sub.comparators):
        return _str(sub.left), False, False
    return None


def _attribute_use(sub, param):
    """context.key, read (the dict's own methods aside)."""
    if isinstance(sub, ast.Attribute) and _is_name(sub.value, param) and isinstance(sub.ctx, ast.Load) \
            and sub.attr not in DICT_METHODS:
        return sub.attr, False, True
    return None


_USES = (_subscript_use, _get_use, _membership_use, _attribute_use)


def _is_name(node, name):
    """Whether `node` is the plain name `name`."""
    return isinstance(node, ast.Name) and node.id == name


def _context_channel(py, found, name, writers, read_by, lines):
    """A context key read by a stage other than its writer is a side channel; one nobody reads is an unread output."""
    readers = {r for r in read_by if any(r != w for w in writers)}
    first = sorted(writers, key=found.order.index)[0]
    rel, line = lines.get((name, first), (found.stages[first]['entry']['path'], found.stages[first]['entry']['line']))
    if readers:
        found.hidden.append({'id': f'{found.id}:ctx:{slug(name)}', 'pipeline': found.id, 'kind': 'side_channel',
                             'channel': 'context', 'name': f"context['{name}']",
                             'stages': sorted(writers | readers, key=found.order.index), 'evidence': site(rel, line, py.line(rel, line))})
    elif not read_by:
        found.hidden.append({'id': f'{found.id}:ctx:{slug(name)}', 'pipeline': found.id, 'kind': 'unread_output',
                             'channel': 'context', 'name': f"context['{name}']", 'stages': sorted(writers, key=found.order.index),
                             'evidence': site(rel, line, py.line(rel, line))})
