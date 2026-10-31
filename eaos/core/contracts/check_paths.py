"""The paths a check can follow, declared once as data: the stages, engine kinds and card patterns each keeps; their names
and what each looks at are the words catalog's (eaos/data/words.json `paths`, the Studio's too). eaos/pipeline/path_choice.py
resolves a choice of them into what runs."""
from ..language.words import catalog

COMPLETE = 'complete'
# The assistant's review every path keeps: the cards it found, judged, ordered and written in both languages.
SPINE = ('proposals', 'triage', 'order', 'translate')
# The person's own rules hold whatever is checked (M16): their stage and their cards are on every path.
HELD = {'stages': ('rules',), 'patterns': ('person_rule',)}
PATHS = {
    'complete': {},
    'security': {'stages': ('engines',), 'kinds': ('secret', 'vulnerability', 'misconfiguration'), 'engines': ('syft', 'presidio', 'ast-grep'),
                 'patterns': ('security_weakness', 'upgrade_dependency', 'layer_boundary', 'real_data')},
    'look': {'stages': ('roles', 'setup', 'session', 'lock', 'record', 'journeys', 'crawl', 'screens', 'visual'), 'patterns': ('design_review', 'one_source')},
    'code': {'stages': ('engines', 'setup', 'verify', 'architecture', 'policy', 'semantic', 'ideal', 'pipeline_gaps'),
             'kinds': ('boundary', 'complexity', 'coupling', 'cycle', 'dataflow', 'dead_code', 'duplication', 'literal_duplication',
                       'surface', 'unused_dependency', 'symbol_metric_external',
                       'sql_quality', 'api_contract'),
             'engines': ('scc', 'ast-grep', 'react-docgen', 'jscpd'),
             'patterns': ('import_cycle', 'duplicated_rule', 'hidden_coupling', 'trace_gap', 'untested_path', 'hotspot', 'split_module',
                          'mutable_state', 'external_write', 'policy_violation', 'layer_boundary', 'canonicalize', 'dead_code', 'remove_dead',
                          'broken_code', 'repository_craft', 'old_engine', 'data_keeping', 'one_source', 'generic')},
    'speed': {'stages': ('engines', 'setup', 'baseline', 'session', 'keeping'),
              'patterns': ('load_blocker', 'redundant_work', 'data_keeping')},
    # the layers tried on the running app (M6.6, M6.7): beside `complete` it is an option of the full check
    'layers': {'stages': ('setup', 'session', 'layers_trial'), 'patterns': ('layer_boundary', 'security_weakness')},
    # simulated users on the running app (M10.9): alone the whole simulation, beside `complete` its short option; the
    # difficulties' cards have no pattern of their own (eaos/analysis/repair/remediation.py classify: generic)
    'experience': {'stages': ('roles', 'setup', 'session', 'experience'), 'patterns': ('generic',)},
}
# each path's (English, Arabic) name and what it looks at, as its readers take them
for _id, _path in PATHS.items():
    _words = catalog()['paths'][_id]
    _path.update(names=tuple(reversed(_words['name'])), looks_at=tuple(reversed(_words['looks_at'])))
