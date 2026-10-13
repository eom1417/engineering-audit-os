"""Deterministic fact extraction. A fact is a reproducible observation, never a model output."""
import ast
import hashlib
import json

SCHEMA_VERSION = 1


def digest(data): return hashlib.sha256(data).hexdigest()


def tree_sitter_tree(text, language):
    """The tree-sitter tree of a file, or None when the parser is missing or fails."""
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser('c_sharp' if language == 'csharp' else language).parse(text.encode('utf-8'))
    except Exception:
        return None


def call_name(node):
    """The last name of a Python callee: f, mod.f, obj.method; None for any other expression."""
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None


def make(kind, extractor, version, input_sha, location, value, resolution=None, limitations=()):
    """Build a fact whose identity is a pure function of its content, so reruns are comparable."""
    payload = json.dumps([kind, extractor, version, input_sha, location, value], sort_keys=True, ensure_ascii=False)
    row = {'id': 'FACT-' + digest(payload.encode('utf-8'))[:16], 'kind': kind, 'extractor': extractor,
           'extractor_version': version, 'input_sha': input_sha, 'location': location, 'value': value}
    if resolution: row['resolution'] = resolution
    if limitations: row['limitations'] = list(limitations)
    return row
