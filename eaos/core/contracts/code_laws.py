"""The laws of good code EAOS holds every project to, and itself (AGENTS.md): written here once, and carried into every
assistant's work, from the semantic reading and the planning to the triage, the review and the fix.

`complexity` is the one count of a function's complexity: the code laws' (tools/code_limits.py) and a check's hotspots
(eaos/facts/code/metrics.py) alike, each nested function counted alone."""
import ast

MAX_COMPLEXITY = 15     # decisions in one function
MAX_LINES = 600         # lines in one module
MAX_FUNCTION_LINES = 50 # lines in one function
MAX_PARAMETERS = 5      # parameters of one function, self and cls aside
# One source per pattern (M15): what repeats lives once, in its home, and is called from everywhere else.
NEAR_COPY = {'similarity': 0.85, 'max_gap_lines': 2, 'min_tokens': 40}   # a near copy of code, as jscpd measures it
PATTERN_REPEATS = 3     # a UI pattern or an idiom written this many times is one component or helper
UI_SIMILARITY = 0.8     # two element trees this alike are one UI pattern
LOOK = ('color', 'font_size', 'spacing', 'radius', 'shadow', 'z_index')   # written only in the tokens file

LAWS = '''THE CODE LAWS (the target of every plan and fix, the program still doing its job well):
1. Least code for the best result: no layer, option or abstraction the project does not need; a change that adds code
   must earn every line.
2. One source of truth: a rule, calculation or function needed in several places is written once, in its home, and
   called from everywhere else, never copied; merging copies into their home is a goal of the plan.
3. One source per pattern: no near copy of code (renamed, a line or two apart, 85% alike); no colour, font size,
   spacing, radius, shadow or z-index outside the tokens file; a screen pattern (pop-up, card, table) or a way of
   working (reading a file, a date, money, a request with its loading and error, drag and drop, validation, an
   endpoint's guard) written three times or more is one component, helper, hook or middleware.
4. Clean: no dead code or unused import; small functions with one job, modules with one responsibility.
A fix never adds a copy, dead code or a new complex function.'''

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
