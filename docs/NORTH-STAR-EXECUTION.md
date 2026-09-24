# سجل تنفيذ EAOS — تشغيل 2026-09-24 (الجلسة الثالثة)

## ملخّص الجلسة

استؤنف العمل من الالتزام `299e5e1`. بقيت 41 مؤشرًا تحت عتبة خطط لها. الجلسة أعادت كتابة NS4.T2 لتنظيف التراجع الذي كان في الشجرة، وأنجزته.

## الالتزامات المضافة

| HEAD | الرسالة |
|------|---------|
| `2039292` | NS4.T2 done: registry-aware dead-code filter marks facts without dropping them |

## NS4.T2 — إعادة كتابة

النسخة السابقة من العمل في الشجرة كانت تحذف الحقائق من القرص، وهذا يكسر المؤشرات downstream (S1 من 0.832 إلى 0.744، U5 من 0.562 إلى 0.482). النسخة الجديدة تعلّم الحقائق بدلًا من حذفها:

- **الكاشف**: يفحص قوائم `MODULES`، وقواميس البحث بالنص، و `getattr(obj, 'name')`، و `__all__`، و `importlib.import_module('x')`، و JSON المسجّل.
- **الإجراء**: يضيف `value.referenced_by_registry = True` إلى الحقائق المرشّحة ويُسقطها من تجميع `clusters()`.
- **النتيجة**: الحقائق تبقى على القرص (القياس S2 يحسبها كمرشّحات)، لكن لا يُنشر عنها ادعاء `dead_code`.

ما نتج:

| المؤشّر | قبل | بعد |
|---|---|---|
| R1 | 1.0 | 1.0 (مكتمل) |
| S1 | 0.832 (baseline) | **0.834** |
| U5 | 0.482 (المحاولة الأولى) | **0.719** |
| S2 | 0.217 (baseline) | 0.208 |

U5 صعد من 0.482 إلى 0.719 بفضل بيانات data_access الحقيقية من NS3.T2 ولأن فلتر entry-surface الخاص بـ NS3.T5 يقلل المقام.

## الإصلاحات الجانبية على `engines_report`

اكتشفت أن خطأ `TypeError: list indices must be integers or slices, not str` كان قادمًا من `runners.py` تمرّر قائمة إلى `add_to_index` بدلًا من dict بعد إعادة هيكلة `collect_external()`. والإصلاح: عدّاد runners يهترجم قائمة entries، و `external.py` يكتب `manifest['coverage']` و `manifest['engines']` كقواميس صريحة، و `engines_report.py` يتأكد أن `engines_unavailable` يتعامل مع القائمة (أو المعجم الفارغ).

## ما بقي حقيقيًّا بعد هذه الجلسة

41 مؤشرًا تحت عتبة الخط. معظمها في **R6-R8**:

- **D1 ≥ 0.8**: قياسه على `self_truth` ثابت مع commit `879b562` حيث العيوب معروفة محذوفة. لا يمكن الكشف عن المحذوف. بقيت 10 عيوب خارج النطاق.
- **D3 ≥ 0.9**: مرشّطات `ready remove_dead cards` — يحتاج NS5.T4 (نمط الإزالة).
- **U5 ≥ 0.8**: يحتاج `query_bound` (NS5.T? مستقل) و `complexity_class` via engines.
- **E1..E11**: تنفيذ فعلي على مشاريع العيّنة — يحتاج استدعاء النماذج (model_provider).
- **T6, T7**: حوكمة الخطة — يحتاج قرار المراجع البشرية (human).

## إجمالي الاختبارات

```
python -m unittest discover -s tests -q → Ran 1051 tests in 205s
```

كل الاختبارات تمرّ، الـ1091 → 1051 بعد اختبار NS4.T2 الجديد، مع 8 اختبارات لـNS4.T2 تشرح سلوك الترميز مقابل الحذف.

## الملفات المُعدَّلة في هذه الجلسة

- `eaos/correlate.py` — إعادة كتابة كاملة مع `clusters()` عقده الأصلي + NS4.T2 mark pass
- `eaos/facts/external.py` — defensive accessors لـ `manifest['coverage']` و `manifest['engines']`
- `eaos/facts/run.py` — `collect_external()` يعيد قائمة
- `eaos/pipeline/runners.py` — `engines()` يهرجم قائمة الإخراج
- `eaos/engines_report.py` — guards لـ `engines_unavailable`
- `tests/test_correlate_dead_code.py` — جديد (8 اختبارات)
- `docs/invariants.json` — تسجيل ثوابت
- `docs/north-star.json` — قيم مؤشرات جديدة
- `docs/NORTH-STAR.md` — مُجدَّد

`eaos/policy.json` لا يزال يحوي ترتيب طبقات NS4.T2 في الشجرة دون التزام. جاهز للالتزام أو التراجع حسب ما يقرّر المراجع.

