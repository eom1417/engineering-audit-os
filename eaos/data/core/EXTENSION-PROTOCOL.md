# 26 — Extension Protocol & Governance

## مصدر الحقيقة

`controls.json` يملك القواعد الفنية، `sources.json` يملك بيانات المصادر، `core/` يملك السياسات والإجراءات، `schemas/` يملك عقود البيانات. modules والدليل الجامع وTAXONOMY عروض مولّدة؛ لا تنسخ قاعدة وتعدلها في دليل آخر. source_id ليس control_id، وFinding ليس Control.

## إدخال مصدر جديد

1. سجّل source_id والرابط والعنوان والناشر والإصدار وتاريخ الوصول ونوع المادة وretrieval_status وحدود القراءة. الفيديو يحتاج duration وtranscript coverage وvisual coverage وأجزاء غير واضحة؛ لا تملأ gaps من عنوانه.
2. اقرأ المادة ذات الصلة، واستخرج claims atomically مع locator (section/timestamp). افصل ما شاهده المؤلف عما افترضه وما أوصى به. لا تنسخ المصدر كاملًا داخل الحزمة؛ احتفظ بالإحالة وبأقل اقتباس لازم.
3. حوّل الادعاء إلى invariant + applicability + failure mechanism + evidence requirements + falsification + verification. إذا تعذر الاختبار أو بيان أثره، يبقى research note ولا يصبح mandatory rule.
4. طابقه مع القواعد الحالية بالدلالة، لا الكلمات: invariant/resource/failure mode. صنّف `NEW | SUPPORTS | REFINES | SUPERSEDES | CONTRADICTS | REJECTED`.
5. SUPPORTS يضيف مرجعًا لا control مكررًا؛ REFINES يعدل نطاق القاعدة ودليلها؛ NEW يأخذ id ثابتًا داخل domain. SUPERSEDES يحتفظ بالقديم deprecated مع migration map. لا تعِد استخدام معرف محذوف.
6. عالج التعارض في decision record: القاعدتان، شروط الانطباق، قوة الدليل، إصدار المعيار، أمثلة counterexample، الحكم. لا تختَر «الأشد دائمًا»: قد يُضعف privacy أو availability أو simplicity. المرجع الرسمي المطبق يتقدم على رأي فيديو في semantics، لكن سياسة العمل ومخاطره تحددان خيار التصميم ضمن الحدود الآمنة.
7. إن كانت القاعدتان صحيحتين في سياقين فقسّم applicability، لا تدمجهما بصياغة مطاطة. مثال: cache reference data مقابل no shared caching for private identity؛ وتسجيل forensic events مقابل عدم تسجيل PII الخام.
8. أضف اختبار قبول وcounterexample يمنع false positive، وحدد artifacts والأثر على coverage، واختبر على fixtures تمثل architecture مناسبة.
9. أعد توليد الملفات ثم شغّل validation وregression cases. حدّث CHANGELOG وmanifest وsource mappings وversion.
10. اعتمد الإضافة عند وجود فائدة لا توفرها قاعدة قائمة؛ عدّ القواعد الجديدة مقابل deprecated؛ لا توسع الحزمة بعدد مصادر لا تضيف failure mode أو verification method.

## الإصدارات

MAJOR: تغيير semantics للبوابات/schema أو breaking IDs. MINOR: قواعد أو وحدات متوافقة إضافية مع تطبيقها على runs الجديدة؛ PATCH: صياغة/رابط/خطأ لا يغير القرار. تسجل كل run framework_version ومصدر package digest. لا تعدّل نتائج قديمة بأثر رجعي عند تحديث rule؛ اعمل reassessment مرتبطًا بالإصدار الجديد.

Overrides محلية تصرح `rule_id, scope, reason, evidence, owner, expiry, compensating_controls`؛ لا تُخفِ تعارضًا مع invariant حرج خلف override. الاستثناء لا يساوي N/A. تقرأ التعليمات حسب أولويتها الفعلية في بيئة الوكيل؛ لا يمنح هذا الملف نفسه سلطة أعلى من المستخدم أو النظام.

## اختبارات جودة الإطار

اختبر: مشروع سليم لا يولد findings، authorization gap يولد FAIL، gateway غير متاح يولد INCONCLUSIVE، static site يجعل DB N/A، refresh-on-401 سليم لا يصنف bug، control مكرر/مرجع مفقود يفشل validator، finding مغلق دون تحقق يرفض، evidence قديم يُعاد تقييمه، load test غير مصرح يتحول إلى خطة محلية، وتنتهي الجلسة الطويلة بcheckpoint قابل للاستئناف.

الإطار نفسه يحتاج calibration على مستودعات متنوعة وقياس false positives/false negatives وتوافق مقيمين. التحقق البنيوي في هذه الحزمة ليس ذلك الاعتماد الميداني.
