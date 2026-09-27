# The assistants, asked in plain words (NS9.T5)

> 2026-09-27. A small test project (`/tmp/ux-try/demo`, not yet checked), EAOS from branch ux-t5, and one question
> each, in Saudi colloquial Arabic, with nothing else said: **«وين وصلنا في فحص مشروعي؟»** ("where are we with
> checking my project?"). Each assistant had only EAOS's guide: the Claude Code skill
> (`eaos/templates/assistants/claude-skill.md`) or the Codex AGENTS.md block (`guide.md`).

## Claude Code

`claude -p "وين وصلنا في فحص مشروعي؟" --allowedTools "Bash(eaos:*)"` · 4 turns · $0.14

It ran `eaos status` by itself, read the box, and answered:

> ما بدأنا فحص مشروعك لسه، ولا خطوة وحدة. شغّلت أداة الفحص (EAOS) في مجلد المشروع، وقالت إنها ما اشتغلت عليه قبل كذا.
> 
> **الخطوة الجاية:** نبدأ الفحص. ياخذ عادةً من 5 إلى 30 دقيقة، وبعدها أقولك كم مشكلة لقينا، وأي منها تنصلح لحالها، وأي منها يحتاج قرارك.
> 
> تبيني أبدأ الفحص الحين؟

## Codex

`codex exec -s workspace-write "وين وصلنا في فحص مشروعي؟"`

It ran `eaos status` by itself (`/bin/bash -lc 'eaos status'`), and answered:

> حسب الحالة المسجلة، فحص مشروعك ما بدأ للحين، وما فيه نتائج جاهزة.
> 
> الخطوة الجاية نبدأ الفحص. تبغاني أبدأ؟

## What this shows

- Both chose the right command from a colloquial question, with no command named in it.
- Both answered in the person's own dialect, in plain words, without the box's technical lines.
- Both **asked before starting** the check, as the guide requires, instead of starting it on their own.
