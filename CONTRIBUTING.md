# المساهمة

## قبل أي التزام

```bash
python -m unittest discover -s tests -q \
  && python tools/validate.py && python tools/invariants.py \
  && python tools/render_capability_plan.py --check \
  && bash tests/gate/self_audit.sh
```

ولأي تغيير يمس ما يقيسه المنتج: `bash tests/gate/capability_no_regression.sh`. البوابة تفشل إن هبط أي مجال عن أعلى ما بلغه.

## قواعد الكود

1. **كل وحدة `.py` جديدة تُعلن في `eaos.policy.json`** في طبقتها، وإلا فشلت بوابة السياسة.
2. **كل جملة docstring تدّعي ثابتًا تُربط باختبار** (`python tools/invariants.py --list`). إن وعد الـdocstring بسلوك لا يفعله الكود، فأصلح الكود لا الجملة.
3. **كل نص يظهر للقارئ يُضاف للغتين معًا** في `eaos/compose/labels.py`، ويفشل `test_report_parity.py` إن وُجد مفتاح في لغة دون الأخرى.
4. **كل وثيقة تقرير جديدة تُعلن في `eaos/compose/artifacts.py`** بمالك وغرض وميزانية أسطر، وتوأم JSON أو سبب غيابه.
5. **اطبع الحقيقة قبل أن تكتب join:** المنتِج والقارئ يتفقان على اسم ثم يختلفان عليه بصمت. اختبر ما يقرؤه القارئ، لا ما كتبه المنتِج فقط.

## قواعد المعرفة الهندسية

1. اقرأ `core/EXTENSION-PROTOCOL.md` وحدد المشكلة أو failure mode الجديد.
2. أضف المصدر بإصداره وحدود قراءته إلى `sources.json`. لا تنسب synthesis إلى فيديو.
3. أعد استخدام control ID إن كان نفس invariant، وافصل applicability عن severity.
4. عدّل `controls.json` أو `core/` أو `schemas/`، ثم `python tools/render.py`. الملفات في `modules/` و`eaos/data/` و`MASTER-MANUAL.md` مولَّدة: لا تحررها يدويًا.

الـCLI مستقل عن مزودي النماذج. إضافة adapter ليست مبررًا لتغيير سياسة «الدليل أولًا» أو لإرسال كود المستخدم تلقائيًا. أي parser دلالي يستخرج حواف مرشحة مع دليلها وثقتها، ولا يرفعها إلى CONFIRMED لمجرد تطابق regex.
