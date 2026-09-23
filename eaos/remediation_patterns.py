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


def classify(claim):
    """Map a claim to a remediation pattern using how it was proven, not how it was worded."""
    specification = (claim.get('probe_spec') or {}).get('specification') or {}
    probe_type = (claim.get('probe_spec') or {}).get('probe_type')
    query = specification.get('query')
    if query == 'cycle_present': return 'import_cycle'
    if query == 'flow_has_unresolved_steps': return 'trace_gap'
    if query == 'no_code_dependency': return 'hidden_coupling'
    if query == 'metric_threshold': return 'hotspot'
    if query == 'mutable_global_present': return 'mutable_state'
    if query == 'external_write_present': return 'external_write'
    if query == 'policy_violation_present': return 'policy_violation'
    if query == 'duplicate_cluster_present': return 'canonicalize'
    if query == 'sequence_cluster_present': return 'canonicalize'
    if query == 'redundancy_present': return 'redundant_work'
    if query == 'load_blocker_present': return 'load_blocker'
    if query == 'engine_cluster_present':
        return _ENGINE_CLUSTER_KINDS.get(specification.get('kind'), 'generic')
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
    if name == 'generic':
        reason = _generic_fallback_reason(claim)
        if reason:
            pattern['fallback_reason'] = reason
    return pattern


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
        'mutable_state': 'تبقى نتيجة التشغيل معتمدة على الترتيب، وتبقى الاختبارات قد تنجح منفردة وتفشل مجتمعة',
        'external_write': 'تبقى الوحدة المالكة عاجزة عن ضمان ثابتها',
        'policy_violation': 'تبقى السياسة المعلنة مخالَفة، فتفقد قيمتها كعقد ويتآكل الالتزام بها',
        'canonicalize': 'يبقى المعنى الواحد مكتوبًا في مواضع متعددة، وأول تعديل يجعلها تختلف',
        'redundant_work': 'يبقى المسار ينفّذ عملًا لا تحتاجه نتيجته في كل تنفيذ',
        'load_blocker': 'تبقى الكلفة تنمو مع الحركة أو البيانات، فتظهر المشكلة عند حمل لا يمكن اختباره بعد وقوعه',
        'dead_code': 'يبقى الكود الميت عبئًا على القراءة والصيانة، ويصعّب تغييرات لا تعرف بوجوده، وقد يُعاد تفعيله دون تحذير',
        'generic': '⧗ غير محددة',
    }[name]
