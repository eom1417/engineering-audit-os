> **أول قاعدة قبل أي شي: كل رد للمالك بالعربي فقط، بدون أي استثناء.** قبل ما ترسل أي رسالة (رد، تحديث، سؤال، ملخص، تقرير، ملخص إشعار) تأكد إنها مكتوبة بالعربي. الرد بالإنجليزي للمالك خطأ ممنوع، حتى لو كانت المحادثة طويلة أو كان الكلام تقني. الكود والتعليقات ورسائل commit فقط بالإنجليزي.
> **First rule, before anything: every reply to the owner is in Arabic only, no exception.** Check every message before sending it; an English reply to the owner is a forbidden mistake, however long the session or technical the topic. Only code, comments and commit messages are in English.
> **وأثناء البرمجة نفسها:** حتى السطر القصير بين خطوة وخطوة ("أشغّل الاختبارات الآن"، "أقرأ الملف") بالعربي، وتقارير المساعدين الفرعيين تُترجم للعربي قبل ما تُنقل للمالك. أي جملة إنجليزية يراها المالك خطأ.
> **While programming too:** even the one-line update between two tool calls is Arabic, and subagents' English reports are translated before they reach the owner.

# Developing EAOS: what every assistant working on this repository must know

This file is for the assistant developing EAOS itself (Codex reads it; CLAUDE.md points Claude Code here).
It is not what EAOS tells the assistants of the projects it audits; that lives in `eaos/data/`.

## The owner

- The owner writes Gulf Arabic and is not a developer. **Every message to them is in Arabic, always**:
  replies, the short progress updates between steps, questions, summaries and the notification summary;
  plain words, no jargon; tables are welcome. **Everything programmed is in English**: code, code
  comments, file and symbol names, commit messages and the technical docs. A command or a file name
  inside an Arabic sentence stays as it is.
- They judge EAOS by what a non-developer feels when using it on a Mac with Codex and Claude Code.
  Fix the cause, not the symptom; prove it with a real assistant trial, not only unit tests; keep the
  progress numbers honest.
- **`main` is the owner's mother copy and is never touched**: no commit, push or merge into it; only the
  owner decides about it. Work is built on a new branch from `develop` (directly on `develop` only when the owner says
  so), verified clean (full suite, gates), merged into `develop` and pushed: the whole flow is in "The development flow".

## The code laws (owner, 2026-10-13)

Always under one condition: EAOS does its job in the best possible way.
1. **Least code, best performance**: the shortest, most direct code that does the job best; no needless layers,
   options or abstractions. A change that adds lines must earn them.
2. **One source of truth**: a function, rule or calculation needed in more than one place is written once, clearly,
   and called from everywhere else; never rewritten, never re-exported from a second home. A change then happens in
   one place.
3. **Clear and clean**: no dead code, no unused import or variable, small functions with one job, modules with one
   responsibility, easy to extend.

`tests/test_code_limits.py` enforces what can be measured (`python tools/code_limits.py` prints it): no function over
cyclomatic complexity 15 and no module over 600 lines, except today's listed ones, which may only shrink (run it
with `--tighten` after shrinking one); no function written twice; no pyflakes finding unless its line says why
(`# noqa`). The bar: an outside reviewer of logic, cohesion, layout, robustness, load and efficiency should conclude
that a top professional engineering house wrote it.

## Versions

`0.0.1`, `0.0.2`, … (`pyproject.toml`, `CHANGELOG.md`). Bump the patch number with each published
update. `1.0.0` is reserved for the first official release, which only the owner declares: after
progress reaches 100%, everything is fixed, and EAOS has audited its own structure with itself.

## Setting up a computer

```bash
bash tools/dev_setup.sh
```

It builds `.venv`, installs every external tool at its pinned version in `~/.eaos/tools`
(`$EAOS_ENGINE_TOOLS`), and fetches the development material into `~/.eaos/dev` (`$EAOS_DEV_HOME`):
the pinned sample corpus and the engines' source checkouts. `python tools/dev_paths.py` shows where
each part is. Never write a path of one machine in code: `tests/test_platforms.py` fails if you do.

## The plan

`ROADMAP.md` is the only plan: the fixes in order and what comes after. There is no other plan, score or
progress file; a finished item is removed from it and recorded in `CHANGELOG.md`.

## Tests

`unittest`, at most about 550 tests and 15 minutes. A fix adds a test only when it reproduces a real failure;
one test per real behaviour, no tests for their own sake. Run the affected modules while working
(`.venv/bin/python -m unittest tests.test_x`), the full suite before pushing, as a background job (the machine is
small, its size changes: one heavy job at a time). `tests/test_journey.py` is the fast end-to-end proof: check, change,
check again, fix, accept.

## Before every commit

```bash
.venv/bin/python -m unittest discover -s tests -q && .venv/bin/python tools/validate.py
(cd studio && npm run build)      # only when studio/ changed
```

## The development flow: EAOS develops EAOS (owner's order, 2026-10-13)

Here EAOS is built with EAOS itself, so it is developed as a tool apart from the project it checks: `beta-trial` is the
working EAOS (its code, its tools, its Studio); `develop` is the project under check, as if it were anyone else's.
Every piece of work follows these steps, in this order, every time:
0. **Build on a new branch from `develop`** (`dev/<topic>`), without asking: that is the owner's standing rule
   (2026-10-17). Work directly on `develop` only when the owner says so explicitly.
1. **Develop and verify** there (full suite, `tools/validate.py`, the Studio built when `studio/` changed).
2. **Merge into `develop`** when the work is done (a new branch: merged, then deleted), and push `origin/develop`.
3. **`develop` goes into `beta-trial` only once the owner approved it**: then
   `bash /workspace/eaos-beta-trial/update.sh --approved`, which stops at the first failure:
   develop clean and pushed; develop merged into `beta-trial` (fast-forward) and pushed; EAOS and its tools
   installed locally from the `beta-trial` checkout, through EAOS; version, commit, every tool and Claude Code up to
   date; that checkout's suite passes; the Studio restarted on it.
4. **Then the check**: of the `develop` branch, from the Studio that runs `beta-trial`, as an outside tool.
A check started any other way does not count; if a fix lands during a check, stop it and start again from step 1.
`main` is never touched (the hooks refuse it).

This flow is ours, for developing EAOS. For everyone else EAOS lets the person choose (the Studio's fix preview):
build on a new branch, continue an EAOS branch, or work directly on their branch; and they decide when and where to
merge. EAOS never decides that for them.
