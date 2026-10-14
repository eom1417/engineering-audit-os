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
    ('security_weakness', {'ar': ('ثغرات أمان في الكود', 'مواضع في كود مشروعك قد يستغلها أحد: أمر أو استعلام يُبنى من مدخل، أو سر مكتوب في الكود.'),
                           'en': ('Security weaknesses in the code', 'Places in your code someone may exploit: a command or query built from input, or a secret written in the code.')}),
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
    ('mutable_state_private', {'ar': ('قيم داخلية تتغير أثناء التشغيل', 'قيم يملكها ملف واحد ويغيّرها من دواله فقط: آمنة ما دامت نسخة واحدة من البرنامج تعمل، وتحتاج قرارًا إن شُغّلت نسختان.'),
                               'en': ('Private values changed while running', 'Values one file owns and changes only through its own functions: safe while one copy of the program runs, a decision once two copies do.')}),
    ('hidden_coupling', {'ar': ('ارتباطات خفية', 'ملفات تتغير معًا دائمًا دون أن يظهر في الكود ما يربطها.'),
                         'en': ('Hidden links', 'Files that always change together, with nothing in the code that shows why.')}),
    ('hotspot', {'ar': ('أجزاء معقدة جدًا', 'دوال كبيرة يمر بها كل تعديل، فيصعب فهمها ويسهل كسرها.'),
                 'en': ('Very complex parts', 'Large functions every change goes through: hard to understand, easy to break.')}),
    ('split_module', {'ar': ('ملفات ضخمة', 'ملفات تحمل أكثر من مسؤولية: يصعب فهمها، وتكبر مع كل ميزة.'),
                      'en': ('Oversized files', 'Files that hold several responsibilities: hard to read, and they grow with every feature.')}),
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
    ('design_review', {'ar': ('ملاحظات على شكل الشاشات', 'أشياء رآها مساعدك في صور شاشات برنامجك: زحمة، أو نص غير واضح، أو عنصر خارج مكانه. تحتاج نظرة قبل أي تعديل.'),
                       'en': ('Notes on how the screens look', 'Things your assistant saw in pictures of your screens: crowding, hard-to-read text, something out of place. Look before changing anything.')}),
    ('investigation', {'ar': ('أسئلة تحتاج تحققًا', 'احتمالات لاحظها مساعدك ولم يثبتها القياس بعد: تُفحص ويُسجَّل قرار، وقد لا تحتاج تعديلًا.'),
                       'en': ('Questions to check', 'Possibilities your assistant noticed that no measurement has proven yet: checked, then decided, and maybe no change.')}),
    ('generic', {'ar': ('ملاحظات أخرى', 'ملاحظات تحتاج نظرة شخص قبل أي تغيير.'),
                 'en': ('Other notes', 'Notes a person should look at before any change.')}),
)
ORDER = [name for name, _ in PROBLEMS]
TEXT = dict(PROBLEMS)


def kind(task):
    """The plain kind of a card: its pattern, except module-level state its own module keeps private (the fact's
    `encapsulated`, carried in the claim's render), which is not "changed by several parts"."""
    pattern = task.get('pattern') or 'generic'
    params = (task.get('render') or {}).get('params') or {}
    return 'mutable_state_private' if pattern == 'mutable_state' and params.get('encapsulated') else pattern


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
    'setup': ('أشغّل برنامجك في نسخة منفصلة', 'Starting your app in a separate copy'),
    'record': ('أسجّل سلوك برنامجك الحالي', "Recording your app's behaviour today"),
    'journeys': ('أسجّل رحلات المستخدم في برنامجك لتُعاد في التقرير', "Recording your app's user journeys, to replay in the report"),
    'crawl': ('أكتشف كل صفحات برنامجك وأقيس كل وحدة', "Finding every page of your app and measuring each"),
    'screens': ('أصوّر صفحات برنامجك وأفحص وضوحها وسرعتها', "Picturing your app's pages and checking their accessibility and speed"),
    'baseline': ('أقيس سرعة برنامجك تحت ضغط مستخدمين كثيرين', "Measuring your app's speed under many users"),
    'verify': ('أشغّل اختبارات المشروع إن طُلب', "Running the project's tests, if asked"),
    'measure': ('أقيس حجم وتعقيد الكود', 'Measuring size and complexity'),
    'architecture': ('أرسم خريطة البنية: المدينة ومجموعات الكود', 'Drawing the architecture map: the city and the code clusters'),
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
    'readiness': ('أقيس جاهزيته تحت الضغط', 'Measuring its readiness under pressure'),
    'quality': ('أراجع جودة التقارير', 'Checking the reports'),
    'pdf': ('أجهّز ملف PDF', 'Making the PDF'),
    'execution_guide': ('أكتب دليل التنفيذ', 'Writing the execution guide'),
    'executive': ('أكتب الملخص', 'Writing the summary'),
    'compose': ('أجمع التقرير النهائي', 'Putting the final report together'),
    'proposals': ('أجهّز اقتراحات الأدوات لمساعدك', "Preparing the tools' proposals for your assistant"),
    'triage': ('مساعدك الذكي يراجع كل بطاقة بدليلها', 'Your AI assistant reviews every card against its evidence'),
    'visual': ('مساعدك الذكي يشوف صور شاشات برنامجك ويحكم على تصميمها', "Your AI assistant looks at your app's screens and judges their design"),
    'cards': ('أبقي البطاقات المؤكدة في الخطة', 'Keeping the confirmed cards in the plan'),
    'ideal': ('مساعدك الذكي يحكم على البنية المقترحة', 'Your AI assistant judges the proposed structure'),
    'pipeline_gaps': ('مساعدك الذكي يخطّط سد فجوات المسارات', 'Your AI assistant plans how to close the pipeline gaps'),
    'reconcile': ('أثبّت البنية المستهدفة النهائية ومن قرّر كل جزء', 'Settling the final target and who decided each part'),
    'order': ('مساعدك الذكي يرتّب خطة العمل', 'Your AI assistant orders the plan'),
    'steps': ('أثبّت ترتيب الخطة', "Settling the plan's order"),
    'bundles': ('أجهّز ملفات التسليم', 'Preparing the handover files'),
    'emit': ('أولّد ملفات الإعداد الجاهزة', 'Generating ready-made config files'),
    'site': ('أجهّز صفحة التصفح', 'Building the browsable page'),
    'validate': ('أتحقق من سلامة كل الملفات', 'Checking every file is valid'),
}


def stage(name, language):
    ar, en = STAGES.get(name, (name, name))
    return ar if language == 'ar' else en
