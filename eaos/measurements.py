"""One row per analysed source file: size, complexity, duplication, change, ownership and dependency, by number.

Nothing here parses code. Every field is read from a fact another stage or engine already recorded, and
the row names where each came from (`sources`):

  loc             scc's code lines (symbol_metric_external, engine scc); else EAOS's own file metric
  language        the syntax extractor's source_file fact
  complexity_max  CodeGraph's cyclomatic complexity of the file's most complex symbol; else EAOS's lexical
                  count, branches + 1, of its functions and methods, or of the file body when it has none
  duplicated_lines lines of this file jscpd found copied elsewhere (its clone sites)
  churn           commits that changed the file (history_churn), with authors and the last change date
  fan_in, fan_out files that import it and files it imports (graph_node)
  coverage        line coverage from verification.json, only when a test command was run

A field with no source stays null and its reason is written in `missing`: an unknown is never a zero.
The rows are the files the audit parsed, so the table and dossier.coverage.files_parsed agree; files it
could not parse are listed under not_measured with their reason.
"""
import json
from pathlib import Path

from .workspace import write

FUNCTION_SCOPES = ('function', 'method')


def _facts(out):
    rows = []
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        rows += [row for row in data.get('facts') or [] if isinstance(row, dict)]
    return rows


def _engines_observed(out):
    try: data = json.loads((Path(out) / 'facts/external.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return set()
    return set((data.get('summary') or {}).get('engines_observed') or [])


def _path_of(fact):
    return (fact.get('location') or {}).get('path')


def _coverage(out):
    """{path: covered fraction 0..1} from verification.json, which holds percents."""
    verification = out / 'verification.json'
    if not verification.is_file(): return {}
    try: return {path: round(value['percent'] / 100, 4)
                 for path, value in (json.loads(verification.read_text(encoding='utf-8')).get('coverage') or {}).items()}
    except (ValueError, KeyError, TypeError): return {}


class _Indexes:
    """Every fact a row is read from, indexed by file once; each method fills its fields of one row, with the source it
    used or the reason it is missing."""

    def __init__(self, out, by_kind):
        metric_external = by_kind.get('symbol_metric_external', [])
        self.scc = {_path_of(f): f['value'] for f in metric_external if f['value'].get('engine') == 'scc'}
        self.codegraph = {}
        for fact in metric_external:
            if fact['value'].get('engine') == 'codegraph' and isinstance(fact['value'].get('complexity'), (int, float)):
                self.codegraph[_path_of(fact)] = max(self.codegraph.get(_path_of(fact), 0), fact['value']['complexity'])
        self.own_file, self.own_symbols = {}, {}
        for fact in by_kind.get('metric', []):
            value = fact['value']
            if value.get('scope') == 'file': self.own_file[_path_of(fact)] = value
            elif value.get('scope') in FUNCTION_SCOPES:
                self.own_symbols[_path_of(fact)] = max(self.own_symbols.get(_path_of(fact), 0), (value.get('branches') or 0) + 1)
        self.jscpd_seen = 'jscpd' in _engines_observed(out)
        self.duplicated = self._duplicated(by_kind.get('engine_finding', []))
        self.churn = {_path_of(f): f['value'] for f in by_kind.get('history_churn', [])}
        self.ownership = {_path_of(f): f['value'] for f in by_kind.get('history_ownership', [])}
        self.graph = {_path_of(f): f['value'] for f in by_kind.get('graph_node', [])}
        self.coverage = _coverage(out)

    @staticmethod
    def _duplicated(findings):
        duplicated = {}
        for fact in findings:
            value = fact['value']
            if value.get('engine') != 'jscpd': continue
            lines = next((m['value'] for m in value.get('measurements') or [] if m['name'] == 'duplicated_lines'), None) or 0
            for site in value.get('sites') or []:
                duplicated[site['path']] = duplicated.get(site['path'], 0) + lines
        return duplicated

    def loc(self, path, row, used, missing):
        if path in self.scc: row['loc'], used['loc'] = self.scc[path].get('code'), 'scc'
        elif path in self.own_file: row['loc'], used['loc'] = self.own_file[path].get('code_lines'), 'eaos.metrics'
        else:
            row['loc'] = None
            missing.append({'field': 'loc', 'reason': 'neither scc nor EAOS measured this file'})

    def complexity(self, path, row, used, missing):
        if path in self.codegraph: row['complexity_max'], used['complexity_max'] = self.codegraph[path], 'codegraph'
        elif path in self.own_symbols: row['complexity_max'], used['complexity_max'] = self.own_symbols[path], 'eaos.metrics (branches + 1)'
        elif path in self.own_file:
            row['complexity_max'], used['complexity_max'] = (self.own_file[path].get('branches') or 0) + 1, 'eaos.metrics (file body, no function)'
        else:
            row['complexity_max'] = None
            missing.append({'field': 'complexity_max', 'reason': 'no symbol or file metric for this file'})

    def duplication(self, path, row, used, missing):
        if self.jscpd_seen: row['duplicated_lines'], used['duplicated_lines'] = self.duplicated.get(path, 0), 'jscpd'
        else:
            row['duplicated_lines'] = None
            missing.append({'field': 'duplicated_lines', 'reason': 'jscpd did not run in this audit'})

    def history(self, path, row, used, missing):
        if path in self.churn:
            row['churn'], row['last_changed'] = self.churn[path].get('commits'), self.churn[path].get('last_change')
            row['authors'] = (self.ownership.get(path) or {}).get('authors')
            used['churn'] = 'git history'
        else:
            row['churn'] = row['authors'] = row['last_changed'] = None
            missing.append({'field': 'churn', 'reason': 'not in the recorded git history' if self.churn else 'the project has no git history'})

    def dependency(self, path, row, used, missing):
        if path in self.graph:
            row['fan_in'], row['fan_out'], used['fan_in'] = self.graph[path].get('fan_in'), self.graph[path].get('fan_out'), 'eaos.graph'
        else:
            row['fan_in'] = row['fan_out'] = None
            missing.append({'field': 'fan_in', 'reason': 'not in the resolved import graph'})

    def tested(self, path, row, used, missing):
        row['coverage'] = self.coverage.get(path)
        if row['coverage'] is None:
            missing.append({'field': 'coverage', 'reason': 'no test command was run' if not self.coverage else 'the tests did not load this file'})

    def row(self, fact):
        path, missing, used = _path_of(fact), [], {}
        row = {'path': path, 'language': fact['value'].get('language') or 'unknown'}
        for fill in (self.loc, self.complexity, self.duplication, self.history, self.dependency, self.tested):
            fill(path, row, used, missing)
        row['missing'], row['sources'] = missing, used
        return row


def build(out):
    out = Path(out)
    by_kind = {}
    for fact in _facts(out): by_kind.setdefault(fact['kind'], []).append(fact)
    files = by_kind.get('source_file', [])
    sources = [f for f in files if (f.get('value') or {}).get('parse_status') == 'OBSERVED']
    skipped = [{'path': _path_of(f), 'reason': f"not parsed: {(f.get('value') or {}).get('parse_status')}"}
               for f in files if (f.get('value') or {}).get('parse_status') != 'OBSERVED']
    indexes = _Indexes(out, by_kind)
    rows = [indexes.row(fact) for fact in sorted(sources, key=_path_of)]
    return {'schema_version': 1, 'files': rows, 'not_measured': skipped,
            'complete': sum(all(r[f] is not None for f in ('loc', 'complexity_max', 'churn', 'fan_in')) for r in rows)}


def render(record, language='ar', top=20):
    ar = language == 'ar'
    lines = _render_head(record, ar)
    show = lambda value: '—' if value is None else str(value)
    ranked = sorted(record['files'], key=lambda r: (-(r['complexity_max'] or 0), -(r['churn'] or 0), r['path']))[:top]
    for row in ranked:
        lines.append(f"| `{row['path']}` | {show(row['loc'])} | {show(row['complexity_max'])} | {show(row['churn'])} | "
                     f"{show(row['fan_in'])} | {show(row['duplicated_lines'])} |")
    return _render_tail(record, ar, lines)


def _render_head(record, ar):
    """The page's title, how many files are measured whole, and the head of the table of the most complex files."""
    return ['# ' + ('القياس لكل ملف' if ar else 'Measurements per file'), '',
             (f"{record['complete']} من {len(record['files'])} ملفًا محللًا لها الحجم والتعقيد والتغيّر والاعتماد كلها. "
              if ar else f"{record['complete']} of {len(record['files'])} analysed files have size, complexity, change and dependency. ")
             + ('التفصيل الكامل في measurements.json.' if ar else 'The full table is measurements.json.'), '',
             ('## أعلى الملفات تعقيدًا' if ar else '## The most complex files'), '',
             '| ' + (' | '.join(['الملف', 'الأسطر', 'أعلى تعقيد', 'مرات التغيير', 'يعتمد عليه', 'مكرر']) if ar else
                    ' | '.join(['File', 'Lines', 'Max complexity', 'Commits', 'Fan-in', 'Duplicated'])) + ' |',
             '|---|---:|---:|---:|---:|---:|']


def _render_tail(record, ar, lines):
    if record['not_measured']:
        lines += ['', ('غير مقيس: ' if ar else 'Not measured: ') + f"{len(record['not_measured'])} " +
                  ('ملفًا لم يُحلَّل (السبب لكل ملف في measurements.json).' if ar else 'files not parsed (each reason is in measurements.json).')]
    return '\n'.join(lines) + '\n'


def run(out, language='ar'):
    record = build(out)
    write(Path(out) / 'measurements.json', record)
    (Path(out) / 'MEASUREMENTS.md').write_text(render(record, language), encoding='utf-8')
    return {'files': len(record['files']), 'complete': record['complete']}
