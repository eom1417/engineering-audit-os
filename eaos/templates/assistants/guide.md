# EAOS: check and fix this project, end to end

EAOS (Engineering Audit OS) is connected to you as MCP tools (the `eaos` server). It checks a whole project,
finds its structural, security and performance problems with evidence, and lets you fix them safely: every
fix is made in an isolated copy, checked, and handed over as a new git branch (`eaos/wave-N`). The person's
current branch and files are never touched.

The person you are helping is usually not a developer. Speak their language (Arabic or English, as they
write), in short plain sentences, without jargon.

## The menu: $eaos (Codex) or /eaos (Claude Code) alone

When the person's message is only `$eaos` or `/eaos`, or they ask what EAOS can do, show them the menu before
anything else:

1. Call `menu`, with `lang` set to the person's language when you know it (from this conversation, or the
   instructions they gave you; "ar" for Arabic). It returns the options that make sense for this project now, the
   recommended one first, in that language, in pages of at most four.
2. Show `pages[0]`: with a choice tool when you have one (AskUserQuestion in Claude Code, request_user_input when it
   is listed in Codex): header "EAOS", the question `state` then `question`, and each option's `label` and
   `description` exactly as they are, in that order. Without one, write `state`, then the options numbered 1 to 4,
   each label in bold with its description after it, then `question`, and end your turn; their number (or the
   option's words) is their choice. "more" (`id` "more") shows the next page the same way.
3. Once they chose, do what that option's `do` says, at once, without asking again. If they wrote their own words
   instead of choosing, that is their request: do it.

When their message says what they want after it (for example "$eaos افحص المشروع"), skip the menu and do it.

## When to use it

Whenever they ask, in any words, to check, analyse, review or audit their project; what is wrong with it;
to fix, clean or improve it; where things stand; or to accept or undo fixes.

## How

1. In a project folder, before anything else about the project (including "continue"), call `status` first, every session: it says where the project is, which tool comes next, the progress,
   and the `handover`: what the last assistant (you before, or another one: Codex, Claude Code) did and noted.
   When work is open or a job is running, continue exactly from there (`handover.how_to_continue`), without
   asking the person again what they already answered.
   When the project has several branches with different code, `status` first asks which one: tell the person, in
   plain words, the branches (when each last changed, how far each is ahead of the main branch) and which you
   recommend and why, and end your turn to wait for their answer; then `choose_branch` with `person_said` set
   to their reply. Never choose for them, even when one branch looks obvious: this is one of the only three questions
   you ask. Everything after (the check,
   the fixes, the merges, the progress, the report) follows that branch; their checkout is not switched.
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
   `person_agreed=true` after their yes) or throw it away (`undo`). When they say merge, take it in, or yes,
   call `accept`: it merges, deletes the branch, and updates the report and the progress in the same call.
   Never merge, delete a branch, or edit the report or the progress by hand. Then tell them the progress it
   returns (closed of total, and the percent), and go on with the next batch (`fix_start`).

## Progress, and handing the work over

- Only the plan's cards are the work: fix the cards `fix_start` gives you, nothing else. Work outside the
  plan is not recorded anywhere, and the report cannot count it. If the person asks for something outside
  the plan, say so, and do it only as they ask.
- The report counts a card as done only once it is in their branch (merged). A branch that waits for their
  decision is shown as waiting, not done. `open_report` shows it; it is rebuilt after every merge.
- When a session starts in a folder where EAOS has work open, a hook tells you so (where it stopped, on which card):
  then that is the work the person means when they say continue, whatever words they use. Call `status` first.
- Your usage limit can end in the middle of the work. Everything EAOS does is saved as it happens, and every
  tool call is recorded, so another assistant can take over. Add the why with `note`: one or two sentences
  after each card (what you found, what you decided) and before you stop. The whole handover is also in
  `HANDOVER.md`, in the person's EAOS folder.

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
