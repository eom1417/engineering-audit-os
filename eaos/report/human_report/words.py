"""The fixed words of REPORT.html, Arabic and English: the page's sections, areas, severities, grades, relations, states."""


SECTIONS = ('summary', 'gaps', 'layers', 'structure', 'system', 'target', 'plan')
HUNDRED = '<span data-meaning="the full score, and the file count a density is measured against">100</span>'

W = {  # every fixed word of the page: (Arabic, English)
    'title': ('تقرير المشروع', 'Project report'),
    'summary': ('ملخص المشروع', 'Project summary'), 'gaps': ('الفجوات والمخاطر', 'Gaps and risks'), 'layers': ('النظام طبقات', 'The system in layers'),
    'structure': ('خريطة البنية', 'Structure map'), 'system': ('خريطة النظام', 'System map'), 'target': ('البنية المستهدفة', 'Target'), 'plan': ('الخطة والتقدم', 'Plan and progress'),
    'security': ('الأمان', 'Security'), 'quality': ('جودة الكود', 'Code quality'),
    'performance': ('الأداء تحت الضغط', 'Performance under load'), 'ux': ('شكل الشاشات', 'How the screens look'),
    'maintainability': ('سهولة التطوير والاختبار', 'Ease of change and testing'),
    'critical': ('حرجة', 'Critical'), 'high': ('عالية', 'High'), 'medium': ('متوسطة', 'Medium'), 'low': ('منخفضة', 'Low'),
    'excellent': ('ممتاز', 'Excellent'), 'good': ('جيد', 'Good'), 'fair': ('مقبول', 'Fair'), 'weak': ('ضعيف', 'Weak'),
    'CONFIRMED': ('مؤكدة', 'Confirmed'), 'LIKELY': ('مرجّحة', 'Likely'), 'HYPOTHESIS': ('فرضية', 'Hypothesis'),
    'S': ('صغير', 'Small'), 'M': ('متوسط', 'Medium'), 'L': ('كبير', 'Large'),
    'na': ('غير متاح في هذا التقرير.', 'Not available in this report.'),
}
W['structure_area'] = ('البنية', 'Structure')
AREA_WHAT = {
    'security': ('هل يستطيع أحد الوصول إلى ما لا يحق له، أو استغلال ثغرة معروفة؟',
                 'Can anyone reach what they should not, or use a known security hole?'),
    'structure': ('هل أجزاء البرنامج منفصلة بوضوح، أم متشابكة يصعب تعديل أحدها وحده؟',
                  'Are the parts of the program clearly separate, or tangled so that none can change alone?'),
    'quality': ('كود ميت لا يستخدمه أحد، وكود منسوخ، ومراجع مكسورة.', 'Dead code nothing uses, copied code, and broken references.'),
    'performance': ('هل يبطئ البرنامج كلما زاد المستخدمون أو البيانات؟', 'Does the program slow down as users or data grow?'),
    'ux': ('هل شاشات البرنامج واضحة ومرتبة في صورها؟', "Do the program's screens look clear and tidy in their pictures?"),
    'maintainability': ('هل يسهل فهم الكود وتغييره واختباره دون كسر شيء؟', 'Is the code easy to understand, change and test without breaking something?'),
}
SEVERITY_MEANS = {
    'critical': ('قد تُسرّب بيانات أو توقف البرنامج الآن؛ تُصلح قبل أي شيء آخر.',
                 'Can leak data or stop the program now; fix it before anything else.'),
    'high': ('ستسبب عطلًا أو ثغرة في الاستخدام العادي؛ تُصلح في الدفعة الأولى.',
             'Will cause a failure or a security hole in normal use; fix it in the first batch.'),
    'medium': ('تُبطئ التطوير أو تسبب أخطاء مع الوقت؛ تُصلح ضمن الخطة.',
               'Slows development or causes bugs over time; fix it as part of the plan.'),
    'low': ('تنظيف يسهّل القراءة والصيانة؛ لا يؤثر على المستخدم مباشرة.',
            'Clean-up that makes reading and changing easier; users do not feel it directly.'),
}
GRADE_MEANS = {
    'excellent': ('المشروع في حالة ممتازة: المشاكل قليلة وخفيفة.', 'The project is in excellent shape: few, light problems.'),
    'good': ('المشروع في حالة جيدة: توجد مشاكل، لكن معظمها غير عاجل.', 'The project is in good shape: there are problems, but most are not urgent.'),
    'fair': ('المشروع يعمل، لكن فيه مشاكل تستحق خطة إصلاح قبل أن تكبر.', 'The project works, but has problems that deserve a fix plan before they grow.'),
    'weak': ('المشاكل كثيرة وتبطئ التطوير وتزيد احتمال الأعطال؛ الإصلاح مطلوب قريبًا.',
             'Problems are many; they slow development and make failures likelier. Fixing is needed soon.'),
    'critical': ('المشروع معرّض لأعطال أو تسريب بيانات؛ ابدأ الإصلاح فورًا.', 'The project is exposed to failures or data leaks; start fixing now.'),
}
RELATION = {'retain': ('يبقى كما هو', 'stays as it is'), 'modify': ('يُعدَّل', 'is changed'),
            'rebuild': ('يُعاد بناؤه', 'is rebuilt'), 'delete': ('يُحذف', 'is removed'),
            'retire': ('يُحذف', 'is removed'), 'introduce': ('جزء جديد', 'is new')}
GAP_STATUS = {'covered': ('الخطة تغطيه', 'the plan covers it'), 'partial': ('الخطة تغطيه جزئيًا', 'the plan covers part of it'),
              'missing': ('لا خطة له بعد', 'no plan for it yet')}
MILESTONE = {'stabilize': ('التثبيت', 'Stabilize'), 'safety_net': ('شبكة الأمان', 'Safety net'),
             'boundaries': ('ترتيب الحدود بين الأجزاء', 'Boundaries'), 'hardening': ('التحصين', 'Hardening')}
OUTCOME = {'repair': ('إصلاحه', 'fix it'), 'retain': ('إبقاؤه كما هو', 'keep it as it is'),
           'blocked_missing_requirement': ('ينقصنا تعريف المطلوب', 'we lack a stated requirement')}
