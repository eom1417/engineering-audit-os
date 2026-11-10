"""A test that needs something this machine may lack (a tool, a parser, a network).

On a contributor's machine the test is skipped and unittest counts the skip; in the verify run
(`EAOS_TESTS_NEED_ALL=1`) a missing tool fails the test, since there every tool is installed. A need that no
machine can be asked to meet (the network, the platform) passes `tool=False` and stays a skip everywhere.
"""
import os
import unittest

STRICT = os.environ.get('EAOS_TESTS_NEED_ALL') == '1'


def need(test, missing, tool=True):
    """Inside a test: stop it when `missing` (a reason, or empty when nothing is missing)."""
    if not missing: return
    if tool and STRICT: test.fail(f'the verify run has every tool: {missing}')
    test.skipTest(missing)


def needs(missing, tool=True):
    """As a decorator of a test or test class: the same, decided when the module is read."""
    if not missing: return lambda target: target
    if not (tool and STRICT): return unittest.skip(missing)

    def fail(self, *args, **kwargs):
        self.fail(f'the verify run has every tool: {missing}')

    def failing(target):
        if isinstance(target, type):
            target.setUp = fail
            return target
        fail.__name__ = target.__name__
        return fail
    return failing
