"""Plain words for a person who did not write the code: what each kind of problem is, and what each stage does.

The report's own files keep their precise, technical wording; this module is only for the first page a user
reads (START-HERE.md) and for the guided commands. Every entry has Arabic and English.
"""

# Problem kinds, most urgent first: something broken or unsafe before something untidy.
PROBLEMS = (
    ('broken_code', {'ar': ('كود مكسور', 'أجزاء ستفشل أول مرة تُستخدم: استيراد لملف غير موجود، أو أمر في التوثيق لم يعد موجودًا.'),
                     'en': ('Broken code', 'Parts that will fail the first time they run: an import of a missing file, or a documented command that no longer exists.')}),
    ('access_gap', {'ar': ('بيانات مكشوفة', 'بيانات المستخدمين يمكن قراءتها أو تعديلها من غير أصحابها.'),
                    'en': ('Exposed data', "Users' data can be read or changed by people who do not own it.")}),
    ('upgrade_dependency', {'ar': ('مكتبات فيها ثغرات معروفة', 'مكتبات يستخدمها مشروعك فيها ثغرات أمنية منشورة، ولها إصدار مُصلَح.'),
                            'en': ('Libraries with known security holes', 'Libraries your project uses have published security holes, and a fixed version exists.')}),
    ('load_blocker', {'ar': ('بطء متوقع مع كثرة المستخدمين', 'أماكن تزيد كلفتها كلما زاد المستخدمون أو البيانات.'),
                      'en': ('Slowdowns as users grow', 'Places whose cost grows with more users or more data.')}),
    ('redundant_work', {'ar': ('عمل مكرر بلا داعٍ', 'البرنامج يطلب الشيء نفسه أكثر من مرة، فيبطئ ويكلّف.'),
                        'en': ('Needless repeated work', 'The app asks for the same thing more than once, which is slower and costs more.')}),
    ('import_cycle', {'ar': ('ملفات متشابكة', 'ملفات يعتمد كل منها على الآخر، فلا يمكن تعديل واحد دون الآخر.'),
                      'en': ('Tangled files', 'Files that depend on each other in a loop, so none can change alone.')}),
    ('duplicated_rule', {'ar': ('قاعدة مكتوبة في أكثر من مكان', 'القاعدة نفسها مكتوبة مرتين، وأول تعديل يجعل النسختين تختلفان.'),
                         'en': ('One rule written in several places', 'The same rule is written twice, and the first change makes the copies disagree.')}),
    ('mutable_state', {'ar': ('بيانات مشتركة يعدلها أكثر من طرف', 'قيم يغيّرها أكثر من جزء، فتختلف النتيجة حسب الترتيب.'),
                       'en': ('Shared values changed from many places', 'Values changed by several parts, so results depend on the order things run.')}),
    ('hidden_coupling', {'ar': ('ارتباطات خفية', 'ملفات تتغير معًا دائمًا دون أن يظهر في الكود ما يربطها.'),
                         'en': ('Hidden links', 'Files that always change together, with nothing in the code that shows why.')}),
    ('hotspot', {'ar': ('أجزاء معقدة جدًا', 'دوال كبيرة يمر بها كل تعديل، فيصعب فهمها ويسهل كسرها.'),
                 'en': ('Very complex parts', 'Large functions every change goes through: hard to understand, easy to break.')}),
    ('canonicalize', {'ar': ('كود منسوخ', 'المنطق نفسه منسوخ في أكثر من ملف.'),
                      'en': ('Copied code', 'The same logic is copied into several files.')}),
    ('remove_dead', {'ar': ('كود ميت', 'كود لا يستخدمه أحد: يثقل القراءة والصيانة.'),
                     'en': ('Dead code', 'Code nothing uses: it makes reading and changing the project harder.')}),
    ('dead_code', {'ar': ('كود ميت', 'كود لا يستخدمه أحد: يثقل القراءة والصيانة.'),
                   'en': ('Dead code', 'Code nothing uses: it makes reading and changing the project harder.')}),
    ('trace_gap', {'ar': ('مسارات غير مفهومة', 'نقاط دخول لا يتضح من الكود ماذا تفعل.'),
                   'en': ('Unclear paths', 'Entry points whose behaviour is not clear from the code.')}),
    ('untested_path', {'ar': ('أجزاء بلا اختبار', 'أجزاء يمكن أن تتغير دون أن يلاحظ أي اختبار.'),
                       'en': ('Untested parts', 'Parts that can change without any test noticing.')}),
    ('external_write', {'ar': ('تعديل من خارج المالك', 'جزء يعدّل بيانات يملكها جزء آخر.'),
                        'en': ('Changes from outside the owner', 'One part changes data another part owns.')}),
    ('policy_violation', {'ar': ('مخالفة للبنية المعلنة', 'استيراد يخالف ترتيب الطبقات الذي أعلنه المشروع.'),
                          'en': ('Breaks the declared structure', 'An import that breaks the layering the project declared.')}),
    ('generic', {'ar': ('ملاحظات أخرى', 'ملاحظات تحتاج نظرة شخص قبل أي تغيير.'),
                 'en': ('Other notes', 'Notes a person should look at before any change.')}),
)
ORDER = [name for name, _ in PROBLEMS]
TEXT = dict(PROBLEMS)


def problem(pattern, language):
    """(name, one sentence) of a problem kind in plain words."""
    return TEXT.get(pattern, TEXT['generic'])[language]


# What each audit stage is doing, as the user sees it while waiting.
STAGES = {
    'facts': ('أقرأ كل ملفات المشروع', 'Reading every file of the project'),
    'features': ('أتعرف على وظائف البرنامج', "Finding the app's features"),
    'lock': ('أجهّز اختبارات الشاشات', 'Preparing screen checks'),
    'intake': ('أتعرف على نوع المشروع', 'Working out what kind of project this is'),
    'engines': ('أشغّل أدوات الفحص', 'Running the checking tools'),
    'verify': ('أشغّل اختبارات المشروع إن طُلب', "Running the project's tests, if asked"),
    'measure': ('أقيس حجم وتعقيد الكود', 'Measuring size and complexity'),
    'policy': ('أراجع ترتيب الطبقات', 'Checking the layering'),
    'load': ('أقدّر السلوك مع كثرة المستخدمين', 'Estimating behaviour under many users'),
    'claims': ('أجمع المشاكل بأدلتها', 'Collecting problems with their evidence'),
    'probe': ('أتحقق من كل مشكلة', 'Double-checking every problem'),
    'semantic': ('مساعدك الذكي يقرأ الحقائق ويفسّرها', 'Your AI assistant reads the facts and interprets them'),
    'sustainability': ('أقيس صحة البنية', 'Measuring structural health'),
    'transform': ('أخطط للتحسينات', 'Planning the improvements'),
    'plan': ('أكتب مهام الإصلاح', 'Writing the fix tasks'),
    'target': ('أرسم البنية المثالية', 'Drawing the ideal structure'),
    'reports': ('أكتب التقارير', 'Writing the reports'),
    'quality': ('أراجع جودة التقارير', 'Checking the reports'),
    'pdf': ('أجهّز ملف PDF', 'Making the PDF'),
    'execution_guide': ('أكتب دليل التنفيذ', 'Writing the execution guide'),
    'executive': ('أكتب الملخص', 'Writing the summary'),
    'compose': ('أجمع التقرير النهائي', 'Putting the final report together'),
    'ideal': ('مساعدك الذكي يخطّط الصورة المثالية', 'Your AI assistant plans the ideal'),
    'bundles': ('أجهّز ملفات التسليم', 'Preparing the handover files'),
    'emit': ('أولّد ملفات الإعداد الجاهزة', 'Generating ready-made config files'),
    'site': ('أجهّز صفحة التصفح', 'Building the browsable page'),
    'validate': ('أتحقق من سلامة كل الملفات', 'Checking every file is valid'),
}


def stage(name, language):
    ar, en = STAGES.get(name, (name, name))
    return ar if language == 'ar' else en
