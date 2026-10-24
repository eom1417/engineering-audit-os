"""The paths a check can follow, declared once as data: their names, what each looks at, and the stages, engine kinds
and card patterns it keeps. eaos/pipeline/paths.py resolves a choice of them into what runs."""

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
             'stages': ('roles', 'setup', 'session', 'lock', 'record', 'journeys', 'crawl', 'screens', 'visual'), 'patterns': ('design_review',)},
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
