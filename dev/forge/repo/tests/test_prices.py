import unittest

from billing.prices import price


class PriceTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(price("basic"), 500)
