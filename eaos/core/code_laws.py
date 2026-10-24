"""The laws of good code EAOS holds every project to, and itself (AGENTS.md): written here once, and carried into every
assistant's work, from the semantic reading and the planning to the triage, the review and the fix.

`complexity` is the one count of a function's complexity: the code laws' (tools/code_limits.py) and a check's hotspots
(eaos/facts/metrics.py) alike, each nested function counted alone."""
import ast

MAX_COMPLEXITY = 15     # decisions in one function
MAX_LINES = 600         # lines in one module
MAX_FUNCTION_LINES = 50 # lines in one function
MAX_PARAMETERS = 5      # parameters of one function, self and cls aside

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

BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.match_case, ast.comprehension)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def complexity(function):
    """McCabe complexity of one Python function: 1 + its decisions, not counting the functions nested in it."""
    score, pending = 1, list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        if isinstance(node, FUNCTIONS + (ast.ClassDef,)): continue
        if isinstance(node, BRANCHES): score += 1 + (len(node.ifs) if isinstance(node, ast.comprehension) else 0)
        elif isinstance(node, ast.BoolOp): score += len(node.values) - 1
        pending.extend(ast.iter_child_nodes(node))
    return score
