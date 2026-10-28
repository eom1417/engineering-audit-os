"""The element trees of a project's screens, and the ones repeated (M15.5): the same structure written in three places or
more is one component.

A tree is read from JSX (tree-sitter), from the HTML of a Vue or Svelte template or an .html file, and from the HTML a
template string builds (a plain-JavaScript screen). Each element is its tag and its static classes; texts, attributes
and expressions aside. Two subtrees are alike by the share of their parts they have in common (Dice over the multiset
of `parent>tag` and `tag.class` items); alike at UI_SIMILARITY or more, they are one pattern. A set of primitives alike on
purpose (components/ui/ of shadcn and its kind) is the source, never a pattern, and so is a tree made mostly of the
project's own components (it already calls them).
"""
import re
from collections import Counter

from .. import tree_sitter_tree
from ...core.contracts.code_laws import PATTERN_REPEATS, UI_SIMILARITY

MIN_ELEMENTS, MAX_ELEMENTS, MAX_CANDIDATES = 6, 80, 6000
PRIMITIVES = re.compile(r'(^|/)(components/ui|ui/primitives|primitives)/')
TAG = re.compile(r'<(/?)([A-Za-z][\w.-]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*?)(/?)>')
CLASS = re.compile(r'\bclass(?:Name)?\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|\{\s*[\'"`]([^\'"`]*)[\'"`]\s*\})')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
JSX_ELEMENTS = ('jsx_element', 'jsx_self_closing_element')


class Element:
    __slots__ = ('tag', 'classes', 'children', 'line', 'end_line', 'span')

    def __init__(self, tag, classes, line, start):
        self.tag, self.classes, self.children, self.line, self.end_line, self.span = tag, classes, [], line, line, [start, start]


def _classes(attributes):
    found = CLASS.search(attributes or '')
    text = next((group for group in found.groups() if group is not None), '') if found else ''
    return tuple(sorted({part for part in text.split() if part and '${' not in part and '{' not in part}))


# ---- HTML (templates, .html files, template strings) ----

def _close(element, line, offset):
    element.end_line, element.span[1] = line, offset


def html_trees(text, first_line=1, first=0):
    """The top elements of an HTML fragment, each with its children; a tag never closed is closed by its parent.
    `first`: the fragment's offset in its file, so two fragments on one line keep apart."""
    roots, stack = [], []
    for match in TAG.finditer(text):
        closing, tag, attributes, self_closing = match.groups()
        line, offset = first_line + text.count('\n', 0, match.start()), first + match.end()
        if closing:
            while stack and stack[-1].tag != tag: _close(stack.pop(), line, offset)
            if stack: _close(stack.pop(), line, offset)
            continue
        element = Element(tag, _classes(attributes), line, first + match.start())
        element.span[1] = offset
        (stack[-1].children if stack else roots).append(element)
        if not self_closing and tag.lower() not in VOID: stack.append(element)
    return roots


# ---- JSX and template strings, through tree-sitter ----

def _jsx_name(node):
    opening = node if node.type == 'jsx_self_closing_element' else node.child_by_field_name('open_tag') or node.children[0]
    name = opening.child_by_field_name('name')
    return name.text.decode('utf-8', 'replace') if name is not None else 'fragment'


def _jsx_classes(node):
    opening = node if node.type == 'jsx_self_closing_element' else node.child_by_field_name('open_tag') or node.children[0]
    return _classes(opening.text.decode('utf-8', 'replace'))


def _jsx_element(node):
    element = Element(_jsx_name(node), _jsx_classes(node), node.start_point[0] + 1, node.start_byte)
    _close(element, node.end_point[0] + 1, node.end_byte)
    element.children = [_jsx_element(child) for child in _nearest(node, skip_self=True)]
    return element


def _nearest(node, skip_self=False):
    """The JSX elements nearest under `node`: inside expressions too ({items.map(i => <li/>)}), not inside another element."""
    if not skip_self and node.type in JSX_ELEMENTS: return [node]
    found = []
    for child in node.children:
        if child.type in ('jsx_opening_element', 'jsx_closing_element'): continue
        found += _nearest(child)
    return found


def script_trees(text, language):
    """The JSX trees of a script, and the HTML its template strings build."""
    tree = tree_sitter_tree(text, language)
    if tree is None: return []
    roots, pending = [], [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type in JSX_ELEMENTS:
            roots.append(_jsx_element(node))
            continue
        if node.type == 'template_string' and '<' in node.text.decode('utf-8', 'replace'):
            text = re.sub(r'\$\{[^}]*\}', lambda m: ' ' * len(m.group(0)), node.text.decode('utf-8', 'replace'))
            roots += html_trees(text, node.start_point[0] + 1, node.start_byte)
        pending.extend(node.children)
    return roots


def file_trees(text, path, language):
    """The element trees of one file, whatever its kind of screen."""
    if language in ('javascript', 'typescript', 'tsx'): return script_trees(text, language)
    if language in ('vue', 'svelte') or path.endswith(('.html', '.htm')):
        return html_trees(re.sub(r'<(script|style)\b.*?</\1>', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S))
    return []


# ---- the repeated ones ----

def _walk(element, parent='^'):
    yield parent, element
    for child in element.children: yield from _walk(child, element.tag)


def _items(element):
    """The multiset a tree is compared by: each element under its parent, and each of its classes."""
    items = Counter()
    for parent, node in _walk(element):
        items[f'{parent}>{node.tag}'] += 1
        items.update(f'{node.tag}.{name}' for name in node.classes)
    return items


def _candidate(path, element):
    elements = [node for _, node in _walk(element)]
    host = sum(1 for node in elements if node.tag[:1].islower()) / len(elements)
    return {'path': path, 'line': element.line, 'end_line': max(node.end_line for node in elements), 'span': element.span, 'tag': element.tag,
            'elements': len(elements), 'host_share': round(host, 2), 'items': _items(element)}


def candidates(path, roots):
    """Every subtree of a file large enough to be a component and made mostly of plain elements."""
    if PRIMITIVES.search(path): return []
    out = []
    for root in roots:
        for _, node in _walk(root):
            size = sum(1 for _ in _walk(node))
            if MIN_ELEMENTS <= size <= MAX_ELEMENTS:
                row = _candidate(path, node)
                if row['host_share'] >= 0.5: out.append(row)
    return out


def similarity(one, other):
    shared = sum((one & other).values())
    return 2 * shared / ((sum(one.values()) + sum(other.values())) or 1)


def _inside(one, other):
    return one['path'] == other['path'] and other['span'][0] <= one['span'][0] and one['span'][1] <= other['span'][1] and one is not other


def _pairs(rows):
    """(i, j, similarity) of every two candidates alike enough, compared only with those of the same root tag and a
    near size (two trees whose sizes differ by half cannot be 80% alike)."""
    by_tag = {}
    for index, row in enumerate(rows): by_tag.setdefault(row['tag'], []).append(index)
    for indexes in by_tag.values():
        indexes.sort(key=lambda i: rows[i]['elements'])
        for at, i in enumerate(indexes):
            for j in indexes[at + 1:]:
                if rows[j]['elements'] > rows[i]['elements'] * 1.5: break
                if _inside(rows[i], rows[j]) or _inside(rows[j], rows[i]): continue
                alike = similarity(rows[i]['items'], rows[j]['items'])
                if alike >= UI_SIMILARITY: yield i, j, alike


def _groups(rows, pairs):
    """The alike candidates joined into groups (alike to alike), each with the lowest likeness of its pairs."""
    parent, pairs = list(range(len(rows))), list(pairs)
    def root(i):
        while parent[i] != i: i = parent[i]
        return i
    for i, j, _ in pairs: parent[root(i)] = root(j)
    groups, lowest = {}, {}
    for i, j, alike in pairs:
        top = root(i)
        groups.setdefault(top, set()).update((i, j))
        lowest[top] = min(lowest.get(top, 1.0), alike)
    return [(sorted(members, key=lambda k: (rows[k]['path'], rows[k]['line'])), lowest[top]) for top, members in groups.items()]


def _outermost(rows, members):
    """The members no other member holds: a tree and its own child are one place."""
    return [m for m in members if not any(_inside(rows[m], rows[k]) for k in members)]


def _nested(rows, members, other):
    """Whether every member holds, or is held by, a member of another group: the same places at another depth."""
    return all(any(_inside(rows[m], rows[k]) or _inside(rows[k], rows[m]) for k in other) for m in members)


def repeated(rows):
    """The patterns: groups of PATTERN_REPEATS alike subtrees or more; of two groups one inside the other, the closer alike."""
    rows = sorted(rows, key=lambda r: -r['elements'])[:MAX_CANDIDATES]
    groups = [(kept, alike) for members, alike in _groups(rows, _pairs(rows)) if len(kept := _outermost(rows, members)) >= PATTERN_REPEATS]
    kept = []
    # The closest likeness first: a pop-up repeated in three pages is the pattern, not the three pages around it.
    for members, alike in sorted(groups, key=lambda g: (-g[1], -rows[g[0][0]]['elements'])):
        if not any(_nested(rows, members, other) for other, _ in kept): kept.append((members, alike))
    return [{'members': [{k: rows[m][k] for k in ('path', 'line', 'end_line', 'tag', 'elements')} for m in members],
             'similarity': round(alike, 2)} for members, alike in kept]
