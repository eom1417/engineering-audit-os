"""What to do about each class of finding, including the option of doing nothing.

A pattern never invents a fix for a claim class it does not know; it says plainly that the change
must be designed by hand, and still requires a runnable acceptance criterion.
"""

DO_NOTHING = {'option': 'لا نفعل شيئًا', 'option_en': 'Do nothing',
              'cost': 'صفر الآن', 'cost_en': 'zero now'}

# Each engine-cluster kind maps to the remediation pattern that already exists for its
# single-engine counterpart. Unknown kinds stay generic; the reason is recorded on the returned
# pattern by pattern_for so the fall-through is not silent.
_ENGINE_CLUSTER_KINDS = {
    'complexity': 'hotspot',
    'coupling': 'hidden_coupling',
    'literal_duplication': 'canonicalize',
    'dead_code': 'dead_code',
}


# The pattern of a claim proven by one of these probe queries.
QUERY_PATTERNS = {
    'cycle_present': 'import_cycle',
    'flow_has_unresolved_steps': 'trace_gap',
    'no_code_dependency': 'hidden_coupling',
    'metric_threshold': 'hotspot',
    'module_size': 'split_module',
    'mutable_global_present': 'mutable_state',
    'external_write_present': 'external_write',
    'policy_violation_present': 'policy_violation',
    'redundancy_present': 'redundant_work',
    'load_blocker_present': 'load_blocker',
    'broken_code_present': 'broken_code',
    'vulnerable_dependency_present': 'upgrade_dependency',
    'weakness_present': 'security_weakness',
    'boundary_finding_present': 'layer_boundary',
    'repository_finding_present': 'repository_craft',
    'real_data_present': 'real_data',
    'old_engine_present': 'old_engine',
    'data_keeping_present': 'data_keeping',
    'one_source_present': 'one_source',
}


# Card keys that are their own pattern, with or without a probe (M13, M14, M15).
OWN_PATTERN = ('old_engine', 'data_keeping', 'one_source')


def _by_query(claim, specification):
    """The pattern the probe's query names, or None when the query names none."""
    query = specification.get('query')
    if (claim.get('render') or {}).get('key') in OWN_PATTERN: return (claim.get('render') or {})['key']     # cards without a probe too
    if query == 'dead_code_present':
        return 'remove_dead' if (claim.get('render') or {}).get('key') == 'dead_code' else 'dead_code'
    if query == 'engine_cluster_present':
        return _ENGINE_CLUSTER_KINDS.get(specification.get('kind'), 'generic')
    return QUERY_PATTERNS.get(query)


def classify(claim):
    """Map a claim to a remediation pattern using how it was proven, not how it was worded."""
    specification = (claim.get('probe_spec') or {}).get('specification') or {}
    probe_type = (claim.get('probe_spec') or {}).get('probe_type')
    found = _by_query(claim, specification)
    if found: return found
    if probe_type == 'absence_search': return 'duplicated_rule'
    if claim.get('claim_type') == 'risk' and 'never executed' in claim['statement']: return 'untested_path'
    if claim.get('claim_type') == 'capability_gap': return 'trace_gap'
    return 'generic'


PATTERNS = {
    'load_blocker': {
        'change': 'اجعل كلفة نقطة الدخول مستقلة عن حجم البيانات: احضر ما يلزم في استعلام واحد محدود، '
                  'وانقل الحالة المشتركة إلى مخزن مشترك، واضبط مهلة على كل نداء خارج.',
        'options': [
            {'option': 'جلب مجمَّع بدل استعلام لكل عنصر', 'cost': 'منخفضة',
             'verdict': 'مختار افتراضيًا حين يكون العائق استعلامًا داخل حلقة'},
            {'option': 'حد أعلى وترقيم صفحات على الرد', 'cost': 'منخفضة',
             'verdict': 'مختار حين ينمو الرد مع حجم الجدول'},
            {'option': 'نقل الحالة إلى مخزن مشترك', 'cost': 'متوسطة',
             'verdict': 'لازم قبل تشغيل أكثر من نسخة'},
            {'option': 'مهلة وإعادة محاولة وقاطع دائرة على النداء الخارج', 'cost': 'منخفضة',
             'verdict': 'مختار حين يكون العائق تبعية غير محمية'},
        ],
        'rollback': 'كل خيار تغيير موضعي في معالج واحد؛ الإرجاع بـrevert واحد بلا هجرة بيانات.',
        'consequence': 'الكلفة تبقى تنمو مع البيانات، فتظهر المشكلة عند حمل لا يمكن اختباره بعد وقوعه.',
    },
    'import_cycle': {
        'change': 'اكسر الاتجاه الأضعف في الدورة: انقل ما يحتاجه الطرفان إلى وحدة ثالثة، أو اعكس الاعتماد بحقنه عند نقطة التركيب.',
        'options': [
            {'option': 'استخراج ما يتشاركانه إلى وحدة ثالثة', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا: يزيل الدورة دون قلب المسؤوليات'},
            {'option': 'عكس الاعتماد بحقن التبعية عند نقطة التركيب', 'cost': 'متوسطة', 'verdict': 'أنسب حين يكون أحد الطرفين سياسة والآخر تنفيذًا'},
            {'option': 'دمج الوحدتين', 'cost': 'منخفضة', 'verdict': 'مقبول فقط إن كانتا مسؤولية واحدة قُسمت بلا سبب'},
        ],
        'rollback': 'التغيير داخل الوحدات المعنية وبلا هجرة بيانات؛ الإرجاع بـrevert واحد.',
    },
    'duplicated_rule': {
        'change': 'أعطِ القاعدة مالكًا واحدًا، واجعل بقية المواضع تستورده، وأضف اختبارًا يثبت تطابق النتيجة عبر المسارات.',
        'options': [
            {'option': 'مالك واحد + استيراد من بقية المواضع', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاء النسخ مع اختبار تكافؤ يربطها', 'cost': 'منخفضة', 'verdict': 'مقبول عبر حدود اللغات حين لا يمكن الاستيراد'},
            {'option': 'توليد القيمة من مصدر إعداد واحد', 'cost': 'متوسطة', 'verdict': 'أنسب حين تتغير القيمة بحسب البيئة'},
        ],
        'rollback': 'إرجاع الاستيراد إلى تعريف محلي؛ لا أثر على البيانات.',
    },
    'hidden_coupling': {
        'change': 'حقّق أولًا: هل الاقتران حقيقي (سبب مشترك للتغيير) أم مصادفة؟ إن كان حقيقيًا، اجعله ظاهرًا في الكود أو في اختبار يربط الطرفين.',
        'options': [
            {'option': 'تحقيق ثم قرار موثق', 'cost': 'منخفضة', 'verdict': 'مختار: لا تُغيّر بنية على إشارة تاريخية وحدها'},
            {'option': 'جعل الاعتماد صريحًا في الكود', 'cost': 'متوسطة', 'verdict': 'بعد إثبات السبب المشترك'},
        ],
        'rollback': 'لا تغيير في الكود قبل انتهاء التحقيق.',
    },
    'trace_gap': {
        'change': 'اجعل المسار قابلًا للتتبع: استبدل الإرسال الديناميكي بربط صريح عند نقطة التسجيل، أو أضف أثرًا تشغيليًا يثبت المسار.',
        'options': [
            {'option': 'ربط صريح عند نقطة التسجيل', 'cost': 'منخفضة', 'verdict': 'مختار حين يكون الإرسال داخل مستودعنا'},
            {'option': 'إضافة كاشف إطار للأداة بدل تغيير المنتج', 'cost': 'متوسطة', 'verdict': 'أنسب حين يكون الإرسال من إطار خارجي'},
            {'option': 'قبول الفجوة وتوثيقها', 'cost': 'صفر', 'verdict': 'مقبول إن كان المسار مغطى باختبار تكاملي'},
        ],
        'rollback': 'التغيير محصور في نقطة التسجيل.',
    },
    'untested_path': {
        'change': 'لكل ملف: إما اختبار ينفّذه فعلًا، أو قرار موثق بأنه ميت مع حذفه.',
        'options': [
            {'option': 'اختبار لكل مسار يصل إليه تنفيذ', 'cost': 'متوسطة', 'verdict': 'مختار للمسارات القابلة للوصول من الإنتاج'},
            {'option': 'حذف ما ثبت أنه ميت', 'cost': 'منخفضة', 'verdict': 'بعد إثبات عدم الوصول من أي نقطة دخول'},
            {'option': 'قبول موثق بمالك وتاريخ', 'cost': 'صفر', 'verdict': 'للمسارات التجريبية أو المؤقتة'},
        ],
        'rollback': 'إضافة اختبارات لا تحتاج تراجعًا؛ الحذف يُراجع بـrevert.',
    },
    'hotspot': {
        'change': 'استخرج كل خطوة أو قرار مستقل إلى دالة بعقد صريح (مدخلات · مخرجات · تحققها)، وأبقِ الدالة الأصلية منسّقًا فقط، دون تغيير سلوك.',
        'options': [
            {'option': 'استخراج المراحل إلى دوال بعقود صريحة', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا: يخفض التفرّع ويجعل كل مرحلة قابلة للاختبار وحدها'},
            {'option': 'جدول قرارات أو سجل قابل للتوسعة بدل سلسلة الشروط', 'cost': 'متوسطة', 'verdict': 'أنسب حين تكون الفروع متجانسة'},
            {'option': 'رفع التغطية على الفروع غير المنفَّذة أولًا ثم إعادة الهيكلة', 'cost': 'منخفضة', 'verdict': 'مقدمة ضرورية إن كانت التغطية منخفضة'},
        ],
        'rollback': 'إعادة الهيكلة بلا تغيير عقود خارجية؛ الإرجاع بـrevert واحد.',
    },
    'split_module': {
        'change': 'قسّم الملف إلى وحدات صغيرة لكل منها مسؤولية واحدة، على حدود مسؤولياته (ما تستورده كل مجموعة من الدوال وما يستوردها)، وأبقِ أسماء ما يستورده الآخرون كما هي، دون تغيير سلوك.',
        'options': [
            {'option': 'تقسيم على حدود المسؤوليات إلى وحدات في حزمة واحدة', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا: كل وحدة تُقرأ وتُختبر وتتغير وحدها'},
            {'option': 'استخراج أكبر مسؤولية وحدها أولًا', 'cost': 'منخفضة', 'verdict': 'أنسب حين يكثر من يستورد الملف'},
            {'option': 'إبقاؤه مع قرار موثق بأنه مسؤولية واحدة', 'cost': 'صفر', 'verdict': 'فقط حين لا تقسيم يجعله أوضح'},
        ],
        'rollback': 'نقل بلا تغيير عقود خارجية؛ الإرجاع بـrevert واحد.',
    },
    'mutable_state': {
        'change': 'اجعل القيمة غير قابلة للتغيير، أو انقل التعديل خلف مالك واحد يُسلسِل الوصول ويُعلن دورة حياة الحالة.',
        'options': [
            {'option': 'تحويلها إلى قيمة ثابتة تُبنى مرة واحدة', 'cost': 'منخفضة', 'verdict': 'مختار حين تكون القيمة إعدادًا لا حالة'},
            {'option': 'مالك واحد يملك التعديل ويُسلسِله', 'cost': 'متوسطة', 'verdict': 'أنسب لحالة تتغير فعلًا أثناء التشغيل'},
            {'option': 'تمريرها صراحةً بدل مشاركتها عالميًا', 'cost': 'متوسطة', 'verdict': 'يزيل المشاركة من جذرها'},
        ],
        'rollback': 'التغيير في موضع التعريف وموضع التعديل؛ بلا هجرة بيانات.',
    },
    'external_write': {
        'change': 'انقل الكتابة إلى الوحدة المالكة خلف عملية مسمّاة تحفظ ثابتها، واستبدل الإسناد المباشر باستدعائها.',
        'options': [
            {'option': 'عملية مسمّاة في الوحدة المالكة', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'تمرير القيمة كمعامل بدل تعديل الحالة', 'cost': 'متوسطة', 'verdict': 'أنظف حين تكون القيمة سياقية'},
        ],
        'rollback': 'استبدال الاستدعاء بالإسناد السابق؛ تغيير محصور.',
    },
    'policy_violation': {
        'change': 'إما إزالة الاعتماد المخالف (بعكسه أو باستخراج ما يتشاركانه)، أو تعديل السياسة بقرار مكتوب يشرح لماذا صار مسموحًا.',
        'options': [
            {'option': 'إزالة الحافة المخالفة', 'cost': 'متوسطة', 'verdict': 'مختار حين تكون السياسة ما زالت معبّرة عن التصميم المقصود'},
            {'option': 'تعديل السياسة بسبب مكتوب', 'cost': 'منخفضة', 'verdict': 'مشروع تمامًا إن كان التصميم تغيّر؛ الممنوع هو التجاهل الصامت'},
        ],
        'rollback': 'أي من المسارين قابل للإرجاع؛ السياسة ملف واحد.',
    },
    'canonicalize': {
        'change': 'أعطِ المعنى المكرر موضعًا مرجعيًا واحدًا يحسبه الرسم (أدنى سلف مشترك لا يُنشئ دورة ولا يخالف الطبقة)، '
                  'وحوّل بقية المواضع إلى إحالة، وولّد اختبار تكافؤ يثبت أن كل موضع ينتج النتيجة نفسها كما قبل التغيير.',
        'options': [
            {'option': 'تعريف واحد في الموضع المرجعي + إحالات + اختبار تكافؤ', 'cost': 'متوسطة',
             'verdict': 'مختار افتراضيًا حين تكون المواضع قاعدة واحدة فعلًا'},
            {'option': 'إبقاء النسخ مع اختبار تكافؤ يربطها', 'cost': 'منخفضة',
             'verdict': 'أنسب عبر حدود اللغات أو الخدمات حين يتعذّر الاستيراد'},
            {'option': 'إبقاء موثّق بعد إثبات اختلاف السببين', 'cost': 'صفر',
             'verdict': 'نتيجة صحيحة لا فشل: التشابه اليوم لا يعني قاعدة واحدة غدًا'},
        ],
        'rollback': 'إرجاع الإحالة إلى تعريف محلي؛ بلا هجرة بيانات.',
    },
    'redundant_work': {
        'change': 'احذف العمل الزائد: احسب مرة واحدة واحتفظ بالنتيجة، أو ارفع النداء خارج الحلقة، '
                  'أو اجلب البيانات دفعة واحدة بدل نداء لكل سجل.',
        'options': [
            {'option': 'حساب واحد وإعادة استعماله في النطاق', 'cost': 'منخفضة', 'verdict': 'مختار للنداء المكرر'},
            {'option': 'رفع النداء خارج الحلقة', 'cost': 'منخفضة', 'verdict': 'حين لا يعتمد على متغيّر الحلقة'},
            {'option': 'جلب دفعي بدل N+1', 'cost': 'متوسطة', 'verdict': 'الأعلى أثرًا على الأداء'},
        ],
        'rollback': 'تغيير محصور داخل الدالة؛ الإرجاع بـrevert واحد.',
    },
    'dead_code': {
        'change': 'احذف المسار أو أضف اختبارًا ينفّذه: الخطر في الكود الميت أنه يُقرأ ويُصان دون أن يعمل، والحذف دون دليل قد يكسر مسارًا لم يره أي فحص.',
        'options': [
            {'option': 'الحذف بعد إثبات أن لا نقطة دخول تصل إليه', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا، بعد الدليل فقط'},
            {'option': 'اختبار ينفّذ المسار فعلًا', 'cost': 'متوسطة', 'verdict': 'مفضّل حين يكون المسار مقصودًا لتغييرات قادمة'},
            {'option': 'إبقاء موثّق بمالك وتاريخ إن ثبت أنه تجريبي', 'cost': 'صفر', 'verdict': 'للمسارات التجريبية أو المؤقتة'},
        ],
        'rollback': 'الحذف يُسترد بـrevert واحد، وإضافة اختبار لا تحتاج تراجعًا.',
    },
    'remove_dead': {
        'change': 'احذف الملف أو الرمز، ثم احذف ما لا يستورده إلا هو، وشغّل الاختبارات: لا مسار إنتاجي يصل إليه ولا نص يذكر اسمه.',
        'options': [
            {'option': 'الحذف الآن مع إعادة التدقيق', 'cost': 'منخفضة', 'verdict': 'مختار: الدليل آلي بالكامل'},
            {'option': 'إبقاؤه بمالك وسبب مكتوب في eaos.engagement.json', 'cost': 'صفر', 'verdict': 'حين يكون تجريبيًا أو قادمًا'},
            {'option': 'لا نفعل شيئًا', 'option_en': 'Do nothing', 'cost': 'يبقى عبئًا على القراءة والمراجعة', 'cost_en': 'stays a reading and review cost', 'verdict': 'مرفوض ما دامت القاعدة قائمة'},
        ],
        'rollback': 'revert واحد يعيد الملف أو الرمز كما كان.',
    },
    'broken_code': {
        'change': 'أصلح المرجع المعطّل: عرّف الاسم في النطاق الذي يقرؤه، أو احذف المفتاح المكرر بعد اختيار قيمته الصحيحة، أو صحّح مسار الاستيراد، أو حدّث الوثيقة إلى الأمر الموجود.',
        'options': [
            {'option': 'إصلاح المرجع مع اختبار يشغّل السطر', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'حذف الكود أو الوثيقة إن ثبت أن لا أحد يستخدمها', 'cost': 'منخفضة', 'verdict': 'حين يكون المسار ميتًا أيضًا'},
        ],
        'rollback': 'تغيير في موضع واحد؛ الإرجاع بـrevert واحد.',
    },
    'upgrade_dependency': {
        'change': 'رقِّ {name} من {installed} إلى {fixed} أو أحدث في ملف الاعتماديات، وأعد توليد ملف القفل بأداة الحزم نفسها، ثم شغّل الاختبارات.',
        'options': [
            {'option': 'ترقية إلى أقل إصدار يصلح كل الثغرات', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا: أصغر تغيير يغلق الخطر'},
            {'option': 'ترقية إلى أحدث إصدار', 'cost': 'متوسطة', 'verdict': 'حين يكون الإصدار متأخرًا كثيرًا؛ قد يغيّر الواجهة'},
            {'option': 'استبدال الحزمة', 'cost': 'مرتفعة', 'verdict': 'حين تكون متروكة بلا صيانة'},
        ],
        'rollback': 'revert واحد يعيد ملف الاعتماديات وملف القفل.',
    },
    'security_weakness': {
        'change': 'أغلق الثغرة عند كل موضع: مرّر المدخل كوسائط لا كنص يُبنى (أوامر واستعلامات)، أو تحقق منه بقائمة مسموحة، أو انقل السر إلى متغير بيئة وبدّله؛ ثم أعد الفحص بالأدوات نفسها.',
        'options': [
            {'option': 'إغلاق الثغرة في موضعها مع اختبار يثبت أن المدخل الخطر يُرفض', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤها مع سبب مكتوب حين لا يصل إليها مدخل غير موثوق', 'cost': 'صفر', 'verdict': 'حين يثبت الكود ذلك، والفرز يكتب السبب'},
        ],
        'rollback': 'revert واحد يعيد الموضع كما كان.',
    },
    'layer_boundary': {
        'change': 'أصلح الحد المكسور كما تقول طبقات النوع المرجعي: انقل الكود إلى الطبقة التي تملكه، أو أضف الحماية الناقصة (تسجيل الدخول، الملكية، أمان الصفوف، فحص المدخل في الخادم)، خلف قفل السلوك؛ ثم أعد قراءة الطبقات.',
        'options': [
            {'option': 'إصلاح الحد في موضعه كما يصفه المرجع', 'cost': 'منخفضة إلى متوسطة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤه مع سبب مكتوب حين يكون مقصودًا (بيانات عامة، نقطة عامة)', 'cost': 'صفر', 'verdict': 'حين يثبت الكود أو المالك ذلك'},
        ],
        'rollback': 'revert واحد يعيد الموضع كما كان.',
    },
    'repository_craft': {
        'change': 'رتّب الموضع كما تقول الملاحظة (مجلد حسب الوظيفة، اسم يقول وش فيه، مسار صحيح، ملف كونتكست أخف)، كدفعة نقل خاصة خلف قفل السلوك؛ ثم أعد قراءة الريبو.',
        'options': [
            {'option': 'الترتيب كدفعة لحالها يثبت إن ولا سلوك تغيّر', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤه مع سبب مكتوب حين يكون عُرفًا للمشروع', 'cost': 'صفر', 'verdict': 'حين يثبته الكود أو المالك'},
        ],
        'rollback': 'revert واحد يعيد الملفات كما كانت.',
    },
    'real_data': {
        'change': 'انقل البيانات إلى مكانها كما تقول البطاقة (قاعدة البيانات، أو ملف بذرة خارج البرنامج، أو قيم تجريبية بدلها)، واقرأها عن طريق طبقة البيانات، خلف قفل السلوك؛ ثم أعد الفحص بـ Presidio و ast-grep.',
        'options': [
            {'option': 'نقلها إلى قاعدة البيانات وحذفها من الكود', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤها مع سبب مكتوب حين تكون بيانات عامة يعرضها البرنامج بقصد', 'cost': 'صفر', 'verdict': 'حين يثبته الكود أو المالك'},
        ],
        'rollback': 'revert واحد يعيد الملفات كما كانت.',
    },
    'old_engine': {
        'change': 'احذف المحرك القديم كما تقول البطاقة (والمفتاح الثابت والفرع اللي يقفله)، أو انقل من يستدعيه إلى الجديد، خلف قفل السلوك؛ ثم أعد قراءة الكود.',
        'options': [
            {'option': 'حذفه بعد ما يثبت إن ما أحد يشغّله', 'cost': 'منخفضة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤه مع سبب مكتوب حين يكون احتياطًا مقصودًا', 'cost': 'صفر', 'verdict': 'حين يثبته الكود أو المالك'},
        ],
        'rollback': 'revert واحد يعيد الكود كما كان.',
    },
    'data_keeping': {
        'change': 'غيّر طريقة الحفظ أو التخزين كما تقول البطاقة (أرسل التغيير بس، الصور ملفات، نسخة احتياطية كاملة خارج الجهاز، رقم نسخة لكل كتابة)، خلف قفل السلوك؛ ثم أعد الفحص بتشغيل التطبيق.',
        'options': [
            {'option': 'إصلاح طريقة الحفظ أو التخزين من أصلها', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاؤها مع سبب مكتوب حين يكون حجم البيانات صغيرًا بقصد', 'cost': 'صفر', 'verdict': 'حين يثبته الكود أو المالك'},
        ],
        'rollback': 'revert واحد يعيد الكود كما كان.',
    },
    'one_source': {
        'change': 'اكتب المصدر الواحد مرة في مكانه كما تقول البطاقة (ملف الـ tokens، أو مكوّن، أو دالة مساعدة، أو أكمل نسخة)، وانقل كل الأماكن له بأداة النقل، خلف قفل السلوك (ما تتغير أي شاشة)؛ ثم أعد الفحص: الكاشف ما يلقى شي.',
        'options': [
            {'option': 'مصدر واحد تناديه كل الأماكن', 'cost': 'متوسطة', 'verdict': 'مختار افتراضيًا'},
            {'option': 'إبقاء نسخة مع سبب مكتوب حين تختلف لسبب حقيقي', 'cost': 'صفر', 'verdict': 'حين يثبته الكود أو المالك'},
        ],
        'rollback': 'revert واحد يعيد الكود كما كان.',
    },
    'generic': {
        'change': '⧗ لا نمط معالجة معروف لهذه الفئة: صمّم التغيير يدويًا، واذكر البديل «لا نفعل شيئًا» صراحة قبل الاعتماد.',
        'options': [{'option': 'تصميم يدوي بعد قراءة الدليل', 'cost': 'غير محددة', 'verdict': 'مطلوب'}],
        'rollback': '⧗ يُحدَّد مع التصميم.',
    },
}


def pattern_for(claim):
    name = classify(claim)
    pattern = dict(PATTERNS[name])
    pattern['name'] = name
    pattern['options'] = [*pattern['options'], dict(DO_NOTHING, verdict=cost_of_inaction(name))]
    render = claim.get('render') or {}
    if render.get('key') in ('layer_finding', 'repository_finding', 'logic_flaw', 'experience_difficulty', 'real_data', *OWN_PATTERN):   # the finding's own fix (M6.11, M7.8)
        pattern['change'] = (render.get('params') or {}).get('fix_ar') or pattern['change']
    if name == 'generic':
        reason = _generic_fallback_reason(claim)
        if reason:
            pattern['fallback_reason'] = reason
    return pattern


def cited(claim, fact_sets, name):
    """The facts of one fact set a claim cites: the evidence an executable repair stands on."""
    own = set(claim.get('fact_ids') or [])
    return [fact for fact in (fact_sets.get(name) or {}).get('facts', []) if fact.get('id') in own]


def _generic_fallback_reason(claim):
    specification = (claim.get('probe_spec') or {}).get('specification') or {}
    query = specification.get('query')
    if query == 'engine_cluster_present':
        kind = specification.get('kind')
        return 'unknown engine-cluster kind: ' + repr(kind) + ' (' + ('absent' if not kind else 'no pattern mapped') + ')'
    return ''


def cost_of_inaction(name):
    return {
        'import_cycle': 'يبقى الطرفان غير قابلين للاختبار أو الاستبدال منفردين، وتزداد الكلفة مع كل إضافة',
        'duplicated_rule': 'يبقى احتمال اختلاف النتيجة بين مسارين عند أول تعديل للقاعدة',
        'hidden_coupling': 'يبقى تغيير أحد الطرفين دون الآخر خطأً محتملًا بلا إشارة في الكود',
        'trace_gap': 'يبقى سلوك نقطة الدخول غير مفهوم من المصدر وحده',
        'untested_path': 'يبقى التغيير قابلًا للشحن بلا اختبار ينفّذه',
        'hotspot': 'يبقى كل تغيير في هذا المسار مارًّا بدالة واحدة كثيفة، وتزداد كلفتها مع كل إضافة',
        'split_module': 'يبقى كل تغيير في إحدى مسؤولياته يقرأ الأخرى ويعرّضها للكسر، ويكبر الملف مع كل ميزة جديدة',
        'mutable_state': 'تبقى نتيجة التشغيل معتمدة على الترتيب، وتبقى الاختبارات قد تنجح منفردة وتفشل مجتمعة',
        'external_write': 'تبقى الوحدة المالكة عاجزة عن ضمان ثابتها',
        'policy_violation': 'تبقى السياسة المعلنة مخالَفة، فتفقد قيمتها كعقد ويتآكل الالتزام بها',
        'canonicalize': 'يبقى المعنى الواحد مكتوبًا في مواضع متعددة، وأول تعديل يجعلها تختلف',
        'redundant_work': 'يبقى المسار ينفّذ عملًا لا تحتاجه نتيجته في كل تنفيذ',
        'load_blocker': 'تبقى الكلفة تنمو مع الحركة أو البيانات، فتظهر المشكلة عند حمل لا يمكن اختباره بعد وقوعه',
        'dead_code': 'يبقى الكود الميت عبئًا على القراءة والصيانة، ويصعّب تغييرات لا تعرف بوجوده، وقد يُعاد تفعيله دون تحذير',
        'broken_code': 'يفشل المسار أول مرة يُنفَّذ فيها عند المستخدم، أو تضلّل الوثيقة من يتبعها',
        'upgrade_dependency': 'تبقى ثغرة منشورة، بإصلاح منشور، في إصدار يشحنه المشروع لكل مستخدم',
        'remove_dead': 'يبقى الكود الميت عبئًا على القراءة والصيانة، ويصعّب تغييرات لا تعرف بوجوده، وقد يُعاد تفعيله دون تحذير',
        'security_weakness': 'يبقى باب مفتوح لمن يرسل مدخلًا مصممًا أو يجد السر، ولا يظهر أثره إلا بعد الاستغلال',
        'layer_boundary': 'يبقى الحد مفتوحًا: سرّ أو بيانات أو قاعدة يصل إليها من لا يملكها',
        'repository_craft': 'يبقى الوصول لأي شي في الريبو أبطأ وأصعب على كل مهندس ومساعد، وتكلّف كل جلسة توكنز أكثر',
        'real_data': 'تبقى بيانات الناس أو سجلات البرنامج تنتقل مع كل نسخة من الكود، وتطلع في الشاشات حتى لو قاعدة البيانات فاضية',
        'one_source': 'يبقى الشي الواحد مكتوب في أكثر من مكان: كل تعديل يتكرر، وأول تعديل ينسى مكان يخلّي الشاشات أو السلوك يختلف',
        'data_keeping': 'يكبر كل حفظ مع البيانات، أو تضيع بيانات أو تعديلات أو صور، ولا تنفع النسخة الاحتياطية يوم تحتاجها',
        'old_engine': 'يبقى كود قديم يُقرأ ويُصان ويُختبر بلا فائدة، ويرجع يشتغل لو انقلب المفتاح بالغلط',
        'generic': '⧗ غير محددة',
    }[name]
