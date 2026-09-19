# Current acceptance evidence — executable runtime

The run/continue/implement/improve commands are implemented. The deterministic integration suite covers a configured model protocol, source retrieval, analysis stages, concrete target design, real baseline/post-change checks, isolated source edits and fresh audits across campaign snapshots. Automated model judgments in these tests are scripted fixtures; HTTP is exercised against a local protocol server. No live external-model benchmark is claimed.

The host coding agent applied the framework to its own code and fixed nine evidence-backed issue groups, protected by twelve before/after regression tests: dependency direction, record/workflow cycle, source integrity during verification, call-budget resumption, final-step completion, cache integrity, credential redaction uncertainty preservation and shared-session locking. See the delivered self-audit report and VALIDATION.md.

Product-level judgment accuracy across arbitrary repositories remains an empirical property, not a guarantee derived from test counts. The current delivery includes the executable system and self-review evidence; it does not claim that every possible architectural defect is discoverable or that a configured model cannot make mistakes. Use the evaluation procedure below for external validation.

## Historical acceptance baseline (2.1, before runtime implementation)

# Acceptance contract — depth before readiness

Version: 2.1.0. This is a release of agent workflow tooling, not a claim that the universal audit product is production-proven.

## Historical 2.1 contract boundary

For the tested contracts, EAOS refuses structurally incomplete work and discloses limitations. Source targets are read-only for CLI commands. A passing contract validator is not a guarantee that an AI understood the repository or found all issues.

| Acceptance criterion | Current evidence | Status |
|---|---|---|
| Start an audit session from one entry point | CLI integration test: audit creates discovery, workflow and plan records without target changes | IMPLEMENTED / TESTED |
| Preserve unsupported languages and parse failures in the denominator | Mixed Python/TS/Go fixture including malformed Python and a sensitive file | IMPLEMENTED / TESTED |
| Reproducible source evidence | Range/hash integrity, deduplication, invalid path/range rejection tests | IMPLEMENTED / TESTED |
| Inventory alone cannot complete an audit | Workflow must proceed through scope/reconstruction/flow/file/control assessment | IMPLEMENTED / TESTED |
| Unrelated evidence cannot certify a file reviewed | Per-file evidence location check | IMPLEMENTED / TESTED |
| Tailored plan must cite actual findings | Task-to-finding/evidence/node/scenario references | IMPLEMENTED / TESTED |
| Plan needs an invariant, alternatives, steps, rollback and tests | Incomplete-plan rejection and end-to-end record fixture | IMPLEMENTED / TESTED |
| Dependencies precede priority; cycles blocked | Task DAG tests | IMPLEMENTED / TESTED |
| No verified repair without passing declared gates and verified findings | Closure rejection tests | IMPLEMENTED / TESTED |
| Changed source invalidates old work | Snapshot invalidation tests | IMPLEMENTED / TESTED |
| Report discloses partial work and separates plan from repairs | Partial/ready report tests | IMPLEMENTED / TESTED |
| Correct semantic architecture on unfamiliar production repositories | Requires independent agent-led repository evaluation | NOT YET DEMONSTRATED |
| Low false positives and detection of known architectural defects | Requires blind benchmark with independent expected findings | NOT YET DEMONSTRATED |
| A proposed plan actually improves a production project without regressions | Requires authorized real-project remediation and baseline comparison | NOT YET DEMONSTRATED |
| Broad semantic parsers and runtime/deployment reconstruction | Python syntax and JS/TS lexical hints only; agent fills remaining gaps | PARTIAL |
| Autonomous model orchestration, automatic repair and revision migration | No such runtime in current code | NOT IMPLEMENTED |

## Evaluation protocol for the remaining product-level goals

1. Freeze each evaluation repository revision, dirty-tree state, build environment and expected scope before the audit. Record the EAOS version and the host agent/model configuration.
2. Choose projects the evaluator has not pre-mapped. Include a simple maintainable project, one with independently identified defects, a monorepo, and a different stack. Use owned or public repositories with suitable usage rights. Synthetic examples support tests but are not substitutes for these evaluations.
3. An independent reviewer prepares expected invariants, critical flows and known defects before seeing the tool's findings. Keep expected findings away from the auditing agent during the run.
4. Run the documented entry command and agent loop. Record manual interventions, questions, time, observed context usage where available, missed stages and incomplete surfaces. Do not assume characters equal tokens.
5. Check each claimed issue against actual source and behavior. Report false positives and known misses separately. An unreviewed unknown is not a confirmed defect, and a missing finding is not proof of safety.
6. Compare the reconstructed ownership and contracts against independently reviewed flows, not folder names. Verify impact predictions using at least one actual change scenario.
7. Evaluate every proposed task for necessity, minimality, invariant preservation, feasibility, dependency ordering and regression testing. Include a counterexample where no architectural change is needed.
8. On at least one authorized project, implement a selected task, run baseline and post-change checks, re-audit and document rollback/recovery. Do not label the complete roadmap successful because one task worked.
9. Publish the evaluation scope, denominators and failures alongside results. Agree scenario-specific pass criteria before testing; do not invent percentages afterward to make results look good.
10. Only claim capabilities for supported, tested conditions. New stacks, deployment environments and larger scales are new evaluation work.

## Why this is the standard

The design follows scenario-driven quality assessment and reviews of design, complexity, behavior and tests. These sources support the method, not a certification of EAOS:

- [SEI Quality Attribute Workshops](https://www.sei.cmu.edu/library/quality-attribute-workshops-qaws-third-edition/).
- [Google: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html).
