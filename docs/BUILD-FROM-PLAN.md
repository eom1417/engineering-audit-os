# Build from a plan

**English** · [العربية](BUILD-FROM-PLAN.ar.md)

## The idea

A check reads what exists, draws the target, and plans the way between them. A project not built yet has no current
state: the target is drawn from the plan itself, and the gap is the whole build. What checks hunt for in an existing
project (duplication, dead code, tangled files, mixed layers, security weaknesses) is kept out from the first line
instead of chased later.

## The way

The person writes to their assistant: "I have my project's plan in this file, build it with EAOS with the best
structure". Or, from the Studio: **"Build from a plan"** in the assistant's panel, with the new project's name, the
plan's files and pictures of its screens (or pasted text); the blueprint is drawn in a new folder beside the project
(`POST /api/plan`, `eaos/interfaces/studio_actions/plan.py`), and the build starts once the person agrees.

| # | Tool | What happens |
| --- | --- | --- |
| 1 | `blueprint_start` | Reads the plan in any format (Markdown, text, HTML, Word, PDF, pasted words, or a folder of them) with the paths of its screen pictures for the assistant to look at (`eaos/analysis/planning/plan_input.py`), and returns it with the spec format and the stack catalogue |
| 2 | `blueprint_spec` | The assistant writes the spec, its look included (`look`: one theme, its colours, fonts and shared components, and each screen with its features and picture): parts with one responsibility, data with one owner, features with acceptance criteria. EAOS answers with what is missing and with choices, each with a recommendation. The assistant researches what products of this kind need, recommends, and asks the person only real choices (technology preferences among them) |
| 3 | `blueprint_design` | The stack (the person's choice, else the recommendation), the target structure, the layer rules, and the build plan in milestones and cards |
| 4 | `build_start` | One agreement, then the first milestone in an isolated copy. The blueprint and its rules enter the project itself (`eaos.policy.json` and `docs/blueprint/`) |
| 5 | `build_edit` | The assistant writes card by card; a card is kept only if it passes the gates, security among them (Bandit and Gitleaks on every card, CodeQL when a milestone closes, where it may run) |
| 6 | `build_finish` | The whole milestone's checks, then a branch `eaos/build-N` on top of the last one; a milestone with screens has them pictured and reviewed against DESIGN.md by the check's own stages (`facts`, `features`, `setup`, `screens`, `visual`, in `look/` beside the report), and what departs is fixed first in the next milestone. Then the next milestone with no new question |
| 7 | `accept` | At the end the person decides: take the last branch (it holds every milestone) or throw it away |
| 8 | `audit` | The acceptance check of the built project; once it is done the project goes on as "Check and fix" |

**In the Studio** the build is a journey of its own (`eaos/data/journeys.json`): read the plan, the spec and the look,
the blueprint, build milestone by milestone, the acceptance check. The live map draws each milestone as a stage and
each card as its step (`eaos/journeys/catalog.py`), and the library's "The blueprint and the look" group shows BLUEPRINT.md and
DESIGN.md before any check exists.

Wherever the blueprint was drawn (the Studio or the person's own assistant session), the Studio reads it from the
blueprint folder (`eaos/report/studio/blueprint_plan.py`): the Plan page lists the milestones and each build card with its
acceptance, files, tests and state; the spec's open questions wait in "Waiting for you", and an answer there goes into
the spec at once and draws the blueprint again; Status says where the build stands and offers its one next step.
"Build the whole product" starts the person's assistant, which builds every milestone in order, each card through
its gates, fixing what each milestone's screen review found before the next one, and stops when the last branch waits
for the person's decision.

**Complete by construction.** Beyond its own features, the blueprint adds the cards every product needs
(`eaos/data/product-standard.json`), chosen by the spec's `nonfunctional` facts and `integrations`: languages and
right-to-left, privacy (consent, export, deletion), offline on the phone, one adapter per integration, security by
default, errors and their states, then, in the last milestone "Ready to release", accessibility, speed, load and CI.
Every requirement of the plan is listed in the spec with what builds it (`requirements[].covered_by`): a requirement
nothing builds stops the blueprint, and the last milestone is not delivered while a requirement has no kept card, nor
while its running screens have serious accessibility problems (axe, touch targets, Lighthouse accessibility and best
practices under 90), while the screen review finds a design departure of high severity, or while a load scenario
(k6 on the production build, at the plan's expected users) goes over its threshold.

## The structure it draws

| Folder | Layer | Depends on |
| --- | --- | --- |
| `shared/src/` | Shared types and validation | nothing |
| `server/src/domain/` | Business rules | shared only |
| `server/src/application/` | Use cases and ports | domain and shared |
| `server/src/infrastructure/<concern>/` | Adapters: the database, sign-in, integrations | application, domain and shared |
| `server/src/interface/http/` | Routes | application and shared |
| `web/src/ui/` | The shared look | shared |
| `web/src/api/` | The one client of the server | shared |
| `web/src/features/<part>/` | The screens | ui, api and shared |
| `web/src/app/` | The app shell | all |

**Each technology lives in one place:** a database or sign-in library is imported only by its adapter folder (and,
for its browser half, by the server's one client). Changing Supabase to PostgreSQL, say, means replacing one folder;
the rest asks for data the same way. Every option in the catalogue (`eaos/data/stacks.json`) says why it is chosen and
how to change it later.

**The look is built once:** the shared-look card turns the spec's `look` into design tokens in `web/src/ui/theme.css`
that no screen overrides, and each feature's card says which screen and picture it follows.

**The look costs almost no tokens:** `blueprint_start` returns a design brief (`eaos/analysis/target_state/look.py`): the EAOS design
standard (phone first, both directions, one theme, readable contrast), a catalogue of Arabic fonts, free pinned design
libraries (UI UX Pro Max, awesome-design-md, tweakcn themes, Anthropic's frontend-design) and the design system UI UX
Pro Max suggests for the product, found offline. The assistant spends its judgement on taste alone and writes the
result as one DESIGN.md (`look.design_md`); components come from shadcn/ui and fonts from Fontsource.

**The order of the build:** the skeleton and its checks first (typecheck, lint and test run from the first card), then
the shared foundations (one home each for errors, validation, configuration, the look and the client), then part after
part in data order (the data's owner before those that use it), then every journey end to end in a browser.

## The gates after every card

They are the gates every change passes, in all three journeys (`eaos/analysis/repair/gates.py`): a fix holds them against the check
of the code it changes, a build against nothing (everything found is the card's), each held to the policy in force.

| Gate | Keeps out |
| --- | --- |
| Layers | A layer using what it may not (business rules importing the database, say) |
| Structure | A file outside the planned folders |
| Technology | An isolated technology's library used outside its folder |
| Cycles | Files importing each other |
| References | An import of a file that does not exist |
| Copies | The same lines in more than one place (outside tests and configuration) |
| Complexity and size | A function past the complexity limit, a module past the line limit |
| Security | A weakness or an exposed secret: Bandit and Gitleaks on every card, CodeQL when a milestone closes, where it may run |
| Tests | A card without a test for its acceptance criteria |
| Project checks | typecheck, lint and test |
| Dead code | At the last milestone: what nothing uses |

A card that breaks a gate goes back to the assistant with the reasons; it fixes it and sends it again.

## What it produces

In the outputs folder (`~/EAOS/<project>/blueprint/`): `SOURCE.md` (the plan as read), `product-spec.json`,
`stack.json`, `eaos.policy.json`, `plan.json`, and `BLUEPRINT.md` (the blueprint in words a person reads: the parts, the
technologies with why and how to change them, the rules, and the order of the build). The target structure is
`technical/target-architecture.json`, where a check keeps its own and in the same shape (its parts are the layers), so
the report and the Studio draw both alike; the look is `DESIGN.md` beside it, where the screen review reads it.

## Extend a project

A project already checked grows the same way: a feature, a page or a part, planned against what the project is, and
built by the batches that fix it. From the Studio: **"Extend the project"** in the assistant's panel (the same form,
without a name); or ask the assistant: "add this feature to my project with EAOS".

| # | Tool | What happens |
| --- | --- | --- |
| 1 | `extend_start` | Reads the feature's plan (`read_plan`, any format, with pictures) and returns it with the project as its check read it: its parts, its layers and their rules (its `eaos.policy.json`, else the check's target), the functions to reuse, and its look (`DESIGN.md`) |
| 2 | `extend_plan` | Checks the spec (the build's own, with `touches`, and for each feature its `paths`, `functions` and `reuses`), then holds it to the project: every file in a layer it allows (a new file names the layer it joins, `layers`), every reused function one the project has and its layer may use, and no function written again that the project already has. Its cards then join the project's plan as one milestone, "Extension: <name>", ready for a batch |
| 3 | `fix_start` … `fix_finish` | Once the person agrees, the cards are built as any fix, through every gate, and handed over as a branch the person takes in or not |
| 4 | `audit` | The check goes on over the project as it is now; a card not built yet stays in the plan after it |


## Measures

| Measure | What it measures | Goal |
| --- | --- | --- |
| B1 | Plan formats read into their text | 1.0 |
| B2 | Blueprint checks on the sample specs | 1.0 |
| B3 | Projects built from a plan that an EAOS check finds clean | 1.0 |
| B4 | Features of built plans that passed their gates with their tests | 1.0 |

## Limits

The build lays out web products in TypeScript: React or Next.js on the web, optionally a Hono, Express or Fastify
server, PostgreSQL, Supabase or SQLite for data, and Better Auth, Supabase Auth or Clerk for sign-in. Native mobile apps
and other server languages are not laid out yet.
