"""The journeys' routes: one spelling of a route, whether a link's target opens it, and what a file reaches by its
imports."""
import re

from ....live.behavior.specs import PARAM

DEPTH = 3
SHARED = 6
TEST = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|fixtures?)/|\.(test|spec)\.[a-z]+$')


def _norm(route):
    route = re.sub(r'^/#(/|$)', lambda m: m.group(1) or '/', str(route or '').strip())    # a hash route /#/x is the /x links name
    return route.rstrip('/') or '/' if route.startswith('/') else route


def _segments(route):
    return [s for s in _norm(route).split('/') if s]


def matches(route, target):
    """Whether a link's target opens this route: segment by segment, a route's parameter (:id, $id, {id}) takes any
    segment, a link's parameter only a route's parameter; a catch-all never matches."""
    r, t = _segments(route), _segments(target)
    if '*' in route or len(r) != len(t): return False
    for a, b in zip(r, t):
        if PARAM.fullmatch(a): continue
        if PARAM.fullmatch(b) or a != b: return False
    return True


def _words(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name).lower()


def _reach(start, imports, depth, stop=()):
    seen, frontier = {start}, [start]
    for _ in range(depth):
        nxt = []
        for f in frontier:
            for g in imports.get(f, ()):
                if g not in seen and g not in stop:
                    seen.add(g)
                    nxt.append(g)
        frontier = nxt
    return seen
