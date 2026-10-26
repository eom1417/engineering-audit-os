"""A small YAML reader for the simple manifests the runtime facts read (eaos/facts/runtime/operations.py: docker-compose). It
reads mappings, sequences and scalars, and refuses what it cannot represent faithfully rather than guess."""
import re


class UnsupportedYaml(ValueError):
    """What this reader will not guess at. The caller records the file as unparsed."""


def yaml_load(text):
    """A minimal YAML reader for the simple structures we encounter. We never
    rely on it for completeness; the parser raises on the rest and we leave it
    as unparsed in the output."""
    text = re.sub(r'#[^\n]*', '', text)
    text = re.sub(r'\A\s*---[ \t]*(?:\n|\Z)', '', text)      # the document's start marker, as compose files often begin
    _refuse_unsupported(text)
    return _yaml_reader(text)


def _refuse_unsupported(text):
    """Raise on the constructs this reader cannot represent faithfully.

    Without this it returned a partial answer instead: `a: [unclosed` became the string
    "[unclosed", and a document with a broken sequence lost its items silently. A parser that
    guesses turns an unreadable file into fabricated facts, which is worse than no facts.
    """
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if line[:len(line) - len(line.lstrip())].count('\t'):
            raise UnsupportedYaml(f'line {number}: tab indentation is not valid YAML')
        for opener, closer in (('[', ']'), ('{', '}')):
            if stripped.count(opener) != stripped.count(closer):
                raise UnsupportedYaml(f'line {number}: unbalanced {opener}{closer} — flow style is '
                                      f'only read when it closes on its own line')
        if stripped.startswith(('&', '*', '<<', '!', '|', '>')) or stripped.endswith(('|', '>')):
            raise UnsupportedYaml(f'line {number}: anchors, tags and block scalars are not read')


def _indent(line):
    return len(line) - len(line.lstrip())


def _yaml_reader(text, indent=0):
    """Read a YAML mapping or sequence at the given indent level."""
    out = {} if _yaml_indent_level(text, indent) in {'map', None} else []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped, current = lines[i].strip(), _indent(lines[i])
        if not stripped or stripped.startswith('#'): i += 1; continue
        if current < indent: return out
        if stripped.startswith('- '): row, i = _seq_row(lines, i, current, stripped[2:].strip())
        elif ':' in stripped: row, i = _map_row(lines, i, current, stripped)
        else: i += 1; continue
        _put(out, row)
    return out


def _put(out, row):
    """(key, value) into the mapping, or (None, value) onto the sequence; a row of the other shape is left out."""
    key, value = row
    if key is None and isinstance(out, list): out.append(value)
    elif key is not None and isinstance(out, dict): out[key] = value


def _seq_row(lines, i, indent, value):
    """((None, the item), the next line) of a `- ...` line: a scalar, or a `key: value` item with what follows it."""
    if ':' in value and not value.startswith('"'): return _item(lines, i, indent, value)
    return (None, _yaml_scalar(value)), i + 1


def _item(lines, i, indent, value):
    """A `- key: value` item and the deeper mapping on the next line, when there is one."""
    key, val = value.split(':', 1)
    item = {key.strip(): _yaml_scalar(val.strip())}
    i += 1
    while i < len(lines) and not lines[i].strip(): i += 1
    if i < len(lines) and _indent(lines[i]) > indent:
        sub = _yaml_reader('\n'.join(lines[i:]), _indent(lines[i]))
        if isinstance(sub, dict): item.update(sub)
        i += 1
    return (None, item), i


def _map_row(lines, i, indent, stripped):
    """((key, value), the next line) of a `key: value` line; an empty value reads the deeper block below it."""
    key, _, val = stripped.partition(':')
    if val.strip(): return (key.strip(), _yaml_scalar(val.strip())), i + 1
    block, i = _block(lines, i + 1, indent)
    return (key.strip(), _yaml_reader('\n'.join(block), indent + 2)), i


def _block(lines, i, indent):
    """The lines from i on indented deeper than `indent`, blank ones left out, and the line after them."""
    block = []
    while i < len(lines):
        if lines[i].strip():
            if _indent(lines[i]) <= indent: break
            block.append(lines[i])
        i += 1
    return block, i


def _yaml_indent_level(text, indent):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): continue
        current = len(line) - len(line.lstrip())
        if current < indent: return None
        if current == indent: return 'map' if ':' in stripped else 'seq'
    return None


def _yaml_scalar(value):
    value = value.strip().strip('"\'')
    if value in {'true', 'yes'}: return True
    if value in {'false', 'no'}: return False
    if re.match(r'^-?\d+$', value): return int(value)
    return value
