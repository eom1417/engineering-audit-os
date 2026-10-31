"""Shared read-only access to a target snapshot for every extractor."""
from fnmatch import fnmatch
from pathlib import Path
from .discovery import classify
from ..core.project.workspace import digest, inventory, safe_file

LANGUAGE_BY_SUFFIX = {
    '.py': 'python', '.pyi': 'python', '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
    '.cjs': 'javascript', '.ts': 'typescript', '.tsx': 'tsx', '.go': 'go', '.java': 'java', '.rs': 'rust',
    '.rb': 'ruby', '.php': 'php', '.cs': 'csharp', '.kt': 'kotlin', '.swift': 'swift', '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.hpp': 'cpp', '.ex': 'elixir', '.exs': 'elixir', '.dart': 'dart',
    '.scala': 'scala', '.sh': 'bash', '.sql': 'sql', '.vue': 'vue', '.svelte': 'svelte',
}

# Minified or bundled output has lines no person writes; checked on scripts and stylesheets only.
GENERATED_SUFFIXES = ('.js', '.mjs', '.cjs', '.css')
GENERATED_LINE = 1000


def language_of(path): return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower())


class Source:
    """One snapshot, read once, shared by all extractors; the target is never written to."""

    def __init__(self, target, inv=None, max_files=100000, max_bytes=2_000_000, exclude=None, include_vendored=False):  # limits: parameters -- the snapshot's bounds, each a keyword with its default
        self.target = Path(target).resolve()
        self.inventory = inv or inventory(self.target, max_files, max_bytes)
        from .scope import GENERATED, vendored_patterns
        if exclude is None:
            exclude = [] if include_vendored else vendored_patterns()
        self.exclude = [prefix.strip('/') for prefix in [*exclude, *GENERATED] if prefix.strip('/')]
        self._text = {}
        self.files, self.excluded_files = self._split()
        self.unread_names = [row for row in self.inventory.get('unread_names', ()) if not self.excluded(row['path'])]

    def _split(self):
        """The files the extractors read (in scope and not generated), and the paths of those left out."""
        files = [item for item in self.inventory['files'] if not self.excluded(item['path']) and not self.generated(item)]
        kept = {item['path'] for item in files}
        return files, [item['path'] for item in self.inventory['files'] if item['path'] not in kept]

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

    def generated(self, item):
        """A script or stylesheet whatever its name whose text has a line over GENERATED_LINE characters: minified
        or bundled output (a built assets/index-B3x9.js), which no person writes or changes."""
        if Path(item['path']).suffix.lower() not in GENERATED_SUFFIXES or item.get('capture') != 'hashed': return False
        text = self.text(item['path']) or ''
        return any(len(line) > GENERATED_LINE for line in text.split('\n'))

    @property
    def fingerprint(self): return self.inventory['fingerprint']

    @property
    def content_fingerprint(self):
        """A digest of what the files say: each in-scope path with its size and content hash, and no
        modification time. The inventory fingerprint also hashes mtimes, so a fresh checkout of the same
        commit gives it a new value; a fact id derived from it would change between machines."""
        return digest('\n'.join(f"{item['path']}\t{item['size']}\t{item['sha256']}"
                                 for item in sorted(self.files, key=lambda item: item['path'])).encode('utf-8'))

    def readable(self):
        return [item for item in self.files if item['capture'] == 'hashed']

    def category(self, rel): return classify(rel)

    def readable_including_sensitive(self):
        """Every readable file plus sensitive-flagged files."""
        return [item for item in self.inventory['files']
                if item.get('capture') in ('hashed', 'sensitive_metadata_only')]

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
