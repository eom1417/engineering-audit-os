# خطة التحول: من مكتبة بأوامر إلى ورك-فلو واحد

> مولَّد من `docs/transformation.json` — لا تحرّره يدويًا. الأساس: الالتزام `3b430cd` بتاريخ 2026-09-21.

## قواعد التنفيذ

1. كل مرحلة تنتهي بأمر يرجع 0 أو لا يرجعه. لا مرحلة تُعتبر منتهية بوصف نصي.
2. لا مرحلة تُغلق قبل أن تمر كل الاختبارات و`python tools/validate.py` و`eaos policy check`.
3. أي ثابت (invariant) يُذكر في docstring ولا يفرضه اختبار يُعدّ فلسفة، ويُحذف أو يُحوَّل إلى اختبار.
4. كل مرحلة تغيّر سلوكًا تضيف اختبار انحدار في نفس الالتزام.
5. لا تُبنى واجهة جديدة قبل حذف التي تحلّ محلها؛ الواجهتان المتوازيتان هما ما نحاربه.

## نقطة البداية المقيسة

| القياس | القيمة |
| --- | --- |
| `package_lines` | 10921 |
| `tests` | 448 |
| `cli_commands` | 39 |
| `modern_path_commands` | 20 |
| `legacy_audit_run_commands` | 18 |
| `legacy_subsystem_lines` | 1476 |
| `modern_imports_of_legacy` | 2 |
| `artifacts_from_review_project` | 15 |
| `subsystems_review_project_silently_skips` | sustainability, engines, transform-plan, probe, verify |
| `output_contract_violations` | 0 |
| `policy_violations` | 0 |
| `python_modules` | 86 |

## المراحل

| # | المرحلة | يعتمد على | الحالة |
| --- | --- | --- | --- |
| T0 | تثبيت خط الأساس قبل أي تحويل | — | ✅ |
| T1 | إعلان خط الأنابيب بيانات لا دالة | T0 | ⬜ |
| T2 | محرّك التنفيذ وسجل التشغيل | T1 | ⬜ |
| T3 | مدخل واحد: eaos audit | T2 | ⬜ |
| T4 | إنهاء خط الأنابيب الثاني | T3 | ⬜ |
| T5 | عقد المصنوعات وترتيب القراءة | T3 | ⬜ |
| T6 | تحويل الفلسفة إلى اختبارات | T3 | ⬜ |
| T7 | خط أساس وبوابة منع الدين الجديد | T3 | ⬜ |
| T8 | سير عمل ترقية المنبع | T3 | ⬜ |
| T9 | تشغيل النظام على نفسه حتى يسكت | T4, T5, T6, T7 | ⬜ |

### T0 — تثبيت خط الأساس قبل أي تحويل

**لماذا:** لا يمكن إثبات أن التحول لم يكسر شيئًا بلا رقم مرجعي مسجّل.

**التغييرات:**
- docs/baseline.json يسجّل: عدد الاختبارات، الأوامر، المصنوعات، المخالفات، زمن الدورة

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
test -f docs/baseline.json && python3 -c "import json;d=json.load(open('docs/baseline.json'));assert d['tests']>0 and d['policy_violations']==0"
```

**التراجع:** حذف الملف؛ لا أثر على الكود

### T1 — إعلان خط الأنابيب بيانات لا دالة

**لماذا:** اليوم الترتيب مكتوب داخل product_review.run كسلسلة استدعاءات، فلا يمكن استعلامه ولا تخطّي مرحلة ولا معرفة ما لم يُشغَّل.

**التغييرات:**
- eaos/pipeline/stages.py: STAGES قائمة مرتبة من {name, produces, requires, optional, reason_if_skipped, runner}
- المُشغِّلات أغلفة رفيعة على الوحدات القائمة؛ لا منطق يُنقل في هذه المرحلة
- eaos/pipeline/__init__.py يصدّر STAGES و graph()

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python -m unittest tests.test_pipeline_graph -q  # يثبت: لا مرجع أمامي، لا دورة، كل requires ينتجه ما قبله
```

**التراجع:** حذف eaos/pipeline؛ product_review يبقى كما هو

### T2 — محرّك التنفيذ وسجل التشغيل

**لماذا:** المرحلة التي تفشل اليوم تُسقط الدورة كلها، والمرحلة التي لا تُشغَّل لا تترك أثرًا — وهذا يخالف قاعدة صدق التغطية التي نفرضها على غيرنا.

**التغييرات:**
- eaos/pipeline/run.py: execute(target, out, only, skip, resume) ينفّذ المراحل بالترتيب
- run-manifest.json: لكل مرحلة status ∈ {ok, skipped, unavailable, failed} + seconds + artifacts + reason
- فشل مرحلة اختيارية لا يوقف الدورة؛ فشل مرحلة مطلوبة يوقفها ويسمّي السبب
- المراحل التالية لمرحلة فاشلة تُسجَّل skipped: dependency_failed، لا تُترك صامتة

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python -m unittest tests.test_pipeline_run -q  # يثبت: مرحلة ترمي → manifest failed، التالية skipped، خروج 2، والاستئناف يعيد الناقص فقط
```

**التراجع:** git revert للالتزام؛ لا مستهلك خارجي بعد

### T3 — مدخل واحد: eaos audit

**لماذا:** review-project ينتج 15 مصنوعة ويتخطى صامتًا خمسة أنظمة فرعية: sustainability و engines و transform-plan و probe و verify.

**التغييرات:**
- eaos/cli.py: أمر audit <target> --out بأعلام --only/--skip/--resume/--engines/--provider
- review-project يصبح غلافًا على audit بمجموعة مراحل مسمّاة، ثم يُعلَن مهجورًا في CHANGELOG
- run-manifest.json يُعرض في README.md المولَّد: ما شُغِّل وما لم يُشغَّل ولماذا

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
eaos audit . --out /tmp/t3 --engines && python3 -c "import json,os;m=json.load(open('/tmp/t3/run-manifest.json'));assert all(s['status'] in ('ok','skipped','unavailable') for s in m['stages'].values());assert os.path.exists('/tmp/t3/SUSTAINABILITY.md') and os.path.exists('/tmp/t3/ENGINES.md') and os.path.exists('/tmp/t3/probes.json')"
```

**التراجع:** إبقاء review-project كما هو وحذف أمر audit

### T4 — إنهاء خط الأنابيب الثاني

**لماذا:** المستودع يحمل نظامين متوازيين: مسار run القديم (18 أمرًا، 1,476 سطرًا) ومسار dossier الحديث (20 أمرًا). المسار الحديث يستورد من القديم مرتين فقط. هذا هو parallel_implementation الذي تحاربه عقيدتنا، في أنفسنا.

**التغييرات:**
- قياس أولًا: ما الذي يقدّمه المسار القديم ولا يقدّمه الحديث (قائمة مكتوبة قبل أي حذف)
- ما له بديل: يُحذف الأمر وتُنقل الوحدة إن لزم
- ما لا بديل له: يصير مرحلة في خط الأنابيب الواحد
- المستهلكان الوحيدان (claims→audit_records، dossier→discovery) يُنقل ما يحتاجانه إلى core

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python -m unittest discover -s tests -q && python3 -c "import json;d=json.load(open('docs/baseline.json'));import subprocess;out=subprocess.run(['eaos','--help'],capture_output=True,text=True).stdout;assert out.count('init')==0 or d.get('legacy_kept')" && python -m unittest tests.test_no_duplicate_artifact_owner -q
```

**التراجع:** الحذف على دفعات، كل دفعة التزام مستقل قابل للعكس

### T5 — عقد المصنوعات وترتيب القراءة

**لماذا:** المخرج اليوم 15 إلى 20 ملفًا بلا مالك معلن ولا ترتيب قراءة مفروض؛ الترتيب موجود في README المكتوب يدويًا لا في عقد يُتحقق منه.

**التغييرات:**
- eaos/compose/artifacts.py: لكل مصنوعة {owner_stage, purpose, reading_order, budget_lines, required}
- README.md يُولَّد من هذا العقد لا من نص مكتوب
- عقد المخرجات يكتسب قاعدة R13: كل ملف في out/ معلن، وكل معلَن مُنتَج أو مُعلَّل غيابه

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python -m unittest tests.test_artifact_contract -q  # كل ملف منتج معلَن، وكل معلَن منتَج أو غيابه مسجّل بسبب
```

**التراجع:** تعطيل R13 وإبقاء README المكتوب

### T6 — تحويل الفلسفة إلى اختبارات

**لماذا:** الكود يعلن ثوابت نصًا في docstrings. الثابت الذي لا يفرضه اختبار ليس ثابتًا؛ إنه نية.

**التغييرات:**
- tools/invariants.py: يستخرج كل docstring يعلن ثابتًا (نمط: never/always/must/لا/يجب) ويطابقه بجدول INVARIANTS
- eaos/invariants.py: جدول {id, statement, enforced_by_test}
- كل ثابت بلا اختبار: إمّا يُكتب له اختبار، أو تُحذف الجملة من الـdocstring

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python tools/invariants.py --check  # خروج 0 يعني: لا ثابت معلن بلا اختبار يفرضه
```

**التراجع:** تحويل الفحص إلى تحذير بدل فشل

### T7 — خط أساس وبوابة منع الدين الجديد

**لماذا:** المحركات تنتج 586 نتيجة على مستودع نظيف نسبيًا. على مشروع قديم ستكون آلافًا، وأول PR سيفشل بذنب دين قديم، فتُطفأ البوابة ويضيع كل شيء.

**التغييرات:**
- eaos baseline pin: يثبّت بصمات النتائج الحالية (content_fingerprint من Reforge، ومعرّفاتنا)
- eaos delta --gate=new: يفشل على الجديد فقط
- تقرير التقادم: كم من خط الأساس أُغلق منذ تثبيته

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
bash tests/gate/no_new_debt.sh  # يثبت: 500 نتيجة قديمة لا تُفشل، ونتيجة جديدة واحدة تُفشل
```

**التراجع:** البوابة تحذيرية بالعلم --warn-only

### T8 — سير عمل ترقية المنبع

**لماذا:** نعتمد على أربعة مشاريع تتحرك. ترقية عمياء تكسر المحوّلات بصمت.

**التغييرات:**
- tools/upstream_check.py: يقارن الإصدار المثبَّت بالأحدث، ويشغّل مجموعة عقود المحوّلات، ويقارن مخططات المخرجات
- tests/contracts/<engine>.json: عيّنة مخرَج مثبَّتة لكل محرك، يفشل الاختبار إن تغيّر شكلها

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
python tools/upstream_check.py --offline  # يمر على العيّنات المثبّتة بلا شبكة
```

**التراجع:** لا شيء؛ أداة مستقلة

### T9 — تشغيل النظام على نفسه حتى يسكت

**لماذا:** أداة تدّعي تحسين المعمارية يجب أن تجتاز قواعدها هي.

**التغييرات:**
- eaos audit . --out /tmp/self --engines ثم إصلاح ما يظهر
- تكرار حتى: صفر مخالفات عقد، صفر مخالفات سياسة، صفر ثوابت بلا اختبار، ولا نتيجة جديدة فوق خط الأساس

**معيار القبول (أمر يُشغَّل، لا وصف):**

```bash
bash tests/gate/self_audit.sh
```

**التراجع:** لا ينطبق
