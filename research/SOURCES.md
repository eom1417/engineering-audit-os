# External Research — المصادر المنتقاة

المراجع أدناه أولية وتضيف بُعدًا أو طريقة تحقق أو تصحيحًا. معرف المصدر يربط الدعم المفاهيمي بالقواعد؛ ليس mapping معتمدًا لكل بند في معيار. توضح حدود القراءة إن كانت صفحة بحث وملخصًا فقط. الإصدارات المحددة ليست ادعاءً بأنها الأحدث عالميًا.

| ID | المرجع والإصدار | ما أضافه | حدود الاستعمال |
|---|---|---|---|
| SRC-ASVS | [OWASP ASVS — 5.0.0](https://github.com/OWASP/ASVS) | متطلبات أمان قابلة للتحقق، بدل الاكتفاء بتسمية الثغرات. | Security baseline؛ لا يدعي الدليل تغطية كل ASVS requirement. |
| SRC-WSTG | [OWASP Web Security Testing Guide — 4.2](https://owasp.org/projects/web-security-testing-guide) | منهج فحص أمني واختبارات سلوك وحدود تحقق. | مرجع اختبار، وليس إثباتًا بأن اختبارًا بعينه نفذ. |
| SRC-API | [OWASP API Security — 2023](https://api-security.owasp.org/editions/2023/en/0x11-t10/) | صلاحيات الكائن والحقول، استهلاك الموارد، وسوء استخدام رحلات العمل. | Top 10 لا يساوي تدقيق API شاملًا. |
| SRC-AUTHZ | [OWASP Authorization Cheat Sheet — صفحة حية](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) | فحص التفويض على الطلبات ومراجعة قواعد المنع والسماح. | المصفوفة والإجراءات التفصيلية هنا من تصميم EAOS. |
| SRC-TENANT | [OWASP Multi Tenant Security — صفحة حية](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) | عزل المستأجر عبر البيانات والبنية والسياق. | ينطبق عند مشاركة موارد أو حدود بين مستأجرين. |
| SRC-OAUTH | [OAuth 2.0 Security BCP — RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html) | ضبط tokens وredirects وrefresh replay على أساس نوع العميل. | ينطبق على OAuth؛ لا يفرض OAuth على كل تطبيق. |
| SRC-C4 | [C4 model — الموقع الرسمي](https://c4model.com/) | مستويات تمثيل النظام وسياقه ومكوناته. | EAOS يضيف روابط الدليل والثقة؛ الرسم ليس تدقيقًا بذاته. |
| SRC-REVIEW | [Google Engineering Practices: What to look for — صفحة حية](https://google.github.io/eng-practices/review/reviewer/looking-for.html) | مراجعة التصميم والتعقيد والاختبارات وقابلية الفهم. | ليس تبريرًا لإعادة كتابة مشروع يعمل. |
| SRC-PRR | [Google SRE: Evolving SRE Engagement Model — كتاب SRE](https://sre.google/sre-book/evolving-sre-engagement-model/) | مراجعة الاستعداد التشغيلي والتعاون المبكر والمسؤولية. | لا يلزم استنساخ حجم فريق Google أو بنيته. |
| SRC-SLO | [Google SRE Workbook: Implementing SLOs — كتاب SRE Workbook](https://sre.google/workbook/implementing-slos/) | ربط أهداف الاعتمادية باحتياج المستخدم وتكلفة الاعتمادية. | الأهداف تحدد لكل منتج؛ لا يفرض الإطار 99.99%. |
| SRC-OVERLOAD | [Google SRE: Handling Overload — كتاب SRE](https://sre.google/sre-book/handling-overload/) | التحكم بالحمل ومنع التضخم والانهيار تحت التشبع. | ضوابط واقعية حسب stack؛ لا يُجرى حمل على طرف غير مصرح. |
| SRC-MONITOR | [Google SRE: Monitoring Distributed Systems — كتاب SRE](https://sre.google/sre-book/monitoring-distributed-systems/) | latency/traffic/errors/saturation، والتفريق بين أعراض العطل وأسبابه. | إضافات EAOS تشمل ربط incident بالرحلة والـtenant مع تقليل البيانات. |
| SRC-SRETEST | [Google SRE: Testing for Reliability — كتاب SRE](https://sre.google/sre-book/testing-reliability/) | دور الاختبارات في تقليل مخاطر التغير وفحص الاعتمادية. | اختبارات الحزمة البنيوية ليست اختبار المنتج. |
| SRC-IDEMP | [Amazon Builders Library: Making retries safe — مقال أصلي](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | أثر الإعادات، هوية قصد العميل، الطلب المتأخر وتغير intent. | تفاصيل dedupe scope وatomicity يجب تكييفها مع المجال. |
| SRC-OUTBOX | [AWS Transactional outbox pattern — دليل أصلي](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | مشكلة dual write بين حالة البيانات والرسالة. | نمط اختياري عند الحاجة، وليس بنية إلزامية. |
| SRC-PGISO | [PostgreSQL Transaction Isolation — 18](https://www.postgresql.org/docs/18/transaction-iso.html) | دلالات العزل والأخطاء التزامنية والحاجة للتعامل مع إعادة المعاملة. | مثال adapter؛ لا نعمم semantics على قواعد أخرى. |
| SRC-PGCON | [PostgreSQL Constraints — 18](https://www.postgresql.org/docs/18/ddl-constraints.html) | حماية uniqueness وreferential integrity في التخزين. | افحص ما إذا كانت الدلالة التي يحتاجها المجال ممثلة فعلًا بالقيد. |
| SRC-PGINDEX | [PostgreSQL CREATE INDEX — 18](https://www.postgresql.org/docs/18/sql-createindex.html) | كلفة الفهارس وسلوك البناء المتزامن وحدوده. | لا يعمم CONCURRENTLY ولا rollback على جميع المحركات. |
| SRC-OAS | [OpenAPI Specification — 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) | وصف العقود والعمليات والمخططات بطريقة قابلة للمعالجة. | مرجع محدد الإصدار؛ ليس ادعاء أنه أحدث إصدار. |
| SRC-PROBLEM | [HTTP Problem Details — RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) | صياغة أخطاء API بعقد مفهوم وقابل للقراءة آليًا. | اتساق العقد مطلوب؛ تبني الصيغة نفسها ليس إلزاميًا. |
| SRC-STRIPE | [Stripe Webhooks — صفحة حية](https://docs.stripe.com/webhooks) | التوقيع والتكرار وعدم ضمان ترتيب الأحداث. | مثال provider؛ تحقق من عقد مزود الدفع الفعلي. |
| SRC-WCAG | [W3C WCAG — 2.2](https://www.w3.org/TR/WCAG22/) | مرجعية لإتاحة الاستخدام بما فيها التركيز والإدخال والمصادقة. | المراجعة المختصرة ليست إعلان مطابقة لجميع Success Criteria. |
| SRC-VITALS | [Google web.dev Web Vitals — صفحة حية](https://web.dev/articles/vitals) | LCP/INP/CLS كقياسات تجربة ويب فعلية. | اختبار مختبري مفرد لا يمثل جميع المستخدمين. |
| SRC-OTEL | [OpenTelemetry Signals — صفحة حية](https://opentelemetry.io/docs/concepts/signals/) | فصل وربط traces/metrics/logs والسياق بين المكونات. | لا يشترط OTEL إذا حققت أدوات أخرى نفس القدرة. |
| SRC-SLSA | [SLSA Specification — 1.2](https://slsa.dev/spec/v1.2/) | مصدر القطعة البرمجية وإثبات البناء والتحقق من سلسلة التوريد. | تم استبعاد v1.1 كنسخة retired؛ لا ادعاء اعتماد SLSA. |
| SRC-GHA | [GitHub Actions Secure Use — صفحة حية](https://docs.github.com/en/actions/reference/security/secure-use) | حدود ثقة CI، الأسرار، وتثبيت actions إلى commit موثوق. | تفاصيل GitHub adapter؛ المبدأ يعمم على أنظمة CI أخرى. |
| SRC-SSDF | [NIST Secure Software Development Framework — SP 800-218 v1.1](https://csrc.nist.gov/pubs/sp/800/218/final) | إدماج الأمن في التطوير والاستجابة للثغرات وحماية المخرجات. | مرجع محدد الإصدار؛ لا يمنح شهادة امتثال. |
| SRC-NEXT | [Next.js Backend for Frontend — وثائق الصفحة بتاريخ القراءة](https://nextjs.org/docs/app/guides/backend-for-frontend) | تصحيح الحكم المطلق على framework بقراءة قدراته وحدوده. | استُخدم لنقد تعميم المصدر فقط؛ الإطار مستقل عن Next.js. |
| SRC-LITM | [Lost in the Middle — arXiv:2307.03172v3](https://arxiv.org/abs/2307.03172) | أثر موضع المعلومة في السياق في مهام ونماذج دُرست؛ يبرر اختبار الاسترجاع لا ادعاء استحالة عامة. | قرئت صفحة البحث والملخص، لا كامل تجاربه. |
| SRC-KVCACHE | [Hugging Face: How caching works — وثائق حية](https://huggingface.co/docs/transformers/en/cache_explanation) | تمييز attention KV tensors عن قاموس key/value تطبيقي. | مرجع مفاهيمي لتصحيح المصطلح، لا تقييم stack الوكيل الحالي. |
| SRC-RAG | [Retrieval-Augmented Generation — arXiv:2005.11401](https://arxiv.org/abs/2005.11401) | الاسترجاع من ذاكرة خارجية لدعم التوليد؛ يختلف عن اختصار محادثة. | قرئت صفحة البحث والملخص؛ لا تُفرض vector database على مستودع. |
| SRC-REACT | [ReAct — arXiv:2210.03629](https://arxiv.org/abs/2210.03629) | التفاعل بين الاستدلال والفعل وملاحظة نتائج الأدوات. | قرئت صفحة البحث والملخص؛ لا يدعي EAOS تمثيل كل agent harness. |
| SRC-ATTN | [Attention Is All You Need — arXiv:1706.03762](https://arxiv.org/abs/1706.03762) | مرجع لبنية attention؛ تكلفة السياق تعتمد على الخوارزمية والمرحلة والتنفيذ. | لا تُستنتج حدود نموذج تجاري أو hardware سقفي من هذه الورقة. |

## مراجع أضيفت لتعميق البنية التحتية

- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html): إضافة منظور مسؤولية التشغيل وأمان البنية ومفاضلات الكلفة والاستدامة. حدود القراءة: قرئت المقدمة؛ الضوابط التفصيلية التالية synthesis وليست اقتباسًا لكل فصل AWS.
- [Kubernetes Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/): فصل network policy عن دعم CNI، وتدقيق واجهات الإدارة وRBAC وPod Security. حدود القراءة: أقسام security checklist ذات الصلة؛ لا تفرض Kubernetes على مشروع لا يستخدمه.

## مصادر الاتجاه المعماري في 2.0

- **VID-03** [هل لازم فعلاً أفهم الكود ولا لا؟ — Bashmohandes Mazen](https://www.youtube.com/watch?v=Pi6C1_91vUM): بذور: العقود والبنية والعلاقات، lifecycle، حدود التعديل. حدود الإثبات: قراءة كاملة للتفريغ، لا تحقق بصري متصل ولا وصول لريبو العرض. مصدر توضيح لا معيار إلزامي.
- **SRC-FOWLER-ARCH** [Software Architecture Guide — Martin Fowler](https://martinfowler.com/architecture/): تمييز القرارات المهمة الداخلية والقدرة على التطور عن تعقيد الشكل. حدود الإثبات: قرئت أقسام التعريف والجدوى والتطبيق؛ لا ادعاء قراءة كل الروابط.
- **SRC-STAMINA** [Design Stamina Hypothesis — Martin Fowler](https://martinfowler.com/bliki/DesignStaminaHypothesis.html): إطار تفكير في كلفة التغيير المتراكمة والاستثمار في التصميم. حدود الإثبات: فرضية مهنية يصفها المؤلف كذلك، ليست ضمان إنتاجية أو علاقة عددية مثبتة.
- **SRC-QAW** [Quality Attribute Workshops Third Edition — SEI](https://www.sei.cmu.edu/library/quality-attribute-workshops-qaws-third-edition/): استخدام سيناريوهات أصحاب المصلحة لتوضيح خصائص الجودة. حدود الإثبات: قرئت صفحة الملخص؛ صيغة السيناريوهات في الحزمة تصميم تشغيلي أصلي، لا ادعاء تنفيذ QAW أو ATAM كامل.
