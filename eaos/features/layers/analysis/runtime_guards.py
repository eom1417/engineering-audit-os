"""Node text in a generated multi-runtime binding is server evidence only outside its proven Node branch.

Recognise the explicit browser, worker and Node tests, including every assignment to their flags. Unknown conditions,
reassignments and parse failures keep the original text. Static imports remain evidence in placement._marks.
"""
import re
from ...code_reading.facts.code.syntax import parser_for

TESTS = {
    'ENVIRONMENT_IS_WEB': r'''typeof window === ['"]object['"]''',
    'ENVIRONMENT_IS_WORKER': r'''typeof importScripts === ['"]function['"]''',
    'ENVIRONMENT_HAS_NODE': r'''typeof process === ['"]object['"] && typeof process\.versions === ['"]object['"] && typeof process\.versions\.node === ['"]string['"]''',
    'ENVIRONMENT_IS_NODE': r'ENVIRONMENT_HAS_NODE && !ENVIRONMENT_IS_WEB && !ENVIRONMENT_IS_WORKER',
}


def _text(node, blob):
    return blob[node.start_byte:node.end_byte].decode('utf-8') if node else ''


def _nodes(root):
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.named_children))


def _flags(nodes, blob):
    """Each runtime flag must be declared false once and assigned its exact test once, with no other writes."""
    declared, assigned = [], []
    for node in nodes:
        if node.type == 'variable_declarator':
            name = _text(node.child_by_field_name('name'), blob)
            if name in TESTS:
                if _text(node.child_by_field_name('value'), blob) != 'false': return False
                declared.append(name)
        elif node.type in ('assignment_expression', 'augmented_assignment_expression', 'update_expression'):
            name = _text(node.child_by_field_name('left') or node.child_by_field_name('argument'), blob)
            if name in TESTS:
                value = re.sub(r'\s+', ' ', _text(node.child_by_field_name('right'), blob)).strip()
                if node.type != 'assignment_expression' or not re.fullmatch(TESTS[name], value): return False
                assigned.append(name)
    return sorted(declared) == sorted(assigned) == sorted(TESTS)


def browser_text(text):
    """Remove only positive Node branch bodies after validating the runtime flags; retain all other text."""
    if 'ENVIRONMENT_IS_NODE' not in text: return text
    parser = parser_for('typescript')
    if parser is None: return text
    blob = text.encode('utf-8')
    tree = parser.parse(blob)
    nodes = list(_nodes(tree.root_node))
    if tree.root_node.has_error or not _flags(nodes, blob): return text
    spans = []
    for node in nodes:
        if node.type != 'if_statement': continue
        condition = _text(node.child_by_field_name('condition'), blob).strip('() \n')
        branch = node.child_by_field_name('consequence')
        if condition == 'ENVIRONMENT_IS_NODE' and branch: spans.append((branch.start_byte, branch.end_byte))
    # Blank spans in place: nested branches and non-ASCII text must not change another branch's byte offsets.
    masked = bytearray(blob)
    for start, end in spans: masked[start:end] = b' ' * (end - start)
    return masked.decode('utf-8')
