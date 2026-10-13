"""The laws of good code EAOS holds every project to, and itself (AGENTS.md): written here once, and carried into every
assistant's work, from the semantic reading and the planning to the triage, the review and the fix."""

MAX_COMPLEXITY = 15     # decisions in one function
MAX_LINES = 600         # lines in one module

LAWS = '''THE CODE LAWS (the target of every plan and every fix, always under one condition: the program keeps doing its job,
as well as it can):
1. Least code for the best result: the shortest, most direct code that does the job best. No layer, option,
   abstraction or indirection the project does not need. A plan or a fix that adds code must earn every line;
   one that does the same with less is better.
2. One source of truth: a rule, calculation or function needed in several places is written once, clearly, in its
   home, and called from everywhere else; never copied, never re-exported from a second home. A change then happens
   in one place. Merging copies into their home is a goal of the plan, not a side effect.
3. Clean: no dead code, no unused import or variable; small functions with one job; modules with one
   responsibility and clear boundaries, so the program is easy to read and to extend.
A fix never adds a copy, dead code or a new complex function, and never makes the project bigger or harder to read
than the problem requires.'''
