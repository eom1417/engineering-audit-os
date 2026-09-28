# Trials: a real assistant builds a project from its plan (B3, B4)

`tools/build_trial.py` gives Claude Code a plan file and nothing else. The person is played by two messages at most:
the request («عندي خطة مشروع في الملف …، ابنه بـ EAOS بأفضل هيكلة ممكنة»), then «خذ توصياتك» to any choice and
«نعم، موافق» to the one agreement. Claude Code has the EAOS tools, its read-only tools and web search; no Bash, Edit or
Write, so every file of the project goes through EAOS's gates. When the build is delivered, EAOS audits the finished
project, and the trial records what that audit finds.

## clinic (عيادتي), 2026-09-28: built, and its own audit finds nothing

The plan: `tests/fixtures/plans/clinic-prd.md`, one page in Arabic for a small dental clinic (a receptionist and two
doctors): sign-in for the team, patients, booking 30-minute visits with no double booking, cancelling with a reason,
the day's schedule per doctor, the doctor's note after a visit. "No preference for the technologies."

| | |
| --- | --- |
| The person's turns | 2: the request, then «نعم، موافق» (it asked no other question: the plan left nothing it could not recommend) |
| Result | 7 milestones delivered as stacked branches; the last, `eaos/build-7`, holds the whole project |
| Features | 7 of 7 built through their gates, each with tests |
| Time | 74 minutes, from the plan file to the last branch |
| Size | 138 TypeScript files: 2,742 lines of code and 1,849 lines of tests (44 test files), 26 commits |
| Files written by hand | 0 |
| EAOS's audit of the result | 0 import cycles, 0 layer or structure or vendor violations, 0 copied code, 0 dead code, 0 broken references |

What it decided on its own, and said: four parts (sign-in and team, patients, appointments, visits); no self sign-up,
the manager adds the team; double booking refused by the database itself, so two receptionists booking the same slot
at once get one booking; cancelled visits kept and shown as cancelled; the doctor's note visible to doctors only;
Riyadh time; a warning, not a refusal, when a phone number is already registered, because families share one.

What the gates did: a card with a type error was refused and sent back; at the last milestone the dead-code gate found
one unused function (`errorMap` in `shared/src/identity`), the assistant removed it with a FIX, and the milestone
closed. Tool calls: blueprint 3, build_start 7, build_edit 32, build_read 11, build_finish 9.

What it said was not done: the three end-to-end journeys were written as browser tests but not run (the trial allows
no command), and the app itself was not started. Running both is the audit path's work (`run_setup`, `safety_net`)
once the person takes the build in; the build gates run the typecheck, lint and unit tests only.
