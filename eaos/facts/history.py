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
from . import digest, make

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
    commits = []
    for chunk in raw.split(RECORD):
        if not chunk.strip(): continue
        header, _, body = chunk.partition('\n')
        parts = header.split(FIELD)
        if len(parts) != 4: continue
        sha, author, date, subject = parts
        files = []
        for line in body.splitlines():
            columns = line.split('\t')
            if len(columns) != 3: continue
            added, deleted, path = columns
            if not path: continue
            files.append((None if added == '-' else int(added), None if deleted == '-' else int(deleted), path))
        commits.append({'sha': sha, 'author': author, 'date': date, 'fix': bool(FIX.search(subject)), 'files': files})
    return commits


def days_between(early, late):
    from datetime import datetime
    return round((datetime.fromisoformat(late) - datetime.fromisoformat(early)).total_seconds() / 86400.0, 1)


def extract(target, raw, input_sha, max_commits=2000, min_support=3, bulk_limit=50, top=40, prefix=''):
    commits = parse(raw)
    if prefix:
        for commit in commits:
            commit['files'] = [(added, deleted, path[len(prefix):]) for added, deleted, path in commit['files'] if path.startswith(prefix)]
        commits = [commit for commit in commits if commit['files']]
    per_file = defaultdict(lambda: {'commits': 0, 'fix_commits': 0, 'added': 0, 'deleted': 0, 'authors': defaultdict(int), 'first': None, 'last': None})
    pairs = defaultdict(int)
    for commit in commits:
        paths = sorted({path for _, _, path in commit['files']})
        for added, deleted, path in commit['files']:
            row = per_file[path]
            row['commits'] += 1
            row['fix_commits'] += int(commit['fix'])
            row['added'] += added or 0
            row['deleted'] += deleted or 0
            row['authors'][commit['author']] += 1
            row['last'] = max(row['last'] or commit['date'], commit['date'])
            row['first'] = min(row['first'] or commit['date'], commit['date'])
        if 1 < len(paths) <= bulk_limit:
            for pair in combinations(paths, 2): pairs[pair] += 1
    # Reference point is the newest commit in the window, never wall-clock time, so reruns are identical.
    reference = max((c['date'] for c in commits), default=None)
    facts = []
    present = {p.relative_to(target).as_posix() for p in Path(target).rglob('*') if p.is_file() and '.git/' not in p.relative_to(target).as_posix()}

    def fact(kind, location, value): return make(kind, NAME, VERSION, input_sha, location, value, limitations=LIMITATIONS)

    for path in sorted(per_file):
        row = per_file[path]
        authors = sorted(row['authors'].items(), key=lambda kv: (-kv[1], kv[0]))
        total = sum(row['authors'].values())
        facts.append(fact('history_churn', {'path': path}, {
            'commits': row['commits'], 'fix_commits': row['fix_commits'], 'lines_added': row['added'],
            'lines_deleted': row['deleted'], 'first_change': row['first'], 'last_change': row['last'],
            'days_since_last_change': days_between(row['last'], reference) if reference else None,
            'exists_in_working_tree': path in present}))
        facts.append(fact('history_ownership', {'path': path}, {
            'authors': len(authors), 'top_author': authors[0][0], 'top_author_share': round(authors[0][1] / total, 3),
            'single_author': len(authors) == 1, 'commits': row['commits']}))
    for (left, right), support in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0])):
        if support < min_support: continue
        confidence = round(support / min(per_file[left]['commits'], per_file[right]['commits']), 3)
        facts.append(fact('history_cochange', {'path': left, 'paired_path': right}, {
            'support': support, 'confidence': confidence,
            'commits_left': per_file[left]['commits'], 'commits_right': per_file[right]['commits']}))
    churn = sorted(per_file.items(), key=lambda kv: (-kv[1]['commits'], kv[0]))
    summary = {
        'commits_analysed': len(commits), 'files_touched': len(per_file), 'window_max_commits': max_commits,
        'reference_commit_date': reference, 'min_support': min_support, 'bulk_commit_limit': bulk_limit,
        'hotspots': [{'path': p, 'commits': r['commits'], 'fix_commits': r['fix_commits'],
                      'lines_changed': r['added'] + r['deleted'], 'authors': len(r['authors'])} for p, r in churn[:top]],
        'single_author_files': sorted(p for p, r in per_file.items() if len(r['authors']) == 1 and r['commits'] > 1),
        'interpretation': 'Attention signals only. High churn or single ownership is not a defect; it marks where a change scenario deserves review.',
    }
    return facts, summary


def run(target, source=None, max_commits=2000, **options):
    target = Path(target)
    if not available(target):
        return {'facts': [], 'summary': {'commits_analysed': 0}, 'available': False, 'input_sha': digest(b''),
                'reason': 'No git work tree at the target; history facts are unavailable for this snapshot.'}
    raw = read_log(target, max_commits)
    input_sha = digest(raw.encode('utf-8'))
    facts, summary = extract(target, raw, input_sha, max_commits=max_commits, prefix=prefix_of(target), **options)
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': input_sha, 'reason': None}
