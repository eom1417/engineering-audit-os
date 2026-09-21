"""Bounded source retrieval reusing the runtime's redaction and evidence format."""
import json
from pathlib import Path
from .runtime.context import Context
from .workspace import inventory, write


class SourceSession:
    def __init__(self, target, out, sets, budget=24000, exclude=()):
        self.remaining = budget
        self.omissions = []
        self.allowed = {f['location']['path']: f for f in sets['syntax']['facts'] if f['kind'] == 'source_file'}
        inv = inventory(target)
        from fnmatch import fnmatch
        from .facts import make
        docs = []
        for item in inv['files']:
            path = item['path']
            if item['capture'] != 'hashed' or Path(path).suffix.lower() not in {'.md', '.rst', '.txt'}: continue
            if any(path == pattern or path.startswith(pattern.rstrip('/') + '/') or fnmatch(path, pattern) for pattern in exclude): continue
            fact = make('source_document', 'semantic_documents', '1', item['sha256'], {'path': path},
                        {'status': 'documented_not_verified'})
            self.allowed[path] = fact
            docs.append(fact)
        write(Path(out) / 'facts/semantic_documents.json', {'facts': docs, 'extractor_version': '1'})
        # Only files analyzed in this exact fact snapshot are eligible.
        inv['files'] = [f for f in inv['files'] if f['path'] in self.allowed
                        and f['sha256'] == self.allowed[f['path']]['input_sha']]
        self.directory = Path(out) / 'semantic-context'
        self.directory.mkdir(exist_ok=True)
        write(self.directory / 'inventory.json', inv)
        write(self.directory / 'evidence.json', [])
        self.context = Context(self.directory, {'target': str(target), 'revision': sets['syntax']['input_sha']}, budget)

    def retrieve(self, requests):
        blocks = []
        if not isinstance(requests, list):
            self.omissions.append({'reason': 'source_requests must be an array'})
            return blocks
        for request in requests[:8]:
            if not isinstance(request, dict):
                self.omissions.append({'reason': 'Invalid source request'}); continue
            path = request.get('path')
            try:
                if path not in self.allowed: raise ValueError('Source not in analyzed scope')
                block = self.context.source(path, request.get('start_line'), request.get('end_line'))
                size = len(json.dumps(block, ensure_ascii=False))
                if size > self.remaining: raise ValueError('Total source budget exhausted')
                self.remaining -= size
                block['fact_id'] = self.allowed[path]['id']
                blocks.append(block)
            except (ValueError, OSError, UnicodeError) as exc:
                self.omissions.append({'path': path, 'reason': str(exc)})
        if len(requests) > 8: self.omissions.append({'reason': 'Only eight ranges allowed per round'})
        return blocks
