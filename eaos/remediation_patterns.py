"""What to do about each class of finding, including the option of doing nothing.

A pattern never invents a fix for a claim class it does not know; it says plainly that the change
must be designed by hand, and still requires a runnable acceptance criterion.
"""

DO_NOTHING = {'option': 'لا نفعل شيئًا', 'option_en': 'Do nothing',
              'cost': 'صفر الآن', 'cost_en': 'zero now'}


def classify(claim):
    """Map a claim to a remediation pattern using how it was proven, not how it was worded."""
    specification = (claim.get('probe_spec') or {}).get('specification') or {}
    probe_type = (claim.get('probe_spec') or {}).get('probe_type')
    query = specification.get('query')
    if query == 'cycle_present': return 'import_cycle'
    if query == 'flow_has_unresolved_steps': return 'trace_gap'
    if query == 'no_code_dependency': return 'hidden_coupling'
    if probe_type == 'absence_search': return 'duplicated_rule'
    if claim.get('claim_type') == 'risk' and 'never executed' in claim['statement']: return 'untested_path'
    if claim.get('claim_type') == 'capability_gap': return 'trace_gap'
    return 'generic'


PATTERNS = {
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
    return pattern


def cost_of_inaction(name):
    return {
        'import_cycle': 'يبقى الطرفان غير قابلين للاختبار أو الاستبدال منفردين، وتزداد الكلفة مع كل إضافة',
        'duplicated_rule': 'يبقى احتمال اختلاف النتيجة بين مسارين عند أول تعديل للقاعدة',
        'hidden_coupling': 'يبقى تغيير أحد الطرفين دون الآخر خطأً محتملًا بلا إشارة في الكود',
        'trace_gap': 'يبقى سلوك نقطة الدخول غير مفهوم من المصدر وحده',
        'untested_path': 'يبقى التغيير قابلًا للشحن بلا اختبار ينفّذه',
        'generic': '⧗ غير محددة',
    }[name]
