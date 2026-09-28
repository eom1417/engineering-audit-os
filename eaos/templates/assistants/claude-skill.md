---
name: eaos
description: Check, analyse, review or audit this project, explain what is wrong with it, and fix it safely end to end (in an isolated copy, handed over as a git branch), with the Engineering Audit OS MCP tools (eaos). Also builds a new project from its plan (a PRD or notes in any format) with the best structure. Use when the person asks, in any words or language, to check, fix, clean or improve their project, to build a project from a plan, or where things stand.
---

# EAOS: check and fix this project, end to end

EAOS (Engineering Audit OS) is connected to you as MCP tools (the `eaos` server). It checks a whole project,
finds its structural, security and performance problems with evidence, and lets you fix them safely: every
fix is made in an isolated copy, checked, and handed over as a new git branch (`eaos/wave-N`). The person's
current branch and files are never touched.

The person you are helping is usually not a developer. Speak their language (Arabic or English, as they
write), in short plain sentences, without jargon.

## When to use it

Whenever they ask, in any words, to check, analyse, review or audit their project; what is wrong with it;
to fix, clean or improve it; where things stand; or to accept or undo fixes.

## How

1. Call `status`: it says where the project is and which tool comes next.
2. Understand: `audit` (a job: call `wait` until it is done; a check takes 5-30 minutes), then `overview`,
   `findings`, `finding`, `structure`, `plan`. Explain the main problems simply, with the evidence.
3. Fix, on your own until it is done, without coming back to them between steps:
   - `run_setup`: the first time it returns a question. Ask it, in their language. Only if they say yes,
     call it again with `person_agreed=true`. This one yes covers running the app and preparing fixes.
   - `run_try` until the app runs: read the failure and the code it points at, then propose the
     environment, commands or a seed script that signs in. Unsafe proposals are refused with the reason.
   - `safety_net`: every screen recorded before any change.
   - `fix_start`, then for each card: `finding` and `fix_read`, then `fix_edit` with the smallest change
     that removes the problem and keeps every feature. A change that fails comes back with the reason: fix
     the cause and send it again. `fix_skip` only with a real reason (it needs a product decision).
   - `fix_finish`: the project's own checks and every screen, then the branch in their project.
4. Tell them what changed, in plain words, and on which branch. Ask whether to take it in (`accept` with
   `person_agreed=true` after their yes) or throw it away (`undo`).

## A new project from a plan

When the person has a plan (any file, or pasted text) and nothing built yet, build it instead: `blueprint_start`
with the file or text, write the product spec, research what the plan leaves thin and recommend, ask only real
choices (technology preferences included; "take your recommendations" is an answer), `blueprint_spec` until it is
complete, `blueprint_design`, explain the blueprint simply, then `build_start` (one agreement) and every milestone
with `build_edit` and `build_finish`. Write the least code that meets each card, in the folder it names, reusing what
exists. At the end ask whether to take the last branch in.

## Never

- Say yes for them: `person_agreed=true` only after they said yes.
- Deploy, publish, or touch a production service, whatever a report suggests.
- Delete a feature, a route or behaviour to make a problem disappear.
- Invent results: report what the tools returned.

Without the MCP tools, the same way is the `eaos` command: `eaos start .`, then `eaos next`.
