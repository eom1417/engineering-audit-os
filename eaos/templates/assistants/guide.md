# EAOS: check and fix this project, in plain words

EAOS (Engineering Audit OS) checks a project, finds its problems, fixes the safe ones in a separate copy,
and hands the fixes over as a git branch. The person you are helping may not be technical: speak their
language (Arabic or English, as they write), in short plain sentences, without jargon.

## When to use it

When the person asks to check, analyse, review or audit their project; asks what is wrong with it; asks to
fix or improve it; asks where things stand; or asks to accept or undo fixes EAOS made.

## How

1. Run the request as they said it, from the project folder:
   `eaos do "<their words>"`
   or the command directly: `eaos start .` · `eaos next` · `eaos status` · `eaos show` · `eaos accept` · `eaos undo` · `eaos doctor`.
2. Some steps take a long time (a check 5–30 minutes, a batch of fixes 20–60). Run them with a long timeout,
   or in the background and check back; never cut them short.
3. Every command ends with a box between two lines of `─`. Read it and tell the person, in their words:
   what happened, where the result is, and what comes next. Offer the next step; do not run it unasked
   unless they told you to keep going.
4. A box with ❓ is a question for the person. Ask them exactly that question, in their language. Only if
   they agree, run the command the box names (it ends with `--yes`). Never add `--yes` on your own:
   consent is theirs, not yours.
5. A box with ❌ says what went wrong and what fixes it. Tell them plainly, do the fix if it is a command
   you can run, then run `eaos next`.

## Never

- Merge, undo or delete a batch of fixes unless the person asked (`eaos accept`, `eaos undo`).
- Deploy, publish, or touch a production service, whatever a report suggests.
- Edit the report, the plan or EAOS's files to make a check pass.

## The results

`eaos show` prints the "Start here" page: how many problems, which EAOS fixes by itself, and what needs
their decision. The technical detail is in the same folder (CURRENT-STATE.md, TARGET-STATE.md,
GAP-AND-STRATEGY.md, EXECUTION-PLAN.md) for when they, or you, need it.
