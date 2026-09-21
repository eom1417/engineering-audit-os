# Changelog

## Unreleased

- A probe now only settles what it can actually settle. A branch-count measurement confirmed a claim about *why* the branches existed; a static check can show that a structure exists but not why, so a claim of cause or responsibility rises to LIKELY at most and the probe is recorded as PARTIAL with the reason.
- Dependency probes can be directional. A claim that one layer must not import another was refuted by an edge running the other way, which is allowed; `direction: one_way` distinguishes the two and reports the reverse edge instead of contradicting the claim.
- An unproven claim now produces an investigation task rather than nothing: prove it or drop it, with no code change until it is decided, and the acceptance criterion is the probe returning a verdict.

- Add `eaos semantic`: the model reads the fact digest and the confirmed claims — never raw files — and may only return interpretations that cite facts already held, each with a falsifier. Model inference can never reach CONFIRMED on its own; a probe has to do that. This is the path that assesses responsibilities, boundaries and internal contracts, and it is labelled as inference throughout.
- Enforce a declared policy as part of the dossier, so a forbidden edge becomes a claim with a task card rather than a separate report.
- Extend the benchmark corpus to nine cases covering every claim class the tool detects, and measure the plan as well as the detection: 8 of 8 planted defects found, no false positives, against 1 of 8 for the grep baseline, with a complete and runnable card for every actionable finding.
- Add `README.md` to the dossier: an index with a reading order for four kinds of reader, and a grade for how well each section is sourced — including the plain statement that responsibilities and internal contracts are not assessed without the model path.
- Add `ONBOARDING.md`: build and test commands taken from declared manifests, the entry points worth trying, the ten files to read first ordered by the graph, the project's own vocabulary, and the traps this snapshot already knows about.
- Render claims in the reader's language from a template and its parameters, and link every finding in the brief to the artifact holding its detail. The Arabic dossier no longer mixes Arabic headings with English sentences.
- Rank answers by structure rather than word overlap, and suggest the next command after every answer. "what handles POST /orders" now returns the entry point first.
- Add `eaos policy check` and `eaos policy init`: the project declares its layers and the dependencies it forbids in `eaos.policy.json`, and every resolved import edge is checked against it. A violation is a fact with a location and the reason the team wrote down, and the command exits nonzero so CI can hold the line. This repository now declares and passes its own policy.
- Add `eaos api-diff`: the exported surface of two snapshots compared, separating what breaks a consumer (a removed name, a removed parameter, a new required one) from what does not (an addition). Function signatures are now captured as facts to make this possible.
- Add three claim classes: a maintenance hotspot where branching concentrates on a central, frequently changed path; module-level state that is actually mutated at runtime, kept separate from tables merely built at import time; and a module writing into another module's namespace. Each carries a probe that can re-decide it on a later snapshot.
- Add `eaos impact-of <path|symbol>`: what a change reaches, computed from resolved imports, traced flows, executed coverage and history — direct and transitive dependents, flows crossing the target, tests that cover it, and files that historically change with it.
- Rank findings by a declared formula — reach × confidence × origin ÷ cost — with every input exposed on the claim, replacing an ordering that effectively sorted by the length of a sentence. New `RISK-REGISTER.md` artifact.
- Add `eaos tasks`: a self-contained card per confirmed claim, with the blast radius from facts, remediation options that always include doing nothing and its cost, a rollback, an effort estimate that states its own confidence, and an acceptance criterion derived from the probe that confirmed the claim. Cards are sequenced into waves, where two tasks touching the same file never share a wave and investigations precede the changes they inform.

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
- Enforce the schema keywords the contracts already declared. `pattern`, `minItems`, `maxItems`, `const`, `minimum` and `maxLength` were silently ignored, so a claim with a malformed id and no method passed validation while the schema said otherwise. Unknown keywords are now reported instead of ignored, and `evidence_ids` no longer claims a minimum the ledger deliberately does not require of fact-backed claims.
- Decide duplicated-rule probes from parsed facts instead of a text search. A mention of a constant inside a test's string literal was enough to refute a true finding; a claim is now withdrawn only on a resolved import that actually brings in that name, and weaker evidence yields INCONCLUSIVE.
- Capture the names an import brings in for tree-sitter languages, which is what makes that judgement possible.
- Mark every claim as coming from product code or test code, rank product findings first in the decision brief, and label test-origin findings.
- Stop stating that no execution evidence exists when a verification run produced it.
- Bind argparse commands to the handler registered through set_defaults, including the loop-over-pairs form. Flow tracing on this repository goes from one useless trace to nineteen that reach real code.
- Collapse one flow per handler instead of one per route, and separate traces that stop at the first boundary from traces that reach further code.
- Restrict the public-API surface to top-level packages, split standard-library imports from third-party ones, rank answers by record kind and let an Arabic question reach the rendered Arabic artifacts, and cut long statements on word boundaries.
- Run verification with the interpreter that is actually running EAOS instead of a bare `python` on PATH. On a system that ships only `python3` the default test commands could not start, and a run silently lost all execution evidence. Found by installing the wheel and running it against the repository from outside.
- Add `--exclude` to `eaos map`, `eaos dossier` and `eaos facts`: leave vendored or fixture paths out of analysis, with the exclusion reported in the output rather than applied silently.
- Add `eaos facts <target> --out <dir> --history`: deterministic repository-history facts (churn, co-change, ownership, age, fix density) with no model call. Commit subjects are classified then discarded, so commit text never enters the fact set. Reruns on the same input are byte-identical; timestamps live in `facts/run.json`, not in fact records.
- Redact source with whole-file context before selecting line ranges, preventing multiline private-key bodies from leaking through partial reads or chunk boundaries. Added two regression tests.
- Correct SECURITY.md to distinguish local audit commands, network/command model providers, and isolated-copy remediation.
- Add local development instructions and an Arabic technical review.

## 2.0.0 — 2026-09-17

تغيير محور المنتج إلى Architecture / Structure / Maintainability / Evolvability. إضافة14 قاعدة مستقلة في مجال27، نموذج معماري بأدلة وعقود وملكية قواعد وسيناريوهات تغير، واستعلامات graph/impact/context. default profile architecture مع مجالات مساندة out of scope صراحةً، وfull يحافظ على التغطية العامة. لا ترقية صامتة لسجلات1.0؛ أنشئ run جديدًا. أضيف تحليل الفيديو الثالث وثلاثة مراجع معمارية، مع فصل البذور عن القواعد المعيارية. لا استخراج AST تلقائي ولا LLM provider invocation.

## 1.0.0 — 2026-09-17

إصدار أول للإطار العام وCLI الجرد والأدلة والتحقق وحزم السياق والاستئناف؛ تحليل نصي للفيديوين الأولين. النسخة محفوظة في تاريخ git.
