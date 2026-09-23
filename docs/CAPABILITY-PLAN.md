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
| N2 | الإشارة فوق الضجيج | N1 | 4/4 | ⬜ |
| N3 | عمق اللغات غير Python | N2 | 4/4 | ⬜ |
| N4 | الكواشف التشغيلية الخمسة الناقصة | N1 | 5/5 | ⬜ |
| N5 | نموذج الحمل — قلب الاستشارة | N3, N4 | 6/6 | ✅ |
| N6 | الصورة المثالية بمحتوى | N3, N5 | 4/4 | ⬜ |
| N7 | خطة تنفيذها مضمون | N6 | 1/2 | ⬜ |
| N8 | تقرير يفهمه أي نموذج وينفّذه | N5, N6, N7 | 3/3 | ⬜ |
| N9 | الحكم المستقل | N8 | 1/2 | ⬜ |
| N10 | إعادة القياس وقرار الإصدار | N2, N3, N4, N5, N6, N7, N8 | 1/2 | ⬜ |
| N11 | إصلاح ما كشفته المراجعة البعدية | N3, N5, N6, N7 | 9/9 | ⬜ |
| N12 | من الملاحظة إلى الوصفة | N11 | 5/5 | ⬜ |

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

### N2.T1 — استبعاد ما ليس كود القارئ افتراضيًا ✅

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

### N2.T2 — الوصول يُقاس من الرسم لا من حجم العنقود ✅

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

### N2.T3 — كاشف التسلسلات يعرف اصطلاحات اللغة ✅

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

### N2.T4 — إثبات على المستودع الحقيقي ✅

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

### N3.T1 — قياس الحل لكل لغة قبل أي تغيير ✅

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

### N3.T2 — محوّل CodeGraph للرسم والاستدعاءات ✅

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

### N3.T3 — دمج رسم المحرك في حقائقنا ✅

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

### N3.T4 — عتبة لكل لغة في القياس ✅

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

### N4.T1 — كاشف حدود الاستعلام ✅

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

### N4.T2 — كاشف سياسات الصمود ✅

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

### N4.T3 — كاشف التخزين المؤقت ✅

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

### N4.T4 — كاشف تحديد المعدّل وحدود التزامن ✅

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

### N4.T5 — كاشف تجمّع الاتصالات ✅

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

### N5.T1 — عقد نموذج الحمل ✅

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

### N5.T2 — سجل كلفة لكل نقطة دخول ✅

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

### N5.T3 — الإسقاط عند ١٠٠٠ ضعف ✅

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

### N5.T4 — مرحلة وتقرير ومصنوعة ✅

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

### N5.T5 — ادعاءات الحمل تدخل السجل ✅

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

### N5.T6 — حالات معنونة تثبت كل سؤال ✅

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

### N6.T1 — المكوّن وحدة معمارية لا رمز ✅

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

### N6.T2 — قاعدة تقييم لكل مكوّن، ودليلها ✅

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

### N6.T3 — قرار معماري ببدائله ✅

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

### N6.T4 — مصفوفة فجوة حقيقية ✅

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

### N7.T1 — أمر قبول قابل للتشغيل لكل مرحلة ✅

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

### N7.T2 — قياس التوقّع بعد التنفيذ ⛔

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

### N8.T1 — دليل التنفيذ المولَّد ✅

**لماذا:** التقرير يصف؛ الدليل ينفَّذ. وشرطك أن أي قصور في الفهم قصور في التدوين.
**يحرّك:** `report_clarity.documents_declared` من `1.0` إلى `1.0`

**الملفات:**

- `eaos/execution_guide.py`
- `eaos/compose/artifacts.py`
- `eaos/pipeline/stages.py`
- `eaos/pipeline/runners.py`
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

### N8.T2 — اختبار قابلية التنفيذ آليًا ✅

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

### N8.T3 — توأم JSON لكل وثيقة ✅

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

### N9.T1 — حزمة المراجعة الجاهزة ✅

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

### N9.T2 — تشغيل المراجعة (يحتاج إنسانًا) ⛔

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

### N10.T1 — إعادة القياس على نفس التقارير ⛔

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

### N10.T2 — قرار الإصدار على الدليل الجديد ✅

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

## N11 — إصلاح ما كشفته المراجعة البعدية

**الهدف:** كل عيب أثبتته المراجعة على مستودع حقيقي يُغلق بقياس على مستودع حقيقي، لا على عيّنة اختبار.

**المشكلة المقيسة:** على enola: 1336 استيرادًا من 1430 مسجّل AMBIGUOUS رغم أن 1326 منها مرشّحاته كلها في مجلد واحد؛ و8 نقاط دخول من 9 بلا معالج قابل للتتبّع فينتج تدفّق واحد على مستودع من 985 ملف Go؛ و79251 حافة استدعاء و10495 رمزًا لا تُستعمل. وعلى مستودعنا: خمسة أسئلة من ثمانية تُسجَّل undetectable بينما السبب المكتوب هو «بحثنا فلم نجد» وهذا جواب لا عجز.

### N11.T1 — استيراد الحزمة في Go يُحلّ إلى مجلد الحزمة ✅

**لماذا:** في Go الاستيراد يشير إلى حزمة أي مجلد، ومحلّلنا يطلب ملفًا واحدًا فيعلن الالتباس حيث لا التباس.
**يحرّك:** `structure_polyglot.imports_resolved_outside_python` من `0.0594` إلى `0.85`

**الملفات:**

- `eaos/facts/resolve.py`
- `tests/test_facts_resolve.py`

**الخطوات:**

1. شغّل التقرير المرجعي للغو واطبع الحقائق module_edge ذات resolution=AMBIGUOUS وعُدّ كم منها مرشّحاته كلها تحت مجلد واحد؛ الرقم المقيس اليوم 1326 من 1336
2. في resolve.py أضف قاعدة للّغات ذات الحزم المجلّدية: إذا كان كل مرشّح تحت مجلد واحد فالهدف هو المجلد
3. سجّل to_path بمسار المجلد و value["target_kind"]="package" و resolution="RESOLVED"
4. أبقِ المرشّحات في السجل كما هي حتى يبقى الدليل مرئيًا للقارئ
5. أبقِ AMBIGUOUS حيث تتوزّع المرشّحات على أكثر من مجلد، فذلك التباس حقيقي
6. لا تغيّر سلوك بايثون: الاستيراد فيها يشير إلى وحدة أي ملف
7. أضف حالة اختبار موجبة لمجلد واحد وحالة سالبة لمجلدين

**معيار القبول:**

```bash
eaos audit /workspace/upstream-src/enola --out /tmp/n11t1 --skip site && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.structure_polyglot('/tmp/n11t1')['imports_resolved_outside_python'];assert v is not None and v>=0.85, v" && eaos audit . --out /tmp/n11t1s --skip site && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.structure_python('/tmp/n11t1s')['python_imports_resolved'];assert v is not None and v>=0.99, v"
```

**التراجع:** git checkout eaos/facts/resolve.py

### N11.T2 — نقطة دخول Go وربط المعالج بالرمز ✅

**لماذا:** تسع نقاط دخول ينتج عنها تدفّق واحد، وهو تدفّق ملف بايثون داخل مستودع Go؛ ثمانٍ بلا معالج قابل للتتبّع، و func main غير معدود نقطة دخول أصلًا.
**يحرّك:** `structure_polyglot.thirdmost_language_depth` من `0.875` إلى `0.875`

**الملفات:**

- `eaos/facts/entrypoints.py`
- `eaos/facts/flows.py`
- `tests/test_facts_entrypoints.py`
- `tests/test_facts_flows.py`

**الخطوات:**

1. أضف كاشف نقطة دخول لثنائيات Go: ملف يعلن package main ويحوي func main هو نقطة دخول surface=cli و framework=go_main و handler=main
2. اطبع من ملخّص flows.json القيمة entry_points_without_traceable_handler وهي 8 اليوم على enola
3. لكل واحدة اطبع اسم المعالج والمسار وابحث عنه في حقائق symbol لتعرف سبب فشل الربط
4. أصلح الربط: طابق المعالج داخل ملفه أولًا بالاسم ثم بالاسم المؤهّل بالمستقبِل لدوال Go ذات المستقبِل
5. أبقِ الخطوة غير المحلولة مسجّلة بسببها، فالتدفّق القصير الظاهر أصدق من تدفّق مبتور صامت
6. أضف حالة اختبار Go فيها cmd/x/main.go و معالج HTTP بمستقبِل

**معيار القبول:**

```bash
eaos audit /workspace/upstream-src/enola --out /tmp/n11t2 --skip site && python3 -c "import json;s=json.load(open('/tmp/n11t2/facts/flows.json'))['summary'];assert s['flows']>=8, s;assert s['entry_points_without_traceable_handler']<=2, s"
```

**التراجع:** git checkout eaos/facts/entrypoints.py eaos/facts/flows.py

### N11.T3 — البحث الذي لم يجد هو جواب، لا عجز ✅

**لماذا:** خمسة أسئلة تُسجَّل undetectable وسببها المكتوب «لا موقع تخزين مؤقت على هذا المسار»؛ هذا جواب قيمته False، وتسجيله عجزًا يبخس الأداة ويضلّل القارئ.
**يحرّك:** `load_model.questions_answered` من `0.2165` إلى `0.7`

**الملفات:**

- `eaos/load_model.py`
- `tests/test_load_model.py`

**الخطوات:**

1. عرّف في load_model.py مجموعة DETECTOR_LANGUAGES لكل سؤال: اللغات التي يملك كاشفه مفرداتها
2. اجعل الجواب answered بقيمة False حين يتحقق شرطان معًا: التدفّق تُتبّع فعلًا، ولغة كل ملف في المسار داخل DETECTOR_LANGUAGES لذلك السؤال
3. اجعل الدليل في هذه الحالة معرّفات حقائق التدفّق التي فُحصت، فالجواب السالب يحتاج دليلًا على أن البحث جرى
4. أبقِ undetectable حين يتعذّر تتبّع التدفّق أو حين تكون لغة المسار خارج DETECTOR_LANGUAGES، مع السبب مكتوبًا
5. أضف سطر limitation يقول إن الجواب السالب يعني غياب الدليل ضمن مفردات الكاشف لا غياب السلوك
6. أضف اختبارًا يثبت أن مسارًا بلغة غير مدعومة يبقى undetectable وأن مسارًا مدعومًا متتبّعًا يصير answered

**معيار القبول:**

```bash
python -m unittest tests.test_load_model -q && eaos audit . --out /tmp/n11t3 --skip site && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.load_model('/tmp/n11t3')['questions_answered'];assert v is not None and v>=0.7, v"
```

**التراجع:** git checkout eaos/load_model.py

### N11.T4 — نفس الأسئلة على Go بعد أن صار له تدفّق ✅

**لماذا:** لا يمكن الإجابة عن سؤال مسار قبل وجود مسار؛ بعد N11.T2 صار للغو تدفّقات فتلزمه مفردات الكواشف.
**يحرّك:** `load_model.questions_answered` من `0.0192` إلى `0.5`
**يعتمد على:** N11.T2, N11.T3

**الملفات:**

- `eaos/facts/runtime.py`
- `eaos/facts/domain.py`
- `eaos/load_model.py`
- `tests/test_facts_runtime.py`

**الخطوات:**

1. أضف مفردات Go لكل كاشف: database/sql و gorm.io/gorm و jmoiron/sqlx لاستدعاء البيانات
2. أضف sync.Mutex و sync.RWMutex و المتغيّرات المعلنة على مستوى الحزمة والقابلة للتعديل للحالة المشتركة
3. أضف context.WithTimeout و context.WithDeadline و http.Client ذي Timeout لحماية الاستدعاء الخارجي
4. أضف golang.org/x/time/rate و ulule/limiter لتحديد المعدّل
5. أضف patrickmn/go-cache و hashicorp/golang-lru و sync.Map للتخزين المؤقت
6. أضف go إلى DETECTOR_LANGUAGES لكل سؤال أضفت مفرداته وحدها
7. أضف لكل كاشف جديد حالة Go موجبة وحالة سالبة تحت tests/fixtures/benchmarks/load

**معيار القبول:**

```bash
eaos audit /workspace/upstream-src/enola --out /tmp/n11t4 --skip site && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.load_model('/tmp/n11t4')['questions_answered'];assert v is not None and v>=0.5, v"
```

**التراجع:** git checkout eaos/facts/runtime.py eaos/facts/domain.py eaos/load_model.py

### N11.T5 — أمر قبول قابل للّصق في كل مرحلة تحويل ✅

**لماذا:** N7.T1 كتب argv والمقياس يقرأ acceptance.command، فهبط المؤشر من 0.9365 إلى صفر بينما نجح اختباره.
**يحرّك:** `transformation_plan.stages_with_runnable_acceptance` من `0.0` إلى `0.9`

**الملفات:**

- `eaos/transform_plan.py`
- `tests/test_transformation_handoff.py`

**الخطوات:**

1. أضف مفتاح command إلى سجل قبول المرحلة يحمل نفس argv مجموعًا بمسافات وجاهزًا للّصق في صدفة
2. أبقِ argv كما هو فهو الشكل الذي يستهلكه المنفّذ الآلي
3. أضف اختبارًا يقرأ transform-plan.json من تقرير حقيقي ويثبت أن كل مرحلة تحمل command غير فارغ

**معيار القبول:**

```bash
python -m unittest tests.test_transformation_handoff -q && eaos audit . --out /tmp/n11t5 --skip site && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.transformation_plan('/tmp/n11t5')['stages_with_runnable_acceptance'];assert v is not None and v>=0.9, v"
```

**التراجع:** git checkout eaos/transform_plan.py

### N11.T7 — منع ابتلاع فشل المحرّك بصمت ✅

**لماذا:** دمج حواف CodeGraph ملفوف بـ except Exception: pass وفوقه شرط ميت or True، فأي فشل هنا غير مرئي في أي تقرير.
**يحرّك:** `layered_engineering.tests_pass` من `1.0` إلى `1.0`

**الملفات:**

- `eaos/facts/external.py`
- `tests/test_engine_contracts.py`

**الخطوات:**

1. احذف except Exception: pass حول دمج حواف CodeGraph وسجّل السبب في summary تحت مفتاح edge_merge
2. احذف الشرط الميت if Path(workdir + "/engines").exists() or True
3. إذا أعاد محرّك صفر حقيقة فسجّل سببًا مقيسًا في summary بدل تركه صامتًا
4. أضف اختبارًا يثبت أن لا معالج استثناء في الملف جسمه pass وحده

**معيار القبول:**

```bash
python -m unittest tests.test_engine_contracts -q && python3 -c "import ast;t=ast.parse(open('eaos/facts/external.py').read());bad=[n.lineno for n in ast.walk(t) if isinstance(n,ast.ExceptHandler) and len(n.body)==1 and isinstance(n.body[0],ast.Pass)];assert not bad, bad"
```

**التراجع:** git checkout eaos/facts/external.py

### N11.T6 — سؤال CodeGraph عن ملف لا عن مجلد ✅

**لماذا:** الأداة ترجع صفرًا عن مجلد وحواف حقيقية عن ملف، وتفهرس 66477 حافة نستخرج منها صفرًا؛ و analyze_complexity مرفوضة اليوم برسالة Missing uri parameter.
**يحرّك:** `load_model.questions_answered` من `0.5` إلى `0.6`
**يعتمد على:** N11.T3, N11.T7

**الملفات:**

- `eaos/engines/codegraph.py`
- `eaos/facts/external.py`
- `tests/test_engine_contracts.py`

**الخطوات:**

1. مرّر uri=file://<مسار الملف المطلق> إلى codegraph_get_dependency_graph و codegraph_analyze_complexity لكل ملف مصدري في الجرد
2. اقرأ الحمولة كما هي: nodes فيها type=codefile ومعها path حقيقي، و type=module ومعها name فقط و path فارغ، و edges فيها from و to و type=import
3. حوّل كل عنصر functions من analyze_complexity إلى حقيقة symbol_metric_external تحمل complexity و grade و lines_of_code ومسار الملف
4. احذف probe_paths المكتوبة يدويًا لملفات enola واستبدلها بمسارات نقاط الدخول المسجّلة في facts/entrypoints.json
5. في find_hot_paths استبعد المسارات التي تطابق NOT_THE_READER_S_CODE فالنتيجة الأولى اليوم داخل testdata
6. تأكد أن complexity_class يصير answered لأن perf_facts صارت تحمل مسارات ملفات المسار

**معيار القبول:**

```bash
eaos audit . --out /tmp/n11t6 --skip site --engines codegraph enola jscpd reforge && python3 -c "import json,collections;d=json.load(open('/tmp/n11t6/facts/external.json'));k=collections.Counter(f['kind'] for f in d['facts']);assert k.get('symbol_metric_external',0)>0, k" && python3 -c "import sys;sys.path.insert(0,'.');from eaos import capability;v=capability.load_model('/tmp/n11t6')['questions_answered'];assert v is not None and v>=0.6, v"
```

**التراجع:** git checkout eaos/engines/codegraph.py eaos/facts/external.py

### N11.T8 — بدائل معمارية تخص المكوّن لا قالبًا مكرّرًا ✅

**لماذا:** تسعة قرارات على تسعة مكوّنات تحمل نفس الخيارين ونفس جملة المقايضة ونفس خطوات الهجرة، و«لا تفعل شيئًا» ليس بديلًا هندسيًا.
**يحرّك:** `target_architecture.decisions_with_alternatives` من `1.0` إلى `1.0`

**الملفات:**

- `eaos/target_architecture.py`
- `tests/test_target_architecture.py`

**الخطوات:**

1. اشتق الخيارات من نوع الدليل: الدورة تُقابَل بكسر الاعتماد أو بإدخال واجهة، وعائق الحمل يُقابَل بتحديد المعدّل أو بالتخزين المؤقت أو بترقيم النتائج، ومخالفة السياسة تُقابَل بنقل الملف أو بتعديل السياسة
2. اكتب المقايضة بأرقام المكوّن المقيسة: عدد الادعاءات الحيّة وعدد المخالفات وعدد عوائق الحمل
3. اجعل خطوات الهجرة تسمّي ملفات المكوّن الفعلية المأخوذة من الدليل
4. احصر قائمة evidence في خمسة معرّفات مع عدّاد للباقي حتى يبقى القرار مقروءًا
5. أضف اختبارًا يثبت أن مجموعات الخيارات ليست كلها متطابقة

**معيار القبول:**

```bash
python -m unittest tests.test_target_architecture -q && eaos audit . --out /tmp/n11t8 --skip site && python3 -c "import json;d=json.load(open('/tmp/n11t8/target-architecture.json'));o=[tuple(x['options']) for x in d['decisions']];assert len(set(o))>=2, len(set(o));assert all(len(x['evidence'])<=6 for x in d['decisions'])"
```

**التراجع:** git checkout eaos/target_architecture.py

### N11.T9 — المحرّكات تعمل وقت الحكم والعلامة لا تُخفَض ✅

**لماذا:** القياس يجري بلا engines فالمحرّكات مطفأة وقت الحكم؛ والبوابة تقارن بالملف الذي تكتبه كل إعادة قياس فوق نفسها، فمرّ هبوط 0.9788 إلى 0.6667 بلا إنذار.
**يعتمد على:** N11.T5

**الملفات:**

- `tools/capability_score.py`
- `tests/gate/capability_no_regression.sh`
- `docs/capability-high-water.json`

**الخطوات:**

1. أضف --engines codegraph enola jscpd reforge إلى كل أمر audit داخل بوابة عدم التراجع
2. اجعل tools/capability_score.py يرفض تقريرًا حالة مرحلة engines فيه unavailable بسبب أن المحرّكات لم تُطلب
3. أنشئ docs/capability-high-water.json يحمل أعلى درجة بلغها كل مجال مع الالتزام الذي بلغها
4. اجعل الكتابة ترفع العلامة عند التحسّن ولا تخفضها أبدًا
5. اجعل البوابة تقارن بالعلامة المثبّتة لا بـ docs/capability-score.json

**معيار القبول:**

```bash
bash tests/gate/capability_no_regression.sh && python3 -c "import json;h=json.load(open('docs/capability-high-water.json'));d=h['domains'];assert d['transformation_plan']>=0.9788, d;assert d['layered_engineering']>=1.0, d"
```

**التراجع:** git checkout tools/capability_score.py tests/gate/capability_no_regression.sh && rm -f docs/capability-high-water.json

## N12 — من الملاحظة إلى الوصفة

**الهدف:** الأداة اليوم تلاحظ وتسأل ولا تصف علاجًا. هذا المعلم يجعلها تصف العلاج حيث يملك المشروع متطلبًا موثّقًا فعلًا، ويعطي كل نتيجة محرّك نمط علاج وأثرًا مقيسًا بدل جملة واحدة مكرّرة.

**المشكلة المقيسة:** قِيس على /tmp/w_self و /tmp/w_go بتاريخ 2026-09-23: 190 بطاقة من 190 نوعها investigate وصفر repair، وكل أمر قبولها «مراجعة بشرية». و96 ادعاءً من 240 على مستودعنا (214 من 787 على enola) نوعها engine_cluster، وكلها تتشارك جملة أثر واحدة حرفيًا، وكلها تسقط إلى النمط generic لأن classify() في eaos/remediation_patterns.py لا تعرف الاستعلام engine_cluster_present.

### N12.T1 — مخالفة السياسة تحمل معرّف الحافة التي أثبتتها ✅

**لماذا:** الإصلاح يحتاج مرجعين متمايزين: المتطلب والدليل. حقيقة المخالفة تحمل سبب القاعدة ولا تحمل معرّف حقيقة الاستيراد.

**الملفات:**

- `eaos/policy.py`
- `tests/test_policy.py`

**الخطوات:**

1. في eaos/policy.py الدالة violations تمرّ على edge من sets["resolve"]["facts"]؛ أضف edge_fact_id بقيمة edge["id"] إلى القاموس المضاف في found
2. مرّر edge_fact_id إلى قيمة حقيقة policy_violation في الدالة run بجانب to_path و from_layer
3. أضف اختبارًا يشغّل الكاشف على tests/fixtures/benchmarks/policy-violation ويثبت أن edge_fact_id موجود وأنه معرّف حقيقة module_edge حقيقية في facts/resolve.json

**معيار القبول:**

```bash
eaos audit tests/fixtures/benchmarks/policy-violation --out /tmp/n12t1 --skip site && python3 -c "import json;p=json.load(open('/tmp/n12t1/facts/policy.json'));r={f['id'] for f in json.load(open('/tmp/n12t1/facts/resolve.json'))['facts']};v=[f for f in p['facts'] if f['kind']=='policy_violation'];assert v, 'the fixture must produce a violation';assert all(f['value'].get('edge_fact_id') in r for f in v), [f['value'].get('edge_fact_id') for f in v]"
```

**التراجع:** git checkout eaos/policy.py

### N12.T2 — مخالفة السياسة المعلنة تصير إصلاحًا بأمر قبول قابل للتشغيل ✅

**لماذا:** المشروع كتب eaos.policy.json بيده، فالمتطلب موثّق ومؤلَّف من صاحبه. هذه هي الحالة الوحيدة التي يملك فيها المحرّك متطلبًا دون أن يخترعه.
**يعتمد على:** N12.T1

**الملفات:**

- `eaos/claims.py`
- `eaos/policy_assessment.py`
- `eaos/acceptance.py`
- `tests/test_decisions.py`

**الخطوات:**

1. اقرأ eaos/decision_review.py: هو المسار الوحيد الذي يكتب assessment اليوم، وشروطه هي المرجع الملزم لشكل ما ستبنيه
2. اقرأ eaos/decisions.py الدالة decide: repair تتطلب confidence=CONFIRMED مع violated_invariant و requirement_refs و evidence_refs، والجاهزية تتطلب checks و reviewed_by و before و after
3. أنشئ eaos/policy_assessment.py يبني assessment لادعاء مخالفة سياسة من حقائقه وحدها
4. violated_invariant: نص القاعدة المعلنة مع سببها المأخوذ من value["reason"]
5. requirement_refs: معرّف حقيقة policy_violation، فهي التي تحمل القاعدة التي أعلنها المشروع
6. evidence_refs: معرّف edge_fact_id، فهو حافة الاستيراد التي خالفتها
7. reviewed_by: مسار ملف السياسة مع بصمته، لأن من كتب الملف هو من أقرّ المتطلب؛ لا تخترع اسم مراجع
8. before و after: وصف الحافة القائمة، ووصف غيابها من الرسم المحلول
9. proposed_change: خذه من نمط policy_violation في eaos/remediation_patterns.py ولا تكتب نصًا ثانيًا
10. checks: فحص واحد kind=command يعيد تشغيل فحص السياسة ويتوقع خروجًا صفريًا؛ اقرأ check_errors في eaos/decisions.py فهو يرفض argv فارغًا أو cwd غير النقطة أو expected_exit غير عدد، ويرفض أن يبدأ argv بـ dossier أو facts أو tasks
11. source_revision في الفحص يساوي eaos.acceptance.fingerprint للمستودع المفحوص، وإلا رفضه العقد
12. في eaos/claims.py أرفق هذا assessment مع ادعاء السياسة عند بنائه
13. لا تلمس decide ولا check_errors: العقد هو الحَكَم ولا يُليَّن ليقبل ما نبنيه

**معيار القبول:**

```bash
eaos audit tests/fixtures/benchmarks/policy-violation --out /tmp/n12t2 --skip site && python3 -c "import json;p=json.load(open('/tmp/n12t2/plan.json'));c=[t for t in p['tasks'] if (t.get('render') or {}).get('key')=='policy'];assert c, 'no policy card';t=c[0];assert t['kind']=='remediate', t['kind'];assert t['decision']['kind']=='repair', t['decision'];assert t['decision']['readiness']=='ready', t['decision'];a=t['acceptance'][0]['command'];assert 'human review' not in a, a"
```

**التراجع:** git checkout eaos/claims.py && rm -f eaos/policy_assessment.py

### N12.T3 — نتيجة المحرّك تُصنَّف إلى نمط علاج حقيقي ✅

**لماذا:** classify() لا تعرف engine_cluster_present، فتسقط 96 بطاقة من 240 إلى النمط generic الذي لا يحمل علاجًا ولا كلفة تقاعس.

**الملفات:**

- `eaos/remediation_patterns.py`
- `tests/test_remediation_patterns.py`

**الخطوات:**

1. الأنواع المقيسة أربعة فقط: complexity و literal_duplication و coupling و dead_code، وهي في claim["render"]["params"]["kind"]
2. في classify() أضف فرعًا للاستعلام engine_cluster_present يقرأ هذا النوع ويعيد: complexity إلى hotspot، و coupling إلى hidden_coupling، و literal_duplication إلى canonicalize
3. أضف نمط dead_code جديدًا في PATTERNS بخطوة تغيير وخيارين وكلفة تقاعس في cost_of_inaction، فالحذف قرار لا ملاحظة
4. أي نوع محرّك غير معروف يبقى generic، وسجّل في النمط سبب السقوط حتى لا يكون صمتًا
5. أضف اختبارًا لكل نوع من الأربعة يثبت النمط المُختار، واختبارًا يثبت أن نوعًا مجهولًا يبقى generic

**معيار القبول:**

```bash
eaos audit . --out /tmp/n12t3 --skip site --engines codegraph enola jscpd reforge && python3 -c "import json,collections;d=json.load(open('/tmp/n12t3/dossier.json'));p=json.load(open('/tmp/n12t3/plan.json'));byid={c['id']:c for c in d['claims']};ec=[t for t in p['tasks'] if (byid.get(t['claim_id'],{}).get('render') or {}).get('key')=='engine_cluster'];assert ec, 'no engine cluster card';bad=[t['id'] for t in ec if t.get('pattern')=='generic'];assert not bad, bad;gen=[t for t in p['tasks'] if t.get('pattern')=='generic'];assert len(gen)/len(p['tasks'])<=0.1, (len(gen),len(p['tasks']))"
```

**التراجع:** git checkout eaos/remediation_patterns.py

### N12.T4 — أثر نتيجة المحرّك يذكر القياس الذي وجده ✅

**لماذا:** ستة وتسعون ادعاءً تتشارك جملة أثر واحدة حرفيًا؛ هذا يخالف قاعدة المنتَج نفسه أن كل ادعاء يذكر أثره، ويجعل أضعف ما نملك يتصدّر موجز القرار.

**الملفات:**

- `eaos/claims.py`
- `eaos/compose/labels.py`
- `tests/test_claims.py`

**الخطوات:**

1. حقائق المحرّك تحمل measurements قائمةَ قواميس فيها name و value و threshold؛ اطبع واحدة من facts/external.json قبل أن تكتب أي ربط
2. اجعل جملة الأثر تختلف بنوع النتيجة وتذكر القياس: التعقيد يذكر القيمة والعتبة، والتكرار الحرفي يذكر عدد المواضع، والاقتران يذكر عدد الأطراف، والكود الميت يذكر الرمز
3. أضف مفاتيح الأثر الجديدة إلى IMPACTS بالعربية والإنجليزية معًا؛ اختبار التكافؤ يفشل إن وُجد مفتاح في لغة دون الأخرى
4. حين تغيب المقاييس أبقِ الجملة العامة واذكر أن المحرّك لم يُبلّغ قياسًا، فالصمت المعلن أصدق من رقم مخترع

**معيار القبول:**

```bash
eaos audit . --out /tmp/n12t4 --skip site --engines codegraph enola jscpd reforge && python3 -c "import json,re;d=json.load(open('/tmp/n12t4/dossier.json'));ec=[c for c in d['claims'] if (c.get('render') or {}).get('key')=='engine_cluster'];assert ec, 'no engine cluster claim';s={(c.get('impact') or {}).get('scenario') for c in ec};assert len(s)>=3, len(s);assert sum(1 for x in s if re.search(r'[0-9]', x or ''))>=2, s" && python -m unittest discover -s tests -p "test_report_parity.py" -q
```

**التراجع:** git checkout eaos/claims.py eaos/compose/labels.py

### N12.T5 — الوصفة تُقاس على المستودعين لا على العيّنة ✅

**لماذا:** كل مهمة سابقة في هذا المشروع نجحت على عيّنة وفشلت على مستودع حقيقي؛ هذه المهمة تمنع تكرار ذلك.
**يعتمد على:** N12.T2, N12.T3, N12.T4

**الملفات:**

- `docs/capability-score.json`
- `docs/CAPABILITY-SCORE.md`
- `docs/capability-high-water.json`

**الخطوات:**

1. أعد إنتاج التقريرين بالمحرّكات: eaos audit . و eaos audit /workspace/upstream-src/enola
2. اطبع نسبة البطاقات من نوع remediate ونسبة النمط generic على كل تقرير وسجّلها في ملاحظة المهمة
3. شغّل python tools/capability_score.py /tmp/n12self /tmp/n12go --write
4. شغّل bash tests/gate/capability_no_regression.sh وتأكد أن لا مجال هبط

**معيار القبول:**

```bash
eaos audit . --out /tmp/n12self --skip site --engines codegraph enola jscpd reforge && eaos audit /workspace/upstream-src/enola --out /tmp/n12go --skip site --engines codegraph enola jscpd reforge && python tools/capability_score.py /tmp/n12self /tmp/n12go --write && bash tests/gate/capability_no_regression.sh
```

**التراجع:** git checkout docs/capability-score.json docs/CAPABILITY-SCORE.md docs/capability-high-water.json
