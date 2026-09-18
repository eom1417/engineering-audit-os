import unittest
from app import quote
from export import exported_total

class ExistingTests(unittest.TestCase):
    def test_standard_customer(self):
        self.assertEqual(quote(100), 100)
        self.assertEqual(exported_total(100), 100)
