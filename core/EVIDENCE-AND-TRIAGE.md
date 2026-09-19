# الأدلة والثقة والشدة والأولوية

## سجل الأدلة

كل دليل له id ونوع JSON معتمد `source | configuration | runtime | test | requirement | external | absence_search`، revision وبيئة وزمن ومصدر محدد وطرق إعادة التحقق. الموقع هو path + symbol + line range اختياري + commit؛ لا تعتمد على رقم سطر وحده. الدليل المحفوظ يتضمن digest إن كان ملفًا، وملخصًا منقحًا لا secrets، والأمر ومجلد العمل وإصدار الأداة وexit code إذا شُغّل أمر.

التفاصيل الدلالية مثل SCHEMA وLOG وMETRIC وTRACE تحفظ كتصنيف إضافي داخل الدليل: schema ضمن source، والقياسات/السجلات/التتبعات ضمن runtime، والوثائق حسب requirement أو external.

فرّق بين evidence_of_claim («ورد الادعاء في فيديو») وevidence_of_system_behavior («نجح اختبار محلي في إعادة الخطأ»). فيديو مراجعة لتطبيق آخر لا يثبت عيبًا في مستودعك. tool output هو observation يحتاج تفسيرًا؛ لا تُسقط كل scanner hit مباشرةً في findings.

### تصنيف الادعاء

| التصنيف | شروط الاستخدام |
|---|---|
| CONFIRMED | دليل مباشر قابل لإعادة التحقق يثبت الادعاء ضمن النطاق؛ اختبار أو مسار source كامل وحاسم؛ لا يشترط استغلال إنتاجي |
| HIGHLY_LIKELY | مسار شبه كامل مع دليل قوي، لكن افتراض حاسم واحد أو أكثر لم يتحقق؛ اذكره |
| POSSIBLE | مؤشر محدد وفرضية قابلة للنفي؛ يحتاج فحصًا إضافيًا ولا يصاغ كحقيقة |
| NOT_VERIFIED | لم تتوفر أدلة كافية أو وصول لازم؛ يوضع كفجوة أو مهمة تحقق، لا bug مؤكد |
| NOT_APPLICABLE | خاص بانطباق القاعدة في coverage؛ بدليل على غياب الحالة التي تشغّلها |

الثقة تعبر عن جودة الأدلة `HIGH/MEDIUM/LOW` مع rationale، لا نسبة احتمالية مختلقة. CONFIRMED يمكن أن يكون code-proven ضمن بيئة محلية، لكن `production_exposure` يبقى NOT_VERIFIED. السبب الجذري له `root_cause_status` مستقل: قد يثبت العطل دون أن يثبت مصدره.

### إثبات الغياب

لادعاء «rate limiting غير موجود»: احصر routes الحساسة، اقرأ route/handler والمشتركات وgateway/ingress/CDN/IaC وإعدادات المزود المتاحة، تحقق من framework defaults، ثم سجّل scoped search corpus وqueries والملفات المستبعدة والوصول الناقص. عدم العثور على كلمة rateLimit ليس إثباتًا. إن لم تتوفر إعدادات gateway، الصياغة الصحيحة: «لا توجد حماية مثبتة في الطبقات المفحوصة؛ فعالية الحد على مسار النشر NOT_VERIFIED».

المثل يطبق على authorization، backups، tests، logs، uniqueness. عدم رؤية ملف في المستودع لا يثبت غياب نظام مُدار خارجه. اختر evidence level يسمح بصياغة أضيق بدل رفع الثقة بلا أساس.

## شدة الأثر — Severity

| القيمة | معيار القرار المقترح للإطار |
|---|---|
| CRITICAL | مسار واقعي إلى اختراق واسع/عابر للمستأجرين أو تنفيذ مسيطر عليه أو فقد دائم واسع لبيانات حرجة أو معاملات خطيرة بلا حماية فعالة |
| HIGH | انتهاك مهم للصلاحيات أو سلامة البيانات، أو تعطل رحلة حرجة/فقد بيانات مهم مع تعرض واقعي |
| MEDIUM | ضرر محدود أو شروط أكثر تقييدًا أو بطء مؤثر/خلل قابل للاستعادة في نطاق محدد |
| LOW | أثر صغير مثبت على مستخدم أو تشغيل أو صيانة، بلا تصعيد مهم معروف |
| INFO | ملاحظة أو فرصة تحسين أو تفضيل تصميم؛ ليست عيبًا مثبتًا بالضرورة |

Severity تتبع أثرًا وسيناريو، لا اسم فئة. Missing header لا يصبح HIGH تلقائيًا؛ وbug صغير في tenant filter قد يكون CRITICAL. اذكر prerequisites، blast radius، data sensitivity، exploitability، recoverability، duration، compensating controls. ضع severity provisional إذا كان الأثر غير متحقق، ولا تخفض أثرًا خطيرًا لمجرد أن التحقق متعذر.

يمكن إضافة CVSS إذا كانت النتيجة ثغرة فعلية ويعرف المقيم إصدار CVSS ومتجهها؛ لا تُنشئ score بلا vector ولا تعمم CVSS على maintainability أو UX. لا يعتمد EAOS عتبات CVSS داخلية.

## أولوية التنفيذ — Priority

| القيمة | الاستخدام |
|---|---|
| P0 | احتواء حادث نشط أو تعرض حرج موثوق؛ أعط إجراء احتواء مستقلًا عن الإصلاح النهائي |
| P1 | معالجة قبل إطلاق متأثر أو ضمن دورة عاجلة يحددها المالك؛ يشمل تحققًا عاجلًا من خطر محتمل شديد |
| P2 | إصلاح مجدول بحسب أثر مستخدم وتكرار وكلفة ومخاطر التغيير |
| P3 | تحسين منخفض الأثر أو دين مقبول له trigger واضح لإعادة التقييم |

رتب بالمخاطر أولًا ثم dependencies والكلفة؛ لا تستخدم حاصل ضرب أرقام اعتباطية لإخفاء عدم اليقين. اكتب priority_rationale مع deadline إن وافق المالك عليه. لا تجعل نتيجة CRITICAL غير مؤكدة مساوية آليًا لحادث P0، ولا تؤجل تحقيقها لأنها غير مؤكدة.

Status منفصل: `OPEN → TRIAGED → PLANNED → IN_PROGRESS → FIXED_PENDING_VERIFICATION → VERIFIED_CLOSED`؛ حالات جانبية `ACCEPTED_RISK, DEFERRED, FALSE_POSITIVE, DUPLICATE`. accepted risk لا يعني fixed، ويحتاج owner وreason وexpiry/review trigger. يُعاد فتح المغلق إذا عاد الإخلال أو تغيرت أدلة الإغلاق.

## Finding contract

استخدم schema المرفق. الخانات النصية غير المناسبة تأخذ `NOT_APPLICABLE: reason`، والمصفوفات [] عند ملاءمتها؛ null مسموح فقط حيث يصرح schema، لا قصة مختلقة. expected_behavior يتضمن مصدره: requirement، invariant، contract، threat model، أو معيار محدد. إذا لم يعرف السبب الجذري اكتب unknown وخطة تمييز البدائل.

الأثر يسجل security/performance/reliability/maintainability/user/business كلًا على حدة. recommended_remediation ليس أمرًا عامًا؛ يحدد الحد المسؤول والإجراء والبديل الأقل تدخلًا. verification_method يحدد observation الذي سيُثبت الإصلاح، وليس «run tests» فقط. links تربط القواعد والأدلة والنتائج المرتبطة وخطة التنفيذ.
