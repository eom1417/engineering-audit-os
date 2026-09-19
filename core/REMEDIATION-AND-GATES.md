# بروتوكول الإصلاح والتحقق والإكمال

## 22 — التصميم قبل التغيير

لكل fix plan سجّل finding_ids، invariant، baseline، root cause أو فرضية مؤكدة بالحد الكافي، affected contract، files/components، options، chosen option، why not smaller fix، complexity added، cost range وافتراضاته، dependencies، migration/data impact، rollback/roll-forward، regression risks، tests، success criteria، deployment evidence required، authorization boundary.

ابدأ بحل يحافظ على العقود ويقلل مساحة التغيير. معالجة العرض مقبولة كاحتواء مؤقت إذا سُميت كذلك ولها خطة سبب جذري. لا تمدد عمر access token لإخفاء فشل التجديد، ولا تضف global cache لإخفاء البطء دون عزل الهوية، ولا ترفع pool إلى حد ينهك قاعدة البيانات.

إذا كان refactor واسعًا ضروريًا، أظهر بديلًا أقل تدخلًا ولماذا لا يحمي invariant. قسّم إلى تغييرات يمكن بناء كل منها والتحقق منها، مع compatibility window. التصميم المقترح ليس تفويض نشر.

## 23 — تنفيذ منضبط

1. سجّل baseline وknown failures قبل التغيير. إذا تعذر baseline وثق هذا القيد.
2. أضف regression test يميّز السلوك الخاطئ عند تناسبه مع الخطر. احرص أن يفشل للسبب المقصود قبل الإصلاح، لا بسبب import مفقود.
3. نفذ fix محدودًا، حافظ على signatures والعقود والسياسات ما لم يتطلب الإصلاح تغييرها صراحةً.
4. لا تُجري network installs أو package scripts غير مفحوصة ضمن إصلاح شكلي. تحديث dependencies يحتاج compatibility وتحقق lockfile.
5. افحص failure paths والتزامن والحدود المجاورة؛ لا يكفي assertion يشابه implementation.
6. انقل الحالة إلى FIXED_PENDING_VERIFICATION. لا تسجل VERIFIED_CLOSED قبل الأدلة المطلوبة.
7. أعِد تدقيق المصدر والـruntime الممكن للمسارات المعدلة وcallers، وحدّث architecture وcoverage إذا تغيرت الحدود.

## 24 — Verification Pipeline

كل gate يأخذ JSON enum `pass | fail | blocked | not_run | not_applicable` (الحروف الكبيرة في الشرح تشير للمعنى نفسه)، مع reason/detector وrevision/environment وcommand/cwd/tool_version وexit_code/artifact_ids. NOT_RUN وBLOCKED لا يتحولان إلى PASS. NOT_APPLICABLE يحتاج تفسيرًا تقنيًا.

| Gate | متى ينطبق؟ | إثبات النجاح |
|---|---|---|
| Build | منتج له build | بناء القطعة المستهدفة من lockfile وإعداد موثق، دون إخفاء فشل |
| Typecheck | stack يدعم فحص أنواع | الأمر الفعلي ينجح على النطاق المتأثر دون تعطيل checks |
| Lint/static analysis | سياسة المشروع | لا violations جديدة متعلقة بالتغيير؛ فصل pre-existing |
| Unit | منطق منعزل أو invariant | حالات الحدود والفشل تتطابق مع contract |
| Integration | DB/cache/queue/external adapter | التكامل الحقيقي المعزول يثبت سلوك الحدود، لا mocks فقط |
| Contract | API/event/schema consumers | النسخ المتوافقة مقبولة والطلبات غير الصالحة مرفوضة |
| Relevant E2E | رحلة متأثرة | مستخدم ممثل ينهي الرحلة وحالة التخزين والواجهة صحيحتان |
| Security | trust/identity/data change | اختبارات deny/allow وcross-user/cross-tenant وnegative inputs المرتبطة |
| Migration | schema/data change | old/new app compatibility، سلامة البيانات، قياس locks، استئناف/backfill، rollback أو roll-forward |
| Runtime | runtime-sensitive fix | الأثر يُلاحظ في بيئة ممثلة مع config حقيقي موثق |
| Performance | claim تحسين أداء | workload ثابت، قبل/بعد، percentiles/error rate/resources دون تدهور آخر |
| Regression | تغيير مسار مشترك | callers والرحلات المجاورة محفوظة |
| Re-audit | كل إصلاح | مراجعة diff ومسار التنفيذ بعده وتحديث findings/coverage |

لا تفرض E2E شاملًا لكل تعديل docs؛ اختر gates مسبقًا بحسب الخطر وسجل عدم الانطباق. لا يُحذف gate بعد فشله كي ينجح التقرير. لا يثبت نجاح الاختبارات أن الإصلاح «لم يكسر أي شيء» على نحو مطلق؛ يثبت اجتياز السيناريوهات المحددة في البيئة المحددة.

### Migrations لا تساوي reversible SQL

قد يكون down migration مدمرًا. افصل rollback للكود عن استرجاع البيانات وعن roll-forward للـschema. استخدم expand → compatible app → backfill resumable → validate → contract عند الحاجة، مع تحديد الإصدارين اللذين يعملان أثناء النشر. افحص النسخ الاحتياطية ومفاتيح فك التشفير واسترجاعًا تجريبيًا قبل تغيير بيانات غير قابل للعكس. لا تزعم zero downtime بلا دليل في بيئة ممثلة.

### تجربة الأداء الصحيحة

عرّف حجم البيانات والتوزيع وtenant count ونوع المستخدم وpermissions وthink time وread/write mix، arrival rate/concurrency، مدة وwarm-up وcache state وموقع مولد الحمل والحدود والموارد وإصدارات التطبيق. قس p50/p95/p99 مع عدد العينات؛ لا تتوقع p99 موثوقًا من عينة صغيرة. أظهر errors/timeouts ومعدل الإنجاز الصحيح، لا سرعة الرد وحدها. ميّز virtual users عن requests/sec وعن مستخدمين أعمال حقيقيين. اذكر closed/open workload وcoordinated omission عندما يؤثر توقف مولّد الطلبات على تفسير التأخر. لا تستنتج DB bottleneck من waterfall المتصفح دون traces أو قياس خادم.

## 25 — Completion Gates

النطاق يثبت في run.json قبل التنفيذ. أي توسعة أو استثناء تسجل scope_change مع السبب ومن أقره. لا تغيّر المقام بعد اكتشاف فجوة لتصنع نسبة 100%.

| حالة audit_completion | الشرط |
|---|---|
| INCOMPLETE | لا inventory موثوق أو لا scope/coverage يمكن قياسه، أو توقف قبل فحص ذي معنى |
| PARTIALLY_COMPLETE | هناك نتائج مفيدة، لكن instance منطبق بلا فحص أو UNKNOWN/N/A بلا إثبات أو gate لازم محجوب أو رحلة ضمن النطاق غير مفحوصة |
| COMPLETE | جميع المجالات صُنفت، وكل instances المنطبقة في النطاق المعلن فُحصت إلى نتيجة PASS أو FAIL ذات دليل حاسم، وكل الحالات غير المنطبقة مبررة، ولا gaps مفحوصة جزئيًا أو inconclusive ضمن النطاق |

مراجعة repo-only يمكن أن تكون COMPLETE **للمستودع فقط** إذا كان ذلك scope المعلن أولًا؛ حالة مراجعة المنتج بما فيه النشر تظل PARTIALLY_COMPLETE إذا لم يفحص النشر. لا تحول runtime unknown إلى repo-only PASS. النتائج المفتوحة المؤكدة لا تمنع اكتمال المراجعة، لكنها قد تمنع جاهزية المنتج.

`remediation_completion`: NOT_REQUESTED / NOT_STARTED / PARTIAL / COMPLETE. COMPLETE يعني جميع إصلاحات النطاق المعتمد verified أو dispositions موثقة، مع عرض عدد accepted/deferred بشكل مستقل؛ لا تسمها «كل المشاكل أصلحت» إذا بقي خطر مقبول.

`production_readiness`: NOT_ASSESSED / UNKNOWN / NOT_READY / READY_WITH_CONDITIONS / READY_FOR_DECLARED_SCOPE. لا READY مع release blocker مفتوح أو بوابة إنتاج لازمة BLOCKED أو بيانات استعادة غير مختبرة حين تكون لازمة. acceptance من مالك مخاطر موثق لا يعوض نقص المعرفة. لا يوجد تصنيف «آمن 100%».

### مؤشرات التغطية

احسب inspected/applicable instances، confirmed-outcomes/applicable instances، critical-journeys-verified/critical-journeys-total، وruntime-verified/runtime-required. أعلن N/A وUNKNOWN منفصلين. لا تجمع أوزانًا تسمح بعشرات low-risk passes لإخفاء route حساس لم يفحص.

### قالب تقرير الإغلاق

- Scope/revision/environments/time؛ exclusions والفرق عن نطاق المنتج الكامل.
- audit_completion/remediation_completion/production_readiness مع الأسباب.
- النتائج حسب priority؛ evidence-backed وhypotheses وgaps في أقسام مختلفة.
- ما تغير ولماذا، الاختبارات الفعلية ونتائجها، limitations، operational follow-up.
- coverage matrix، release blockers، accepted risks مع مالك وموعد، next actions.
- لا «Done» بلا links للنتائج والأدلة والبوابات. لا شهادة مطابقة تنظيمية من مجرد checklist.

في finding تُحدد `required_gate_ids` قبل الإصلاح؛ عند الإغلاق يجب إدراجها ضمن `verification_ids` وأن تكون pass ذات أدلة. إضافة `required_for_audit: true` إلى gate تجعل عدم تنفيذه أو حجبه فجوة تمنع اكتمال المراجعة. مخرجات CLI تراجع اتساق هذه الإعلانات؛ لا تثبت أن الوكيل لم يحذف requirement من الملف عمدًا. احتفظ بتاريخ git لسجلات التشغيل ومراجعة بشرية للقرارات المرتفعة الأثر.
