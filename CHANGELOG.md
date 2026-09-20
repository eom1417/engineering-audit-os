# Changelog

## Unreleased

- Verify the isolated copy as a whole tree: any file added, removed or modified outside the planned task files now blocks `VERIFIED_IN_ISOLATED_COPY`, and `changes.patch` is derived from the real difference between the original and the delivered candidate. Two regression tests, one reproducing the prior defect where a check could create an unplanned file and still reach a verified state.
- Derive the expected packaged data set from canonical sources instead of the files that happen to exist, so a missing, stale or leftover packaged file fails validation. New `tests/test_packaging.py`.
- Add a deterministic fact layer (`eaos/facts/`) with nine extractors: multi-language syntax (tree-sitter, optional extra), import resolution to real file targets, entry-point detection through framework plugins, configuration and environment reads, size/branching/duplication metrics, repository history, domain constants and data models, the dependency graph with a declared attention ranking, and static flow traces from each entry point. Per-file results are cached by content hash; a cached run is cheaper but byte-identical.
- Add `eaos map`: a full structural picture (system map, coupling atlas, evolution lens) with no model call, in about a second on a mid-size repository.
- Add a unified claim ledger (`eaos/claims.py`, `schemas/claim.schema.json`): every assertion carries confidence, method, evidence or facts, and a mandatory falsifier. Existing findings, architecture records and flows bridge into it without gaining certainty.
- Add `eaos dossier`: assembles `dossier.json` and derives every human artifact from it, under an output contract (`eaos/compose/rules.py`, rules R1–R8) that fails the build on an unsourced claim, a budget overrun, a live risk with no disposition, a task with no runnable acceptance command, or a record dump in a human artifact.
- Add `eaos probe`: re-decides claims mechanically. A claim can declare `probe_spec`, so it stays testable on later snapshots; a failing probe marks it REFUTED and keeps it in the ledger.
- Add `eaos verify --execute`: runs the test suite with coverage in an isolated copy and maps real execution onto components and entry points, so a claim can be confirmed by something that ran.
- Add `eaos delta`: compares two dossiers and exits nonzero on a new confirmed or likely risk, making the tool usable as a CI drift gate.
- Add `eaos ask`: answers strictly from recorded facts and claims with citations, and says plainly when nothing in the records answers the question.
- Add `eaos site`: one self-contained HTML page with navigation and search, rendering the same records.
- Add `eaos evaluate`: measures detection against benchmark cases with declared ground truth and against a grep baseline, and states what was not measured.
- Feed deterministic facts into the model pipeline: the audit now inspects files in attention order and can declare a file budget, with deferred files recorded as omissions rather than silently dropped.
- Add `verify_command` to the roadmap task contract so a task's acceptance criterion can be executed rather than described.
- Add `--exclude` to `eaos map`, `eaos dossier` and `eaos facts`: leave vendored or fixture paths out of analysis, with the exclusion reported in the output rather than applied silently.
- Add `eaos facts <target> --out <dir> --history`: deterministic repository-history facts (churn, co-change, ownership, age, fix density) with no model call. Commit subjects are classified then discarded, so commit text never enters the fact set. Reruns on the same input are byte-identical; timestamps live in `facts/run.json`, not in fact records.
- Redact source with whole-file context before selecting line ranges, preventing multiline private-key bodies from leaking through partial reads or chunk boundaries. Added two regression tests.
- Correct SECURITY.md to distinguish local audit commands, network/command model providers, and isolated-copy remediation.
- Add local development instructions and an Arabic technical review.

## 2.0.0 — 2026-09-17

تغيير محور المنتج إلى Architecture / Structure / Maintainability / Evolvability. إضافة14 قاعدة مستقلة في مجال27، نموذج معماري بأدلة وعقود وملكية قواعد وسيناريوهات تغير، واستعلامات graph/impact/context. default profile architecture مع مجالات مساندة out of scope صراحةً، وfull يحافظ على التغطية العامة. لا ترقية صامتة لسجلات1.0؛ أنشئ run جديدًا. أضيف تحليل الفيديو الثالث وثلاثة مراجع معمارية، مع فصل البذور عن القواعد المعيارية. لا استخراج AST تلقائي ولا LLM provider invocation.

## 1.0.0 — 2026-09-17

إصدار أول للإطار العام وCLI الجرد والأدلة والتحقق وحزم السياق والاستئناف؛ تحليل نصي للفيديوين الأولين. النسخة محفوظة في تاريخ git.
