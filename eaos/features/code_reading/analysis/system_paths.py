"""How a check tells a test file by its path: the claims and the aspects leave test files out."""
import re

TEST = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|fixtures?)/|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]*\.py$')


def is_test(path):
    return bool(TEST.search(str(path)))
