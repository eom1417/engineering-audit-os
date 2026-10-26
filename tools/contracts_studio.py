"""The Studio's data contract, its first sections (NS36): the manifest and the sections a v1 reader
knows, and what every section shares (tools/make_contracts.py writes them)."""
from contract_shapes import B, N, NI, NS, S, arr, enum, obj

# The Studio's data contract (NS36): studio/manifest.json and one file per section, written by EAOS
# after every check. Every section carries the contract version; a ratio is bounded to 0..1; a number the Studio shows
# is a measure with its source; what was not measured is null, never 0; a path is relative to the project.
STUDIO_CONTRACT = 1
SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system')
# Contract v2: sections added without breaking a v1 reader. They keep "contract": 1 (the number a
# reader-breaking change raises) and carry "revision": 2; a v1 reader ignores a section it does not know.
STUDIO_REVISION = 2
SECTIONS_V2 = ('functions', 'screens', 'gaps', 'operations', 'history', 'coverage', 'paths', 'journeys', 'hidden', 'data_paths', 'infra',
               'pipeline', 'ideal', 'nodes', 'library', 'layers')
REF = lambda name: {'$ref': f'#/$defs/{name}'}
DEFS = {
    'ratio': {'type': 'number', 'minimum': 0, 'maximum': 1},
    'source': {'type': 'string', 'minLength': 1, 'description': 'file#field, or the formula, the number comes from'},
    'measure': obj({'value': {'type': ['number', 'null'], 'minimum': 0}, 'src': REF('source'),
                    'unit': enum('count', 'seconds', 'bytes', 'lines')}, ['value', 'src']),
    'ratio_measure': obj({'value': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}, 'src': REF('source')},
                         ['value', 'src']),
    'path': {'type': 'string', 'minLength': 1, 'pattern': r'^(?![/\\~])(?![A-Za-z]:)(?!(.*/)?\.\.(/|$))'},
    'scan': obj({'commit': NS, 'branch': NS, 'at': S, 'recorded': B, 'detached': {'type': ['boolean', 'null']},
                 'dirty': {'type': ['boolean', 'null']}}, ['commit', 'branch', 'at']),
}
CARD_STATES = ('open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped')
PLAN_STATES = ('draft', 'registered', 'approved', 'rejected', 'active', 'review', 'merged', 'closed', 'regressed', 'archived')
TASK_STATES = ('todo', 'active', 'done', 'blocked', 'regressed')
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
COVERAGE_STATES = ('measured', 'empty', 'partial', 'not_measured', 'failed')
COVERAGE_REASONS = ('written', 'nothing_found', 'some_parts_missing', 'not_built', 'facts_not_exported', 'stage_failed',
                    'section_error', 'needs_run', 'needs_screens')


def section(props, required):
    return obj({'schema_version': {'const': 1}, 'contract': {'const': STUDIO_CONTRACT}, **props},
               ['schema_version', 'contract', *required])


def section_v2(props, required):
    return obj({'schema_version': {'const': 1}, 'contract': {'const': STUDIO_CONTRACT}, 'revision': {'const': STUDIO_REVISION},
                **props}, ['schema_version', 'contract', 'revision', *required])


COUNT = {'type': 'integer', 'minimum': 0}
REFS = arr(S)


# The system section (studio/system.json): the territory maps of today and of the target, laid out by EAOS so the
# Studio only draws (eaos/report/studio/system.py, eaos/report/studio/territory.py). The precursor of NS39.T1's unified graph.
_COUNT = {'type': 'integer', 'minimum': 0}
_XY = {'type': 'number'}
_OP = enum('retain', 'modify', 'rebuild', 'delete', 'merge', 'introduce')
_NAME = obj({'ar': S, 'en': S, 'ident': B}, ['ar', 'en', 'ident'])
_LABEL = obj({'x': _XY, 'y': _XY, 'anchor': enum('start', 'middle', 'end'), 'size': N, 'placed': B, 'big': B},
             ['x', 'y', 'anchor', 'size', 'placed'])
_REGION = obj({'id': S, 'kind': enum('dir', 'rest', 'top', 'layer'), 'folder': NS, 'name': _NAME, 'components': _COUNT,
               'files': _COUNT, 'findings': NI, 'lead': S,
               'label': obj({'x': _XY, 'y': _XY, 'tx': _XY, 'ty': _XY}, ['x', 'y', 'tx', 'ty']),
               'land': arr(obj({'level': {'type': 'integer', 'minimum': 0, 'maximum': 2}, 'd': S}, ['level', 'd']))},
              ['id', 'kind', 'name', 'components', 'files', 'lead', 'label', 'land'])
_EDGE = obj({'from': S, 'to': S, 'imports': _COUNT, 'cycle': B, 'd': S, 'mid': arr(_XY), 'width': N},
            ['from', 'to', 'imports', 'd', 'width'])
_PLACE = {'x': _XY, 'y': _XY, 'r': {'type': 'number', 'minimum': 0}, 'label': _LABEL}
_SEVERITY = obj({'critical': _COUNT, 'high': _COUNT, 'medium': _COUNT, 'low': _COUNT, 'total': _COUNT},
                ['critical', 'high', 'medium', 'low', 'total'])
_VIEW = lambda node: obj({'regions': arr(_REGION), 'nodes': arr(node), 'edges': arr(_EDGE), 'scale': N,
                          'bounds': arr(N)}, ['regions', 'nodes', 'edges', 'bounds'])
SYSTEM_SECTION = section({
    'world': obj({'width': _COUNT, 'height': _COUNT}, ['width', 'height']), 'graph': S,
    'counts': obj({k: REF('measure') for k in ('components', 'regions', 'edges', 'imports', 'target_components',
                                                'target_edges', 'target_regions')},
                  ['components', 'regions', 'edges', 'imports', 'target_components', 'target_edges']),
    'operations': obj({k: REF('measure') for k in ('retain', 'modify', 'rebuild', 'delete', 'merge', 'introduce')}),
    'src': {'type': 'object', 'additionalProperties': REF('source')},
    'capped': _COUNT,
    'current': _VIEW(obj({'id': S, 'short': S, 'kind': S, 'region': S, 'files': _COUNT, 'fan_in': NI, 'fan_out': NI,
                          'findings': _SEVERITY, 'op': _OP, 'target': NS, 'merged_with': _COUNT, 'reason': S,
                          'decision': {'type': ['object', 'null'], 'properties': {'id': S, 'chosen': S}}, **_PLACE},
                         ['id', 'short', 'region', 'files', 'findings', 'op', 'x', 'y', 'r', 'label'])),
    'target': _VIEW(obj({'id': S, 'short': S, 'layer': NS, 'region': S, 'files': _COUNT, 'responsibility': S,
                         'sources': arr(S), 'op': _OP, 'carried': _COUNT, **_PLACE},
                        ['id', 'short', 'region', 'files', 'sources', 'op', 'x', 'y', 'r', 'label'])),
}, ['world', 'counts', 'operations', 'src', 'current', 'target'])


STUDIO = {
 'manifest': ('The index of the Studio\'s data, written last so a reader never sees a half-written set: which EAOS built it, which scan, and every section with its fingerprint.',
  section({'language': enum('ar', 'en'),
           'locales': obj({'en': obj({'file': {'const': 'locale.js'}, 'sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}}, ['file', 'sha256'], extra=False)}, [], extra=False),
           'built': obj({'version': S, 'commit': S, 'digest': S, 'studio_digest': S, 'built': S}),
           'project': obj({'name': {'type': 'string', 'minLength': 1}}),
           'scanned': REF('scan'),
           'revision': {'type': 'integer', 'minimum': 1},
           'sections': arr(obj({'name': enum(*SECTIONS, *SECTIONS_V2), 'file': {'type': 'string', 'pattern': '^[a-z][a-z_]*\\.json$'},
                                'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                                'bytes': {'type': 'integer', 'minimum': 0}}), 1)},
          ['built', 'project', 'scanned', 'sections'])),
 'meta': ('What the project is: its languages, its size and the stages of the check that ran.',
  section({'languages': arr(obj({'name': S, 'files': {'type': 'integer', 'minimum': 0}, 'share': REF('ratio')})),
           'files': REF('measure'), 'lines': REF('measure'),
           'stages': arr(obj({'id': S, 'title': S, 'state': enum('done', 'partial', 'skipped', 'failed')}))},
          ['languages', 'files', 'lines', 'stages'])),
 'head': ('What every page shows on top: the scan, the EAOS that made it, whether it is still fresh, the verdict in one sentence and the next step.',
  section({'scanned': REF('scan'), 'eaos': obj({'version': S, 'commit': S, 'digest': S}),
           'freshness': enum('fresh', 'behind', 'rewritten', 'dirty', 'other_branch', 'branch_moved', 'eaos_updated', 'unknown'),
           'freshness_detail': obj({'state': S, 'reason': NS, 'behind': {'type': ['object', 'null']}, 'eaos_updated': B}, ['state']),
           'verdict': S, 'next': obj({'action': S, 'tool': NS}, ['action'])},
          ['scanned', 'eaos', 'freshness', 'verdict', 'next'])),
 'health': ('The project\'s health: one score by one formula, its domains, and the score after every scan.',
  section({'score': REF('ratio_measure'), 'formula': S,
           'domains': arr(obj({'id': S, 'name': S, 'score': REF('ratio_measure'), 'cards': {'type': 'integer', 'minimum': 0}})),
           'history': arr(obj({'at': S, 'commit': NS, 'score': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}}))},
          ['score', 'formula', 'domains', 'history'])),
 'cards': ('Every card of the plan on its own file and evidence, with its state read from the ledger and why it matters in both languages.',
  section({'cards': arr(obj({'id': S, 'key': S, 'title': S, 'kind': S, 'category': S,
                             'severity': enum('critical', 'high', 'medium', 'low', 'info'),
                             'fixable': B, 'needs_decision': B, 'scope': enum('place', 'group'),
                             'place': {'type': ['string', 'null']}, 'paths': arr(REF('path')),
                             'evidence': arr(S), 'state': enum(*CARD_STATES), 'milestone': NS,
                             'confidence': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1},
                             'why': obj({'ar': S, 'en': S}),
                             # what the assistant decided for the card (eaos/report/studio/export.py resolution_of): fix it, or
                             # ask the owner one real product choice
                             'resolution': obj({'kind': enum('fix', 'owner'), 'by': S, 'words': S, 'why': S, 'change': S,
                                                'capped': B, 'question': S, 'options': arr(S), 'recommendation': S},
                                               ['kind', 'by', 'words', 'why'])},
                            ['id', 'key', 'title', 'kind', 'severity', 'fixable', 'scope', 'paths', 'evidence', 'state']))},
          ['cards'])),
 'evidence': ('The facts the cards cite: which engine found what, and where, with the lines of code around the place (never for a secret).',
  section({'facts': arr(obj({'id': S, 'kind': S, 'engine': NS, 'path': {'type': ['string', 'null']}, 'line': NI,
                             'summary': S, 'sites': arr(obj({'path': REF('path'), 'line': NI}, ['path'])),
                             'code': {'oneOf': [{'type': 'null'}, obj({'start': {'type': 'integer', 'minimum': 1}, 'line': {'type': 'integer', 'minimum': 1},
                                                                       'lines': arr({'type': 'string', 'maxLength': 240}, 1),
                                                                       'hidden': arr({'type': 'integer', 'minimum': 1})},
                                                                      ['start', 'line', 'lines', 'hidden'])]}},
                            ['id', 'kind', 'summary']))},
          ['facts'])),
 'story': ('The current state, the ideal picture and the gap between them, as one story.',
  section({'current': obj({'summary': S, 'components': arr(obj({'name': S, 'layer': NS, 'files': {'type': 'integer', 'minimum': 0}},
                                                                 ['name', 'files']))}),
           'target': obj({'summary': S, 'components': arr(obj({'name': S, 'responsibility': S, 'layer': NS}, ['name', 'responsibility']))}),
           'gap': arr(obj({'component': S, 'relation': enum('retain', 'modify', 'rebuild', 'delete', 'missing'), 'to': NS,
                           'files': {'type': 'integer', 'minimum': 0}, 'cards': arr(S), 'closed': {'type': 'integer', 'minimum': 0}},
                          ['component', 'relation', 'files', 'cards'])),
           'indicators': arr(obj({'id': S, 'name': S, 'today': REF('measure'), 'expected': REF('measure'), 'target': REF('measure')},
                                 ['id', 'name', 'today', 'target']))},
          ['current', 'target', 'gap', 'indicators'])),
 'docs': ('Every document the check wrote, grouped by purpose, in reading order.',
  section({'docs': arr(obj({'id': S, 'title': S, 'path': REF('path'), 'group': S,
                            'bytes': {'type': 'integer', 'minimum': 0}, 'order': NI,
                            'headings': arr(obj({'level': {'type': 'integer', 'minimum': 1, 'maximum': 6}, 'text': S}, ['level', 'text']))},
                           ['id', 'title', 'path', 'group']))},
          ['docs'])),
 'plans': ('Every plan in one model (fix, build, product, owner and sub-plans): steps, tasks and gates, with states computed from git, gates and recorded decisions, never set by hand.',
  section({'plans': arr(obj({'id': S, 'title': S, 'kind': enum('fix', 'build', 'product', 'owner', 'sub'), 'parent': NS,
                             'state': enum(*PLAN_STATES), 'goal': S, 'indicators': arr(S), 'progress': REF('ratio_measure'),
                             'steps': arr(obj({'id': S, 'title': S, 'state': enum(*TASK_STATES), 'weight': {'type': 'number', 'minimum': 0},
                                               'gate': NS, 'depends_on': arr(S), 'sub_plan': NS,
                                               'tasks': arr(obj({'id': S, 'title': S, 'state': enum(*TASK_STATES),
                                                                 'acceptance': NS, 'depends_on': arr(S)}, ['id', 'title', 'state']))},
                                              ['id', 'title', 'state', 'tasks']))},
                            ['id', 'title', 'kind', 'state', 'steps', 'progress']))},
          ['plans'])),
 'decisions': ('What waits for the person: one question each, its recommendation, and what it blocks.',
  section({'decisions': arr(obj({'id': S, 'question': S, 'recommendation': S, 'recommended_option': NS, 'revision': S,
                                 'options': arr(obj({'id': S, 'label': S})), 'blocks': arr(S),
                                 'state': enum('waiting', 'answered', 'withdrawn'), 'answer': NS, 'plan': NS,
                                 'asked': S, 'tool': NS}, ['id', 'question', 'recommendation', 'state']))},
          ['decisions'])),
 'media': ('The images of the project: screens before and after each batch, diagrams and charts.',
  section({'images': arr(obj({'id': S, 'path': REF('path'), 'title': S, 'kind': enum('screen', 'diagram', 'chart'),
                              'batch': NS, 'phase': {'type': ['string', 'null'], 'enum': ['before', 'after', 'baseline', None]},
                              'route': NS, 'viewport': NS, 'pair': NS}, ['id', 'path', 'title', 'kind']))},
          ['images'])),
 'system': ('The project as two territory maps, today and the target: components with their files, findings and operation, the weighted imports between them, and the layout computed by EAOS so the Studio only draws. The precursor of NS39.T1\'s unified graph.',
  SYSTEM_SECTION)
}
