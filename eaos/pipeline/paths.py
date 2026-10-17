"""The paths of a check, declared once: what each looks at, and the stages, engines and cards a choice of them runs.

A check follows one path or several together. Every path runs the spine (the required stages, which are cheap and make
the report, and the assistant's review of the cards); each adds the optional stages it needs, the engines whose
capabilities it looks at (a new engine joins its path by what it finds, not by its name), and keeps the card patterns
it is about. `complete` is all of them.

    resolve(['security', 'look'])  {'paths', 'stages', 'engines', 'patterns'}: the union, closed over what they require

How scalability splits: how easily the code grows is in `code`, how the app holds under load is in `speed`.
"""
from .stages import BY_NAME, ORDER, REQUIRED, STAGES

COMPLETE = 'complete'
# The assistant's review every path keeps: the cards it found, judged, ordered and written in both languages.
SPINE = ('proposals', 'triage', 'order', 'translate')
PATHS = {
    'complete': {'names': ('Complete', 'شامل'),
                 'looks_at': ('Every path, together: the whole check', 'كل المسارات معًا: الفحص كامل')},
    'security': {'names': ('Security', 'الأمان'),
                 'looks_at': ('Exposed secrets, vulnerabilities, dependencies and their licences, dangerous settings, access gaps',
                              'الأسرار المكشوفة، والثغرات، والمكتبات وتراخيصها، والإعدادات الخطرة، وثغرات الصلاحيات'),
                 'stages': ('engines',), 'kinds': ('secret', 'vulnerability', 'misconfiguration'), 'engines': ('syft',),
                 'patterns': ('security_weakness', 'access_gap', 'upgrade_dependency')},
    'look': {'names': ('Look and screens', 'الشكل والشاشات'),
             'looks_at': ("The app's screens, their accessibility and speed, the design review, users' journeys",
                          'الشاشات، وسهولة الاستخدام، وسرعة الصفحات، ومراجعة التصميم، ورحلات المستخدم'),
             'stages': ('setup', 'lock', 'record', 'journeys', 'crawl', 'screens', 'visual'), 'patterns': ('design_review',)},
    'code': {'names': ('Code', 'الكود'),
             'looks_at': ('Structure and layers, cycles and coupling, complexity, duplication, dead code, the tests, how easily it grows',
                          'البنية والطبقات، والتشابك، والتعقيد، والتكرار، والكود الميت، والاختبارات، وسهولة التوسع'),
             'stages': ('engines', 'setup', 'verify', 'architecture', 'policy', 'semantic', 'ideal', 'pipeline_gaps'),
             'kinds': ('boundary', 'complexity', 'coupling', 'cycle', 'dataflow', 'dead_code', 'duplication', 'literal_duplication',
                       'surface', 'unused_dependency', 'call_edge_external', 'module_edge_external', 'symbol_metric_external',
                       'sql_quality', 'api_contract'),
             'engines': ('scc', 'ast-grep', 'react-docgen'),
             'patterns': ('import_cycle', 'duplicated_rule', 'hidden_coupling', 'trace_gap', 'untested_path', 'hotspot', 'split_module',
                          'mutable_state', 'external_write', 'policy_violation', 'canonicalize', 'dead_code', 'remove_dead',
                          'broken_code', 'generic')},
    'speed': {'names': ('Speed and scale', 'السرعة والتحمل'),
              'looks_at': ('The app under load, the cost of each entry at 1000 times the use, the hot paths, production readiness',
                           'البرنامج تحت الضغط، وكلفة كل نقطة دخول لو زاد الاستخدام 1000 مرة، والمسارات الساخنة، وجاهزية التشغيل الفعلي'),
              'stages': ('engines', 'setup', 'baseline'), 'kinds': ('hot_path_external', 'call_edge_external'),
              'patterns': ('load_blocker', 'redundant_work')},
}


def _closed(names):
    """`names` and every stage they require, in the declared order."""
    wanted, frontier = set(), list(names)
    while frontier:
        name = frontier.pop()
        if name in wanted: continue
        wanted.add(name)
        frontier += BY_NAME[name].requires
    return [name for name in ORDER if name in wanted]


def resolve(paths):
    """What a check following `paths` runs: {'paths', 'stages' (None: all), 'engines' (None: every installed one, []:
    none asked), 'patterns' (None: all)}. Unknown paths are refused."""
    paths = sorted(set(paths or [COMPLETE]))
    unknown = [p for p in paths if p not in PATHS]
    if unknown: raise ValueError(f"unknown check path: {', '.join(unknown)} (one of {', '.join(PATHS)})")
    if COMPLETE in paths: return {'paths': [COMPLETE], 'stages': None, 'engines': None, 'patterns': None}
    chosen = [PATHS[p] for p in paths]
    joined = lambda key: sorted({value for path in chosen for value in path.get(key, ())})
    spine = [stage.name for stage in STAGES if stage.necessity == REQUIRED] + list(SPINE)
    return {'paths': paths, 'stages': _closed(spine + joined('stages')), 'engines': _engines(joined('kinds'), joined('engines')),
            'patterns': joined('patterns')}


def _engines(kinds, named):
    """The engines that find any of `kinds`, and those `named`."""
    from ..engines import ADAPTERS
    return sorted({name for name, adapter in ADAPTERS.items() if set(kinds) & {c.kind for c in adapter.capabilities()}} | set(named))
