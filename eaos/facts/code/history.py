"""Repository history as deterministic facts: churn, co-change, ownership and age.

Co-change is the only signal here that no static analysis can produce: files that keep changing
together without any visible dependency between them. Commit subjects are classified and then
discarded, so no commit text (which can carry credentials) enters the fact set.
"""
from collections import defaultdict
from itertools import combinations
import os
from pathlib import Path
import re
import subprocess
from typing import NamedTuple
from .. import digest, make

NAME = 'git_history'
VERSION = '1'
FIX = re.compile(r'\b(fix|fixes|fixed|bug|bugfix|hotfix|regression|revert|patch)\b', re.I)
FIELD = '\x1f'
RECORD = '\x1e'
LIMITATIONS = [
    'Merge commits are excluded; squashed or migrated history under-reports real change.',
    'Renames are not followed: a renamed file appears as a new path.',
    'Commits touching more than the bulk limit are excluded from co-change as vendor/bulk edits.',
    'Author identity is the committer-supplied name; it is not proof of who reviewed or owns the code.',
    'Change frequency is not defect probability; it is an attention signal that needs a change scenario.',
    'When the target is a subdirectory, history is scoped to that subtree and earlier moves are invisible.',
]


def git(target, args, timeout=120):
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'SystemRoot', 'WINDIR'}}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    return subprocess.run(['git', '-C', str(target), '--no-pager', '-c', 'core.quotepath=false', '-c', 'gc.auto=0', *args],
                          capture_output=True, text=True, env=env, timeout=timeout, check=False)


def available(target):
    probe = git(target, ['rev-parse', '--is-inside-work-tree'])
    return probe.returncode == 0 and probe.stdout.strip() == 'true'


def prefix_of(target):
    """When the target is a subdirectory of a repository, history must be scoped to that subtree."""
    result = git(target, ['rev-parse', '--show-prefix'])
    return result.stdout.strip() if result.returncode == 0 else ''


def read_log(target, max_commits):
    fmt = RECORD + '%H' + FIELD + '%an' + FIELD + '%aI' + FIELD + '%s'
    result = git(target, ['log', '--no-merges', '--no-renames', '--numstat', '--max-count=' + str(max_commits),
                          '--pretty=format:' + fmt, '--', '.'])
    if result.returncode != 0: raise ValueError('git log failed; inspect the repository locally')
    return result.stdout


def parse(raw):
    """Return commits as (sha, author, date, is_fix, [(added, deleted, path)]). Subjects are dropped here."""
    commits = (_commit(chunk) for chunk in raw.split(RECORD) if chunk.strip())
    return [commit for commit in commits if commit is not None]


def _numstat(body):
    """(added, deleted, path) of every file a commit's numstat lists; a binary file counts None lines."""
    files = []
    for columns in (line.split('\t') for line in body.splitlines()):
        if len(columns) != 3 or not columns[2]: continue
        added, deleted, path = columns
        files.append((None if added == '-' else int(added), None if deleted == '-' else int(deleted), path))
    return files


def _commit(chunk):
    header, _, body = chunk.partition('\n')
    parts = header.split(FIELD)
    if len(parts) != 4: return None
    sha, author, date, subject = parts
    return {'sha': sha, 'author': author, 'date': date, 'fix': bool(FIX.search(subject)), 'files': _numstat(body)}


def days_between(early, late):
    from datetime import datetime
    return round((datetime.fromisoformat(late) - datetime.fromisoformat(early)).total_seconds() / 86400.0, 1)


class Settings(NamedTuple):
    """How the history is read: the commit window, the support a pair of files needs, the largest commit counted
    as a change together, and how many hotspots the summary lists."""
    max_commits: int = 2000
    min_support: int = 3
    bulk_limit: int = 50
    top: int = 40


def extract(target, raw, input_sha, settings=Settings(), prefix=''):
    commits = _under(parse(raw), prefix)
    per_file, pairs = _tally(commits, settings.bulk_limit)
    # Reference point is the newest commit in the window, never wall-clock time, so reruns are identical.
    reference = max((c['date'] for c in commits), default=None)
    present = _working_tree(target)
    facts = [fact for path in sorted(per_file) for fact in _file_facts(path, per_file[path], reference, present, input_sha)]
    facts += _cochange_facts(pairs, per_file, settings.min_support, input_sha)
    return facts, _summary(commits, per_file, reference, settings)


def _under(commits, prefix):
    """The commits' files under the app root `prefix`, relative to it; commits left with none dropped."""
    if not prefix: return commits
    for commit in commits:
        commit['files'] = [(added, deleted, path[len(prefix):]) for added, deleted, path in commit['files'] if path.startswith(prefix)]
    return [commit for commit in commits if commit['files']]


def _new_file_row():
    return {'commits': 0, 'fix_commits': 0, 'added': 0, 'deleted': 0, 'authors': defaultdict(int), 'first': None, 'last': None}


def _count_change(row, commit, added, deleted):
    row['commits'] += 1
    row['fix_commits'] += int(commit['fix'])
    row['added'] += added or 0
    row['deleted'] += deleted or 0
    row['authors'][commit['author']] += 1
    row['last'] = max(row['last'] or commit['date'], commit['date'])
    row['first'] = min(row['first'] or commit['date'], commit['date'])


def _tally(commits, bulk_limit):
    """(per file: its changes, authors and dates; per pair of files: how many commits changed both)."""
    per_file, pairs = defaultdict(_new_file_row), defaultdict(int)
    for commit in commits:
        for added, deleted, path in commit['files']: _count_change(per_file[path], commit, added, deleted)
        paths = sorted({path for _, _, path in commit['files']})
        if 1 < len(paths) <= bulk_limit:
            for pair in combinations(paths, 2): pairs[pair] += 1
    return per_file, pairs


def _working_tree(target):
    return {p.relative_to(target).as_posix() for p in Path(target).rglob('*') if p.is_file() and '.git/' not in p.relative_to(target).as_posix()}


def _fact(input_sha, kind, location, value): return make(kind, NAME, VERSION, input_sha, location, value, limitations=LIMITATIONS)


def _file_facts(path, row, reference, present, input_sha):
    authors = sorted(row['authors'].items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(row['authors'].values())
    return [_fact(input_sha, 'history_churn', {'path': path}, {
                'commits': row['commits'], 'fix_commits': row['fix_commits'], 'lines_added': row['added'],
                'lines_deleted': row['deleted'], 'first_change': row['first'], 'last_change': row['last'],
                'days_since_last_change': days_between(row['last'], reference) if reference else None,
                'exists_in_working_tree': path in present}),
            _fact(input_sha, 'history_ownership', {'path': path}, {
                'authors': len(authors), 'top_author': authors[0][0], 'top_author_share': round(authors[0][1] / total, 3),
                'single_author': len(authors) == 1, 'commits': row['commits']})]


def _cochange_facts(pairs, per_file, min_support, input_sha):
    facts = []
    for (left, right), support in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0])):
        if support < min_support: continue
        confidence = round(support / min(per_file[left]['commits'], per_file[right]['commits']), 3)
        facts.append(_fact(input_sha, 'history_cochange', {'path': left, 'paired_path': right}, {
            'support': support, 'confidence': confidence,
            'commits_left': per_file[left]['commits'], 'commits_right': per_file[right]['commits']}))
    return facts


def _summary(commits, per_file, reference, settings):
    churn = sorted(per_file.items(), key=lambda kv: (-kv[1]['commits'], kv[0]))
    return {
        'commits_analysed': len(commits), 'files_touched': len(per_file), 'window_max_commits': settings.max_commits,
        'reference_commit_date': reference, 'min_support': settings.min_support, 'bulk_commit_limit': settings.bulk_limit,
        'hotspots': [{'path': p, 'commits': r['commits'], 'fix_commits': r['fix_commits'],
                      'lines_changed': r['added'] + r['deleted'], 'authors': len(r['authors'])} for p, r in churn[:settings.top]],
        'single_author_files': sorted(p for p, r in per_file.items() if len(r['authors']) == 1 and r['commits'] > 1),
        'interpretation': 'Attention signals only. High churn or single ownership is not a defect; it marks where a change scenario deserves review.',
    }


def additions(target, max_commits=500, bulk_limit=Settings().bulk_limit):
    """Newest first, each commit's {sha, date, added, changed} (paths relative to `target`), for a project's extension
    guide: what an addition touched. Merges and mass commits (over `bulk_limit` files) are left out; no git, none."""
    if not available(target): return []
    done = git(target, ['log', '--no-merges', '--no-renames', '--name-status', f'--max-count={max_commits}',
                        f'--pretty=format:{RECORD}%h{FIELD}%aI', '--', '.'])
    prefix = prefix_of(target)
    commits = (_changes(chunk, prefix) for chunk in done.stdout.split(RECORD) if chunk.strip())
    return [commit for commit in commits if 0 < len(commit['changed']) <= bulk_limit]


def _changes(chunk, prefix):
    header, _, body = chunk.partition('\n')
    sha, date = header.split(FIELD)
    rows = [line.split('\t') for line in body.splitlines() if line.count('\t') == 1]
    rows = [(status, path[len(prefix):]) for status, path in rows if path.startswith(prefix)]
    return {'sha': sha, 'date': date[:10], 'added': [path for status, path in rows if status == 'A'],
            'changed': [path for status, path in rows if status != 'D']}


def run(target, source=None, max_commits=2000, **options):
    target = Path(target)
    if not available(target):
        return {'facts': [], 'summary': {'commits_analysed': 0}, 'available': False, 'input_sha': digest(b''),
                'reason': 'No git work tree at the target; history facts are unavailable for this snapshot.'}
    raw = read_log(target, max_commits)
    input_sha = digest(raw.encode('utf-8'))
    facts, summary = extract(target, raw, input_sha, Settings(max_commits, **options), prefix_of(target))
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': input_sha, 'reason': None}
