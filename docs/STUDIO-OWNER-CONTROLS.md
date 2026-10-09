# Studio owner controls (NS46.T17, F15)

Codex implementation, 2026-10-09. This is an implementation handover, not release or acceptance evidence.

Report answers use the existing authenticated command centre:

- `GET /api/decisions`: authoritative report questions, stable scope, saved response and execution.
- `POST /api/decisions/<id>/answer`: scope plus an authoritative option ID **or** exact custom text.
- Run questions continue through `POST /api/questions/<id>/answer`; identical resubmissions return the original result.
- Execution uses existing run events, queue and `POST /api/runs/<id>/retry`.

The server stores report responses in the project's EAOS workspace at `runs/decisions.json`, with timestamp, selected source label, provenance, status, run ID and saved/queued history. The run's durable state/events record acknowledgement, execution and failure independently. The canonical source revision plus report path and decision ID prevents unrelated questions inheriting an answer; source report JSON is never overwritten by an answer. Exported canonical revisions and recommended option IDs do not depend on presentation language. Legacy reports without a revision reconcile conservatively and may invalidate an answer after a language-changing re-export.

Custom text is accepted on **every** report decision and waiting-run question. It must be non-whitespace and at most 4000 Unicode characters; leading/trailing spaces and newlines are preserved. Send either option or text, never both. Invalid IDs, stale scopes, conflicting responses, missing launch/CSRF tokens and foreign origins are rejected. A label supplied by the client cannot grant authority. The UI keeps a failed draft and waits for server success before removing a question.

A custom run answer is persisted in the original run, then sent to read-only assistant clarification. The original question/mode/session is retained durably and restored as a new explicit question after clarification or failure. Setup remains unapproved until an explicit authoritative `yes` answer. No model-generated answer, arbitrary text containing “yes”, report answer or recommendation authorizes merge/undo. Report response dispatch only explains the exact answer and evidence; subsequent code-changing actions use the existing preview and confirmation flows. This deliberately does not claim automatic implementation of arbitrary owner instructions.

A recommendation uses an explicit option ID when supplied, otherwise an unambiguous legacy source-label match. No default first-option recommendation is fabricated. Recommendation is blue with a text/icon cue in both themes; the saved owner selection is shown separately. Snapshot mode is read-only and explains connecting to live Studio; copy/export is optional.

| Workflow | Backend and UI coverage | Remaining proof/gap |
| --- | --- | --- |
| Scan/refresh, explain, plan/re-plan | Existing command-centre actions and queue | Full real combined owner trial pending |
| Fix selected cards/groups/steps | Existing selection resolver, previews and assistant runs | Combined live implementation/acceptance trial pending |
| Report decisions, including ideal questions | Durable authoritative responses and read-only assistant review | Integrated localized live UI and real assistant decision trial pending |
| Waiting-run questions/setup | Supplied options and exact custom answers; original authorization question restored | Live integration trial pending |
| Queue/live events, pause/resume/stop/retry | Existing run manager, stream and lifecycle | Existing controls require combined proof |
| Diff/tests, accept/undo | Existing outcome review and separate confirmation; assistant person-only tools blocked | No owner decision or merge executed during implementation |
| New-project building | Existing backend blueprint/build tools only | No arbitrary new-project Studio wizard promised |
| Branch inventory/management | Dedicated branch-control follow-up | Not implemented by this worker |

Remote mode is opt-in: `eaos studio PROJECT --no-open --port PORT --remote-origin https://engineering-audit-os--PORT.dev.remote.e-m.sa`. Only the exact Remote HTTPS host/port is accepted. Token, exact Host/Origin and CSRF checks remain required; binding `0.0.0.0` without this configuration remains refused. Remote mode never prints a launch token. Existing static previews and source translation catalogs must be retained. Deployment of the combined localized UI belongs to integration.

The additive owner-request task NS46.T17 stays `todo`. Its locked acceptance reads current shipped-digest real evidence from `$EAOS_MEASURE/owner-controls/{EAOS,FleetManageWeb}/trial.json`, using `tools/north_star_studio.py` case and viewport requirements. F15 cannot reach 1.0 on legacy command-centre trials alone. Mock backend/browser checks are useful implementation verification and never recorded as live measured completion. Re-plan proposals and final owner judgement remain pending.

Preview handover preparation is saved at `/workspace/eaos-dev/workers/owner-controls-live-prepared/`. Its runner refuses to bind until integration explicitly enables it with the reviewed combined build digest. The real source catalogs remain untouched. The prepared dedicated EAOS homes still need valid guided project state matching each report; simply serving a static report beside an empty home does not prove plan/fix controls work. No public live deployment or owner-decision execution was performed by this worker. On integration, protect `revision` and `recommended_option` as immutable keys in the combined localization projection.
