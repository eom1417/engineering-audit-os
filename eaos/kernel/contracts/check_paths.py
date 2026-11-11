"""The paths a check can follow, declared once as data: the stages, engine kinds and card patterns each keeps; their
names and what each looks at are the words catalog's (eaos/data/words.json `paths`). eaos/features/check/journey/path_choice.py
resolves a choice of them into what runs."""
from ..language.words import catalog

COMPLETE = 'complete'
# The assistant's review every path keeps: the cards it found, judged, ordered and written in both languages.
SPINE = ('triage', 'order', 'translate')
# The person's own rules hold whatever is checked: their stage and their cards are on every path.
HELD = {'stages': ('rules',), 'patterns': ('person_rule',)}
PATHS = {
    'complete': {},
    'security': {'stages': ('engines',), 'kinds': ('secret', 'vulnerability', 'misconfiguration'),
                 'engines': ('presidio', 'ast-grep'),
                 'patterns': ('security_weakness', 'upgrade_dependency', 'layer_boundary', 'real_data')},
    'look': {'stages': ('roles', 'setup', 'session', 'lock', 'record', 'journeys', 'crawl', 'screens'),
             'patterns': ('design_review', 'one_source')},
    'code': {'stages': ('engines', 'setup', 'verify', 'architecture', 'policy'),
              'kinds': ('boundary', 'complexity', 'coupling', 'cycle', 'dataflow', 'dead_code', 'duplication',
              'literal_duplication',
                       'surface', 'unused_dependency', 'symbol_metric_external',
                       'sql_quality', 'api_contract'),
             'engines': ('ast-grep', 'jscpd'),
              'patterns': ('import_cycle', 'duplicated_rule', 'hidden_coupling', 'trace_gap', 'untested_path',
              'hotspot', 'split_module',
                           'mutable_state', 'external_write', 'policy_violation', 'layer_boundary',
                           'canonicalize', 'dead_code', 'remove_dead',
                          'broken_code', 'repository_craft', 'old_engine', 'data_keeping', 'one_source', 'generic')},
    'speed': {'stages': ('engines', 'setup', 'session'),
              'patterns': ('load_blocker', 'redundant_work', 'data_keeping')},
}
# each path's (English, Arabic) name and what it looks at, as its readers take them
for _id, _path in PATHS.items():
    _words = catalog()['paths'][_id]
    _path.update(names=tuple(reversed(_words['name'])), looks_at=tuple(reversed(_words['looks_at'])))
