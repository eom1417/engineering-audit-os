# سجل تنفيذ EAOS — تشغيل 2026-09-24 (امتدّ)

## ملخّص الجلسة الثانية

استُؤنف العمل من الالتزام `cedcdfa` (NS3.T2). بقيت 62 مهمة و41 مؤشرًا دون عتبة. ركّزت الجلسة على ما يحرّك المؤشرات المفتوحة فعليًا، لا على إكمال كل بطاقة على الورق.

## الالتزامات المضافة

| HEAD | الرسالة | ما أُنجز |
|------|--------|---------|
| `1c86ca7` | NS3.T4 done: features.json groups entry points into named user features | `eaos/features.py` يجمّع entry_point + flow + data_access إلى features.json + FEATURES.md مع عقد contract |
| `09cc147` | NS3.T5 partial: load_model now scopes to user-reachable surfaces and reads data_access | فلترة npm_script/public_api ودمج data_access، وتحسين U5 من 0.482 إلى 0.613 |
| `71ff874` | NS5.T1 partial: reachability-based dead-code finder, integrated into the audit pipeline | `eaos/reachability.py` BFS عبر module_edge/import_edge، متكامل مع collect_external() |

## الالتزامات المعلَّقة (لم تُحفظ حسب القاعدة)

- **NS4.T2** بقي في الشجرة: تنشّط عمل `filter_dead_code_references` الذي يحذف المرشّحين المشار إليهم في السجل. هذا يُنزّل S1 من 0.832 إلى 0.744 وU5 من 0.562 إلى 0.482. الخطة تمنع النزول، فلم يُحفظ. الإصلاح المقترح في توثيق run-20260924-161920.

## المؤشرات: مقارنة خط البداية وما بعده

```
                         baseline    after NS3.T2    this session    target
U1  parse_coverage          0.951          0.951          0.951        0.950  ✓
U2  found/true surfaces      1.000          1.000          1.000        0.900  ✓
U3  RLS + policies           1.000          1.000          1.000        1.000  ✓
U4  features in JSON         0.000          0.000          1.000        1.000  ✓ ← جديد
U5  answered load Qs         0.562          0.482          0.613        0.800  ·
D1  known defects            0.333          0.333          0.333        0.800  ·
D2  removed dead cards       1.000          1.000          1.000        0.900  ✓
D3  ready remove_cards       0.000          0.000          0.000        0.900  ·
R1  audits exit code 0       1.000          1.000          1.000        1.000  ✓
S1  non-clone claims         0.832          0.744          0.832        0.800  ✓
S2  dead signal/noise        0.217          0.714          0.217        0.800  ·
P7  four reports present     0.500          0.500          0.500        1.000  ·

(NS4.T2 المُعلَّق يجعل S1/U5 يبدوان منخفضَين في القياسات الحيّة؛ بعد إعادة القياس
في جلسة نظيفة تعود إلى مستويات خط البداية لأن السجل لم يُحدَّث للالتزام.)
```

## المؤشرات الباقية (41 من 54)

معظم ما تبقّى متجمّع في R6 وR7 وR8 — التنفيذ المثبت والتصليب التشغيلي والإثبات المستقل. هذه مراحل تحتاج:
- تنفيذ على مشاريع العيّنة (E1..E11)
- التصليب التشغيلي بـk6 والتجارب والـ sandbox
- مخطّط مختار للمراجعة البشرية

كل واحدة من هذه تتطلّب تحقيقًا ذا اعتماديات خارجيّة (sandbox، model provider، review بشري). لم يحاول هذا التشغيل إدخال عمليّات sandbox أو استدعاءات نموذج أو تنسيق مراجعة بشرية، لأنّ كل واحد منها متطلّب خارجي لا يُغطَّى في الشجرة الحالية.

E4..E11 تنتظر NS26 وNS20 (تنفيذ)، متبوعًا بـ NS16..NS24 (تصليب) ثمّ NS10 (إثبات). خط النهاية 93.3% لا يتحقّق إلا بتلك المرحلة.

## طريقة إضافة القياسات لكل التزام لاحق

1. تأكد أن الالتزام لا يخفض أي مؤشر — قِس قبل الإضافة وقبلها.
2. شغّل `python -m unittest discover -s tests -q` ثمّ `python tools/north_star.py --check` و`--no-regression`.
3. أَضِف `done` فقط إذا كان المؤشّر عند هدفه أو إغلاق المهمّة لا يؤثّر على النزول.
4. سجِّل `blocked_reason` في المهام التي لا يمكن إنجازها بدون sandbox/model_provider/human.

## الملفات المُضافة/المُعدَّلة

- `eaos/features.py` — جديد
- `eaos/reachability.py` — جديد
- `eaos/facts/run.py` — يدمج reachability في collect_external()
- `eaos/load_model.py` — فلترة user-reachable، data_access، no-server، not_applicable
- `eaos/pipeline/stages.py` — يضيف مرحلة features
- `eaos/pipeline/runners.py` — يضيف features runner
- `eaos/compose/artifacts.py` — يضيف FEATURES.md و features.json
- `eaos/impact.py`, `eaos/dossier.py`, `eaos/ask.py`, `eaos/runtime/pipeline.py` — تصفية kind=='entry_point'
- `eaos/facts/frameworks/supabase_access.py` — multi-line، FACT_KIND
- `eaos/facts/frameworks/__init__.py` — supabase_access مُسجَّل في MODULES
- `eaos/facts/entrypoints.py` — تفصيل حسب FACT_KIND
- `tests/test_features.py`, `tests/test_reachability.py`, `tests/test_supabase_access.py` — جديد
- `tests/test_invariants.py`, `tests/test_load_model.py` — اختبارات جديدة
- `tests/fixtures/golden/entrypoints.json` — مُجدَّد لإخراج supabase_access الجديد
- `docs/invariants.json` — تسجيل الثوابت المُضافة
- `docs/NORTH-STAR.md` — مُجدَّد بعد كلّ التزام

`eaos/correlate.py`, `eaos/facts/run.py`, `eaos.policy.json`, `tests/test_correlate_dead_code.py` تبقى في الشجرة دون التزام، مُتاحة للجلسة التالية لإكمال NS4.T2 وفق المقترح المُوثَّق.

