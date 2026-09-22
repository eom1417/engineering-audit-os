# خطة رفع القدرات: من 0.49 إلى 0.80+ في كل مجال

> مولَّد من `docs/capability-plan.json` — لا تحرّره يدويًا. الأساس: `47f4886` · 2026-09-22.

**الهدف:** كل مجال ≥ 0.80، مقيسًا بـ tools/capability_score.py لا بالرأي.

## الوضع المقيس اليوم

| المجال | الدرجة | الهدف |
| --- | --- | --- |
| layered_engineering | 1.0 | 0.80 |
| report_clarity | 0.92 | 0.80 |
| structure_python | 0.9592 | 0.80 |
| transformation_plan | 0.6667 | 0.80 |
| runtime_surface | 0.4583 | 0.80 |
| structure_polyglot | 0.3027 | 0.80 |
| load_model | 0.0 | 0.80 |
| target_architecture | 0.0 | 0.80 |
| independent_proof | 0.0 | 0.80 |

**الإجمالي 0.4874** — 3 من 9 مجالات بلغت الهدف.

## كيف ينفّذ أي نموذج هذه الخطة

١. شغّل: python tools/capability_score.py <report-dirs> — هذا وضعك الحالي.
٢. افتح docs/capability-plan.json، وخذ أول مهمة status=todo اكتملت كل depends_on لها.
٣. اقرأ حقل files: هذه هي الملفات التي ستلمسها. لا تلمس غيرها.
٤. نفّذ steps بالترتيب حرفيًا. كل خطوة جملة واحدة قابلة للتنفيذ.
٥. شغّل acceptance كما هو مكتوب. خروج 0 = انتهت. غير ذلك = لم تنتهِ، مهما بدا الكود صحيحًا.
٦. شغّل بوابة العبور (gate أدناه). إن فشلت، أصلح قبل أن تكمل.
٧. غيّر status إلى done في هذا الملف، وشغّل python tools/render_capability_plan.py، ثم التزم بالتغيير.
٨. لا تضف عملًا خارج steps. ما ينقص يُسجَّل مهمة جديدة في نهاية نفس المعلم.
٩. مهمة فشلت مرتين: status=blocked مع سطر واحد يشرح السبب، ثم انتقل إلى مهمة لا تعتمد عليها.

**بوابة العبور بعد كل مهمة:**

```bash
python -m unittest discover -s tests -q && python tools/validate.py && python tools/invariants.py && python tools/render_capability_plan.py --check && bash tests/gate/self_audit.sh
```

## قواعد غير قابلة للتفاوض

1. لا مهمة تُغلق بوصف نصي؛ معيار القبول أمر يرجع 0.
2. كل كاشف جديد يأتي معه fixture فيه الحالة الموجبة والحالة السالبة.
3. كل حقيقة جديدة تُضاف إلى schemas/fact.schema.json وإلى نسخة eaos/data عبر tools/render.py.
4. كل وحدة جديدة تُعلَن في eaos.policy.json وإلا فشلت بوابة السياسة.
5. كل docstring يدّعي ثابتًا يُسجَّل في docs/invariants.json مع اختبار يفرضه.
6. كل مصنوعة جديدة تُعلَن في eaos/compose/artifacts.py بمالك وغرض وميزانية.
7. لا تقيس بالرأي: إن لم يتحرك المؤشر في tools/capability_score.py فالمهمة لم تنجح.

## المراجع

| ما هو | أين |
| --- | --- |
| أداة القياس | `tools/capability_score.py و eaos/capability.py` |
| النموذج المقاس | `docs/capability-score.json (الخط الأساسي) و docs/CAPABILITY-SCORE.md` |
| خط الأنابيب | `eaos/pipeline/stages.py (16 مرحلة معلَنة)` |
| عقد المصنوعات | `eaos/compose/artifacts.py` |
| عقد المخرجات | `eaos/compose/rules.py (R1–R13)` |
| طبقة المحركات | `eaos/engines/ و upstreams/registry.yaml` |
| المحركات المثبّتة | `/workspace/engine-tools/bin/{enola,codegraph-server,reforge,jscpd}` |
| نسخ المنبع | `/workspace/upstream-src/{enola,CodeGraph,Reforge,jscpd}` |
| أدوات CodeGraph | `codegraph-server --graph-only -w <dir> --run-tool <tool> --tool-args '{}'` |
| تقارير مرجعية للقياس | `أعد إنتاجها: eaos audit . --out /tmp/selfr && eaos audit /workspace/upstream-src/enola --out /tmp/gor --skip site` |

## المعالم

| # | المعلم | يعتمد على | المهام | الحالة |
| --- | --- | --- | --- | --- |
| N1 | أداة القياس وبوابة عدم التراجع | — | 3/3 | ✅ |
| N2 | الإشارة فوق الضجيج | N1 | 0/4 | ⬜ |
| N3 | عمق اللغات غير Python | N2 | 0/4 | ⬜ |
| N4 | الكواشف التشغيلية الخمسة الناقصة | N1 | 0/5 | ⬜ |
| N5 | نموذج الحمل — قلب الاستشارة | N3, N4 | 0/6 | ⬜ |
| N6 | الصورة المثالية بمحتوى | N3, N5 | 0/4 | ⬜ |
| N7 | خطة تنفيذها مضمون | N6 | 0/2 | ⬜ |
| N8 | تقرير يفهمه أي نموذج وينفّذه | N5, N6, N7 | 0/3 | ⬜ |
| N9 | الحكم المستقل | N8 | 0/2 | ⬜ |
| N10 | إعادة القياس وقرار الإصدار | N2, N3, N4, N5, N6, N7, N8 | 0/2 | ⬜ |

## N1 — أداة القياس وبوابة عدم التراجع

**الهدف:** رقم لكل مجال يُحسب من الأدلة، فيصير كل هدف بعده قابلًا للتحقق.

### N1.T1 — نموذج القدرات وحاسبته ✅

**لماذا:** خطة بأهداف غير قابلة للقياس ليست خطة.

**الملفات:**

- `eaos/capability.py`
- `tools/capability_score.py`
- `tests/test_capability.py`

**الخطوات:**

1. تسعة مجالات، لكل مجال مؤشرات تُحسب من مجلد تقرير حقيقي
2. مؤشر بلا دليل = غير مقيس، ولا يُحتسب نجاحًا
3. أضعف تقرير يحدد درجة المجال

**معيار القبول:**

```bash
python -m unittest tests.test_capability -q
```

**التراجع:** حذف الوحدة والأداة

### N1.T2 — تسجيل الخط الأساسي ✅

**لماذا:** بلا خط أساس لا يوجد "تحسّن".

**الملفات:**

- `docs/capability-score.json`
- `docs/CAPABILITY-SCORE.md`

**الخطوات:**

1. شغّل الحاسبة على تقريرين: هذا المستودع ومستودع Go خارجي
2. اكتب النتيجة بـ --write

**معيار القبول:**

```bash
test -f docs/capability-score.json
```

**التراجع:** حذف الملف

### N1.T3 — بوابة عدم التراجع ✅

**لماذا:** مجال بلغ هدفه يجب ألا يعود تحته بصمت.
**يعتمد على:** N1.T2

**الملفات:**

- `tests/gate/capability_no_regression.sh`
- `tests/test_capability.py`

**الخطوات:**

1. سكربت يعيد حساب الدرجات ويقارنها بـ docs/capability-score.json
2. يفشل إذا نزل أي مجال أكثر من 0.02 عن آخر قيمة مسجلة
3. يُحدّث الملف المسجل عند التحسّن فقط

**معيار القبول:**

```bash
bash tests/gate/capability_no_regression.sh
```

**التراجع:** حذف السكربت

## N2 — الإشارة فوق الضجيج

**الهدف:** أن يكون أول ما يقرأه القارئ عن كوده هو، لا عن تجهيزات مشروعه.

**المشكلة المقيسة:** على مستودع Go حقيقي: 8 من 19 ادعاءً جاءت من internal/engine/testdata، و5 ادعاءات "421 دالة تنفّذ نفس التسلسل" تسلسلها len→Fatalf→len وهو اصطلاح اختبارات Go. وأولوية الضجيج 0.233 مقابل 0.0014 لدالة فيها 189 تفرّعًا.

### N2.T1 — استبعاد ما ليس كود القارئ افتراضيًا ⬜

**لماذا:** تقرير عن fixtures المشروع المفحوص ليس تقريرًا عنه.
**يحرّك:** `report_clarity.top_findings_are_about_the_reader_s_code` من `0.6` إلى `1.0`

**الملفات:**

- `eaos/facts/scope.py`
- `eaos/facts/source.py`
- `tests/test_facts_scope.py`

**الخطوات:**

1. أضف VENDORED = ("testdata", "fixtures", "vendor", "node_modules", "third_party", "generated", ".venv", "dist", "build") إلى eaos/facts/scope.py
2. اجعل declared_exclusions تُرجع الاستثناءات المعلنة + VENDORED، ما لم يعلن المشروع include_vendored: true في eaos.policy.json
3. سجّل في ملخص مجموعة الحقائق كم ملفًا استُبعد ولماذا — الاستبعاد الصامت ممنوع
4. أضف اختبارًا: مشروع فيه testdata/ لا تظهر ملفاته في facts، والعدد المستبعد مذكور

**مراجع:** `eaos/facts/scope.py` · `eaos.policy.json`

**معيار القبول:**

```bash
python -m unittest tests.test_facts_scope -q
```

**التراجع:** إرجاع VENDORED إلى قائمة فارغة

### N2.T2 — الوصول يُقاس من الرسم لا من حجم العنقود ⬜

**لماذا:** عنقود من 421 دالة اختبار يسحق دالة إلهية حقيقية لأن المعادلة تكافئ الحجم.
**يحرّك:** `report_clarity.top_findings_are_about_the_reader_s_code` من `0.6` إلى `1.0`
**يعتمد على:** N2.T1

**الملفات:**

- `eaos/ranking.py`
- `tests/test_impact_ranking.py`

**الخطوات:**

1. في eaos/ranking.py: احسب reach من عدد المعتمدين والتدفقات ونقاط الدخول في facts/graph.json فقط
2. عنقود بلا عقد في الرسم: reach = 0 وليس حجم العنقود
3. أضف حقل reach_source إلى priority_factors بقيمة "graph" أو "no_graph_node"
4. اختبار: عنقود من 400 عضو بلا عقد رسم أولويته أقل من دالة واحدة فيها 189 تفرّعًا

**مراجع:** `eaos/ranking.py:12 WEIGHTS`

**معيار القبول:**

```bash
python -m unittest tests.test_impact_ranking -q
```

**التراجع:** إرجاع المعادلة السابقة من git

### N2.T3 — كاشف التسلسلات يعرف اصطلاحات اللغة ⬜

**لماذا:** len→Fatalf→len ليس تكرارًا في الأعمال؛ هو كيف تُكتب اختبارات Go.
**يحرّك:** `report_clarity.top_findings_are_about_the_reader_s_code` من `0.6` إلى `1.0`
**يعتمد على:** N2.T1

**الملفات:**

- `eaos/facts/sequences.py`
- `tests/fixtures/idioms/`
- `tests/test_facts_sequences.py`

**الخطوات:**

1. أضف IDIOMS في eaos/facts/sequences.py: قاموس لغة → مجموعات نداءات اصطلاحية (go: t.Run/t.Fatalf/t.Errorf/require/assert/len/err؛ python: assertEqual/assertTrue/patch؛ javascript: expect/describe/it)
2. تسلسل كل نداءاته من الاصطلاحات لا يصير عنقودًا
3. أضف fixture لكل لغة: ملف اختبارات اصطلاحي (يجب ألا يُبلَّغ) وملف فيه تكرار حقيقي (يجب أن يُبلَّغ)
4. سجّل في الملخص عدد العناقيد المستبعدة كاصطلاح — لا إسقاط صامت

**مراجع:** `eaos/facts/sequences.py`

**معيار القبول:**

```bash
python -m unittest tests.test_facts_sequences -q
```

**التراجع:** تفريغ IDIOMS

### N2.T4 — إثبات على المستودع الحقيقي ⬜

**لماذا:** الإصلاح يُثبت على المستودع الذي كشف العيب، لا على fixture.
**يحرّك:** `report_clarity.top_findings_are_about_the_reader_s_code` من `0.6` إلى `1.0`
**يعتمد على:** N2.T2, N2.T3

**الملفات:**

- `tests/gate/signal_first.sh`

**الخطوات:**

1. سكربت: eaos audit /workspace/upstream-src/enola --out <tmp> --skip site
2. يفشل إذا كان أي من أعلى 10 ادعاءات مساره داخل testdata أو vendor
3. يفشل إذا لم يظهر أي ادعاء hotspot ضمن أعلى 10

**معيار القبول:**

```bash
bash tests/gate/signal_first.sh
```

**التراجع:** حذف السكربت

## N3 — عمق اللغات غير Python

**الهدف:** structure_polyglot من 0.30 إلى ≥0.80.

**المشكلة المقيسة:** استيرادات Go تُحلّ بنسبة 6.7٪ عبر اللغات غير Python. بلا رسم اعتماد لا يوجد نطاق أثر ولا تدفقات ولا ترتيب ذو معنى: 65 نقطة دخول أنتجت 7 تدفقات فقط.

### N3.T1 — قياس الحل لكل لغة قبل أي تغيير ⬜

**لماذا:** بلا رقم لكل لغة لن نعرف أي محوّل نفع.
**يحرّك:** `structure_polyglot.imports_resolved_outside_python` من `0.067` إلى `0.067`

**الملفات:**

- `tools/language_depth.py`
- `docs/language-depth.json`

**الخطوات:**

1. أداة تطبع لكل لغة: عدد الملفات، نسبة التحليل النحوي، نسبة حل الاستيرادات الداخلية، عدد الرموز
2. شغّلها على /workspace/upstream-src/enola و CodeGraph و Reforge واكتب النتيجة
3. هذا هو خط الأساس لكل مهمة بعده

**معيار القبول:**

```bash
python tools/language_depth.py --write && test -f docs/language-depth.json
```

**التراجع:** حذف الأداة والملف

### N3.T2 — محوّل CodeGraph للرسم والاستدعاءات ⬜

**لماذا:** نستعمل أداة واحدة من 68. الأدوات الأربع هذه هي بالضبط ما يسدّ فجوة الـ6.7٪.
**يحرّك:** `structure_polyglot.imports_resolved_outside_python` من `0.067` إلى `0.5`
**يعتمد على:** N3.T1

**الملفات:**

- `eaos/engines/codegraph.py`
- `tests/contracts/codegraph.json`
- `tests/test_engine_contracts.py`

**الخطوات:**

1. أضف إلى TOOLS: codegraph_get_dependency_graph و codegraph_get_call_graph و codegraph_analyze_coupling و codegraph_find_hot_paths
2. لكل أداة: شغّلها مرة على /workspace/upstream-src/enola وسجّل شكل المخرج قبل كتابة أي تطبيع
3. أضف kind جديدًا "call_edge_external" و "module_edge_external" إلى eaos/engines/contract.py:KINDS
4. إن رجعت أداة تحذيرًا في payload: خفّض تقييمها إلى partial كما يفعل كاشف الدورات
5. أضف عيّنة مثبّتة لكل أداة في tests/contracts/codegraph.json
6. إن أعادت أداة لا شيء على enola: سجّلها في DECLINED بالسبب المقيس ولا تضفها

**مراجع:** `/workspace/upstream-src/CodeGraph/crates` · `eaos/engines/codegraph.py`

**معيار القبول:**

```bash
python -m unittest tests.test_engine_contracts -q
```

**التراجع:** إرجاع TOOLS إلى أداة واحدة

### N3.T3 — دمج رسم المحرك في حقائقنا ⬜

**لماذا:** الرسم الخارجي بلا دمج يبقى معلومة لا يستعملها نطاق الأثر ولا التدفقات.
**يحرّك:** `structure_polyglot.imports_resolved_outside_python` من `0.5` إلى `0.8`
**يعتمد على:** N3.T2

**الملفات:**

- `eaos/facts/resolve.py`
- `eaos/facts/graph.py`
- `eaos/facts/external.py`
- `tests/test_facts_resolve.py`

**الخطوات:**

1. في eaos/facts/external.py: حوّل call_edge_external و module_edge_external إلى حقائق حواف
2. في resolve.py: عندما يعجز حلّالنا عن حافة ويوجد لها حل خارجي، سجّلها resolution=RESOLVED_BY_ENGINE مع اسم المحرك في الحقيقة — لا تخلطها مع حلّنا
3. في graph.py: أدخل الحواف الخارجية في الرسم مع وسم مصدرها
4. أضف إلى ملخص resolve: resolved_by_us و resolved_by_engine منفصلين
5. اختبار: مشروع Go تُحلّ حوافه عبر المحرك، والحقيقة تقول أي محرك حلّها

**معيار القبول:**

```bash
python -m unittest tests.test_facts_resolve -q && python tools/language_depth.py
```

**التراجع:** إسقاط RESOLVED_BY_ENGINE وإرجاع الرسم لحلّنا وحده

### N3.T4 — عتبة لكل لغة في القياس ⬜

**لماذا:** متوسط عبر اللغات يخفي لغة ميتة.
**يحرّك:** `structure_polyglot.languages_with_depth` من `0.5385` إلى `0.8`
**يعتمد على:** N3.T3

**الملفات:**

- `eaos/capability.py`
- `tests/test_capability.py`

**الخطوات:**

1. في structure_polyglot: اجعل languages_with_depth يعدّ اللغات التي depth لها ≥ 0.80
2. أضف مؤشرًا thirdmost_language_depth: عمق ثالث أضعف لغة لها ≥5 ملفات
3. اختبار: لغة واحدة ممتازة وأربع ميتة لا تعطي درجة عالية

**معيار القبول:**

```bash
python -m unittest tests.test_capability -q && python tools/capability_score.py /tmp/selfr /tmp/gor
```

**التراجع:** إرجاع المؤشر السابق

## N4 — الكواشف التشغيلية الخمسة الناقصة

**الهدف:** runtime_surface من 0.46 إلى ≥0.80.

**المشكلة المقيسة:** سبعة كواشف تشغيلية من اثني عشر مطلوبة. الخمسة الناقصة هي بالضبط ما يحتاجه نموذج الحمل: حدود الاستعلام، الصمود، التخزين المؤقت، تحديد المعدّل، تجمّع الاتصالات.

### N4.T1 — كاشف حدود الاستعلام ⬜

**لماذا:** استعلام بلا حد أعلى يعمل على ألف صف ويسقط على مليون.
**يحرّك:** `runtime_surface.detectors_implemented` من `0.5833` إلى `0.6667`

**الملفات:**

- `eaos/facts/runtime.py`
- `tests/fixtures/runtime/query-bounds/`
- `tests/test_facts_runtime.py`
- `schemas/fact.schema.json`

**الخطوات:**

1. أضف kind "query_bound" إلى schemas/fact.schema.json ثم شغّل python tools/render.py
2. اكشف في Python: .limit( .offset( [:n] paginate( first( .all() )بلا حد
3. اكشف في JavaScript/TypeScript: .limit( .take( .skip( findMany({take
4. اكشف في Go: LIMIT في نص SQL، و .Limit( في ORM
5. كل حقيقة تحمل: bounded=true/false، والآلية، والموضع
6. fixture: ملف فيه استعلام محدود وآخر غير محدود لكل لغة من الثلاث
7. ما لا تعرفه: لا تحكم. سجّل bounded=unknown مع السبب

**مراجع:** `eaos/facts/runtime.py`

**معيار القبول:**

```bash
python -m unittest tests.test_facts_runtime -q
```

**التراجع:** حذف الكاشف ونوع الحقيقة

### N4.T2 — كاشف سياسات الصمود ⬜

**لماذا:** نداء خارجي بلا مهلة يحوّل بطء خدمة أخرى إلى توقف عندك.
**يحرّك:** `runtime_surface.detectors_implemented` من `0.6667` إلى `0.75`
**يعتمد على:** N4.T1

**الملفات:**

- `eaos/facts/runtime.py`
- `tests/fixtures/runtime/resilience/`
- `tests/test_facts_runtime.py`
- `schemas/fact.schema.json`

**الخطوات:**

1. أضف kind "resilience_policy"
2. لكل integration_target مكتشف: ابحث في نفس النداء عن timeout= أو Timeout أو ctx مع مهلة
3. اكشف إعادة المحاولة: retry/Retry/backoff/tenacity/@retry
4. اكشف قاطع الدائرة: circuit/breaker/hystrix/resilience4j/pybreaker
5. كل حقيقة: {target, has_timeout, has_retry, has_circuit_breaker} وكل قيمة true/false/unknown
6. fixture: نداء محمي وآخر عارٍ

**معيار القبول:**

```bash
python -m unittest tests.test_facts_runtime -q
```

**التراجع:** حذف الكاشف

### N4.T3 — كاشف التخزين المؤقت ⬜

**لماذا:** بلا معرفة ما هو مُخزَّن مؤقتًا، كل تقدير للحمل خطأ بمقدار مجهول.
**يحرّك:** `runtime_surface.detectors_implemented` من `0.75` إلى `0.8333`
**يعتمد على:** N4.T2

**الملفات:**

- `eaos/facts/runtime.py`
- `tests/fixtures/runtime/cache/`
- `tests/test_facts_runtime.py`
- `schemas/fact.schema.json`

**الخطوات:**

1. أضف kind "cache_policy"
2. اكشف: lru_cache/cached_property/functools.cache، redis/memcached/cache.get، Cache-Control في الردود، @Cacheable، revalidate
3. كل حقيقة: {mechanism, scope: process|shared|http, ttl_declared: true/false/unknown, location}
4. fixture: تخزين داخل العملية، وتخزين مشترك، ولا تخزين

**معيار القبول:**

```bash
python -m unittest tests.test_facts_runtime -q
```

**التراجع:** حذف الكاشف

### N4.T4 — كاشف تحديد المعدّل وحدود التزامن ⬜

**لماذا:** نقطة دخول بلا حد معدّل تُسقط النظام كله عند أول ارتفاع.
**يحرّك:** `runtime_surface.detectors_implemented` من `0.8333` إلى `0.9167`
**يعتمد على:** N4.T3

**الملفات:**

- `eaos/facts/runtime.py`
- `tests/fixtures/runtime/limits/`
- `tests/test_facts_runtime.py`
- `schemas/fact.schema.json`

**الخطوات:**

1. أضف kind "rate_limit"
2. اكشف في الكود: @limiter/@throttle/RateLimiter/semaphore/Semaphore/max_concurrent
3. اكشف في الإعداد: nginx limit_req، Kubernetes resources.limits، إعدادات gateway
4. كل حقيقة: {entry_point_or_global, mechanism, declared_limit, source: code|config}
5. fixture: نقطة محدودة وأخرى مفتوحة

**معيار القبول:**

```bash
python -m unittest tests.test_facts_runtime -q
```

**التراجع:** حذف الكاشف

### N4.T5 — كاشف تجمّع الاتصالات ⬜

**لماذا:** حجم التجمّع هو السقف الحقيقي لعدد الطلبات المتزامنة، ونادرًا ما ينتبه له أحد.
**يحرّك:** `runtime_surface.detectors_implemented` من `0.9167` إلى `1.0`
**يعتمد على:** N4.T4

**الملفات:**

- `eaos/facts/runtime.py`
- `tests/fixtures/runtime/pool/`
- `tests/test_facts_runtime.py`
- `schemas/fact.schema.json`

**الخطوات:**

1. أضف kind "connection_pool"
2. اكشف: pool_size/max_connections/maxPoolSize/SetMaxOpenConns/pool_pre_ping، و DATABASE_URL بمعاملات تجمّع
3. كل حقيقة: {resource, declared_size, source, location}؛ غير المعلن = unknown لا افتراض
4. fixture: تجمّع معلن وآخر بالإعداد الافتراضي

**معيار القبول:**

```bash
python -m unittest tests.test_facts_runtime -q && python tools/capability_score.py /tmp/selfr /tmp/gor
```

**التراجع:** حذف الكاشف

## N5 — نموذج الحمل — قلب الاستشارة

**الهدف:** load_model من 0.00 إلى ≥0.80: ثمانية أسئلة مُجابة لكل نقطة دخول، وإسقاط عند ١٠٠٠ ضعف.

**المشكلة المقيسة:** نملك 50 نتيجة O(n²)/O(n³) من enola وكاشف N+1 وحالة وحدة قابلة للتغيير — ولا شيء منها مُجمَّع في جواب واحد عن نقطة دخول واحدة.

**الأسئلة الثمانية:**

- `data_access_calls — كم استعلامًا/نداء تخزين يُصدره هذا المسار؟`
- `repeats_per_iteration — هل أحدها داخل حلقة (N+1)؟`
- `result_is_bounded — هل النتيجة محدودة (limit/pagination)؟`
- `complexity_class — ما رتبة المعالج الزمنية؟`
- `shared_mutable_state — هل يلمس حالة على مستوى الوحدة تمنع التشغيل الأفقي؟`
- `outbound_calls_protected — هل النداءات الخارجة محمية بمهلة/إعادة محاولة؟`
- `cached — هل على المسار تخزين مؤقت، وأي نطاق؟`
- `rate_limited — هل لنقطة الدخول حد معدّل أو حد تزامن؟`

### N5.T1 — عقد نموذج الحمل ⬜

**لماذا:** قبل الحساب، يُكتب شكل الجواب — وإلا صار كل جواب شكلًا مختلفًا.
**يحرّك:** `load_model.questions_answered` من `0.0` إلى `0.0`

**الملفات:**

- `eaos/load_model.py`
- `schemas/load-model.schema.json`
- `tests/test_load_model.py`

**الخطوات:**

1. أنشئ eaos/load_model.py بثابت QUESTIONS يحوي الأسئلة الثمانية بأسمائها الحرفية
2. لكل سؤال جواب بالشكل: {status: answered|not_applicable|undetectable, value, evidence: [fact_ids], reason}
3. status=undetectable يجب أن يحمل reason غير فارغ — الغياب بلا سبب ممنوع
4. أضف schemas/load-model.schema.json وتحقق منه
5. أعلن eaos/load_model.py في eaos.policy.json تحت ledger

**معيار القبول:**

```bash
python -m unittest tests.test_load_model -q
```

**التراجع:** حذف الوحدة والمخطط

### N5.T2 — سجل كلفة لكل نقطة دخول ⬜

**لماذا:** الجواب يكون عن نقطة دخول يعرفها القارئ، لا عن دالة لا يعرف أين تُستدعى.
**يحرّك:** `load_model.entry_points_with_a_cost_record` من `0.0` إلى `0.9`
**يعتمد على:** N5.T1

**الملفات:**

- `eaos/load_model.py`
- `tests/test_load_model.py`

**الخطوات:**

1. لكل entry_point غير اختباري: اجمع التدفق المتتبَّع له من facts/flows.json
2. data_access_calls: عُدّ نداءات التخزين على المسار من facts/structure.json + _N1_NAMES في redundancy
3. repeats_per_iteration: من حقائق redundancy kind=n_plus_one الواقعة على المسار
4. complexity_class: من حقائق external rule=performance على رموز المسار
5. result_is_bounded: من query_bound (N4.T1)
6. shared_mutable_state: من domain mutable_global و external_state_write على المسار
7. outbound_calls_protected: من resilience_policy (N4.T2) على integration_target في المسار
8. cached: من cache_policy (N4.T3)
9. rate_limited: من rate_limit (N4.T4)
10. كل جواب يحمل fact_ids؛ جواب بلا دليل ممنوع
11. تدفق لم يُتتبَّع = كل الأسئلة undetectable بسبب "the flow could not be traced"

**معيار القبول:**

```bash
python -m unittest tests.test_load_model -q
```

**التراجع:** إرجاع الوحدة إلى العقد وحده

### N5.T3 — الإسقاط عند ١٠٠٠ ضعف ⬜

**لماذا:** العميل لا يسأل "كم استعلامًا"؛ يسأل "هل يصمد".
**يحرّك:** `load_model.projection_recorded` من `0.0` إلى `1.0`
**يعتمد على:** N5.T2

**الملفات:**

- `eaos/load_model.py`
- `tests/test_load_model.py`

**الخطوات:**

1. لكل نقطة دخول: احسب كيف تتضاعف الأجوبة عند مضاعف حركة m (افتراضي 1000)
2. القاعدة صريحة ومكتوبة في المخرج: استعلام ثابت ×m، استعلام داخل حلقة ×m×n، نتيجة غير محدودة تنمو مع البيانات لا مع الحركة
3. رتّب العوائق: حالة الوحدة أولًا (تمنع النسخ المتعددة)، ثم N+1، ثم غياب الحد
4. اكتب الافتراضات صراحةً: هذا إسقاط حسابي من البنية، وليس قياس أداء
5. نقطة دخول فيها سؤال undetectable: الإسقاط لها يقول "غير مكتمل" ويسمّي السؤال الناقص

**معيار القبول:**

```bash
python -m unittest tests.test_load_model -q
```

**التراجع:** إسقاط الإسقاط والاكتفاء بالسجل

### N5.T4 — مرحلة وتقرير ومصنوعة ⬜

**لماذا:** ما لا يظهر في المخرج لم يُنجز.
**يحرّك:** `load_model.entry_points_with_a_cost_record` من `0.9` إلى `0.95`
**يعتمد على:** N5.T3

**الملفات:**

- `eaos/pipeline/stages.py`
- `eaos/pipeline/runners.py`
- `eaos/compose/artifacts.py`
- `eaos/load_report.py`
- `tests/test_load_model.py`

**الخطوات:**

1. أضف مرحلة "load" بعد "probe" تنتج load-model.json و LOAD-MODEL.md
2. requires=("facts","claims")، ضرورية لا اختيارية
3. أعلن المصنوعتين في eaos/compose/artifacts.py بمالك load وميزانية 200 سطر ورابط record
4. LOAD-MODEL.md: جدول نقاط الدخول مرتبًا بخطر الحمل، ثم أسوأ خمس نقاط بتفصيلها، ثم قسم "ما لم نستطع قياسه ولماذا"
5. اربط كل سطر بـ fact_ids كما تفعل بقية الوثائق

**معيار القبول:**

```bash
eaos audit . --out /tmp/lm --skip site && test -f /tmp/lm/LOAD-MODEL.md && python3 -c "import json;d=json.load(open('/tmp/lm/load-model.json'));assert d['entry_points']"
```

**التراجع:** إزالة المرحلة والمصنوعتين

### N5.T5 — ادعاءات الحمل تدخل السجل ⬜

**لماذا:** خطر حمل لا يصير ادعاءً لا يصير بطاقة ولا يُنفَّذ.
**يحرّك:** `load_model.questions_answered` من `0.5` إلى `0.8`
**يعتمد على:** N5.T4

**الملفات:**

- `eaos/claims.py`
- `eaos/probes.py`
- `eaos/compose/labels.py`
- `eaos/remediation_patterns.py`
- `tests/test_load_model.py`

**الخطوات:**

1. ولّد ادعاءً من كل عائق حمل: N+1 على مسار، حالة وحدة على مسار، نداء خارجي بلا مهلة، نتيجة غير محدودة على نقطة دخول عامة
2. لكل ادعاء ناقض: مثلًا "قياس يُظهر أن هذا الاستعلام يُنفَّذ مرة واحدة مهما كان عدد البنود"
3. أضف probe_spec بنوع graph_query واستعلام load_blocker_present
4. أضف قوالب العرض في labels.py ونمط إصلاح في remediation_patterns.py لكل نوع عائق
5. DETAIL_ARTIFACT لهذه الادعاءات = LOAD-MODEL.md

**معيار القبول:**

```bash
python -m unittest tests.test_load_model tests.test_claims -q
```

**التراجع:** حذف المولّدات

### N5.T6 — حالات معنونة تثبت كل سؤال ⬜

**لماذا:** كاشف بلا حالة موجبة وسالبة ليس مقيسًا.
**يحرّك:** `load_model.questions_answered` من `0.8` إلى `0.9`
**يعتمد على:** N5.T5

**الملفات:**

- `tests/fixtures/benchmarks/load/`
- `tools/engine_precision.py`

**الخطوات:**

1. لكل سؤال من الثمانية: مشروع صغير فيه الحالة الموجبة والسالبة
2. ground-truth.json لكل حالة يذكر السؤال والجواب المتوقع وسبب أهميته
3. وسّع tools/engine_precision.py ليقيس أسئلة الحمل أيضًا
4. سجّل النتيجة في docs/engine-precision.json

**معيار القبول:**

```bash
python tools/engine_precision.py --write
```

**التراجع:** حذف الحالات

## N6 — الصورة المثالية بمحتوى

**الهدف:** target_architecture من 0.00 إلى ≥0.80.

**المشكلة المقيسة:** على المستودعين: 0٪ من المكوّنات مُقيَّمة. المخرج قائمة بـ10,938 رمزًا كلها "unassessed"، ومصفوفة الفجوة كلها "unassessed". أي أن "الصورة المثالية" اليوم هيكل فارغ.

### N6.T1 — المكوّن وحدة معمارية لا رمز ⬜

**لماذا:** 10,938 مكوّنًا ليست معمارية؛ هي قائمة رموز.
**يحرّك:** `target_architecture.components_assessed` من `0.0` إلى `0.3`

**الملفات:**

- `eaos/target_architecture.py`
- `tests/test_target_architecture.py`

**الخطوات:**

1. عرّف المكوّن كعقدة وحدة/حزمة من facts/graph.json، لا كرمز من syntax
2. ادمج الرموز تحت مكوّنها؛ عدد المكوّنات يجب أن يكون بعشرات لا بالآلاف
3. اختبار: مستودع بـ10,000 رمز في 40 حزمة ينتج 40 مكوّنًا لا 10,000

**معيار القبول:**

```bash
python -m unittest tests.test_target_architecture -q
```

**التراجع:** إرجاع التعريف السابق

### N6.T2 — قاعدة تقييم لكل مكوّن، ودليلها ⬜

**لماذا:** "unassessed" مقبول كجواب، لكن ليس كجواب وحيد لكل شيء.
**يحرّك:** `target_architecture.components_assessed` من `0.3` إلى `0.85`
**يعتمد على:** N6.T1

**الملفات:**

- `eaos/target_architecture.py`
- `tests/test_target_architecture.py`

**الخطوات:**

1. retain: مكوّن بلا مخالفة سياسة ولا دورة ولا عائق حمل ولا تكرار — والدليل هو غياب هذه
2. modify: مكوّن عليه ادعاء CONFIRMED واحد على الأقل — الدليل هو معرّفات تلك الادعاءات
3. introduce: بيت قانوني مقترح من canonical_home لعنقود تكرار عابر للمكوّنات
4. retire: مكوّن كل رموزه في حقائق dead_code ولا نقطة دخول تصله
5. unassessed: يبقى فقط لمكوّن لم يصله أي استخراج، ومعه reason إلزامي
6. كل مكوّن يحمل evidence: [fact_ids] و reason؛ تقييم بلا دليل ممنوع بالاختبار

**معيار القبول:**

```bash
python -m unittest tests.test_target_architecture -q
```

**التراجع:** إرجاع الكل إلى unassessed

### N6.T3 — قرار معماري ببدائله ⬜

**لماذا:** قرار بلا بديل مرفوض ليس قرارًا؛ هو تفضيل.
**يحرّك:** `target_architecture.decisions_with_alternatives` من `0.0` إلى `0.85`
**يعتمد على:** N6.T2

**الملفات:**

- `eaos/target_architecture.py`
- `docs/adr/`
- `tests/test_target_architecture.py`

**الخطوات:**

1. لكل مكوّن بتقييم modify/introduce/retire: ولّد ADR
2. كل ADR: {id, problem, evidence: [fact_ids], options: [بديلان على الأقل أحدهما "لا تفعل شيئًا"], chosen, tradeoffs, consequences, migration}
3. اكتبها ملفات في docs/adr/ADR-NNN.md وسجلًا في target-architecture.json
4. اختبار: ADR بخيار واحد أو بلا مقايضة يُرفض

**معيار القبول:**

```bash
python -m unittest tests.test_target_architecture -q
```

**التراجع:** حذف مولّد ADR

### N6.T4 — مصفوفة فجوة حقيقية ⬜

**لماذا:** مصفوفة كلها "unassessed" لا تقول أين نحن من الهدف.
**يحرّك:** `target_architecture.gap_matrix_resolved` من `0.0` إلى `0.85`
**يعتمد على:** N6.T3

**الملفات:**

- `eaos/target_architecture.py`
- `eaos/bundles.py`
- `tests/test_target_architecture.py`

**الخطوات:**

1. لكل مكوّن صف: {component, current, target, gap: covered|partial|missing, evidence, blocking_tasks}
2. covered = التقييم retain ولا ادعاء مفتوح عليه
3. partial = عليه ادعاءات وبعضها له بطاقة مهمة
4. missing = عليه ادعاءات بلا بطاقة، أو تقييمه introduce ولا مرحلة تحويل تنتجه
5. اربط كل صف ببطاقات PLAN/ التي تغلقه

**معيار القبول:**

```bash
python -m unittest tests.test_target_architecture -q && eaos audit . --out /tmp/ta --skip site && python3 -c "import json;d=json.load(open('/tmp/ta/target-architecture.json'));rows=d['gap_matrix'];assert sum(1 for r in rows if r['gap']!='unassessed')/len(rows) >= 0.85"
```

**التراجع:** إرجاع المصفوفة السابقة

## N7 — خطة تنفيذها مضمون

**الهدف:** transformation_plan من 0.67 إلى ≥0.85.

**المشكلة المقيسة:** صفر مرحلة تحمل أمر قبول قابلًا للتشغيل، ولا توقّع واحد جرت مقارنته بما حدث.

### N7.T1 — أمر قبول قابل للتشغيل لكل مرحلة ⬜

**لماذا:** معيار قبول لا يُشغَّل ليس معيارًا.
**يحرّك:** `transformation_plan.stages_with_runnable_acceptance` من `0.0` إلى `0.9`

**الملفات:**

- `eaos/transform_plan.py`
- `tests/test_transformation_handoff.py`

**الخطوات:**

1. لكل مرحلة: اشتق أمرًا من أمر اختبار المشروع المكتشف (facts/config أو manifests)
2. إن لم يكن للمشروع أمر اختبار: الأمر هو فحص تكافؤ مولَّد، ويُعلَن كذلك
3. الأمر يجب أن يكون قائمة argv لا نصًا، و cwd جذر المرشّح، و expected_exit عددًا
4. امنع أوامر إعادة توليد التقرير كمعيار قبول (موجود في decisions.check_errors — أعد استخدامه)
5. اختبار: كل مرحلة في خطة مولَّدة على هذا المستودع لها أمر يمر decisions.check_errors

**معيار القبول:**

```bash
python -m unittest tests.test_transformation_handoff -q
```

**التراجع:** إرجاع المعيار الوصفي

### N7.T2 — قياس التوقّع بعد التنفيذ ⬜

**لماذا:** توقّع لا يُقارن بما حدث هو ادعاء عن المستقبل بلا حساب.
**يحرّك:** `transformation_plan.predictions_verified` من `None` إلى `0.85`
**يعتمد على:** N7.T1

**الملفات:**

- `eaos/guarantee.py`
- `eaos/pipeline/stages.py`
- `eaos/pipeline/runners.py`
- `tests/test_guarantee.py`

**الخطوات:**

1. اجعل تسجيل التوقّع جزءًا من مرحلة transform: prediction.json لكل مرحلة
2. أضف أمرًا eaos guarantee --before <dir> --after <dir> يكتب GUARANTEE.md و guarantee.json
3. أعلن المصنوعتين في artifacts.py
4. اختبار: مرحلة نُفّذت فعلًا على مشروع تجريبي، والمقارنة تعطي HONEST/OVERSTATED/UNDERSTATED

**معيار القبول:**

```bash
python -m unittest tests.test_guarantee -q
```

**التراجع:** إبقاء guarantee أمرًا يدويًا

## N8 — تقرير يفهمه أي نموذج وينفّذه

**الهدف:** report_clarity ≥0.90 مع بقاء كل ما سبق، ودليل تنفيذ يقرأه نموذج ضعيف فينفّذ.

### N8.T1 — دليل التنفيذ المولَّد ⬜

**لماذا:** التقرير يصف؛ الدليل ينفَّذ. وشرطك أن أي قصور في الفهم قصور في التدوين.
**يحرّك:** `report_clarity.documents_declared` من `1.0` إلى `1.0`

**الملفات:**

- `eaos/execution_guide.py`
- `eaos/compose/artifacts.py`
- `eaos/pipeline/stages.py`
- `tests/test_execution_guide.py`

**الخطوات:**

1. ولّد EXECUTION-GUIDE.md من plan.json و transform-plan.json و load-model.json
2. لكل مهمة بالترتيب: الهدف في جملة، الملفات بالضبط، الخطوات مرقّمة، أمر القبول، التراجع، الاعتماديات
3. ابدأ الوثيقة بقسم "اقرأ هذا أولًا": كيف يُنفَّذ، ما الممنوع، ومتى يتوقف المنفّذ ويسأل
4. كل معرّف في الدليل (مسار، رمز، أمر) يُكتب حرفيًا بلا اختصار ولا ترجمة
5. أعلن المصنوعة في artifacts.py بميزانية 300 سطر و record=plan.json

**معيار القبول:**

```bash
eaos audit . --out /tmp/eg --skip site && python -m unittest tests.test_execution_guide -q
```

**التراجع:** حذف المولّد والمصنوعة

### N8.T2 — اختبار قابلية التنفيذ آليًا ⬜

**لماذا:** ادعاء "أي نموذج يفهمه" يجب أن يكون قابلًا للفشل.
**يحرّك:** `report_clarity.documents_declared` من `1.0` إلى `1.0`
**يعتمد على:** N8.T1

**الملفات:**

- `tests/test_execution_guide.py`

**الخطوات:**

1. عرّف FORBIDDEN_TOKENS في eaos/execution_guide.py: قائمة الرموز التي تجعل خطوة غير قابلة للتنفيذ — علامات الحذف، وأدوات التقريب والاحتمال، وكلمات النيابة عن قيمة لم تُحدَّد بعد. القائمة تُكتب هناك مرة واحدة ولا تُكرَّر هنا.
2. اختبار: كل مهمة في الدليل لها ملفات موجودة فعلًا على القرص
3. اختبار: كل أمر قبول قابل للتحليل كـargv ولا يحتوي أي رمز من FORBIDDEN_TOKENS
4. اختبار: كل خطوة جملة أمرية واحدة ولا تحتوي أي رمز من FORBIDDEN_TOKENS
5. اختبار: كل مهمة لها تراجع غير فارغ
6. اختبار: ترتيب المهام طوبولوجي — لا مهمة قبل اعتماديتها

**معيار القبول:**

```bash
python -m unittest tests.test_execution_guide -q
```

**التراجع:** حذف الاختبارات

### N8.T3 — توأم JSON لكل وثيقة ⬜

**لماذا:** النموذج يقرأ السجل؛ الإنسان يقرأ الوثيقة. الاثنان من مصدر واحد.
**يحرّك:** `report_clarity.documents_declared` من `1.0` إلى `1.0`
**يعتمد على:** N8.T2

**الملفات:**

- `eaos/compose/artifacts.py`
- `tests/test_artifact_contract.py`

**الخطوات:**

1. كل مصنوعة من نوع document يجب أن تحمل record غير فارغ، أو absent_when يشرح لماذا لا سجل لها
2. أضف قاعدة R14 في compose/rules.py: وثيقة بلا توأم سجل ولا تعليل = مخالفة
3. اختبار طفرة: أضف وثيقة بلا record → يجب أن تفشل R14

**معيار القبول:**

```bash
python -m unittest tests.test_artifact_contract -q
```

**التراجع:** إسقاط R14

## N9 — الحكم المستقل

**الهدف:** independent_proof من 0.00 إلى ≥0.80. هذا المعلم وحده يحتاج إنسانًا.

> هذا المعلم لا يستطيع نموذج إتمامه وحده.

### N9.T1 — حزمة المراجعة الجاهزة ⬜

**لماذا:** حكم مستقل لم يحدث لأن تجهيزه لم يُجهَّز، لا لأنه صعب.
**يحرّك:** `independent_proof.independent_reviews` من `0.0` إلى `0.0`

**الملفات:**

- `evaluations/review-pack/`
- `tools/build_review_pack.py`

**الخطوات:**

1. أداة تبني حزمة: تقرير على مشروع لم تُضبط عليه الأداة + استمارة حكم من عشرة أسئلة
2. الأسئلة تُجاب بنعم/لا/لا أستطيع الحكم: هل الادعاء صحيح؟ محدد؟ له موضع؟ هل البطاقة قابلة للتنفيذ بلا سؤالي؟ هل الترتيب منطقي؟ هل الحدود واضحة؟
3. الحزمة لا تحتوي إجابات الحقيقة — المحكّم يرى المخرج فقط
4. تعليمات المحكّم في صفحة واحدة، والوقت المطلوب لا يتجاوز 30 دقيقة

**معيار القبول:**

```bash
python tools/build_review_pack.py --out evaluations/review-pack && test -f evaluations/review-pack/README.md
```

**التراجع:** حذف الحزمة

### N9.T2 — تشغيل المراجعة (يحتاج إنسانًا) ⬜

**لماذا:** لا يستطيع نموذج أن يشهد لنفسه بالفائدة.
**يحرّك:** `independent_proof.independent_reviews` من `0.0` إلى `0.8`
**يعتمد على:** N9.T1

**الملفات:**

- `evaluations/release-evidence.json`

**الخطوات:**

1. أعطِ الحزمة لمهندس لم يشارك في بناء الأداة ولم يكتب أي ground truth
2. سجّل إجاباته حرفيًا في human_judgement مع independent=true واسمه أو رمزه
3. لا تُعدّل جوابًا ولا تُلخّصه؛ الإجابة السلبية دليل مثل الإيجابية

**معيار القبول:**

```bash
python tools/check_release_evidence.py evaluations/release-evidence.json
```

**التراجع:** إرجاع الحالة إلى blocked

## N10 — إعادة القياس وقرار الإصدار

**الهدف:** إثبات أن كل مجال بلغ ≥0.80، ثم اتخاذ قرار الإصدار على هذا الدليل.

### N10.T1 — إعادة القياس على نفس التقارير ⬜

**لماذا:** القياس على تقارير أخرى ليس مقارنة.
**يحرّك:** `overall` من `0.4874` إلى `0.8`

**الملفات:**

- `docs/capability-score.json`
- `docs/CAPABILITY-SCORE.md`

**الخطوات:**

1. أعد إنتاج نفس التقريرين: eaos audit . --out /tmp/selfr و eaos audit /workspace/upstream-src/enola --out /tmp/gor --skip site
2. شغّل python tools/capability_score.py /tmp/selfr /tmp/gor --write
3. قارن بـ docs/capability-score.json السابق واكتب جدول قبل/بعد في CHANGELOG

**معيار القبول:**

```bash
python tools/capability_score.py /tmp/selfr /tmp/gor && python3 -c "import json;c=json.load(open('docs/capability-score.json'));bad={k:v['score'] for k,v in c['domains'].items() if not v['meets_target'] and k!='independent_proof'};assert not bad, bad"
```

**التراجع:** لا ينطبق

### N10.T2 — قرار الإصدار على الدليل الجديد ⬜

**لماذا:** القرار يتبع الدليل، لا العكس.
**يحرّك:** `overall` من `0.8` إلى `0.8`
**يعتمد على:** N10.T1

**الملفات:**

- `evaluations/release-evidence.json`
- `README.md`
- `CHANGELOG.md`

**الخطوات:**

1. حدّث results.measured بالدرجات الجديدة و supported_scope بما صار مدعومًا
2. انقل من unsupported_scope ما أثبتّه فقط، واترك الباقي
3. اختر release أو limited_release أو pilot حسب ما يسمح به tools/check_release_evidence.py
4. حدّث README بنطاق الدعم المُثبت وبأوامر التشغيل والرجوع

**معيار القبول:**

```bash
python tools/check_release_evidence.py evaluations/release-evidence.json && python -m unittest tests.test_installed_review -q
```

**التراجع:** إرجاع القرار السابق
