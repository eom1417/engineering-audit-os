"""What every layer check reads of one project, read once: its files by kind, their imports, its resolved import edges
and its packages, from the facts of the check (syntax, resolve) and the project's own files."""
import json
import re
from collections import defaultdict
from functools import cached_property
from pathlib import Path

from ...core.vocabulary import classify
from ...facts.store import read_set

TYPE_ONLY = re.compile(r'^\s*(import|export)\s+type\b')
LIMIT = 400_000          # characters of one file a check reads: a larger file is generated or data


class Project:
    def __init__(self, root, out):
        self.root, self.out = Path(root), Path(out)
        self._texts, self._lines = {}, {}
        syntax = read_set(self.out, 'syntax').get('facts') or []
        self._files = {f['location']['path']: f['value'] for f in syntax if f.get('kind') == 'source_file'}
        self._imports = [f for f in syntax if f.get('kind') == 'import_edge']

    def text(self, path):
        if path not in self._texts:
            try: self._texts[path] = (self.root / path).read_text(encoding='utf-8', errors='replace')[:LIMIT]
            except OSError: self._texts[path] = ''
        return self._texts[path]

    def lines(self, path):
        if path not in self._lines: self._lines[path] = self.text(path).split('\n')
        return self._lines[path]

    def language(self, path):
        return (self._files.get(path) or {}).get('language')

    @cached_property
    def built(self):
        from .placement import built
        return sorted(path for path in self._files if built(path))

    @cached_property
    def tests(self):
        return sorted(path for path in self._files if classify(path) == 'test' and path not in self.built)

    @cached_property
    def schemas(self):
        found = [path for path in self._files if path.endswith('.sql') and path not in self.tests]
        found += [str(p.relative_to(self.root)) for p in self.root.rglob('*.prisma') if 'node_modules' not in p.parts]
        return sorted(set(found) - set(self.built))

    @cached_property
    def code(self):
        """The source files that ship: neither tests, nor schemas, nor built output."""
        skipped = set(self.tests) | set(self.schemas) | set(self.built)
        return sorted(path for path, value in self._files.items() if path not in skipped and value.get('language') not in (None, 'sql'))

    @cached_property
    def imports(self):
        """{path: [module as written]}."""
        found = defaultdict(list)
        for fact in self._imports: found[fact['location']['path']].append(fact['value']['module'])
        return found

    @cached_property
    def edges(self):
        """{path: {path it imports}} of the resolved imports that exist when the code runs."""
        found = defaultdict(set)
        for fact in read_set(self.out, 'resolve').get('facts') or []:
            source, target = fact['location']['path'], fact['value'].get('to_path')
            if fact.get('resolution') != 'RESOLVED' or not target or source == target: continue
            if self._type_only(source, fact['location'].get('start_line')): continue
            found[source].add(target)
        return found

    @cached_property
    def importers(self):
        """{path: {paths that import it}}."""
        found = defaultdict(set)
        for source, targets in self.edges.items():
            for target in targets: found[target].add(source)
        return found

    def _type_only(self, path, line):
        lines = self.lines(path)
        return bool(line) and 0 < line <= len(lines) and bool(TYPE_ONLY.match(lines[line - 1]))

    @cached_property
    def packages(self):
        """The names in every package.json of the project (its root and the app folders)."""
        names = set()
        for manifest in [self.root / 'package.json', *self.root.glob('*/package.json'), *self.root.glob('apps/*/package.json')]:
            try: data = json.loads(manifest.read_text(encoding='utf-8'))
            except (OSError, ValueError): continue
            names |= set(data.get('dependencies') or {}) | set(data.get('devDependencies') or {})
        return names

    def facts(self, name, kind=None):
        return [f for f in read_set(self.out, name).get('facts') or [] if kind is None or f.get('kind') == kind] \
            if (self.out / 'facts' / f'{name}.json').is_file() else []
