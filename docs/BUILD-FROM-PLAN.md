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
(`POST /api/plan`, `eaos/studio/actions/plan.py`), and the build starts once the person agrees.

| # | Tool | What happens |
| --- | --- | --- |
| 1 | `blueprint_start` | Reads the plan in any format (Markdown, text, HTML, Word, PDF, pasted words, or a folder of them) with the paths of its screen pictures for the assistant to look at (`eaos/plan_source.py`), and returns it with the spec format and the stack catalogue |
| 2 | `blueprint_spec` | The assistant writes the spec, its look included (`look`: one theme, its colours, fonts and shared components, and each screen with its features and picture): parts with one responsibility, data with one owner, features with acceptance criteria. EAOS answers with what is missing and with choices, each with a recommendation. The assistant researches what products of this kind need, recommends, and asks the person only real choices (technology preferences among them) |
| 3 | `blueprint_design` | The stack (the person's choice, else the recommendation), the target structure, the layer rules, and the build plan in milestones and cards |
| 4 | `build_start` | One agreement, then the first milestone in an isolated copy. The blueprint and its rules enter the project itself (`eaos.policy.json` and `docs/blueprint/`) |
| 5 | `build_edit` | The assistant writes card by card; a card is kept only if it passes the gates, security among them (Bandit and Gitleaks on every card, CodeQL when a milestone closes, where it may run) |
| 6 | `build_finish` | The whole milestone's checks, then a branch `eaos/build-N` on top of the last one, and the next milestone with no new question |
| 7 | `accept` | At the end the person decides: take the last branch (it holds every milestone) or throw it away |

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

**The order of the build:** the skeleton and its checks first (typecheck, lint and test run from the first card), then
the shared foundations (one home each for errors, validation, configuration, the look and the client), then part after
part in data order (the data's owner before those that use it), then every journey end to end in a browser.

## The gates after every card

| Gate | Keeps out |
| --- | --- |
| Layers | A layer using what it may not (business rules importing the database, say) |
| Structure | A file outside the planned folders |
| Technology | An isolated technology's library used outside its folder |
| Cycles | Files importing each other |
| References | An import of a file that does not exist |
| Copies | The same lines in more than one place |
| Security | A weakness or an exposed secret: Bandit and Gitleaks on every card, CodeQL when a milestone closes, where it may run |
| Tests | A card without a test for its acceptance criteria |
| Project checks | typecheck, lint and test |
| Dead code | At the last milestone: what nothing uses |

A card that breaks a gate goes back to the assistant with the reasons; it fixes it and sends it again.

## What it produces

In the outputs folder (`~/EAOS/<project>/blueprint/`): `SOURCE.md` (the plan as read), `product-spec.json`,
`stack.json`, `target-architecture.json`, `eaos.policy.json`, `plan.json`, and `BLUEPRINT.md` (the blueprint in words a
person reads: the parts, the technologies with why and how to change them, the rules, and the order of the build).

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
