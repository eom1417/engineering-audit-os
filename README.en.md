# Engineering Audit OS

**[العربية](README.md)** · version 3.0.0 · status: **Pilot** · progress: [where we stand](#-where-we-stand)

> **A full engineering review team in one command.**
> EAOS reads your project the way an architect, a code reviewer, a performance engineer and a tech lead would, together. It hands you an evidenced picture of where the project stands today, the professional shape it should reach, and an ordered task plan that any engineer or AI model can execute and prove done.

```bash
eaos audit /path/to/project --out /path/to/report
```

---

## 🎯 Why

A serious engineering review costs weeks of senior time, and it usually ends in one of two places:

- **An opinion report** that nobody can verify.
- **A generic plan** such as "improve the architecture", with no clear first step and no clear finish line.

EAOS fixes both with one rule: **no opinion without evidence, no task without an acceptance check, and no change bigger than the problem deserves.**

## 🏢 The idea: what a software company does, in one command

You built a program by vibe coding. It works, but you do not know how it is built, what goes in and out, where its limits are, or how complex and repetitive it is. A software company asked to rebuild it as a professional product would hand you four things, in order. That is what EAOS must deliver:

| # | Report | What it holds |
|---|---|---|
| 1 | **Current state** | What the program does, its inputs, outputs and limits, its structure, complexity and duplication, its dead code and leftovers, its risks |
| 2 | **Ideal state** | The same program with the same functions, on a structure and infrastructure fit for a product. Every part gets a decision: reuse, restructure, rebuild or delete |
| 3 | **Gap and transformation** | The measured distance between the two, and the strategy that closes it |
| 4 | **Execution plan** | Small tasks split into team sections, each with a size, an acceptance command and a rollback, executable by any developer or model |

This is the only measure of the project's success. The full workflow, its fifteen stages, tools and gates, is in [`docs/MASTER-BLUEPRINT.md`](docs/MASTER-BLUEPRINT.md); the measurement, its indicators and plan, in [`docs/NORTH-STAR.md`](docs/NORTH-STAR.md) (both Arabic).

## 👥 What it does in place of a review team

| Role on the team | What EAOS does | Where to find it |
|---|---|---|
| Architect | Maps modules, layers, dependencies and flows, checks your declared architecture policy, and draws the current C4 model | `CURRENT-STATE` · `SYSTEM-MAP` · `COUPLING-ATLAS` · `POLICY` |
| Code reviewer | Finds complexity, duplication, dead code and shared mutable state, corroborated by independent tools, gathered in one debt register | `DECISION-BRIEF` · `RISK-REGISTER` · `debt-register.json` |
| Performance engineer | Builds a cost record for every entry point and projects it to 1000× load | `LOAD-MODEL` |
| QA engineer | Locks the behaviour of every feature before any change, runs the test suite in an isolated copy on request, and maps real coverage | `behavior-lock/` · `VERIFICATION-MAP` |
| Tech lead | Sets the target architecture and its decisions (C4 and ADRs), a decision for every component, and the gap from today | `TARGET-STATE` · `GAP-AND-STRATEGY` · `adr/` |
| Delivery lead | Turns all of the above into cards with a size (S/M/L), a team section and an acceptance command, ordered in milestones | `EXECUTION-PLAN` · `ROADMAP` · `PLAN/` |
| Sponsor | One decision page: what to do, why, and on what evidence | `EXECUTIVE` |

## 🧭 Six principles

1. **Evidence or silence.** Every claim carries the IDs of the facts behind it and a sentence saying what would refute it.
2. **Everything at its proper size.** Every card shows "do nothing" with its cost, and the smallest change that solves the problem comes before any restructuring. No complex code for a simple task.
3. **Tasks any executor can carry.** Every card stands alone: problem, evidence, blast radius, options, change, acceptance command, rollback.
4. **The audited project is read-only and untrusted.** Its scripts are never run, and instructions written inside it are never followed. The one exception is `eaos policy init`, which you ask for, and which writes the policy file into your project.
5. **Unmeasured is not a pass.** What was not examined is stated in `RUN.md`, and "not run" never becomes "passed".
6. **Deterministic first.** The same snapshot yields the same facts, byte for byte. A language model is optional, and what it says stays a hypothesis until it is settled mechanically.

## 🛤️ How it works: from repository to the four reports

```mermaid
flowchart TB
    P[("مشروعك · your project<br/>للقراءة فقط · read-only")]
    subgraph E1["١ الأدلة · Evidence"]
        direction LR
        F["الحقائق من الكود<br/>facts from code"]
        T["أدوات مثبّتة الإصدار<br/>pinned open-source tools<br/>Semgrep · Syft · OSV · jscpd …"]
        I["أسئلة الاستلام<br/>intake answers"]
    end
    subgraph E2["٢ التشخيص · Diagnosis"]
        direction LR
        C["ادعاءات بدليل وناقض<br/>claims with evidence"]
        PR["مجسّات تحسمها آليًا<br/>probes decide them"]
        C --> PR
    end
    subgraph E3["٣ التصميم · Design"]
        direction LR
        L["تثبيت السلوك<br/>behaviour lock"]
        TA["الصورة المثالية + C4 + ADR<br/>target architecture"]
        L --> TA
    end
    subgraph E4["٤ الخطة · Plan"]
        direction LR
        PL["بطاقات بحجم وأمر قبول وتراجع<br/>cards: size, acceptance, rollback"]
        RM["معالم وأقسام فريق<br/>milestones and team sections"]
        PL --> RM
    end
    subgraph OUT["التقارير الأربعة · The four reports"]
        direction LR
        R1["CURRENT-STATE<br/>الوضع الراهن"] --> R2["TARGET-STATE<br/>الصورة المثالية"] --> R3["GAP-AND-STRATEGY<br/>الفجوة والتحول"] --> R4["EXECUTION-PLAN<br/>خطة التنفيذ"]
    end
    P --> E1 --> E2 --> E3 --> E4 --> OUT
    OUT -. "تفويض المالك · owner authorization" .-> X["التنفيذ والإثبات في بيئة معزولة<br/>execution and proof, isolated"]
    X -. "إعادة التدقيق · re-audit" .-> E1
    classDef out fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a,stroke-width:2px
    class R1,R2,R3,R4 out
```

| Step | What it does | What it produces |
|---|---|---|
| **1 Evidence** | Extracts facts from files, symbols, imports, entry points and git history; runs external tools at pinned versions with verified checksums (`upstreams/toolchain.json`); reads the owner's intake answers | `facts/*.json` · `sbom.cdx.json` · `intake.json` |
| **2 Diagnosis** | Turns facts into claims that each carry a confidence, evidence and a falsifier; settles what can be settled with mechanical probes; gathers the evidence in one debt register | `dossier.json` · `debt-register.json` · `measurements.json` |
| **3 Design** | Locks the behaviour of every feature before any change, then chooses the target architecture among seven reference architectures from the project's own files, and decides for each component: reuse, restructure, rebuild or delete | `behavior-lock/` · `target-architecture.json` · `architecture/*/workspace.dsl` · `adr/` |
| **4 Plan** | Turns every claim into a card: a ready repair whose acceptance command re-checks the problem itself, or an investigation that waits for a recorded decision. Then orders the cards into milestones and team sections | `plan.json` · `ROADMAP.md` · `PLAN/` |
| **The four reports** | What a software company hands over: current state, target state, gap and strategy, execution plan | `CURRENT-STATE.md` · `TARGET-STATE.md` · `GAP-AND-STRATEGY.md` · `EXECUTION-PLAN.md` |

See the stages exactly as the code declares them: `eaos stages` · and whether each stage's gate passes: `eaos engage status report`

---

## 📦 What you receive

Every report opens with its own `README.md` that sends each reader where they need to go:

| If you… | Start with | Time |
|---|---|---|
| want the whole picture | `CURRENT-STATE` → `TARGET-STATE` → `GAP-AND-STRATEGY` → `EXECUTION-PLAN` | 20 min |
| decide where effort goes | `DECISION-BRIEF` → `RISK-REGISTER` → `PLAN/WAVES` | 5 min |
| join the project today | `ONBOARDING` → `SYSTEM-MAP` → `FLOWS` | 45 min |
| review the architecture | `POLICY` → `COUPLING-ATLAS` → `CONTRACTS` | 30 min |
| are about to change one file | `eaos impact-of <path> --out <report>` | 1 min |

Every document has one owner and a line budget it stays inside, and every human document has a JSON twin a model can act on, or a written reason why it has none.

### Anatomy of a task card

```text
TASK-003 — complexity 83 (threshold 15) in eaos/sustainability.py
├─ kind          investigate (a recorded decision before any change) | remediate (change, then verify)
├─ size, section S/M/L from files and dependents · security, infrastructure, data, backend, frontend, quality
├─ evidence      fact IDs + probe + what would refute the claim
├─ blast radius  files, direct and indirect importers, flows, covering tests
├─ options       smallest change → restructuring → "do nothing", each with its cost
├─ acceptance    a runnable command: `eaos recheck` re-checks the problem itself, or `eaos decided` for an investigation
└─ rollback      how to take one step back
```

## 🚀 Quick start

**Requirements:** Python 3.10 or newer. The external tools (Semgrep, Syft, OSV-Scanner, jscpd, dependency-cruiser, Structurizr and more) install with one command at their pinned versions and verified checksums; their sources and licences are in [`upstreams/toolchain.json`](upstreams/toolchain.json) and [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md). When one is missing, the report says so and carries on.

```bash
# from the root of this repository
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[facts,runtime]"    # facts: tree-sitter parsers for non-Python code · runtime: coverage for the verify stage
eaos tools install --stage assessment  # the assessment tools; eaos tools doctor shows what is installed, at which version

# full audit, no model
eaos audit /path/to/project --out /path/to/report

# with the four engines, an English report and a stated goal
eaos audit /path/to/project --out /path/to/report \
  --engines codegraph enola jscpd reforge --lang en --goal evolution
```

Open `report/README.md` and start with the four reports (`CURRENT-STATE.md` → `TARGET-STATE.md` → `GAP-AND-STRATEGY.md` → `EXECUTION-PLAN.md`), or `report/index.html` for search and navigation.

> ⚠️ `--test-command` runs the project's tests in an isolated copy. The copy is not an operating-system sandbox: use it only on trusted projects, or inside an isolated environment.

### Everyday commands

| Purpose | Command |
|---|---|
| What a change to a file or symbol touches | `eaos impact-of eaos/claims.py --out report` |
| A question answered from the records, with citations | `eaos ask "where is the discount rule computed" --out report` |
| Scaffold an architecture policy, then check it | `eaos facts . --out report` → `eaos policy init . --out report` (writes `eaos.policy.json` into your project; add your rules and their reasons) → `eaos policy check . --out report` |
| Freeze today's debt and fail CI only on new findings | `eaos audit . --out report` → `eaos baseline pin --out report` → in CI: `eaos audit . --out report --gate new` |
| Compare two audits (drift gate) | `eaos delta old-report new-report --fail-on-new-severe` |
| Breaking surface between two versions (fact sets from `eaos facts`) | `eaos api-diff old-facts new-facts --fail-on-breaking` |
| Installed engines and their versions | `eaos engines list` · `eaos tools doctor` |
| Files in each tool's own format (CI, pre-commit, Renovate, k6…), judged by that tool | `eaos emit report --validate` |
| Whether each stage's gate passes, and why not | `eaos engage status report` |

### Model path (advanced)

Needs a provider file, set up once as described in [`core/RUNTIME.md`](core/RUNTIME.md):

```bash
eaos run /path/to/project --out audit --provider provider.json        # model-led review
eaos implement audit --task TASK_ID --out candidate \
  --checks checks.json --provider provider.json                        # one task in a separate copy
eaos improve audit --out campaign --checks checks.json \
  --provider provider.json --max-steps 10                              # execute → verify → re-audit → next
```

No command modifies the original project, publishes anything or merges anything.

---

## 📊 Where we stand

This section is generated from [`docs/north-star.json`](docs/north-star.json); `python tools/north_star.py --check` fails when it falls behind the record. Every capability, indicator and task is detailed in [`docs/NORTH-STAR.md`](docs/NORTH-STAR.md) (Arabic).

<!-- north-star:start -->
<!-- generated from docs/north-star.json by python tools/north_star.py; do not edit by hand -->

### Actual progress: **14 of 25 milestones (56.0%)**

`██████████████░░░░░░░░░░░` 56.0%

| Current milestone | Measured output quality (not a completion rate) | Last measured |
|---|---|---|
| 15 · NS14 — Report quality checked automatically | 87.6% | 2026-09-26 · `f48d997+` |

> **Progress is the number of closed milestones.** A milestone counts only when every task in it passed its acceptance command, and the product is complete at 25 of 25. "Output quality" measures what the part built so far delivers on 3 real projects (54 indicators across 10 capabilities); it rises faster because the first milestones built the heaviest capabilities. Every milestone and task is detailed in [docs/NORTH-STAR.md](docs/NORTH-STAR.md) (Arabic).

(`+`: on changes over this commit, saved in the next one)

**Need owner input before they can close:** 17 NS26, 18 NS9, 19 NS20, 20 NS21, 21 NS22, 22 NS23, 23 NS24, 24 NS16, 25 NS10

### The pipeline: fifteen stages

Each stage passes its gate before the next begins. S01 to S07 only read the project and end with the four reports; S08 to S14 run the project's code in an isolated environment, and start only with its owner's authorization.

```mermaid
flowchart TB
    subgraph ASSESS["التقييم: قراءة فقط · Assessment: read-only"]
        direction LR
        S01["S01 · DISCOVER<br/>الاستلام والجرد"]:::done
        S02["S02 · MAP<br/>رسم العمارة الحالية"]:::done
        S03["S03 · MEASURE<br/>القياس"]:::done
        S04["S04 · DIAGNOSE<br/>التشخيص وسجل الدَّين"]:::done
        S05["S05 · LOCK CURRENT BEHAVIOR<br/>تثبيت السلوك الحالي"]:::current
        S06["S06 · DESIGN TARGET ARCHITECTURE<br/>الصورة المثالية"]:::done
        S07["S07 · PLAN TRANSFORMATION<br/>الفجوة وخطة التحول"]:::current
        S01 --> S02 --> S03 --> S04 --> S05 --> S06 --> S07
    end
    subgraph EXECUTE["التنفيذ: عزل وتفويض · Execution: isolated, authorized"]
        direction LR
        S08["S08 · REBUILD / REFACTOR<br/>التنفيذ"]:::next
        S09["S09 · VERIFY<br/>التحقق الوظيفي"]:::next
        S10["S10 · SECURE<br/>الأمن"]:::next
        S11["S11 · LOAD TEST<br/>الحمل"]:::next
        S12["S12 · BREAK IT DELIBERATELY<br/>الأعطال المتعمدة"]:::next
        S13["S13 · OBSERVE<br/>الرصد"]:::next
        S14["S14 · PRODUCTION READINESS<br/>الجاهزية للإنتاج"]:::next
        S08 --> S09 --> S10 --> S11 --> S12 --> S13 --> S14
    end
    subgraph GOVERN["الحوكمة والتسليم · Governance and handover"]
        direction LR
        S15["S15 · CONTINUOUS GOVERNANCE<br/>الحوكمة المستمرة والتسليم"]:::next
    end
    ASSESS ==>|تفويض المالك · owner authorization| EXECUTE
    EXECUTE ==> GOVERN
    LOOP["↺ إعادة التدقيق بعد كل تغيير<br/>re-audit after every change"]:::next
    GOVERN -.-> LOOP
    classDef done fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px
    classDef current fill:#fef9c3,stroke:#ca8a04,color:#713f12,stroke-width:3px
    classDef next fill:#f1f5f9,stroke:#64748b,color:#1e293b
    classDef owner fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-dasharray:5 3
```

### The roadmap: twenty-five milestones in execution order

```mermaid
flowchart TB
    subgraph R1["R1 · الأساس: الوصول والرؤية والإشارة<br/>Foundation: reach, visibility, signal"]
        direction LR
        NS1["1 · NS1<br/>القياس آليًا<br/>Automated measurement"]:::done
        NS2["2 · NS2<br/>لا يفشل على مشروع حقيقي<br/>Never fails on a real project"]:::done
        NS3["3 · NS3<br/>تقرير الوضع الراهن<br/>Current state"]:::done
        NS4["4 · NS4<br/>الإشارة لا الضجيج<br/>Signal, not noise"]:::done
        NS5["5 · NS5<br/>الكود الميت والمخلفات<br/>Dead code and leftovers"]:::done
        NS6["6 · NS6<br/>نظافة الأمن الأساسية<br/>Basic security hygiene"]:::done
        NS1 --> NS2 --> NS3 --> NS4 --> NS5 --> NS6
    end
    subgraph R2["R2 · منصة الأدوات: تثبيت، وقراءة، وتوليد، ومراحل، وعزل<br/>Tool platform"]
        direction LR
        NS17["7 · NS17<br/>منصة الأدوات<br/>Tool platform"]:::done
    end
    R1 --> R2
    subgraph R3["R3 · الأدلة الكاملة من الأدوات الجاهزة<br/>Full evidence from proven tools"]
        direction LR
        NS11["8 · NS11<br/>الاستلام<br/>Intake"]:::done
        NS12["9 · NS12<br/>محوّلات الفحص الساكن<br/>Static-analysis adapters"]:::done
        NS18["10 · NS18<br/>القياس وسجل الدَّين<br/>Measurement and debt register"]:::done
        NS11 --> NS12 --> NS18
    end
    R2 --> R3
    subgraph R4["R4 · تثبيت السلوك والصورة المثالية<br/>Behaviour lock and target state"]
        direction LR
        NS15["11 · NS15<br/>تثبيت السلوك<br/>Behaviour lock"]:::done
        NS7["12 · NS7<br/>تقرير الصورة المثالية<br/>Target-state report"]:::done
        NS13["13 · NS13<br/>نموذج العمارة وقراراتها<br/>Architecture model and decisions (C4, ADR)"]:::done
        NS15 --> NS7 --> NS13
    end
    R3 --> R4
    subgraph R5["R5 · الخطة والتقارير وعدّة التسليم<br/>Plan, reports and handover kit"]
        direction LR
        NS8["14 · NS8<br/>خطة التنفيذ للفريق والتقارير الأربعة<br/>Team execution plan and the four reports"]:::done
        NS14["15 · NS14<br/>جودة التقرير تُفحص آليًا<br/>Report quality checked automatically"]:::current
        NS25["16 · NS25<br/>عدّة التشغيل والتسليم<br/>Operations and handover kit"]:::next
        NS8 --> NS14 --> NS25
    end
    R4 --> R5
    subgraph R6["R6 · التنفيذ المثبت<br/>Proven execution"]
        direction LR
        NS26["17 · NS26<br/>خط الأساس الحي<br/>Live baseline"]:::owner
        NS9["18 · NS9<br/>إثبات التنفيذ<br/>Proven execution"]:::owner
        NS20["19 · NS20<br/>التحقق الوظيفي<br/>Functional verification"]:::owner
        NS26 --> NS9 --> NS20
    end
    R5 --> R6
    subgraph R7["R7 · التصليب التشغيلي<br/>Operational hardening"]
        direction LR
        NS21["20 · NS21<br/>الأمن بعد التحول<br/>Security after the transformation"]:::owner
        NS22["21 · NS22<br/>الحمل<br/>Load"]:::owner
        NS23["22 · NS23<br/>الأعطال المتعمدة<br/>Deliberate failures (chaos)"]:::owner
        NS24["23 · NS24<br/>الرصد<br/>Observability"]:::owner
        NS16["24 · NS16<br/>الجاهزية للإنتاج<br/>Production readiness"]:::owner
        NS21 --> NS22 --> NS23 --> NS24 --> NS16
    end
    R6 --> R7
    subgraph R8["R8 · الإثبات المستقل<br/>Independent proof"]
        direction LR
        NS10["25 · NS10<br/>الإثبات المستقل<br/>Independent proof"]:::owner
    end
    R7 --> R8
    classDef done fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px
    classDef current fill:#fef9c3,stroke:#ca8a04,color:#713f12,stroke-width:3px
    classDef next fill:#f1f5f9,stroke:#64748b,color:#1e293b
    classDef owner fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d,stroke-dasharray:5 3
```

✅ done · 🟡 in progress now (a pipeline stage: partly built) · ⬜ next, doable by a model or a developer · 🔴 needs owner input (a sandbox and authorization, a model provider, or a human reviewer)

<!-- north-star:end -->

**Status, plainly:** this is a pilot, not a release. The numbers are measured on 3 real hobby projects pinned at their commits, and on this repository itself. What was not measured does not count as a pass, and a milestone that needs a real project's code to run closes only when it has actually run.

## 🛠️ For developers

```bash
python -m unittest discover -s tests -q \
  && python tools/validate.py && python tools/invariants.py \
  && python tools/render_capability_plan.py --check \
  && python tools/north_star.py --check \
  && bash tests/gate/self_audit.sh
```

| Document | What it holds |
|---|---|
| [`docs/NORTH-STAR.md`](docs/NORTH-STAR.md) | The destination: 10 capabilities, 54 indicators, and the twenty-five milestones with their tasks and acceptance commands (Arabic) |
| [`docs/MASTER-BLUEPRINT.md`](docs/MASTER-BLUEPRINT.md) | The fifteen stages, their tools and gates (Arabic) |
| [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) | Every external tool: version, checksum, licence, and the stage it runs in |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | Full command reference and internal structure (Arabic) |
| [`tools/upstream_check.py`](tools/upstream_check.py) | Is an engine upgrade safe? Runs the pinned adapter contracts first (`--offline`) |
| [`docs/CAPABILITY-PLAN.md`](docs/CAPABILITY-PLAN.md) | The capability plan: 49 tasks, 46 done and 3 blocked for measured reasons |
| [`docs/CAPABILITY-SCORE.md`](docs/CAPABILITY-SCORE.md) | Today's measurement of the nine domains |
| [`evaluations/release-evidence.json`](evaluations/release-evidence.json) | What the evidence supports, and what it does not |
| [`design/output-first/OUTPUT-SPEC.md`](design/output-first/OUTPUT-SPEC.md) | The target output specification |
| [`MASTER-MANUAL.md`](MASTER-MANUAL.md) | The 27 domains and 165 engineering rules the analysis draws on |

What the evidence supports, and what it does not, is recorded in `evaluations/release-evidence.json`.
