# سيناريوهات مراجعة أصلية — ليست نتائج فعلية على مشروع

| السيناريو | invariant | إجراء الإثبات | أقل اتجاه إصلاح عند ثبوت الكسر | regression |
|---|---|---|---|---|
| حذف Owner | كل منظمة نشطة لها مالك صالح أو حالة إغلاق محددة | تتبع delete/transfer وjobs وFKs؛ نفذ حذف آخر مالك وعمليتين متزامنتين | transaction وتحكم lifecycle، لا مجرد إخفاء الزر | رفض آخر مالك أو إغلاق صريح؛ نقل صحيح ومتزامن |
| webhook مرتين | حدث مالي واحد لا يمنح مرتين | أعد نفس event ID بعد crash بين الأثر وack | dedup durable مع effect atomic أو reconciliation | redelivery قبل وبعد commit وبعد انتهاء نافذة مزود الخدمة |
| دفع نجح وDB فشل | لا يضيع المال ولا تمنح خدمة بلا reconciliation | sandbox دفع ثم إسقاط update؛ تتبع retry وledger | سجل intent وربط provider ID وreconcile؛ لا transaction وهمية عابرة للخدمات | تكرار reconcile لا يضاعف منح أو خصم |
| plan تغيّر أثناء job | سياسة quota محددة عند admission/execution/commit | ابدأ مهمة وخفّض الخطة خلال انتظارها | versioned entitlement decision حسب سياسة المنتج | حماية من تجاوز quota وعدم إتلاف عمل مسموح |
| نافذتان للعملية نفسها | one logical action ينتج أثرًا واحدًا | concurrent requests بنفس business key وبمفاتيح مختلفة | unique invariant/transaction مع idempotency مناسب | assertions على count/ledger وليس status فقط |
| downgrade فوق limit | لا حذف صامت ولا deadlock للعميل | خفض خطة عميل لديه موارد أكثر من الحد | منع إنشاء إضافي/grace/read-only حسب العقد مع export/delete | العميل يستطيع تقليل الاستخدام واستعادة الوصول |
| cache عبر tenants | response مرتبط بالهوية وtenant والpolicy | tenant A يملأ cache ثم B يطلب URL ذاته | key/partition صحيح وinvalidation عند تغير العضوية | منع تسرب البيانات مع hit وبعد revoke |
| حجز متزامن وDST | مورد واحد لا يُحجز مرتين حسب time semantics | طلبان لنفس slot؛ أيام تغير التوقيت المحلي | invariant فيDB وtimezone policy صريحة | fold/gap DST وcancel/rebook وretry |
| migration كبيرة | التوافق قائم أثناء mixed versions | schema expand، old/new app، backfill، locks measured | expand/contract وbatch resumable وrollforward | لا كتابة قديمة تكسر schema الجديدة ولا rollback يفقد البيانات |
| refresh بعد401 | إعادة المحاولة محدودة ولا تنفذ mutation مرتين | token منتهي مع عدة tabs وrefresh rotation وnetwork retry | single-flight مناسب وrotation/reuse policy | 401→refresh واحد ثمretry محدود؛403 لا يسبب refresh loop |

كل سيناريو يبدأ ببيئة isolated وبيانات مصطنعة؛ لا fault injection فيproduction لمجرد أن framework ذكره. تظل النتيجة NOT VERIFIED حتى يوجد دليل من المشروع. غياب circuit breaker مثلًا ليس finding مستقلًا دون اعتماد خارجي أو failure budget يبرره.
