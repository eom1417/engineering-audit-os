# Taxonomy

| ID | Domain | Applies when | Controls |
|---|---|---|---|
| 01 | Discovery & Inventory | كل مستودع؛ بعض عناصر الجرد تصبح N/A بدليل | 4 |
| 02 | Architecture & Domain Boundaries | كل مشروع؛ عمق الرسم يتناسب مع حجمه | 6 |
| 03 | Product Logic & State Machines | كل منتج ذي وظائف؛ حجم العينة لا يخفي رحلات حرجة | 4 |
| 04 | Code Quality & Maintainability | الكود المملوك للمشروع | 5 |
| 05 | Security & Data Flow | أي مدخل غير موثوق أو بيانات حساسة أو سطح شبكي | 10 |
| 06 | Authentication & Session Lifecycle | مشروع به مستخدمون أو machine identities أو token exchange | 6 |
| 07 | Authorization & Permissions | بيانات أو عمليات تختلف صلاحياتها بحسب هوية أو سياق | 5 |
| 08 | Database & Data Integrity | كل تخزين دائم؛ اختر adapter للمحرك الفعلي | 10 |
| 09 | API Contracts & Integration | HTTP/RPC/GraphQL/WebSocket أو تكامل خارجي | 6 |
| 10 | Frontend State & Rendering | واجهة متصفح أو PWA | 6 |
| 11 | Performance & Capacity | كل منتج؛ الحمل الفعلي أو المتوقع موثق | 5 |
| 12 | Reliability & Distributed Failure | اتصالات أو أعمال خلفية أو حالة حرجة؛ ليس microservices فقط | 8 |
| 13 | SaaS Tenancy & Organization Lifecycle | عدة مؤسسات أو tenants أو فرق تشترك بالمنصة | 6 |
| 14 | Subscriptions Billing & Entitlements | دفع أو اشتراك أو metering أو حدود خطط | 6 |
| 15 | Testing Strategy & Quality | كل مشروع؛ نوع الاختبارات يتبع المخاطر | 5 |
| 16 | Infrastructure Deployment & Recovery | أي منتج منشور أو مخطط لنشره | 12 |
| 17 | CI/CD & Build Integrity | أي سلسلة بناء أو نشر آلي/يدوي | 5 |
| 18 | Observability & Incident Diagnosis | أي خدمة أو رحلة إنتاجية لها أثر يستدعي التحقيق | 5 |
| 19 | UX Robustness Mobile & Recovery | واجهة يستخدمها أشخاص | 5 |
| 20 | Accessibility | أي واجهة بشرية؛ حدد مستوى الهدف ونطاق WCAG | 4 |
| 21 | Dependencies & Supply Chain | أي مكتبات أو أدوات بناء أو artifacts خارجية | 5 |
| 22 | Configuration Documentation & Operations | كل مشروع؛ العمق بحسب تشغيله | 4 |
| 23 | Privacy Data Lifecycle & Exports | بيانات شخصية/حساسة أو retention/export/delete | 4 |
| 24 | Time Scheduling & Constraint Systems | جدولة أو حجوزات أو recurrence أو quota windows أو وظائف زمنية | 5 |
| 25 | AI Features & Agent Boundaries | منتج يستخدم LLM/RAG/tools/generated actions؛ ليس لمجرد أن الكود كُتب بالـAI | 5 |
| 26 | AI Audit Execution Context & Handoffs | كل تشغيل لهذا الإطار بواسطة coding agent؛ التفويض متعدد الوكلاء اختياري ومشروط | 5 |
| 27 | Architecture Structure Maintainability & Evolution | المحور الأساسي لكل منتج؛ يخصص العمق حسب الحجم والعمر والتغير المتوقع | 14 |
