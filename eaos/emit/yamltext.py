"""YAML for the files a person keeps and edits (CI, pre-commit, Collector, SLOs, Goss, the site): block style,
written without a YAML library. Mappings keep their order; a string is quoted whenever YAML could read it as
something else, and a multi-line string is a literal block. The tools that read these files are their judges.
"""
import json
import re

PLAIN = re.compile(r'^[A-Za-z_./][A-Za-z0-9_./@+-]*$')
KEYWORDS = {'true', 'false', 'yes', 'no', 'on', 'off', 'null', 'y', 'n', '~'}


def scalar(value):
    if value is None: return 'null'
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, (int, float)): return json.dumps(value)
    text = str(value)
    if PLAIN.match(text) and text.lower() not in KEYWORDS: return text
    return json.dumps(text, ensure_ascii=False)


def key(name):
    name = str(name)
    return name if PLAIN.match(name) and name.lower() not in KEYWORDS else json.dumps(name, ensure_ascii=False)


def lines(value, indent=0):
    pad = ' ' * indent
    if isinstance(value, dict):
        if not value: return [pad + '{}']
        out = []
        for name, item in value.items():
            if isinstance(item, (dict, list)) and item:
                out.append(f'{pad}{key(name)}:')
                out += lines(item, indent + 2)
            elif isinstance(item, str) and '\n' in item:
                out.append(f'{pad}{key(name)}: |')
                out += [(pad + '  ' + line) if line else '' for line in item.rstrip('\n').split('\n')]
            else:
                out.append(f'{pad}{key(name)}: ' + ('{}' if item == {} else '[]' if item == [] else scalar(item)))
        return out
    if isinstance(value, list):
        if not value: return [pad + '[]']
        out = []
        for item in value:
            if isinstance(item, (dict, list)) and item:
                nested = lines(item, indent + 2)
                out.append(pad + '- ' + nested[0][indent + 2:])
                out += nested[1:]
            elif isinstance(item, str) and '\n' in item:
                out.append(pad + '- |')
                out += [(pad + '    ' + line) if line else '' for line in item.rstrip('\n').split('\n')]
            else:
                out.append(pad + '- ' + scalar(item))
        return out
    return [pad + scalar(value)]


def dump(value, comment=''):
    head = [f'# {line}' if line else '#' for line in comment.splitlines()] if comment else []
    return '\n'.join(head + lines(value)) + '\n'
