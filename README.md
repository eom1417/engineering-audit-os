# Engineering Audit OS — Architecture Edition 2.0.0

ريبو CLI محلي لمراجعة **Architecture وStructure وقابلية الصيانة والتطور** بالتعاون مع Coding Agent. التركيز على فهم المسؤوليات والعقود والاعتماديات ومكان منطق العمل ومدى أمان وكلفة التغيير. لا يفرض لغة أو framework أو نمطًا معماريًا.

## البدء

```bash
# داخل الريبو: Python 3.10+، دون dependencies وقت التشغيل
python -m eaos init /path/to/project --out /path/to/audit-run --profile architecture
python -m eaos plan /path/to/audit-run
# الوكيل يقرأ START-HERE.md ثم يعيد بناء architecture.json بالأدلة
python -m eaos graph /path/to/audit-run
python -m eaos impact /path/to/audit-run --node NODE_ID --depth 2
python -m eaos context /path/to/audit-run --node NODE_ID --budget-chars 18000
python -m eaos validate /path/to/audit-run --require-complete
```

استبدل NODE_ID بمعرف فعلي في نموذجك. أو ثبّت محليًا باستخدام `python -m pip install .` أو wheel المرفقة لاستدعاء `eaos` من أي مكان. لا نفترض package منشورة على registry عام. Windows/macOS/Linux تستخدم Python؛ التحقق الفعلي لهذا الإصدار كان على Linux.

الـCLI لا يشغّل نموذجًا ولا يرسل code إلى خدمة خارجية؛ الوكيل الذي تختاره يعيد بناء النموذج ويجمع الأدلة، والأداة تتحقق من اتساق السجلات وتحسب الاستعلامات وتجهز السياق. target يبقى read-only بالنسبة للـCLI؛ الإصلاح في المنتج مهمة منفصلة للوكيل ضمن تفويض المستخدم.

## المسارات

| الملف | الاستخدام |
|---|---|
| START-HERE.md | تعليمات الوكيل الجاهزة |
| core/ARCHITECTURE-FIRST.md | البروتوكول المركزي للبنية والصيانة والتطور |
| core/CLI-AND-CONTEXT.md | التشغيل وميزانية السياق والاستئناف |
| MASTER-MANUAL.md | الدليل الكامل؛ حمّل منه ما يلزم تدريجيًا |
| controls.json + modules/ | 27 مجالًا و165 قاعدة؛ modules مولدة |
| schemas/ + templates/ | Finding/evidence/coverage/gates/architecture |
| research/RESEARCH.md | تحليل المصدرين الأولين والمبادئ وgap analysis |
| research/ARCHITECTURE-SEED.md | تحليل الفيديو الثالث وتحويله إلى مفاهيم مستقلة |
| research/SOURCES.md + sources.json | 41 سجل مصدر، منها الفيديوهات الثلاثة، وحدود القراءة |
| examples/architecture/ | نموذج توضيحي يختبر عقود graph، ليس audit لمشروع حقيقي |
| tests/ + VALIDATION.md | اختبارات وإثبات الإصدار وحدوده |

profile الافتراضي architecture يجعل مجالات البنية والجودة والاختبار والتوثيق والسياق هي الأساس، ويحتفظ بالأمن والأداء والتشغيل وغيرها كعدسات تُفعّل عند الصلة. `--profile full` يحتفظ بالمراجعة العامة الشاملة. COMPLETE للمراجعة البنيوية لا يعني تدقيقًا أمنيًا كاملًا ولا جاهزية نشر.

## ما ينفذ فعليًا

Discovery بالمسارات وhashes؛ نموذج graph يتحقق من الأدلة والمراجع؛ حساب cycles وfan-in/out؛ مطابقة dependency policies المعلنة؛ impact walk محدود مع frontier؛ context packets مرتبطة بالعقود والقواعد؛ checkpoint/resume؛ findings وcoverage وإغلاق يحتاج أدلة. مؤشرات graph ليست نتائج آلية عن جودة المشروع.

لا يتضمن الإصدار semantic/AST extraction شاملًا لكل اللغات، ولا cloud adapters ولا scanner ثغرات شاملًا. هذه حدود تنفيذ صريحة، وليست مناطق تُسجل PASS. جودة الخريطة والأحكام تحتاج مراجعة المصدر والسيناريوهات.

## إعادة التوليد والاختبار

```bash
python tools/render.py
python tools/validate.py
python -m unittest discover -s tests -v
```

المصادر canonical هي controls.json وsources.json وcore وschemas. لا تعدل modules/ أو eaos/data أو MASTER-MANUAL مباشرة. نسخة2.0 تتطلب run جديدًا بدل ترقية حالات1.0 يدويًا.

## حدود مراجعة الفيديوهات

قرئت التفريغات الآلية كاملة للفيديوهات الثلاثة؛ لم تُنجز مشاهدة مرئية متصلة أو إعادة تدقيق مستقلة للمستودعات المعروضة. لا نعتمد أرقام جداول غير مقروءة بصريًا، ولا نعيد نشر التفريغات. القواعد synthesis مستقلة لها شروط وأدلة، وليست نسبًا مطلقة للفيديو.
