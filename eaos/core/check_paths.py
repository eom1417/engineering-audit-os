"""The paths a check can follow, declared once as data: the stages, engine kinds and card patterns each keeps; their names
and what each looks at are the words catalog's (eaos/data/words.json `paths`, the Studio's too). eaos/pipeline/paths.py
resolves a choice of them into what runs."""
from .words import catalog

COMPLETE = 'complete'
# The assistant's review every path keeps: the cards it found, judged, ordered and written in both languages.
SPINE = ('proposals', 'triage', 'order', 'translate')
PATHS = {
    'complete': {},
    'security': {'stages': ('engines',), 'kinds': ('secret', 'vulnerability', 'misconfiguration'), 'engines': ('syft',),
                 'patterns': ('security_weakness', 'upgrade_dependency', 'layer_boundary')},
    'look': {'stages': ('roles', 'setup', 'session', 'lock', 'record', 'journeys', 'crawl', 'screens', 'visual'), 'patterns': ('design_review',)},
    'code': {'stages': ('engines', 'setup', 'verify', 'architecture', 'policy', 'semantic', 'ideal', 'pipeline_gaps'),
             'kinds': ('boundary', 'complexity', 'coupling', 'cycle', 'dataflow', 'dead_code', 'duplication', 'literal_duplication',
                       'surface', 'unused_dependency', 'call_edge_external', 'module_edge_external', 'symbol_metric_external',
                       'sql_quality', 'api_contract'),
             'engines': ('scc', 'ast-grep', 'react-docgen'),
             'patterns': ('import_cycle', 'duplicated_rule', 'hidden_coupling', 'trace_gap', 'untested_path', 'hotspot', 'split_module',
                          'mutable_state', 'external_write', 'policy_violation', 'layer_boundary', 'canonicalize', 'dead_code', 'remove_dead',
                          'broken_code', 'generic')},
    # the layers tried on the running app (M6.6, M6.7): beside `complete` it is an option of the full check
    'layers': {'stages': ('setup', 'session', 'layers_trial'), 'patterns': ('layer_boundary', 'security_weakness')},
    'speed': {'stages': ('engines', 'setup', 'baseline'), 'kinds': ('hot_path_external', 'call_edge_external'),
              'patterns': ('load_blocker', 'redundant_work')},
}
# each path's (English, Arabic) name and what it looks at, as its readers take them
for _id, _path in PATHS.items():
    _words = catalog()['paths'][_id]
    _path.update(names=tuple(reversed(_words['name'])), looks_at=tuple(reversed(_words['looks_at'])))
