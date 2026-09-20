"""Labels for rendered artifacts. Content is language-neutral; only wording changes."""

LABELS = {
    'ar': {
        'system_map': 'خريطة النظام', 'coupling_atlas': 'أطلس الترابط', 'evolution': 'عدسة التطور',
        'decision_brief': 'موجز القرار', 'provenance': 'المصدر وإعادة الإنتاج', 'coverage': 'التغطية',
        'not_examined': 'ما لم يُفحص', 'entry_points': 'نقاط الدخول', 'surface': 'السطح', 'method': 'الطريقة',
        'route': 'المسار', 'handler': 'المعالج', 'location': 'الموضع', 'framework': 'الإطار',
        'languages': 'اللغات', 'language': 'اللغة', 'files': 'ملفات', 'lines': 'أسطر', 'components': 'التجمعات البنيوية',
        'directory': 'المجلد', 'dependencies': 'الاعتماديات', 'most_depended': 'الأكثر اعتمادًا عليه',
        'fan_in': 'وارد', 'fan_out': 'صادر', 'path': 'الملف', 'cycles': 'الدورات', 'members': 'الأعضاء',
        'clones': 'الكتل المكررة', 'occurrences': 'المواضع', 'attention': 'ترتيب الانتباه', 'score': 'الدرجة',
        'factors': 'العوامل', 'hotspots': 'البؤر الساخنة', 'commits': 'تغييرات', 'fixes': 'إصلاحات',
        'authors': 'المساهمون', 'cochange': 'الاقتران بالتغيير المشترك', 'support': 'التكرار', 'confidence': 'الثقة',
        'hidden_coupling': 'اقتران خفي (بلا اعتماد ظاهر في الكود)', 'ownership': 'الملكية وتركّز المعرفة',
        'top_author': 'المساهم الأول', 'share': 'الحصة', 'stale': 'مناطق لم تتغير منذ مدة',
        'days': 'أيام', 'unreachable': 'ملفات لا يصل إليها أي مسار من نقاط الدخول المكتشفة',
        'signal_note': 'إشارات انتباه فقط: لا شيء هنا حكم على جودة التصميم.',
        'truncated': 'عُرض %(shown)d من %(total)d؛ البقية في سجلات الحقائق.',
        'no_rows': 'لا توجد بيانات لهذا القسم في هذه اللقطة.',
        'generated': 'مولَّد آليًا من حقائق حتمية، بلا استدعاء أي نموذج.',
        'attention_note': 'الترتيب اصطلاح معلن بأوزان ظاهرة، وليس تنبؤًا مقاسًا بالمخاطر.',
        'flows': 'التدفقات المتتبعة', 'step': 'الخطوة', 'call': 'الاستدعاء', 'resolution': 'الحسم',
        'touched': 'الملفات التي يمسها', 'env': 'متغيرات البيئة على المسار', 'entry': 'نقطة الدخول',
        'flow_note': 'تتبع ساكن: كل خطوة لها موضع فعلي، والخطوة غير المحسومة تعني توقف التتبع لا توقف التنفيذ.',
        'domain_data': 'المجال والبيانات', 'contracts_doc': 'العقود والحدود', 'constant': 'الثابت',
        'defined_in': 'معرّف في', 'duplicated_rule': 'قيمة قاعدة مكررة في أكثر من موضع',
        'external_deps': 'الاعتماديات الخارجية', 'config_contract': 'عقد الإعداد', 'name': 'الاسم',
        'read_in': 'يُقرأ في', 'declared': 'معلن', 'data_models': 'نماذج البيانات والمخططات',
        'verification': 'خريطة التحقق', 'executed': 'نُفِّذ فعلًا', 'coverage_pct': 'التغطية %',
        'uncovered': 'مسارات حرجة بلا تغطية منفذة', 'tests': 'ملفات الاختبار',
        'verify_note': 'دليل تنفيذ فعلي: ما لم يُنفَّذ يبقى غير مثبت، وعدم التغطية ليس دليل موت الكود.',
    },
    'en': {
        'system_map': 'System map', 'coupling_atlas': 'Coupling atlas', 'evolution': 'Evolution lens',
        'decision_brief': 'Decision brief', 'provenance': 'Provenance and reproduction', 'coverage': 'Coverage',
        'not_examined': 'Not examined', 'entry_points': 'Entry points', 'surface': 'Surface', 'method': 'Method',
        'route': 'Route', 'handler': 'Handler', 'location': 'Location', 'framework': 'Framework',
        'languages': 'Languages', 'language': 'Language', 'files': 'Files', 'lines': 'Lines', 'components': 'Structural groupings',
        'directory': 'Directory', 'dependencies': 'Dependencies', 'most_depended': 'Most depended upon',
        'fan_in': 'Fan-in', 'fan_out': 'Fan-out', 'path': 'File', 'cycles': 'Cycles', 'members': 'Members',
        'clones': 'Duplicated blocks', 'occurrences': 'Occurrences', 'attention': 'Attention order', 'score': 'Score',
        'factors': 'Factors', 'hotspots': 'Hotspots', 'commits': 'Commits', 'fixes': 'Fix commits',
        'authors': 'Authors', 'cochange': 'Co-change coupling', 'support': 'Support', 'confidence': 'Confidence',
        'hidden_coupling': 'Hidden coupling (no visible code dependency)', 'ownership': 'Ownership concentration',
        'top_author': 'Top author', 'share': 'Share', 'stale': 'Areas unchanged for a long time',
        'days': 'Days', 'unreachable': 'Files no path from a detected entry point reaches',
        'signal_note': 'Attention signals only: nothing here judges design quality.',
        'truncated': 'Showing %(shown)d of %(total)d; the rest stays in the fact records.',
        'no_rows': 'No data for this section in this snapshot.',
        'generated': 'Generated from deterministic facts with no model call.',
        'attention_note': 'The order is a declared convention with visible weights, not a measured risk prediction.',
        'flows': 'Traced flows', 'step': 'Step', 'call': 'Call', 'resolution': 'Resolution',
        'touched': 'Files touched', 'env': 'Environment reads on the path', 'entry': 'Entry point',
        'flow_note': 'Static trace: every step has a real location, and an unresolved step means the trace stopped, not execution.',
        'domain_data': 'Domain and data', 'contracts_doc': 'Contracts and boundaries', 'constant': 'Constant',
        'defined_in': 'Defined in', 'duplicated_rule': 'Rule value duplicated in more than one place',
        'external_deps': 'External dependencies', 'config_contract': 'Configuration contract', 'name': 'Name',
        'read_in': 'Read in', 'declared': 'Declared', 'data_models': 'Data models and schemas',
        'verification': 'Verification map', 'executed': 'Actually executed', 'coverage_pct': 'Coverage %',
        'uncovered': 'Critical paths with no executed coverage', 'tests': 'Test files',
        'verify_note': 'Execution evidence: what did not run stays unproven, and no coverage is not proof of dead code.',
    },
}


TEMPLATES = {
    'ar': {
        'cycle': 'دورة استيراد بين: {members}',
        'cochange': '{left} و{right} يتغيّران معًا في {support} تغييرات بلا اعتماد ظاهر في الكود',
        'duplicated_rule': '{name} معرّف في {count} مواضع ({places})' ,
        'duplicated_rule_differs': '{name} معرّف في {count} مواضع **بقيم مختلفة** ({places})',
        'trace_gap': 'تدفق {flow} ({surface} {route}) يتوقف عند {count} استدعاءات لا يمكن حلّها',
        'hotspot': '{symbol} في {path}: {branches} تفرّعًا عبر {lines} سطرًا، في ملف ترتيبه {rank} في الانتباه',
        'mutable_global': '{name} في {path} حالة على مستوى الوحدة تتغيّر أثناء التشغيل ({how}، سطر {line})',
        'external_write': '{path} يكتب في {module}.{attribute}، وهي حالة لا يملكها',
        'untested': '{count} ملفًا يصل إليها مسار من نقطة دخول ولم ينفّذها أمر الاختبار',
        'policy': '{path} يستورد {to}، وهو ما تمنعه السياسة المعلنة ({from_layer} ← {to_layer})',
    },
    'en': {
        'cycle': 'Import cycle between: {members}',
        'cochange': '{left} and {right} change together in {support} commits with no visible code dependency',
        'duplicated_rule': '{name} is defined in {count} places ({places})',
        'duplicated_rule_differs': '{name} is defined in {count} places **with different values** ({places})',
        'trace_gap': 'Flow {flow} ({surface} {route}) stops at {count} unresolvable calls',
        'hotspot': '{symbol} in {path} carries {branches} branches over {lines} lines, in a file ranked {rank} for attention',
        'mutable_global': '{name} in {path} is module-level state changed at runtime ({how}, line {line})',
        'external_write': '{path} writes into {module}.{attribute}, state it does not own',
        'untested': '{count} files reachable from an entry point were never executed by the test command',
        'policy': '{path} imports {to}, which the declared policy forbids ({from_layer} → {to_layer})',
    },
}
IMPACTS = {
    'ar': {
        'cycle': 'تغيير أي عضو قد يفرض تغيير البقية معه؛ ولا يمكن اختبار المجموعة أو استبدالها منفردة.',
        'cochange': 'تغيير أحدهما يستدعي غالبًا تغييرًا مقابلًا في الآخر، بلا أي إشارة في الكود.',
        'duplicated_rule': 'تعديل القاعدة في موضع دون الآخر يجعل مسارين يختلفان.',
        'duplicated_rule_differs': 'تعديل القاعدة في موضع دون الآخر يجعل مسارين يختلفان — وهما مختلفان أصلًا.',
        'trace_gap': 'سلوك نقطة الدخول هذه غير مرئي بالكامل من المصدر وحده.',
        'hotspot': 'كل تغيير في هذا المسار يمرّ عبر دالة واحدة كثيفة؛ وهي أكثر مخاطرة صيانة مركزة في الوحدة.',
        'mutable_global': 'قد يرى مستدعيان قيمتين مختلفتين حسب الترتيب، وقد تنجح الاختبارات منفردة وتفشل مجتمعة.',
        'external_write': 'الوحدة المالكة لا تستطيع ضمان ثابتها، لأن وحدة أخرى تكتب فيها مباشرة.',
        'untested': 'تغيير في هذه الملفات قد يُشحن دون أن ينفّذه أي اختبار.',
    },
    'en': {},
}


def impact_of(claim, language):
    render = claim.get('render') or {}
    key = render.get('key')
    if key == 'duplicated_rule' and (render.get('params') or {}).get('differs') == 'yes': key = 'duplicated_rule_differs'
    translated = IMPACTS.get(language, {}).get(key)
    return translated or (claim.get('impact') or {}).get('scenario') or '—'


# Which artifact carries the detail behind each kind of claim, so a reader is never left searching.
DETAIL_ARTIFACT = {
    'cycle': 'COUPLING-ATLAS.md', 'cochange': 'EVOLUTION.md', 'duplicated_rule': 'DOMAIN-AND-DATA.md',
    'trace_gap': 'FLOWS.md', 'hotspot': 'COUPLING-ATLAS.md', 'mutable_global': 'DOMAIN-AND-DATA.md',
    'external_write': 'DOMAIN-AND-DATA.md', 'untested': 'VERIFICATION-MAP.md', 'policy': 'POLICY.md',
}


def statement_of(claim, language):
    """Render a claim in the reader language when it declares a template; otherwise keep it verbatim."""
    render = claim.get('render') or {}
    key = render.get('key')
    if not key: return claim['statement']
    if key == 'duplicated_rule' and (render.get('params') or {}).get('differs') == 'yes': key = 'duplicated_rule_differs'
    template = TEMPLATES.get(language, TEMPLATES['ar']).get(key)
    if not template: return claim['statement']
    try: return template.format(**render.get('params', {}))
    except (KeyError, IndexError): return claim['statement']


def detail_artifact(claim):
    return DETAIL_ARTIFACT.get((claim.get('render') or {}).get('key'))


def labels(language): return LABELS.get(language, LABELS['ar'])
