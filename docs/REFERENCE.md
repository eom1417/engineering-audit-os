# Engineering Audit OS — المرجع التفصيلي

> الصفحة الرئيسية ورؤية المشروع في [README.md](../README.md). هذه الوثيقة تحفظ التفاصيل الكاملة للأوامر والبنية الداخلية.

نظام مراجعة **Architecture / Structure / Maintainability / Evolvability**: اكتشاف المشروع، إعادة بناء البنية، مراجعة الأسباب الجذرية، تصميم البنية المستهدفة وخطة الانتقال، ثم إصلاحات قابلة للتحقق في نسخة مستقلة.

## التشغيل المتصل بالنموذج

```bash
python -m pip install .
eaos run /absolute/project --out /absolute/audit --provider /absolute/provider.json
```

هذا الأمر ينفذ مراحل التحليل فعلًا باستدعاء النموذج المحدد. يحتاج إعداد مزود مرة واحدة؛ لا توجد حزمة منشورة على registry مفترضة ولا مفتاح API مضمّن. راجع [دليل التشغيل الكامل](../core/RUNTIME.md) لإعداد HTTP أو adapter لوكيلك الحالي، وحدود البيانات والتكلفة والصلاحيات.

```bash
# استكمال العمل المحفوظ
eaos continue /absolute/audit --provider /absolute/provider.json

# تنفيذ مهمة محددة في نسخة منفصلة، مع اختبارات فعلية
eaos implement /absolute/audit --task TASK_ID --out /absolute/candidate \
  --checks /absolute/checks.json --provider /absolute/provider.json

# سلسلة تحسينات: تنفيذ → اختبارات → إعادة مراجعة المصدر الجديد → المهمة التالية
eaos improve /absolute/audit --out /absolute/campaign \
  --checks /absolute/checks.json --provider /absolute/provider.json --max-steps 10
```

استبدل TASK_ID وgate IDs بمعرفات الخطة الفعلية. run لا يعدل المشروع. implement/improve ينشئان نسخة جديدة وpatch وأدلة تحقق؛ لا ينشران ولا يدمجان التغييرات في مستودعك الأصلي.

## المخرجات

- `EXECUTIVE.md`: النتائج وأسبابها وأولوياتها.
- `ARCHITECTURE.md` و`architecture.mmd`: البنية الفعلية والعقود وملكية القواعد.
- `TARGET-ARCHITECTURE.md` و`target-architecture.mmd`: المكوّنات المستهدفة، قرارات التصميم، البدائل وخطة الهجرة.
- `IMPLEMENTATION-PLAN.md`: مهام مرتبة بالاعتماديات، مع invariants والاختبارات والتراجع.
- `report.md`: التقرير الكامل؛ `findings/evidence/coverage/roadmap.json`: سجلات قابلة للمعالجة.
- `diagnosis-challenge.json` و`plan-challenge.json`: مراجعة مضادة للتشخيص والتصميم.
- `engine-state.json` و`usage.json` و`jobs/`: حالة التنفيذ وميزانية السياق والاستئناف.

## المسار الحتمي: خريطة وملف مراجعة بلا نموذج

```bash
eaos map /absolute/project --out /absolute/out          # خريطة النظام والاقتران والتطور
eaos dossier /absolute/project --out /absolute/out      # ملف المراجعة الكامل + موجز القرار
eaos verify /absolute/project --out /absolute/out --execute   # تشغيل الاختبارات بتغطية في نسخة معزولة
eaos probe /absolute/project --out /absolute/out        # إعادة حسم الادعاءات آليًا
eaos ask "أين تُحسب قاعدة الخصم" --out /absolute/out     # إجابة من السجلات باستشهاد
eaos site --out /absolute/out                           # صفحة HTML واحدة بالبحث
eaos delta /absolute/old /absolute/new --fail-on-new-severe   # بوابة انحراف في CI
eaos evaluate /absolute/benchmarks --out /absolute/eval # قياس الاكتشاف مقابل حقيقة أرضية
eaos tasks /absolute/project --out /absolute/out        # بطاقات مهام وموجات تنفيذ من الادعاءات المؤكدة
eaos impact-of <path|symbol> --out /absolute/out        # ما الذي يمسّه تغيير هذا الملف أو الرمز
eaos policy check /absolute/project --out /absolute/out # فحص السياسة المعمارية المعلنة (بوابة CI)
eaos api-diff /absolute/old /absolute/new               # سطح الكسر بين لقطتين
eaos semantic /absolute/project --out /absolute/out --provider p.json   # طبقة دلالية فوق الحقائق
```

`eaos tasks` ينتج لكل ادعاء مؤكد بطاقة مكتفية بذاتها: المشكلة وموضعها، الدليل، **نطاق الأثر محسوبًا من الرسم**، خيارات معالجة تتضمن دائمًا «لا نفعل شيئًا» وكلفتها، **معيار قبول مشتق من المجسّ الذي أكد الادعاء**، التراجع، وتقدير يعلن ثقته. والبطاقات مرتبة في موجات: مهمتان تتشاركان ملفًا لا تقعان في موجة واحدة.

`eaos policy check` يقرأ `eaos.policy.json` من المشروع الهدف: الطبقات والاعتماديات الممنوعة بسبب مكتوب. كل حافة مخالفة تصير ادعاءً بموضعها، والأمر يخرج بغير صفر فتصلح بوابةً في CI.

`dossier` ينتج `dossier.json` كمصدر وحيد، ويشتق منه: `README.md` (فهرس وترتيب قراءة ودرجة إسناد لكل قسم)، `DECISION-BRIEF.md` (صفحتان)، `RISK-REGISTER.md` (ترتيب بمعيار: مدى × ثقة ÷ كلفة)، `ONBOARDING.md`، `SYSTEM-MAP.md` (نقاط الدخول والتجمعات)، `FLOWS.md` (تتبع كل نقطة دخول بـ`file:line`)، `DOMAIN-AND-DATA.md` (مصدر الحقيقة والقواعد المكررة)، `CONTRACTS.md`، `COUPLING-ATLAS.md`، `EVOLUTION.md`، `VERIFICATION-MAP.md`، `PROVENANCE.md`. كل ادعاء يحمل ثقته وطريقته ودليله وما ينقضه؛ وعقد المخرج يرفض البناء عند مخالفته.

`--audit-run <dir>` يدمج سجلات مراجعة نموذجية سابقة داخل نفس الملف.

## حقائق حتمية بلا نموذج

```bash
eaos facts /absolute/project --out /absolute/facts --history
```

مُستخرِجات برمجية حتمية لا تستدعي أي نموذج: معدل التغيير، الاقتران بالتغيير المشترك، توزيع الملكية، عمر آخر تغيير، كثافة الإصلاحات. نفس المدخل يعطي نفس الملف بايت-بايت؛ الطوابع الزمنية في `facts/run.json` وحده. رسائل الـcommit تُصنَّف ثم تُهمل ولا تُخزَّن. غياب `.git` يُعلَن في المخرج ولا يُعد خطأ. هذه إشارات انتباه، وليست أحكامًا على جودة التصميم.

## الاستخدام داخل وكيل برمجي دون adapter مستقل

```bash
eaos audit /absolute/project --out /absolute/audit
eaos next /absolute/audit
```

أعط الوكيل `START-HERE.md` و`core/AGENT-WORKFLOW.md`. الوكيل المستضيف يقرأ ويحلل، والـCLI يدير الأدلة والسجلات والبوابات. هذا نمط مختلف عن run الذي يستدعي النموذج بنفسه.

## كيف يحافظ على العمق

حصر الملفات لا يساوي فهم البنية. المحرك يراجع المسؤوليات والحدود ومصادر الحقيقة وتدفقات العمل وسيناريوهات التغيير. يحدد نطاق الفحوص قبل تنفيذها، ثم يتحدى التشخيص والتصميم ويعيدهما للتصحيح عند الحاجة. لا تُمحى الأسئلة غير المحسومة بالاختصار. الخطة تربط الإصلاح بسبب مثبت وبنية مستهدفة، ولا تفرض تقسيم ملفات أو خدمات بلا داعٍ.

اختبارات الإصلاح تعمل فعليًا قبل التغيير وبعده، ويتحقق النظام من بقاء المصدر خارج الخطة دون تعديل ومن عدم تغيير أوامر الفحص للمصدر بعد إعداد الإصلاح. النسخة المنفصلة ليست sandbox لنظام التشغيل؛ شغّل المشاريع غير الموثوقة داخل بيئة عزل مناسبة.

## البنية الداخلية

- `sessions.py` و`workspace.py`: إنشاء الجلسة والوصول المقيد إلى الملفات.
- `architecture.py` و`surface_records.py` و`audit_records.py`: نموذج العلاقات وعقود الأدلة والاكتمال.
- `workflow.py`: سير العمل لوكيل مستضيف.
- `runtime/provider.py`: النقل إلى نموذج HTTP أو adapter صريح.
- `runtime/context.py` و`jobs.py`: قراءة الأسطر، التنقيح، السياق، التحقق والاستئناف.
- `runtime/contracts.py` و`pipeline.py`: عقود المراحل وتنفيذ المراجعة والتصميم.
- `runtime/remediate.py` و`campaign.py`: تنفيذ الإصلاحات والتحقق وإعادة المراجعة.
- `runtime/reporting.py`: المخرجات المقروءة والرسوم.

## المعرفة والتطوير

27 مجالًا و165 قاعدة و41 سجل مصدر، منها الفيديوهات الثلاثة كبذور مفاهيمية. `controls.json` و`sources.json` و`core/` و`schemas/` هي المصادر canonical؛ `modules/` و`eaos/data/` و`MASTER-MANUAL.md` مولدة.

```bash
python tools/render.py
python tools/validate.py
python -m unittest discover -s tests -v
```

راجع `VALIDATION.md` للأدلة الفعلية و`ACCEPTANCE.md` لحدود الاستنتاج. اختبارات المحرك تستخدم مزودًا تجريبيًا مبرمجًا وخادم HTTP محليًا؛ ليست تقييمًا حيًا لنموذج خارجي. المراجعة الذاتية المنفذة بواسطة الوكيل موثقة بنتائج واختبارات فاشلة قبل الإصلاح وناجحة بعده.

لا يعني COMPLETE ضمان اكتشاف جميع الأخطاء أو الجاهزية للإنتاج. النطاق غير المتاح يظهر صراحة. لم يتم نشر هذا المستودع أو package خارجيًا ضمن التسليم المحلي. تشغيل المصادر والفيديوهات موثق في research؛ قرئت التفريغات الآلية الثلاثة، ولا تُدّعى مشاهدة مرئية متصلة أو مراجعة مستقلة لمستودعات الفيديوهات.

## Output-first project review (development preview)

```bash
eaos review-project /path/to/repository --out /path/outside/repository --goal evolution --lang ar
```

Generates `PRODUCT-REPORT.md`, a typed decision ledger, investigation/repair cards and a browsable `index.html`. Without `--provider`, the result is explicitly facts-only. Confirmed structural observations do not automatically authorize repairs. `decision-review` records sourced engineering judgments; `acceptance` runs explicitly authorized checks bound to a candidate fingerprint. Disappearing observations are unobserved, not automatically repaired.

See [implementation status and remaining release gates](../design/output-first/IMPLEMENTATION-STATUS.md) and the measured [capability scorecard](CAPABILITY-SCORE.md).

**Status: pilot, not a release.** Measured on two real repositories with all four engines on, seven of nine capability domains are at target (overall 0.8537). The two that are not cannot be closed by any amount of further coding:

- `transformation_plan` scores 1.0 on its three measurable indicators, and `predictions_verified` stays unmeasured because verifying a prediction needs a report taken *after* the change, and this engine never writes code.
- `independent_proof` is 0.0 until somebody outside this project works through `evaluations/review-pack/` and returns the form.

Live-model evaluation and independent usefulness judgement remain outstanding. `evaluations/release-evidence.json` records what the evidence does and does not support.
