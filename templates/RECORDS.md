# عقد السجلات

`init` ينشئ arrays فارغة. الوكيل يملؤها بـJSON؛ لا تعوّض محتوى placeholder عن الملاحظة. revision هو fingerprint inventory وليس commit Git. احفظ commit وdeployment revision كـevidence إضافي عند توفرهما. لا يُنشر محتوى السجلات افتراضيًا.

## evidence.json

```json
[{"id":"E-001","kind":"source","location":"src/path:10-25","revision":"COPY_RUN_REVISION","observed_at":"ISO8601","observation":"Concrete observed behavior","method":"Inspected handler and callers","limitations":"Runtime path not executed"}]
```

kind: source/runtime/test/configuration/requirement/external/absence_search. absence_search يحتاج أيضًا search_scope، queries، shared_controls_checked، remaining_unknowns كنصوص صريحة؛ استخدم `none known after ...` عند عدم وجود مجهول وليس string فارغ. المصدر السلبي يحدد corpus؛ لا يدعي عدم وجود شيء خارج corpus. يمكن إضافة hash، environment، command، exit_code، redacted_output، actor، tenant، expected/actual بدون تضمين secrets.

## coverage.json

```json
[{"id":"C-001","control_id":"EAOS-07-001","component":"API","flow":"export","environment":"isolated-test","revision":"COPY_RUN_REVISION","status":"not_run","rationale":"Pending role matrix execution","evidence_ids":[],"finding_ids":[]}]
```

الوحدة control × component × flow × environment؛ أنشئ عدة instances للمسارات الحرجة. `expected_instances` في run يحتوي كل IDs المعلنة؛ `pass` لا يغطي تلقائيًا مسارًا آخر. حالات not_applicable تحتاج سببًا ودليلًا. fail يربط finding. لا تنسَ admin/background/batch paths. الآلة لا تستطيع اكتشاف flow أخفاه الوكيل في تعريف scope؛ يتحقق reviewer من تطابق inventory وexpected_instances.

## gates.json

```json
[{"id":"G-001","name":"integration","status":"not_run","revision":"COPY_RUN_REVISION","rationale":"Cross-tenant regression pending","evidence_ids":[]}]
```

لكل gate سجل command/environment/expected/actual في evidence. حالات pass/fail تتطلب دليل تنفيذ. لا يُسجل pass عند تعذر dependencies أو credentials. لا يستلزم audit-only تشغيل كل gate غير ذي صلة؛ remediation يحدد بوابات التغيير قبل التعديل.

## decisions.json

```json
[{"id":"D-001","decision":"Keep modular monolith","reason":"No independent scaling/deployment requirement established","alternatives":["microservices"],"evidence_ids":["E-001"],"revisit_when":"Independent ownership or SLO constraints appear"}]
```

## fix-plan.json

```json
{"finding_ids":[],"root_cause":"UNVERIFIED","invariant":"DEFINE","current_design_failure":"DEFINE","options":[],"selected_option":"DEFINE","least_intrusive_alternative":"DEFINE","cost":"ESTIMATE_WITH_ASSUMPTIONS","risks":[],"affected_flows":[],"authorized_scope":"DEFINE","tests_before_change":[],"verification_gates":[],"rollback_or_rollforward":"DEFINE","stop_conditions":[]}
```

## finding.json

انسخ template المقابل. `impacts` يتضمن security/performance/reliability/maintainability/user/business؛ استخدم `NONE_OBSERVED` مع تفسير بدل اختراع أثر في كل بُعد. dependencies تشمل IDs findings أو تغيرات prerequisite. `required_tests` أوصاف assertions لا أسماء ملفات فقط. confirmed root cause يحتاج دليل مستقل إن لم يكن متضمنًا في trace. لا يوجد field يسمى NOT_APPLICABLE داخل finding؛ هذا قرار applicability في coverage.

JSON schemas تصف الشكل الأساسي، والـCLI يضيف الشروط المشتركة بين السجلات. فاحص CLI ليس تطبيقًا عامًا لكل Draft 2020-12. `required_gate_ids` تحدد قبل الإصلاح، ولا يكفي اختيار gate ناجح واحد وتجاهل البقية.
