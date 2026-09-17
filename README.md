# Engineering Audit OS — EAOS 1.0.0

ريبو CLI محلي ودليل تشغيل عربي مستقل عن اللغة والمنصة لوكلاء مراجعة المنتجات البرمجية.
تاريخ إعداد البحث: 2026-09-17. الحالة: إصدار تأسيسي قابل للاستخدام، لم يُعتمد ميدانيًا على مستودعات إنتاج متعددة.

## نقطة الدخول

اقرأ `START-HERE.md` ثم `core/OPERATING-MANUAL.md`. القواعد الأصلية في `controls.json`، والملفات في `modules/` عروض مولّدة منها. لا تعدّل النسخ المولّدة مباشرة. `MASTER-MANUAL.md` تجميع للقراءة أو للأدوات التي لا تستطيع تحميل المجلد. البحث في `research/RESEARCH.md`.

احتفظ بريبو EAOS خارج المستودع الهدف. لا تستبدل تعليمات المشروع أو ملفات AGENTS.md. الـCLI يفرض أن تكون نتائج التشغيل خارج المشروع المستهدف.

```bash
python -m eaos init /path/to/project --out /path/to/audit-run
python -m eaos plan /path/to/audit-run
python -m eaos packet /path/to/audit-run --module 01
python -m eaos validate /path/to/audit-run --require-complete
```

نفّذ الأوامر من جذر ريبو EAOS، أو ثبّت الأداة محليًا باستخدام `python -m pip install .` لتستدعي `eaos` من أي مكان. تفاصيل التثبيت والعقد وكفاءة السياق في `core/CLI-AND-CONTEXT.md`. لا حزمة منشورة ولا تكامل cloud أو model API مفترض.

## خريطة المخرجات المطلوبة

| المخرج | الملف |
|---|---|
| 1–3 تحليل المصدر، مبادئه، وحدود تغطيته | research/RESEARCH.md |
| 4 المراجع وما أضافه كل منها | research/SOURCES.md + sources.json |
| 5 Taxonomy | TAXONOMY.md |
| 6 Master Framework | core/OPERATING-MANUAL.md |
| 7 Detailed Modules | modules/ + controls.json |
| 8 Finding Schema | schemas/finding.schema.json + templates/finding.json |
| 9–10 الشدة، الأولوية، الأدلة، الثقة | core/EVIDENCE-AND-TRIAGE.md |
| 11–13 الإصلاح، التحقق، الإكمال | core/REMEDIATION-AND-GATES.md |
| 14 التوسعة والإصدارات | core/EXTENSION-PROTOCOL.md |
| 15 النسخة الجاهزة للوكيل | START-HERE.md + MASTER-MANUAL.md |

## حدود مهمة

المراجعة المنجزة للجزأين هي قراءة تفريغيهما الآليين كاملين: الأول من 00:00 إلى 29:52 (المدة 29:54)، والثاني من 00:00 إلى 24:56 (المدة 25:00)، مع وصفي الناشر. لم تتوفر مشاهدة مرئية متصلة أو قراءة مستقلة لجداول الأداء داخل الصورة. لذلك أرقام تلك الجداول غير معتمدة، ولا يوجد ادعاء بمشاهدة كل إطار من الفيديو. لا تتضمن الحزمة تفريغًا معاد نشره للفيديو.

الإطار لا يضمن انعدام العيوب، ولا يمنح شهادة OWASP أو WCAG أو SLSA. اكتمال مراجعة النطاق المحدد لا يساوي أمان المنتج أو جاهزيته للإنتاج. الأهداف العددية يحددها المنتج، ولا يفرضها الدليل تعسفًا.

## إعادة التوليد والفحص

`python3 tools/render.py` يعيد بناء الوحدات والفهرس والدليل الجامع من الملفات الأصلية.
`python3 tools/validate.py` يفحص اتساق الحزمة ومعرفات القواعد والمراجع والنسخ المولدة.
`python3 tools/validate.py /path/to/audit-runs/RUN-ID` يفحص سجلات تشغيل فعلية. الفاحص البنيوي لا ينفذ اختبارًا أمنيًا ولا يثبت صحة الأدلة.

`python -m unittest discover -s tests -v` يختبر سلوك CLI وبوابات السجلات. `eaos/data/` نسخة مولدة لازمة للتثبيت وليست مصدر قواعد ثانٍ.

## حالة الإصدار

26 مجالًا، 151 قاعدة، 37 سجل مصدر يتضمن الفيديوين. الاختبارات وحدود الإثبات موثقة في `VALIDATION.md`. الريبو محلي وجاهز للنقل إلى منصة Git؛ لم يُنشر remote أو package عامة.
