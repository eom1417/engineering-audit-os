# EAOS — سجل الأدوات

> **ما هذه الوثيقة:** قرار كل أداة من أدوات البحث (52 أداة) ومعها أدوات التقارير: هل تدخل EAOS، وبأي دور، وفي أي مرحلة، وبأي معلم. ولكل أداة معتمدة: كيف تُثبَّت، وأي أمر يشغّلها، وماذا يُقرأ من مخرجها.
> **التحقق:** 2026-09-24، من صفحات المستودعات مباشرة: ملف الرخصة، وشارة الأرشفة، وتاريخ آخر التزام.
> **علاقتها بالوثائق الأخرى:**
> - `docs/MASTER-BLUEPRINT.md`: المراحل والتسلسل.
> - `docs/north-star.json`: المهام وأوامر قبولها.
> - `upstreams/registry.yaml`: الإصدار المثبّت لكل أداة **بعد** دمجها (المهمة NS17.T1).

---

## ١. خمسة أدوار: كيف نستفيد من أداة بأقل كود

المبدأ: **لا نعيد كتابة ما تفعله أداة ناضجة، ولا ننسخ كودها داخل EAOS.** كل أداة تبقى برنامجًا منفصلًا بإصدار مثبّت، وتتصل بـEAOS من أحد خمسة أبواب:

| الدور | ماذا يحدث | الكود الذي نكتبه | أمثلة |
|---|---|---|---|
| **تقرأ** (read) | يشغّلها EAOS على المشروع، ويقرأ مخرجها المنظم، ويحوّله إلى مفردات موحّدة | محوّل صغير. وللأدوات التي تُخرج SARIF: **قارئ واحد مشترك** وصفوف ترجمة في JSON | Syft، Semgrep، Trivy، Checkov، dependency-cruiser |
| **يولّد لها** (emit) | يكتب EAOS ملف إدخالها بصيغتها الأصلية من الحقائق | قالب نصي، ودالة تملؤه | سكربت k6، مواصفة Playwright، إعداد OpenTelemetry Collector |
| **تدقّق** (validate) | الأداة نفسها تحكم على ما ولّده EAOS: `k6 inspect`، و`sloth validate`، و`actionlint`… | لا شيء. أمر في السجل | كل ملف مولَّد |
| **تُشغَّل** (run) | تعمل على نسخة حية من المشروع داخل بيئة معزولة وبتفويض، ثم يُقرأ مخرجها | إعادة استخدام «تقرأ» | Playwright، k6، ZAP، Toxiproxy، Goss |
| **يوصي** (recommend) | تدخل الصورة المثالية للمشروع كقرار مسبَّب، ويولّد EAOS إعدادها الأولي في عدّة التسليم | لا شيء، أو قالب | Renovate، OpenTofu، SigNoz، Unleash، Traefik |

**لماذا هذا يقلل الكود:** ست أدوات (Semgrep وTrivy وCheckov وOSV-Scanner وSpectral وZAP) تُخرج SARIF 2.1.0. قارئ واحد (NS17.T2) يجعل محوّل كل منها نحو 20 سطرًا. وأدوات التشغيل لا نكتب لها محرّكات: نكتب لها **ملفات إدخال** وتقرر هي صحتها. ويبقى عملنا في ثلاثة أشياء: الربط بين الأدلة، والقرار بقواعد مكتوبة، وكتابة التقرير.

---

## ٢. سياسة الاعتماد

لا تدخل أداة إلا إذا اجتازت الشروط الستة:

1. **رخصة تسمح بتشغيلها كعملية منفصلة في مشروع مفتوح المصدر مجاني وغير تجاري** (قرار المالك في 2026-09-24). الأداة تبقى عملية منفصلة ولا يُضمَّن كودها، فرخص AGPL (k6 وRenovate وUnleash وPyroscope) ورخصة PolyForm Noncommercial (GitNexus) مقبولة. **وما تمنع رخصته التوزيع لا يُنسخ إلى مستودع EAOS**، بل يجلبه `eaos tools install` إلى جهاز المستخدم (مكتبة قواعد Semgrep الرسمية).
2. **نشطة:** التزام خلال آخر 12 شهرًا، وغير مؤرشفة.
3. **مخرج أو إدخال منظم:** JSON أو SARIF أو CycloneDX أو YAML موثّق.
4. **تعمل دون اتصال** في عقد التقييم. الاستثناء: قواعد بيانات الثغرات، وتُحدَّث قبل التشغيل وتُسجَّل نسختها.
5. **إصدار مثبّت ومعه عيّنة عقد** في `tests/contracts/`: إن غيّرت الأداة شكل مخرجها بصمت، فشل الاختبار.
6. **لا تكرر قدرة موجودة** إلا كشاهد مستقل يرفع الثقة في ادعاء.

---

## ٣. سجل القرار: كل الأدوات

**مفتاح القرار:**
- **أساسية:** تدخل عقد التقييم، وتعمل على كل مشروع تنطبق عليه.
- **تنفيذ:** تدخل عقد التنفيذ، في بيئة معزولة.
- **مشروطة:** تعمل فقط حين يتحقق شرط (لغة، أو Docker، أو OpenAPI).
- **توصية:** لا يشغّلها EAOS؛ تدخل الصورة المثالية وعدّة التسليم.
- **اختيارية:** شاهد إضافي، لا تدخل البوابات.
- **مرفوضة:** مع سببها وبديلها.

| # | الأداة | الرخصة | آخر التزام | القرار | الدور | المرحلة | المعلم |
|---|---|---|---|---|---|---|---|
| 1 | GitNexus | PolyForm Noncommercial 1.0.0 (مقبولة: EAOS غير تجاري) | 2026-09-24 | أساسية، على نسخة لا على المشروع | تقرأ | S02، S04 | NS12.T10 |
| 2 | Syft | Apache-2.0 | 2026-09-23 | أساسية | تقرأ | S01 | NS12.T1 |
| 3 | scc | MIT | 2026-09-24 | أساسية | تقرأ | S01، S03 | NS12.T2 |
| 4 | Stratify | MIT | 2026-02-15 | مرفوضة (§٥) | — | — | — |
| 5 | Structurizr (`structurizr/structurizr`) | Apache-2.0 | 2026-09-19 | أساسية كصيغة | يولّد لها | S02، S06 | NS13 |
| 6 | ArchUnit | Apache-2.0 | 2026-09-23 | مشروطة: Java | يولّد لها | S06، S15 | NS25.T1 |
| 7 | SonarQube Community Build | LGPL-3.0 | 2026-09-23 | اختيارية وتوصية | تقرأ (Web API) | S04، S15 | — |
| 8 | jscpd | MIT | 2026-09-23 | **مدمجة** | تقرأ | S03، S04 | قائمة |
| 9 | Lizard | MIT | 2026-09-16 | اختيارية | تقرأ | S03 | — |
| 10 | dependency-cruiser | MIT | 2026-09-23 | أساسية: JS/TS | تقرأ، يولّد لها | S02، S04، S15 | NS12.T6، NS25.T1 |
| 11 | Code Maat | GPL-3.0 | 2025-07-03 | مرفوضة (§٥) | — | — | — |
| 12 | Renovate | AGPL-3.0 | 2026-09-24 | توصية وتنفيذ | يولّد لها، تدقّق، تُشغَّل | S06، S08، S15 | NS25.T1 |
| 13 | OSV-Scanner | Apache-2.0 | 2026-09-24 | أساسية | تقرأ (SARIF) | S01، S04، S10 | NS12.T1 |
| 14 | ApprovalTests (Java، Python، Node) | Apache-2.0 | 2026-09-24 | تنفيذ: حسب اللغة | يولّد لها، تُشغَّل | S05، S09 | NS15.T1، NS26.T1 |
| 15 | Pact JS | MIT | 2026-09-23 | مشروطة: واجهة تنادي خادمًا للمشروع | يولّد لها، تُشغَّل | S05، S09 | NS15.T1 |
| 16 | Playwright | Apache-2.0 | 2026-09-24 | تنفيذ: **أساس شبكة الأمان للويب** | يولّد لها، تُشغَّل | S05، S09 | NS15.T1، NS26.T1 |
| 17 | Sloth | Apache-2.0 | 2026-05-26 | توصية | يولّد لها، تدقّق | S13 | NS25.T2 |
| 18 | k6 | AGPL-3.0 | 2026-09-23 | تنفيذ | يولّد لها، تدقّق، تُشغَّل | S05، S11 | NS15.T2، NS26.T2، NS22 |
| 19 | OpenTelemetry Collector | Apache-2.0 | 2026-09-24 | تنفيذ وتوصية | يولّد لها، تدقّق، تُشغَّل | S13 | NS25.T2، NS24 |
| 20 | MADR | MIT | 2026-08-28 | أساسية كصيغة | يولّد لها | S06 | NS13.T3 |
| 21 | Log4brains | Apache-2.0 | 2024-12-17 | مرفوضة (§٥) | — | — | — |
| 22 | adr-tools | GPL-3.0 | 2020-03-30 | مرفوضة (§٥) | — | — | — |
| 23 | OpenRewrite | Apache-2.0 | 2026-09-24 | مشروطة: Java | تُشغَّل | S07، S08 | NS8.T6 |
| 24 | jscodeshift | MIT | 2026-07-15 | تنفيذ: JS/TS | تُشغَّل | S07، S08 | NS8.T6 |
| 25 | Unleash | AGPL-3.0 | 2026-09-24 | توصية: Strangler | يوصي | S06، S08 | NS7.T3، NS8.T2 |
| 26 | Traefik | MIT | 2026-09-23 | توصية: Strangler بخادم | يوصي | S06، S08 | NS7.T3، NS8.T2 |
| 27 | SchemaSpy | LGPL-3.0 | 2026-03-05 | اختيارية | تُشغَّل | S09 | — |
| 28 | Liquibase | **FSL-1.1-ALv2** (ليست مفتوحة بتعريف OSI) | 2026-09-22 | توصية مشروطة: JVM | يوصي | S06 | NS7.T3 |
| 29 | SQLFluff | MIT | 2026-09-23 | أساسية: ملفات SQL | تقرأ | S04 | NS12.T7 |
| 30 | Bytebase | مختلطة (أجزاء enterprise برخصة خاصة) | 2026-09-24 | توصية نادرة | يوصي | S06 | — |
| 31 | Spectral | Apache-2.0 | 2026-09-17 | مشروطة: OpenAPI | تقرأ (SARIF) | S04 | NS12.T8 |
| 32 | Schemathesis | MIT | 2026-09-23 | مشروطة: OpenAPI | يولّد لها، تُشغَّل | S05، S09 | NS15.T1 |
| 33 | oasdiff | Apache-2.0 | 2026-09-16 | مشروطة: OpenAPI | تقرأ | S04، S09، S15 | NS12.T8، NS20 |
| 34 | Semgrep (المحرّك، والقواعد الرسمية تُجلب لجهاز المستخدم) | LGPL-2.1 | 2026-09-23 | أساسية: قواعدنا والرسمية | تقرأ (SARIF)، يولّد لها | S04، S10، S15 | NS12.T3، NS25.T1 |
| 35 | Trivy | Apache-2.0 | 2026-09-23 | أساسية | تقرأ (SARIF) | S04، S10 | NS12.T4، NS21 |
| 36 | OWASP ZAP | Apache-2.0 | 2026-09-24 | تنفيذ | يولّد لها، تُشغَّل | S10 | NS15.T2، NS21 |
| 37 | GitHub Actions Runner | MIT | 2026-09-22 | لا تكامل | — | S15 | — (EAOS يولّد سير العمل الذي يشغّله) |
| 38 | pre-commit | MIT | 2026-08-17 | توصية وتنفيذ | يولّد لها، تدقّق، تُشغَّل | S14، S15 | NS25.T1، NS16 |
| 39 | act | MIT | 2026-06-01 | مشروطة: Docker | تُشغَّل | S14 | NS16 |
| 40 | OpenTofu | MPL-2.0 | 2026-09-24 | توصية | يوصي | S06 | NS7.T3 |
| 41 | Ansible | GPL-3.0 | 2026-09-22 | توصية مشروطة: خوادم | يوصي | S06 | NS7.T3 |
| 42 | Checkov | Apache-2.0 | 2026-09-17 | أساسية: CI أو IaC | تقرأ (SARIF) | S04، S10 | NS12.T5 |
| 43 | SigNoz | MIT للنواة (مجلد `ee/` برخصة خاصة) | 2026-09-24 | توصية | يوصي | S13 | NS7.T3، NS25.T2 |
| 44 | (مكررة مع 19) OpenTelemetry Collector | — | — | — | — | — | — |
| 45 | Grafana Pyroscope | AGPL-3.0 | 2026-09-24 | اختيارية | تُشغَّل | S11 | NS22 |
| 46 | Toxiproxy | MIT | 2026-08-25 | تنفيذ | يولّد لها، تُشغَّل | S05، S12 | NS15.T2، NS23 |
| 47 | Pumba | Apache-2.0 | 2026-08-27 | مشروطة: Docker | تُشغَّل | S12 | NS23 |
| 48 | Chaos Mesh | Apache-2.0 | 2026-09-06 | توصية مشروطة: Kubernetes | يوصي | S12 | — |
| 49 | Goss | Apache-2.0 | 2026-09-14 | تنفيذ | يولّد لها، تدقّق، تُشغَّل | S14 | NS25.T3، NS16 |
| 50 | OpenSSF Scorecard | Apache-2.0 | 2026-09-08 | مشروطة: GitHub ورمز وصول | تقرأ | S10، S15 | NS21 |
| 51 | Apache DevLake | Apache-2.0 | 2026-09-23 | توصية | يوصي | S15 | — |
| 52 | MkDocs | BSD-2-Clause | 2025-10-20 | يُستبدل بـ**Zensical** | — | S15 | NS25.T4 |

**الحصيلة:**
- **أساسية لعقد التقييم (11):** Syft، وscc، وOSV-Scanner، وSemgrep، وTrivy، وCheckov، وdependency-cruiser، وSQLFluff، وSpectral، وoasdiff، وGitNexus. تُضاف إلى 4 محرّكات مدمجة: CodeGraph، وenola، وjscpd، وreforge.
- **تنفيذ (9، منها مشروطة):** Playwright، وApprovalTests، وPact، وSchemathesis، وk6، وZAP، وToxiproxy، وGoss، وOpenTelemetry Collector. يولّد EAOS إدخالها في عقد التقييم، وتُشغَّل في عقد التنفيذ.
- **توصية:** Renovate، وpre-commit، وSloth، وSigNoz، وOpenTofu، وAnsible، وUnleash، وTraefik، وLiquibase، وBytebase، وChaos Mesh، وDevLake، وSonarQube. تدخل الصورة المثالية بقرار مسبَّب، و«لا حاجة» قرار مقبول بسببه.
- **مرفوضة (5):** Stratify، وCode Maat، وLog4brains، وadr-tools، وMkDocs (يحل محلها Zensical). **لا شيء منها رُفض لرخصته**: الأسباب تكرار القدرة أو توقف التطوير.

---

## ٤. بطاقات التكامل

كل سطر هنا يصير حقل `install` و`command` في `upstreams/registry.yaml` عند دمج الأداة. الإصدار يُثبَّت **يوم التنفيذ** على آخر إصدار مستقر، ومعه sha256 للملفات الثنائية.

### عقد التقييم: أدوات تقرأ المشروع ولا تشغّله

| الأداة | التثبيت | الأمر (TARGET مشروع للقراءة فقط) | المخرج | يدخل EAOS كـ |
|---|---|---|---|---|
| Syft | release (ملف ثنائي) | `syft dir:TARGET -o cyclonedx-json=sbom.cdx.json` | CycloneDX | `sbom.cdx.json` كما هو، وعدد المكوّنات |
| OSV-Scanner | release | `osv-scanner scan --sbom sbom.cdx.json --format sarif` | SARIF | `vulnerable_dependency`، وادعاء risk بعلاج «ترقية» |
| scc | release | `scc --format json --by-file TARGET` | JSON | `loc` واللغة لكل ملف في `measurements.json` |
| Semgrep | pip، والقواعد الرسمية `git clone` عند التزام مثبّت إلى `engine-tools/semgrep-rules` | `semgrep scan --config eaos/data/semgrep --config engine-tools/semgrep-rules/<لغة> --sarif --metrics off TARGET` | SARIF | `vulnerability` و`boundary` و`dataflow` |
| GitNexus | npm | على نسخة من المشروع: `gitnexus analyze COPY --skip-agents-md --skip-skills --skip-embeddings` مع `GITNEXUS_HOME` في workdir، ثم `gitnexus cypher` و`gitnexus impact` | مخرج الاستعلام (يُثبَّت شكله في عيّنة العقد) | `call_edge_external` و`module_edge_external` و`coupling` والمجتمعات مرشحةً لحدود المكوّنات |
| Trivy | release | `trivy fs --scanners vuln,secret,misconfig --format sarif TARGET` | SARIF | `vulnerability` و`misconfiguration` و`secret` (شاهد ثانٍ على المفاتيح) |
| Checkov | pip | `checkov -d TARGET -o sarif --quiet` | SARIF | `misconfiguration` في CI وIaC وDocker |
| dependency-cruiser | npm | `depcruise TARGET --config <workdir>/rules.cjs --output-type json` | JSON | `module_edge_external` و`cycle` و`boundary` |
| SQLFluff | pip | `sqlfluff lint --format json --dialect postgres <ملفات .sql>` | JSON | `sql_quality`؛ فئات الخطر فقط تصير ادعاءات |
| Spectral | npm | `spectral lint -f sarif <openapi>` | SARIF | `api_contract` |
| oasdiff | release | `oasdiff breaking <old> <new> -f json` | JSON | `api_contract`: الكسر بين إصدارين |
| Lizard (اختياري) | pip | `lizard --xml TARGET` | XML (cppncss) | شاهد ثالث على `complexity` |

### ما يولّده EAOS، والمدقق الذي يحكم عليه

| الملف المولَّد | من أي حقائق | المدقق (الأداة نفسها) | المعلم |
|---|---|---|---|
| `architecture/*/workspace.dsl` | الحاويات والمكوّنات والتكاملات | اختبار البنية النحوية (Structurizr يحتاج Java، فلا يدخل الافتراضي) | NS13 |
| `adr/ADR-NNN.md` بصيغة MADR | `decisions[]` | markdownlint-cli2 وVale | NS13.T3 |
| `behavior-lock/*.spec.ts` | الأسطح والوظائف | `npx playwright test --list` | NS15.T1 |
| `nfr/k6/*.js` | سيناريوهات الحمل ونموذج الحمل | `k6 inspect` | NS15.T2 |
| `nfr/toxiproxy.json` و`nfr/experiments.json` | الاعتماديات الخارجية | مخطط JSON في الاختبار | NS15.T2 |
| `nfr/zap.yaml` | الأسطح | مخطط JSON في الاختبار | NS15.T2 |
| `.github/workflows/eaos.yml` | ما ينطبق على المشروع | `actionlint` (MIT، 2026-04-19) | NS25.T1 |
| `.pre-commit-config.yaml` | الأدوات المنطبقة | `pre-commit validate-config` | NS25.T1 |
| `renovate.json` | مدير الحزم | `renovate-config-validator` | NS25.T1 |
| `.dependency-cruiser.cjs` | الحدود المستهدفة | `depcruise --validate` | NS25.T1 |
| قواعد Semgrep | الحدود والاتفاقيات | `semgrep --validate --config` | NS25.T1 |
| `otel/collector.yaml` | المكدّس | `otelcol-contrib validate --config` | NS25.T2 |
| `slo/*.yaml` | سيناريوهات الجودة | `sloth validate -i` | NS25.T2 |
| `readiness/goss.yaml` | الصورة المثالية | `goss render` | NS25.T3 |
| `handover/mkdocs.yml` مع `docs/` | التقارير الأربعة وADR والرسوم | `zensical build` | NS25.T4 |
| `plan.json → tasks[].codemod` | البطاقات الآلية | `jscodeshift --dry` على نسخة | NS8.T6 |

### عقد التنفيذ: أدوات تعمل على نسخة حية داخل البيئة المعزولة

| الأداة | التثبيت | الأمر | يُكتب إلى |
|---|---|---|---|
| Playwright | npm مع متصفحاته | `npx playwright test --reporter=json` | `behavior-lock/results*.json` |
| Schemathesis | pip | `schemathesis run <openapi> --url BASE_URL` | `behavior-lock/results*.json` |
| k6 | release | `k6 run --summary-export out.json nfr/k6/<s>.js` | `runtime/performance.json` |
| OWASP ZAP | tarball، ويحتاج Java 17 | `zap.sh -cmd -autorun nfr/zap.yaml` | `runtime/security.json` |
| Toxiproxy | release | `toxiproxy-server -config nfr/toxiproxy.json`، ثم `toxiproxy-cli toxic add …` | `runtime/resilience.json` |
| OpenTelemetry Collector | release (contrib) | `otelcol-contrib --config otel/collector.yaml` مع مصدّر file | `runtime/telemetry.json` |
| Goss | release | `goss -g readiness/goss.yaml validate --format json` | `PRODUCTION-READINESS.json` |
| pre-commit | pip | `pre-commit run --all-files` | `PRODUCTION-READINESS.json` |
| Pumba، act | release | يحتاجان Docker | يُسجلان «غير منطبق» بسببه إن غاب |

---

## ٥. المرفوضة: لماذا، وما البديل

| الأداة | السبب | ما يغطي قدرتها |
|---|---|---|
| **Stratify** | تكرر الرسم والتصوير، وتركيزها على Clojure | CodeGraph وdependency-cruiser وMermaid |
| **Code Maat** | آخر التزام 2025-07-03، ويحتاج JVM | `eaos/facts/history.py`: التقلّب، والاقتران الزمني، والملكية |
| **Log4brains** | آخر التزام 2024-12-17 | EAOS يكتب MADR مباشرة، ويعرضها موقع التسليم (Zensical) |
| **adr-tools** | آخر التزام 2020-03-30 | EAOS يكتب MADR مباشرة |
| **MkDocs** | آخر التزام 2025-10-20، وفريق Material انتقل إلى Zensical (MIT، نشط) | **Zensical**، ويقرأ `mkdocs.yml` نفسه |

**ملاحظات على رخص المقبولة:**
- **Liquibase** صارت FSL: تتحول إلى Apache بعد سنتين، وتمنع المنافسة التجارية. لذلك توصي بها الصورة المثالية لمشاريع JVM فقط، وتفضّل أداة المكدّس الأصلية (Supabase CLI، أو Prisma، أو Alembic).
- **OpenRewrite:** المحرّك Apache-2.0، لكن بعض وحدات الوصفات برخصة Moderne الخاصة. تُفحص رخصة كل وحدة قبل استخدامها.
- **Semgrep:** المحرّك LGPL-2.1. مكتبة القواعد الرسمية رخصتها (Semgrep Rules License v1.0) **تمنع توزيعها**، ولا علاقة لها بالتجاري: تُجلب إلى جهاز كل مستخدم ولا تُنسخ إلى مستودع EAOS. قواعدنا في `eaos/data/semgrep/` تُوزَّع معه.
- **GitNexus:** رخصتها PolyForm Noncommercial، وهي مقبولة لأن EAOS مفتوح المصدر وغير تجاري. لكن **مستخدم EAOS الذي يشغّله داخل شركة تجارية ملزم برخصتها**، لذلك يطبع `eaos tools install` تنبيهًا عند تثبيتها، ويستطيع المستخدم استبعادها بـ`--skip gitnexus` دون أن تفشل البوابات، لأن CodeGraph وdependency-cruiser يغطيان قدرتها الأساسية.
- **`gitnexus analyze` يكتب في المستودع** (AGENTS.md وCLAUDE.md وskills وhooks)، فلا يُشغَّل إلا على نسخة من المشروع.

---

## ٦. أدوات كتابة التقارير

| الطبقة | الأداة | الرخصة | الدور |
|---|---|---|---|
| المصدر | Markdown مع توأم JSON | — | موجود اليوم |
| الرسوم | **Mermaid** | MIT | C4 والتدفقات، وتُعرض مباشرة على GitHub |
| نموذج العمارة | **Structurizr DSL** (صيغة)، و**LikeC4** بديل عرض (MIT) | Apache-2.0 | النموذج الحالي والمستهدف من مصدر نصي واحد |
| الأسلوب | **Vale** بحزمة EAOS | MIT | يرفض الكلام المبهم، ويفرض ربط كل رقم بدليل |
| البنية | **markdownlint-cli2** | MIT | العناوين والجداول والروابط |
| PDF | **Typst** | Apache-2.0 | ملخص تنفيذي بصفحة واحدة (NS14.T3) |
| الموقع | **Zensical** | MIT | موقع التسليم للمالك (NS25.T4) |

---

## ٧. قيود البيئة الحالية

| القيد | أثره | كيف تتعامل معه الخطة |
|---|---|---|
| لا Docker في الحاوية الحالية | Pumba، وact، وTrivy image، ونصوص ZAP المعلّبة | backend العزل يتدرج: docker، ثم `unshare`، ثم process مع قيد مسجل (NS17.T5). الأدوات المعتمدة على Docker تُسجل «غير منطبق» بسببه |
| لا Java | ZAP، وSchemaSpy، وOpenRewrite، وArchUnit، وعرض Structurizr | ZAP وحده يدخل البوابات: `eaos tools install` يطبع سطر تثبيت Java 17 ولا يثبّته بصمت |
| لا Kubernetes | Chaos Mesh | توصية فقط لمشاريع Kubernetes |
| لا مزوّد نموذج مضبوط | مرحلة S08 بالنموذج | البطاقات الآلية تُنفَّذ بأدواتها (NS8.T6) دون نموذج |
