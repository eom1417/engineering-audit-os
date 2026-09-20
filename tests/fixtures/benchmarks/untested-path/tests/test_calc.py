import unittest

import calc


class CalcTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(calc.add(1, 2), 3)
