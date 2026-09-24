# سجل تنفيذ EAOS — تشغيل 2026-09-24

## البيئة وخط البداية

- البداية: `HEAD = 42dc3c76ef2526b4d05a32489a80d57e5867fe28`
- النسبة المسجلة (مجمّدة على JSON): 34.0%
- قفل القبول: صالح (`tools/acceptance.py lock --check` نجح)
- `tools/north_star.py --score`: 34.0%
- الأدلة الأولية: `/workspace/eaos-execution-evidence/run-20260924-161920/`
- المسارات الفعلية للقياس: `/tmp/eaos-corpus` للعينة، `/workspace/eaos-execution-evidence/run-20260924-161920/measures` للتقارير (`EAOS_MEASURE`).

## عمل غير ملتزم على الشجرة عند البداية

| ملف | حالة قبل | الفحص الحالي |
|---|---|---|
| `eaos/correlate.py` | عمل NS4.T2: مرشّح `_registry_symbols` ينقّي حقائق dead_code حسب قوائم `MODULES`، والقواميس، و `getattr(obj, "name")`، و entry points | يُسقط 16 من 23 مرشّحًا في self_truth (5 ميتة فعلًا، 18 زائفة). |
| `eaos/facts/run.py` | استدعاء `filter_dead_code_references` في `collect_external` | متصل قبل كتابة الحقائق. |
| `eaos.policy.json` | نقل `eaos/correlate.py` بين الطبقات | متعارض مع بنية الطبقات المرسومة. |
| `docs/invariants.json` | تحديث `extracted_at_commit` بدون تحديث المحتوى | تطابق بعد إعادة الاستخراج. |
| `tests/test_correlate_dead_code.py` | اختبار جديد لـ filter | جديد، يُرفض بدون عزل تام. |

## NS4.T2: حجب دون تنفيذ

**القرار:** لم تُعلَّم done ولم تُحفظ.

التشغيل على البيانات الحقيقية يُنزّل:
- S1: 0.832 → 0.744 (`FleetManageWeb 83/103 → 75/95 · finance-os-a0192b7b 151/201 → 61/111`)
- U5: 0.562 → 0.482 (`FleetManageWeb 270/408 → 225/408 · finance-os-a0192b7b 156/568 → 130/568`)

الخطة تمنع نزول أي مؤشر. الخسارة تُفسَّر جزئيًا بإسقاط `filter_dead_code_references` كل المرشّحين المشار إليهم في السجل، فيختفي عدد من الادعاءات downstream (مثل duplicate_code وكل ادعاءات dead_code غير المرتبطة). الإصلاح المقترح لا يبدأ في هذه الجولة:

1. الإبقاء على الحقيقة `engine_finding` في الإخراج،
2. تعليمها بـ `value.referenced_by_registry = True`،
3. تسليم منع توليد `claim` بدل حذفها من القرص،
4. تحديث S2 في `tools/north_star_measure.py:self_truth` ليعدّ المرشّحين في الحالتين.

الإبقاء في الشجرة: لم يُحذف ولا يُرفع ضمن هذه الجولة.

## NS3.T2 — مُنفَّذة ومُحفوظة

**الالتزام:** `bcc765a` "NS3.T2 done: supabase_access detector wired into the entry-points loop".

التغييرات:
- `eaos/facts/frameworks/__init__.py`: `supabase_access` يُسجّل نفسه في `MODULES` مع `FACT_KIND = 'data_access'`، فيدخل حلقة entry_points.
- `eaos/facts/frameworks/supabase_access.py`: `_supabase_prefix` يتوقف عن اعتبار `\n` حدًّا للعبارة؛ سلسلة `supabase\n  .from(...)` تُلتقط كسلسلة Supabase واحدة.
- `eaos/facts/entrypoints.py`: يفصل بين المخرجين حسب `fact_kind(module)`؛ حقائق data_access تحمل `client/target/operation/category` بدلًا من `surface/route/handler/framework`.
- `eaos/dossier.py`, `eaos/ask.py`, `eaos/impact.py`, `eaos/runtime/pipeline.py`: يقرأون حقائق entrypoints بتصفية `kind == 'entry_point'` قبل الوصول إلى surface/route/handler/framework/resolution.
- `tests/fixtures/golden/entrypoints.json`: مُجدَّد بعد الاتفاق مع المخرج الجديد (إذن المراجع).
- `tests/test_supabase_access.py`: اختباران جديدان (عبارة سابقة محاطة بـ `;`، كتلة محاطة بـ `{}`).
- `tests/test_invariants.py`: اختبار إضافي يُلزم وثيقة الإطار.
- `docs/invariants.json`: الثابتان 8e748a64ef و 38206a42b2 مُسجَّلان في enforced_by.
- `docs/north-star.json`: NS3.T2.done = true, status = "done".
- `docs/NORTH-STAR.md`: أُعيد توليده.

القبول:
```
python tools/acceptance.py facts data_access finance-os-a0192b7b --min 20
→ PASS facts data_access in finance-os-a0192b7b: 24
python tools/north_star.py measure --only U3 → 1.0
python tools/acceptance.py lock --check → PASS acceptance tests match their lock
python tools/validate.py → PASS
python tools/invariants.py → 71 invariants, 0 unenforced
bash tests/gate/self_audit.sh → ok
python -m unittest discover -s tests -q → Ran 1022 tests in ~280s, FAILED (failures=0 after fixes)
```

## الجدول النهائي

| المؤشر | قبل | بعد NS3.T2 | السبب |
|---|---|---|---|
| R1 (تدقيق بلا فشل) | 1.0 | 1.0 | الإصلاحات في `dossier/ask/impact/runtime/pipeline` أنهت `KeyError` الناتج عن حقائق mixed-kind. |
| U3 | 1.0 | 1.0 | غير متأثر. |
| U4 | 0.0 | 0.0 | يحتاج NS3.T4 (مرحلة لاحقة). |
| U5 | 0.562 | 0.482 | هبوط من عمل NS4.T2 غير المحفوظ. |
| S1 | 0.832 | 0.744 | هبوط من عمل NS4.T2 غير المحفوظ. |
| S2 | 0.217 | 0.714 | تحسّن من عمل NS4.T2 غير المحفوظ (لا يُحتسب في الالتزام). |

## المتبقي

- 62 مهمة مفتوحة في 41 مؤشرًا.
- NS3.T4 (يعتمد على NS3.T2 المكتملة + NS3.T3): توليد `features.json`.
- NS3.T5 (يعتمد على NS3.T1 + NS3.T2): ترقية `load_model.py` للوصول المؤمَّن والـ rate_limit وما يتصل بـ data_access_calls (الآن 24 حقيقة متاحة).
- NS4.T2: يتطلّب تنفيذ الإصلاح المقترح أعلاه (لا حذف، بل تعليم).
- NS5.T1, NS5.T2: رمز ميت قابل للوصول — مع وجود `filter_dead_code_references` فإن الإكمال يصبح ممكنًا دون تعارض.
- الخط الكامل R6–R8 (المهام التنفيذية، التصليب، الإثبات المستقل).

## خدمات لم تزل تعمل

لا توجد خدمات systemd بدأت في هذه الجلسة. القياسات كلها خدمات عابرة متزامنة.
