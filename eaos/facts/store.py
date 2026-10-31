"""Fact sets on disk, and the one way to read them. Files carry content only; run timestamps live apart so reruns stay
byte-identical.

A field every fact of a set holds with one same value (its extractor, version and limitations) is written once beside
them (`fact_fields`) and put back on read: it was half of each set's bytes. A reader asks for the facts it needs (of a
kind, by id, or one set) and only the sets that can hold them are read: every caller used to read all of them, 280 MB
on EAOS, often several times per stage.
"""
from collections.abc import Mapping
import json
from pathlib import Path
from . import SCHEMA_VERSION, digest
from ..core.system.files import read_json
from ..core.system.clock import now

SHARED = ('extractor', 'extractor_version', 'limitations')


def facts_dir(out):
    path = Path(out) / 'facts'
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialise(payload): return json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n'


def write_set(out, name, extractor, version, limitations, result):  # limits: parameters -- the set's file name and its extractor's name, version and limitations, each a module's constants (history writes git_history)
    """facts/<name>.json of an extractor's `result`, the dict every extractor's run() returns: its facts and input_sha,
    and optionally its summary, available (True when absent) and reason. Returns its index entry."""
    facts, available, reason = result['facts'], result.get('available', True), result.get('reason')
    shared = _shared(facts)
    payload = {'schema_version': SCHEMA_VERSION, 'extractor': extractor, 'extractor_version': version,
               'available': available, 'input_sha': result['input_sha'], 'limitations': list(limitations),
               'summary': result.get('summary') or {}, 'fact_fields': shared,
               'facts': [{key: value for key, value in fact.items() if key not in shared} for fact in facts]}
    if reason: payload['reason'] = reason
    text = serialise(payload)
    (facts_dir(out) / (name + '.json')).write_text(text, encoding='utf-8')
    return {'set': name, 'extractor': extractor, 'extractor_version': version, 'available': available,
            'facts': len(facts), 'kinds': sorted({fact['kind'] for fact in facts if fact.get('kind')}),
            'content_sha256': digest(text.encode('utf-8'))}


def _shared(facts):
    """The SHARED fields every fact holds with the first fact's value."""
    first = facts[0] if facts else {}
    return {key: first[key] for key in SHARED if key in first and all(fact.get(key, ...) == first[key] for fact in facts)}


def read_set(out, name):
    """One set as it was made: the fields written once put back on each fact."""
    data = json.loads((Path(out) / 'facts' / (name + '.json')).read_text(encoding='utf-8'))
    shared = data.pop('fact_fields', None) or {}
    if shared: data['facts'] = [{**fact, **shared} for fact in data.get('facts') or []]
    return data


class Sets(Mapping):
    """The sets present in a report, each read on first use: a caller pays for the sets it reads."""
    def __init__(self, out, names=None):
        self.out, self.read = Path(out), {}
        present = sorted(path.stem for path in (self.out / 'facts').glob('*.json') if path.stem not in ('index', 'run'))
        self.names = [name for name in present if names is None or name in names]

    def __getitem__(self, name):
        if name not in self.names: raise KeyError(name)
        if name not in self.read: self.read[name] = read_set(self.out, name)
        return self.read[name]

    def __setitem__(self, name, value):
        """A set made by the caller in place of the report's (a recheck reads the code again)."""
        self.read[name] = value
        if name not in self.names: self.names.append(name)

    def __iter__(self): return iter(self.names)

    def __len__(self): return len(self.names)


def _holding(out, kinds):
    """The sets that can hold a fact of `kinds`: those the index lists with one, and any it does not describe."""
    index = {row['set']: row.get('kinds') for row in (read_json(Path(out) / 'facts/index.json') or {}).get('sets') or []}
    return [name for name in Sets(out) if index.get(name) is None or set(index[name]) & set(kinds)]


def facts(out, *kinds):
    """Every fact of the report's sets of one of `kinds` (all facts when none is named), reading only the sets that can
    hold them; a set that does not read is skipped."""
    rows = []
    for name in (_holding(out, kinds) if kinds else Sets(out)):
        try: rows += [row for row in read_set(out, name).get('facts') or [] if isinstance(row, dict)]
        except (OSError, ValueError): continue
    return [row for row in rows if not kinds or row.get('kind') in kinds]


def by_id(out, ids):
    """{id: fact} for `ids`, reading the sets from the smallest until every one is found."""
    wanted, found = set(ids), {}
    for name in sorted(Sets(out), key=lambda name: (Path(out) / 'facts' / f'{name}.json').stat().st_size):
        if wanted <= found.keys(): break
        try: rows = read_set(out, name).get('facts') or []
        except (OSError, ValueError): continue
        found.update((row['id'], row) for row in rows if isinstance(row, dict) and row.get('id') in wanted)
    return found


def write_index(out, target, entries, unread_names=()):
    """index.json is content-addressed; run.json carries the non-deterministic provenance. `unread_names`: the files and
    folders no fact speaks of because their names are not valid UTF-8."""
    index = {'schema_version': SCHEMA_VERSION, 'sets': sorted(entries, key=lambda e: e['set'])}
    if unread_names: index['unread_names'] = list(unread_names)
    (facts_dir(out) / 'index.json').write_text(serialise(index), encoding='utf-8')
    (facts_dir(out) / 'run.json').write_text(serialise(
        {'target': str(target), 'produced_at': now('auto'),
         'sets': [e['set'] for e in index['sets']]}), encoding='utf-8')
    return index
