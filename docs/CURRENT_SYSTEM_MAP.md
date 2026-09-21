# خريطة النظام الحالي

> قياس، لا انطباع. كل رقم هنا مأخوذ من تشغيل فعلي على هذا المستودع بتاريخ 2026-09-21، على الالتزام `a7ca112`.

## 1. ما هو هذا النظام فعليًا

`eaos` حزمة Python من **9,951 سطرًا** في **27 وحدة**، تُثبَّت كـ wheel وتُشغَّل من سطر الأوامر على مستودع هدف **للقراءة فقط**. وظيفتها ليست «العثور على مشاكل» بل **إنتاج سجل ادعاءات قابل للتفنيد** حول مستودع، ثم اشتقاق قرارات وخطة منه.

## 2. الطبقات كما يفرضها `eaos.policy.json`

| الطبقة | المحتوى | المسؤولية |
| --- | --- | --- |
| `facts` | `eaos/facts/**` (17 وحدة) | استخراج حتمي فقط: tree-sitter + `ast`. لا تفسير، لا عرض. |
| `engines` | `eaos/engines/**` | محرّكات خارجية مثبّتة الإصدار تُستدعى كعمليات فرعية وتُطبَّع إلى نفس مخطط الحقائق. |
| `ledger` | `claims, dossier, decisions, ranking, impact, probes, policy, apidiff, delta, verify, semantic, map, ask, site` | التفسير: ادعاء + ناقض + ثقة + مصدر. |
| `planning` | `plan, remediation_patterns, acceptance` | تحويل الادعاءات المؤكَّدة إلى بطاقات مهام وموجات. |
| `compose` | `eaos/compose/**` | العرض فقط، بميزانيات أسطر معلنة وعقد مخرجات R1–R12. |
| `runtime` | `eaos/runtime/**` | مسار النموذج الاختياري؛ الطبقة الحتمية تعمل بدونه. |
| `core` | `workspace, discovery, architecture, audit_records, workflow, sessions` | لبنات مشتركة. |
| `orchestration` | `cli, views, evaluate, decision_review, product_review` | من يستدعي من. |

سبعة قواعد `deny` تمنع الاتجاهات الخاطئة، و`eaos policy check` يفشل عند خرقها. القاعدة الأهم عمليًا: `facts` ممنوعة من `ledger` و`runtime` — لهذا يعمل `eaos map` بلا مزوّد نموذج.

## 3. مجموعات الحقائق (17)

`syntax, resolve, structure, graph, entrypoints, config, metrics, history, flows, domain, sequences, redundancy, fingerprint, scope, source, store, run`

كلها محتواة العنونة (content-addressed) وقابلة للتكرار بايتًا ببايت. `facts/run.py` هو السجل الوحيد لأسماء المجموعات وترتيبها — بعد أن كانت القائمة منسوخة في خمس وحدات.

## 4. ما فوق الحقائق — وهو ما يميّز هذا النظام

- **سجل الادعاءات**: كل ادعاء يحمل `falsifier` إلزاميًا، و`confidence` من {CONFIRMED, LIKELY, HYPOTHESIS, REFUTED}، و`method`، و`origin`، و`probe_spec`.
- **محرّك الفحوص (probes)**: لكل نوع فحص خريطة `DECIDABLE` تحدد ما يستطيع حسمه؛ ما لا يُحسم يعود `PARTIAL` أو `INCONCLUSIVE`، لا «سليم».
- **عقد القرار**: `repair | investigate | retain` + `readiness` + `blockers`، ولكل قرار فحوص قبول مرتبطة بمراجعة محددة.
- **عقد المخرجات R1–R12**: يُتحقق منه آليًا؛ `eaos review-project` يفشل إن خُرق.
- **السياسة المعمارية ككود**: 9 طبقات، 7 قواعد منع، واستثناءات تحليل معلنة.
- **عقيدة الاستدامة P1–P6** ولوحة مؤشرات مقيسة، مع `measured: false` صراحةً حين لا يوجد ما يُقاس.
- **البيت القانوني (`canonical_home`) وخطة التحويل (`transform_plan`)**: أين يجب أن يعيش المفهوم المكرر ومن يملكه.

## 5. الأوامر (24)

`facts, dossier, map, probe, verify, semantic, policy, review-project, decision-review, tasks, impact-of, sustainability, transform-plan, delta, api-diff, acceptance, evaluate, site, ask, graph, packet, checkpoint, observe, roadmap`

## 6. الأرقام المقيسة اليوم

| القياس | القيمة |
| --- | --- |
| `eaos facts .` | 7.3 ثانية |
| دورة كاملة (verify بتنفيذ الاختبارات + review-project + probe + sustainability + transform-plan + policy) | 115 ثانية |
| الاختبارات | 425، كلها تمر |
| `tools/validate.py` | `errors: []` |
| `eaos policy check` | OK، صفر مخالفات |
| الادعاءات على كودنا | 52، كلها CONFIRMED |
| المهام/الموجات | 31 / 14 |
| اللغات المعلنة | 29 امتدادًا (~24 لغة)، والعمق الحقيقي في Python وحدها |

## 7. نقاط الضعف المعروفة قبل أي دمج

1. **عمق لغة واحدة**: الاستخراج العميق (AST، تدفقات، تكرار بنيوي) لـ Python فقط. البقية tree-sitter سطحي.
2. **لا مقياس تعقيد دوري**: `facts/metrics.py` يقيس أحجامًا، لا cyclomatic complexity ولا تقدير رتبة زمنية.
3. **لا كشف استنساخ على مستوى الرموز (token-level)**: كاشفنا بنيوي (AST-shape)؛ النسخ الحرفي عبر لغات غير Python غير مُغطى.
4. **الدورات على مستوى الملف لا الحزمة**: كشفنا يرى دورات الوحدات، لا دورات الحزم.
5. **لا خط زمني معماري**: `delta` يقارن لقطتين، ولا يوجد تاريخ قابل للاستعلام.
6. **البطء النسبي**: 7.3 ثانية لاستخراج الحقائق مقابل 0.7 ثانية لمحرك Go يستخرج ضعف عدد الحقائق.
