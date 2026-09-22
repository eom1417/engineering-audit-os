"""Shared read-only access to a target snapshot for every extractor."""
from fnmatch import fnmatch
from pathlib import Path
from ..discovery import classify
from ..workspace import inventory, safe_file

LANGUAGE_BY_SUFFIX = {
    '.py': 'python', '.pyi': 'python', '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
    '.cjs': 'javascript', '.ts': 'typescript', '.tsx': 'tsx', '.go': 'go', '.java': 'java', '.rs': 'rust',
    '.rb': 'ruby', '.php': 'php', '.cs': 'csharp', '.kt': 'kotlin', '.swift': 'swift', '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.hpp': 'cpp', '.ex': 'elixir', '.exs': 'elixir', '.dart': 'dart',
    '.scala': 'scala', '.sh': 'bash', '.sql': 'sql', '.vue': 'vue', '.svelte': 'svelte',
}


def language_of(path): return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower())


class Source:
    """One snapshot, read once, shared by all extractors; the target is never written to."""

    def __init__(self, target, inv=None, max_files=100000, max_bytes=2_000_000, exclude=None, include_vendored=False):
        self.target = Path(target).resolve()
        self.inventory = inv or inventory(self.target, max_files, max_bytes)
        if exclude is None:
            from .scope import vendored_patterns
            exclude = [] if include_vendored else vendored_patterns()
        self.exclude = [prefix.strip('/') for prefix in exclude if prefix.strip('/')]
        self.files = [item for item in self.inventory['files'] if not self.excluded(item['path'])]
        self.excluded_files = [item['path'] for item in self.inventory['files'] if self.excluded(item['path'])]
        self._text = {}

    def excluded(self, rel):
        for prefix in self.exclude:
            if rel == prefix:
                return True
            if rel.startswith(prefix + '/') or rel.startswith('/' + prefix + '/'):
                return True
            if '/' + prefix + '/' in '/' + rel or rel.startswith(prefix + '/'):
                return True
            if fnmatch(rel, prefix) or fnmatch(rel, '*/' + prefix) or fnmatch(rel, '*/' + prefix + '/*'):
                return True
        return False

    @property
    def fingerprint(self): return self.inventory['fingerprint']

    def readable(self):
        return [item for item in self.files if item['capture'] == 'hashed']

    def category(self, rel): return classify(rel)

    def text(self, rel):
        """UTF-8 text of an in-target file, or None when it is binary, oversize or excluded."""
        if rel in self._text: return self._text[rel]
        value = None
        try:
            raw = safe_file(self.target, rel).read_bytes()
            decoded = raw.decode('utf-8')
            value = None if '\x00' in decoded else decoded
        except (ValueError, OSError, UnicodeError):
            value = None
        self._text[rel] = value
        return value
